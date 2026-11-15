"""New-brochure notifications (scraper/notify.py). Offline: FCM and the token endpoint are mocked."""

from __future__ import annotations

import json
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

import httpx
import pytest

from scraper import notify
from scraper.notify import build_messages, date_text, main, new_brochures

TODAY = date(2026, 11, 15)
TOKEN_URI = "https://oauth2.example.test/token"
FCM_URL = "https://fcm.googleapis.com/v1/projects/demo-project/messages:send"


def chain(chain_id: str, name: str, kind: str = "scraped") -> dict[str, Any]:
    return {"id": chain_id, "name": name, "kind": kind}


def brochure(
    brochure_id: str,
    chain_id: str,
    valid_from: str | None = "2026-11-13",
    valid_to: str | None = "2026-11-19",
    date_label: str | None = None,
) -> dict[str, Any]:
    return {
        "id": brochure_id,
        "chain_id": chain_id,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "date_label": date_label,
        "first_seen": "2026-11-15T03:20:00Z",
    }


CHAINS = [chain("bim", "BİM"), chain("sok", "Şok"), chain("a101", "A101", "webview")]


def catalog(*brochures: dict[str, Any], chains: list[dict[str, Any]] = CHAINS) -> dict[str, Any]:
    return {"chains": chains, "brochures": list(brochures)}


OLD = brochure("bim-old", "bim", "2026-11-10", "2026-11-16")


# --- what counts as new ---------------------------------------------------------------


def test_only_ids_absent_from_the_previous_catalog_are_new() -> None:
    previous = catalog(OLD)
    current = catalog(OLD, brochure("bim-new", "bim"))
    assert {k: [b["id"] for b in v] for k, v in new_brochures(previous, current, TODAY).items()} == {"bim": ["bim-new"]}


def test_first_run_is_silent() -> None:
    assert new_brochures(None, catalog(brochure("bim-new", "bim")), TODAY) == {}
    assert build_messages(None, catalog(brochure("bim-new", "bim")), TODAY) == []


def test_unchanged_catalog_sends_nothing() -> None:
    assert build_messages(catalog(OLD), catalog(OLD), TODAY) == []


def test_webview_chains_are_ignored() -> None:
    current = catalog(OLD, brochure("a101-x", "a101"))
    assert new_brochures(catalog(OLD), current, TODAY) == {}


def test_a_chain_new_to_the_catalog_does_not_announce_its_back_catalogue() -> None:
    previous = catalog(OLD, chains=[chain("bim", "BİM")])
    current = catalog(OLD, brochure("sok-1", "sok"))
    assert new_brochures(previous, current, TODAY) == {}


def test_expired_brochures_are_ignored_but_open_and_ending_today_are_kept() -> None:
    current = catalog(
        OLD,
        brochure("bim-expired", "bim", "2026-11-08", "2026-11-14"),
        brochure("bim-ends-today", "bim", "2026-11-09", "2026-11-15"),
        brochure("bim-open", "bim", "2026-11-14", None),
    )
    ids = [b["id"] for b in new_brochures(catalog(OLD), current, TODAY)["bim"]]
    assert sorted(ids) == ["bim-ends-today", "bim-open"]


def test_unknown_chain_ids_are_skipped() -> None:
    assert new_brochures(catalog(OLD), catalog(OLD, brochure("x-1", "ghost")), TODAY) == {}


# --- messages ---------------------------------------------------------------------------


def test_one_message_per_chain_with_count_and_newest_brochure() -> None:
    current = catalog(
        OLD,
        brochure("bim-a", "bim", "2026-11-15", "2026-11-21"),
        brochure("bim-c", "bim", "2026-11-20", "2026-11-26"),
        brochure("bim-b", "bim", "2026-11-17", "2026-11-23"),
        brochure("sok-1", "sok", "2026-11-18", "2026-11-24"),
    )
    messages = build_messages(catalog(OLD), current, TODAY)
    assert [m["topic"] for m in messages] == ["chain-bim", "chain-sok"]
    bim, sok = messages
    assert bim["notification"] == {"title": "BİM: yeni broşür", "body": "3 yeni broşür yayında"}
    assert bim["data"] == {"chain_id": "bim", "brochure_id": "bim-c"}
    assert sok["notification"] == {"title": "Şok: yeni broşür", "body": "18–24 Kasım broşürü yayında"}


def test_payload_shape() -> None:
    [message] = build_messages(catalog(OLD), catalog(OLD, brochure("bim-new", "bim")), TODAY)
    assert message == {
        "topic": "chain-bim",
        "notification": {"title": "BİM: yeni broşür", "body": "13–19 Kasım broşürü yayında"},
        "data": {"chain_id": "bim", "brochure_id": "bim-new"},
        "android": {"priority": "HIGH", "notification": {"channel_id": "new_brochures"}},
    }
    # FCM rejects non-string data values; the topic is given without the /topics/ prefix.
    assert all(isinstance(v, str) for v in message["data"].values())


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"valid_from": "2026-11-13", "valid_to": "2026-11-19"}, "13–19 Kasım"),
        ({"valid_from": "2026-10-22", "valid_to": "2026-11-04"}, "22 Ekim – 4 Kasım"),
        ({"valid_from": "2026-11-13", "valid_to": "2026-11-13"}, "13 Kasım"),
        ({"valid_from": "2027-01-05", "valid_to": "2027-01-11"}, "5–11 Ocak 2027"),
        ({"valid_from": "2026-12-29", "valid_to": "2027-01-04"}, "29 Aralık 2026 – 4 Ocak 2027"),
        ({"valid_from": "2026-11-13", "valid_to": None, "date_label": " 13  Kasım Cuma "}, "13 Kasım Cuma"),
        ({"valid_from": None, "valid_to": None, "date_label": None}, None),
    ],
)
def test_date_text(fields: dict[str, Any], expected: str | None) -> None:
    assert date_text({"date_label": None, **fields}, TODAY) == expected


def test_body_without_any_date() -> None:
    new = brochure("bim-x", "bim", None, None, None)
    [message] = build_messages(catalog(OLD), catalog(OLD, new), TODAY)
    assert message["notification"]["body"] == "Yeni broşür yayında"


# --- command line and sending -----------------------------------------------------------


@cache
def _private_key_pem() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


def service_account_json() -> str:
    return json.dumps(
        {
            "type": "service_account",
            "project_id": "demo-project",
            "private_key_id": "kid-1",
            "private_key": _private_key_pem(),
            "client_email": "sender@demo-project.iam.gserviceaccount.com",
            "client_id": "1",
            "token_uri": TOKEN_URI,
        }
    )


class FakeServer:
    """Token endpoint + FCM; ``fcm_status`` per topic, anything else 404."""

    def __init__(self, *, token_status: int = 200, fcm_status: dict[str, int] | None = None, error: Exception | None = None):
        self.token_status = token_status
        self.fcm_status = fcm_status or {}
        self.error = error
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        url = str(request.url)
        if url == TOKEN_URI:
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "invalid_grant", "error_description": "bad key"})
            return httpx.Response(200, json={"access_token": "ya29.test-token", "expires_in": 3600, "token_type": "Bearer"})
        if url == FCM_URL:
            topic = json.loads(request.content)["message"]["topic"]
            status = self.fcm_status.get(topic, 200)
            body = {"name": "projects/demo-project/messages/1"} if status == 200 else {"error": {"status": "INTERNAL"}}
            return httpx.Response(status, json=body)
        return httpx.Response(404)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))

    def fcm_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if str(r.url) == FCM_URL]


def write_catalogs(tmp_path: Path, previous: dict[str, Any] | None, current: dict[str, Any]) -> list[str]:
    prev_path, cur_path = tmp_path / "state" / "catalog.json", tmp_path / "out" / "catalog.json"
    for path, data in ((prev_path, previous), (cur_path, current)):
        if data is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return ["--previous", str(prev_path), "--current", str(cur_path), "--today", TODAY.isoformat()]


TWO_CHAINS_NEW = catalog(OLD, brochure("bim-new", "bim"), brochure("sok-1", "sok", "2026-11-18", "2026-11-24"))


def run(tmp_path: Path, server: FakeServer, *extra: str, previous: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> int:
    args = write_catalogs(tmp_path, catalog(OLD) if previous is None else previous, TWO_CHAINS_NEW)
    return main([*args, *extra], env={notify.SERVICE_ACCOUNT_ENV: service_account_json()} if env is None else env, client_factory=server.client)


def test_sends_one_request_per_chain_with_an_oauth_token(tmp_path, capsys) -> None:
    server = FakeServer()
    assert run(tmp_path, server) == 0
    token_requests = [r for r in server.requests if str(r.url) == TOKEN_URI]
    assert len(token_requests) == 1
    # Service account JWT bearer grant asking for the FCM scope.
    assert b"grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer" in token_requests[0].content
    sent = server.fcm_requests()
    assert [json.loads(r.content)["message"]["topic"] for r in sent] == ["chain-bim", "chain-sok"]
    assert all(r.method == "POST" and r.headers["authorization"] == "Bearer ya29.test-token" for r in sent)
    assert set(json.loads(sent[0].content)) == {"message"}
    out = capsys.readouterr().out
    assert "done: 2 sent, 0 failed" in out
    assert "ya29.test-token" not in out and "PRIVATE KEY" not in out


def test_scope_is_firebase_messaging(monkeypatch) -> None:
    from google.oauth2 import service_account

    seen: dict[str, Any] = {}
    real = service_account.Credentials.from_service_account_info

    def spy(info, **kwargs):
        seen.update(kwargs)
        return real(info, **kwargs)

    monkeypatch.setattr(service_account.Credentials, "from_service_account_info", spy)
    account = notify.service_account_from_env({notify.SERVICE_ACCOUNT_ENV: service_account_json()})
    assert account is not None and account.project_id == "demo-project"
    with FakeServer().client() as client:
        assert notify.access_token(account, client) == "ya29.test-token"
    assert seen["scopes"] == ["https://www.googleapis.com/auth/firebase.messaging"]


def test_missing_secret_disables_notifications(tmp_path, capsys) -> None:
    server = FakeServer()
    assert run(tmp_path, server, env={}) == 0
    assert server.requests == []
    out = capsys.readouterr().out
    assert out.count("notifications disabled") == 1


def test_broken_secret_disables_without_echoing_it(tmp_path, capsys) -> None:
    server = FakeServer()
    assert run(tmp_path, server, env={notify.SERVICE_ACCOUNT_ENV: "{not json SECRET-VALUE"}) == 0
    assert server.requests == []
    out = capsys.readouterr().out
    assert "notifications disabled" in out and "SECRET-VALUE" not in out


def test_incomplete_secret_disables(tmp_path, capsys) -> None:
    server = FakeServer()
    assert run(tmp_path, server, env={notify.SERVICE_ACCOUNT_ENV: json.dumps({"project_id": "p"})}) == 0
    assert server.requests == []
    assert "lacks client_email, private_key, token_uri" in capsys.readouterr().out


def test_first_run_sends_nothing(tmp_path, capsys) -> None:
    server = FakeServer()
    args = write_catalogs(tmp_path, None, TWO_CHAINS_NEW)
    assert main(args, env={notify.SERVICE_ACCOUNT_ENV: service_account_json()}, client_factory=server.client) == 0
    assert server.requests == []
    assert "first run" in capsys.readouterr().out


def test_dry_run_prints_and_never_sends(tmp_path, capsys) -> None:
    server = FakeServer()
    assert run(tmp_path, server, "--dry-run") == 0
    assert server.requests == []
    out = capsys.readouterr().out
    assert "would send 2 message(s)" in out
    assert '"topic": "chain-bim"' in out and "13–19 Kasım broşürü yayında" in out


def test_one_failed_message_does_not_stop_the_others(tmp_path, capsys) -> None:
    server = FakeServer(fcm_status={"chain-bim": 500})
    assert run(tmp_path, server) == 0
    assert len(server.fcm_requests()) == 2
    out = capsys.readouterr().out
    assert "chain-bim: send failed: HTTP 500" in out and "chain-sok: sent" in out
    assert "done: 1 sent, 1 failed" in out and "::warning::1 notification(s)" in out


def test_token_failure_never_raises(tmp_path, capsys) -> None:
    server = FakeServer(token_status=400)
    assert run(tmp_path, server) == 0
    assert server.fcm_requests() == []
    assert "::warning::notifications failed: RefreshError" in capsys.readouterr().out


def test_network_failure_never_raises(tmp_path, capsys) -> None:
    server = FakeServer(error=httpx.ConnectError("offline"))
    assert run(tmp_path, server) == 0
    assert "notifications failed" in capsys.readouterr().out


def test_broken_catalog_never_raises(tmp_path, capsys) -> None:
    args = write_catalogs(tmp_path, catalog(OLD), TWO_CHAINS_NEW)
    Path(args[3]).write_text("{broken", encoding="utf-8")
    assert main(args, env={}, client_factory=FakeServer().client) == 0
    assert "notifications failed: JSONDecodeError" in capsys.readouterr().out


def test_missing_current_catalog(tmp_path, capsys) -> None:
    prev = tmp_path / "state.json"
    prev.write_text("{}", encoding="utf-8")
    assert main(["--previous", str(prev), "--current", str(tmp_path / "none.json")], env={}) == 0
    assert "nothing to notify" in capsys.readouterr().out
