from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from scraper.core.http import CONTACT_ENV, DEFAULT_CONTACT_URL, HttpClient, user_agent


class FakeTime:
    """Clock and sleep that advance virtual time only."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(
    handler: Callable[[httpx.Request], httpx.Response], fake: FakeTime, **kwargs
) -> HttpClient:
    return HttpClient(transport=httpx.MockTransport(handler), clock=fake.clock, sleep=fake.sleep, **kwargs)


class Recorder:
    def __init__(self, *responses: int | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []
        self.times: list[float] = []
        self.fake: FakeTime | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fake:
            self.times.append(self.fake.now)
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, Exception):
            raise item
        return httpx.Response(item, text=f"status {item}")


def test_headers_identify_the_bot_honestly(monkeypatch) -> None:
    monkeypatch.delenv(CONTACT_ENV, raising=False)
    fake = FakeTime()
    rec = Recorder(200)
    with make_client(rec, fake) as client:
        client.get("https://example.com/")
    ua = rec.requests[0].headers["user-agent"]
    assert ua == f"AktuelBrosurBot/0.1 (+{DEFAULT_CONTACT_URL})"
    assert "Mozilla" not in ua
    assert rec.requests[0].headers["accept-language"] == "tr-TR,tr;q=0.9"


def test_contact_url_comes_from_environment(monkeypatch) -> None:
    monkeypatch.setenv(CONTACT_ENV, "https://github.com/someone/aktuel_brosur")
    assert user_agent() == "AktuelBrosurBot/0.1 (+https://github.com/someone/aktuel_brosur)"
    assert user_agent("https://x.example/") == "AktuelBrosurBot/0.1 (+https://x.example/)"


def test_same_host_requests_are_spaced_one_second_apart() -> None:
    fake = FakeTime()
    rec = Recorder(200)
    rec.fake = fake
    with make_client(rec, fake) as client:
        client.get("https://a.example/1")
        fake.now += 0.3  # some parsing work in between
        client.get("https://a.example/2")
        client.get("https://a.example/3")
    assert rec.times[1] - rec.times[0] >= 1.0
    assert rec.times[2] - rec.times[1] >= 1.0
    assert fake.sleeps == [pytest.approx(0.7), pytest.approx(1.0)]


def test_different_hosts_are_not_delayed() -> None:
    fake = FakeTime()
    rec = Recorder(200)
    with make_client(rec, fake) as client:
        client.get("https://a.example/")
        client.get("https://b.example/")
        client.get("https://c.example/")
    assert fake.sleeps == []


def test_no_wait_when_enough_time_has_passed() -> None:
    fake = FakeTime()
    rec = Recorder(200)
    with make_client(rec, fake) as client:
        client.get("https://a.example/1")
        fake.now += 5
        client.get("https://a.example/2")
    assert fake.sleeps == []


def test_5xx_is_retried_then_succeeds() -> None:
    fake = FakeTime()
    rec = Recorder(503, 502, 200)
    with make_client(rec, fake) as client:
        response = client.get("https://a.example/")
    assert response.status_code == 200
    assert len(rec.requests) == 3


def test_5xx_gives_up_after_two_retries_and_returns_last_response() -> None:
    fake = FakeTime()
    rec = Recorder(500)
    with make_client(rec, fake) as client:
        response = client.get("https://a.example/")
    assert response.status_code == 500
    assert len(rec.requests) == 3  # first try + 2 retries


@pytest.mark.parametrize("status", [403, 429, 404, 400])
def test_client_errors_are_not_retried(status: int) -> None:
    fake = FakeTime()
    rec = Recorder(status)
    with make_client(rec, fake) as client:
        response = client.get("https://a.example/")
    assert response.status_code == status
    assert len(rec.requests) == 1
    assert fake.sleeps == []


def test_network_errors_are_retried() -> None:
    fake = FakeTime()
    rec = Recorder(httpx.ConnectError("refused"), httpx.ReadTimeout("slow"), 200)
    with make_client(rec, fake) as client:
        assert client.get("https://a.example/").status_code == 200
    assert len(rec.requests) == 3


def test_network_error_is_raised_after_retries() -> None:
    fake = FakeTime()
    rec = Recorder(httpx.ConnectError("refused"))
    with make_client(rec, fake) as client, pytest.raises(httpx.ConnectError):
        client.get("https://a.example/")
    assert len(rec.requests) == 3


def test_retries_respect_rate_limit_and_back_off() -> None:
    fake = FakeTime()
    rec = Recorder(503, 503, 200)
    rec.fake = fake
    with make_client(rec, fake) as client:
        client.get("https://a.example/")
    gaps = [b - a for a, b in zip(rec.times, rec.times[1:])]
    assert all(g >= 1.0 for g in gaps)
    assert gaps[1] > gaps[0]  # back-off grows


def test_max_retries_zero_sends_one_request() -> None:
    fake = FakeTime()
    rec = Recorder(503)
    with make_client(rec, fake, max_retries=0) as client:
        assert client.get("https://a.example/").status_code == 503
    assert len(rec.requests) == 1


def test_redirects_are_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "https://a.example/new"})
        return httpx.Response(200, text="new")

    with make_client(handler, FakeTime()) as client:
        response = client.get("https://a.example/old")
    assert response.status_code == 200
    assert str(response.url) == "https://a.example/new"


def test_timeout_is_passed_per_request() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.extensions["timeout"])
        return httpx.Response(200)

    with make_client(handler, FakeTime()) as client:
        client.get("https://a.example/")
        client.get("https://b.example/", timeout=60)
    assert seen[0]["read"] == 30
    assert seen[1]["read"] == 60
