from __future__ import annotations

import httpx

from scraper import probe
from scraper.core.http import HttpClient
from scraper.probe import ProbeTarget, format_markdown, format_table, run_probe

TARGETS = (
    ProbeTarget("good", "https://good.example/list", "data-bigimg"),
    ProbeTarget("blocked", "https://blocked.example/", "seoTitle"),
    ProbeTarget("broken", "https://broken.example/", ".pdf"),
    ProbeTarget("challenge", "https://challenge.example/", "mcdate"),
    ProbeTarget("moved", "https://moved.example/old", "<loc>", timeout=60),
)


def handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "good.example":
        return httpx.Response(200, html='<img data-bigimg="a.jpg">')
    if host == "blocked.example":
        return httpx.Response(403, html="<html><title>Access Denied</title></html>")
    if host == "broken.example":
        raise httpx.ConnectError("connection refused")
    if host == "challenge.example":
        return httpx.Response(200, html="<html><head><title>Just a moment...</title></head></html>")
    if request.url.path == "/old":
        return httpx.Response(302, headers={"location": "https://moved.example/new"})
    return httpx.Response(200, content=b"<urlset><loc>x</loc></urlset>", headers={"content-type": "application/xml"})


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 0.25
        return self.t


def client() -> HttpClient:
    return HttpClient(transport=httpx.MockTransport(handler), max_retries=0, sleep=lambda s: None)


def test_every_source_is_reported_even_when_one_raises() -> None:
    with client() as c:
        results = run_probe(c, TARGETS, clock=Clock())
    by_name = {r.name: r for r in results}
    assert list(by_name) == ["good", "blocked", "broken", "challenge", "moved"]

    assert by_name["good"].status == 200 and by_name["good"].marker_found is True
    assert by_name["good"].content_type == "text/html"
    assert by_name["good"].size == len('<img data-bigimg="a.jpg">')
    assert by_name["good"].duration_ms == 250

    assert by_name["blocked"].status == 403 and by_name["blocked"].marker_found is False
    assert "Access Denied" in by_name["blocked"].note

    assert by_name["broken"].status is None and by_name["broken"].marker_found is None
    assert "ConnectError" in by_name["broken"].note

    assert by_name["challenge"].status == 200 and by_name["challenge"].marker_found is False
    assert "Just a moment" in by_name["challenge"].note

    assert by_name["moved"].marker_found is True
    assert "moved.example/new" in by_name["moved"].note


def test_unexpected_exception_does_not_stop_the_probe() -> None:
    class Exploding(HttpClient):
        def get(self, url, **kwargs):
            if "blocked" in url:
                raise RuntimeError("boom")
            return super().get(url, **kwargs)

    c = Exploding(transport=httpx.MockTransport(handler), max_retries=0, sleep=lambda s: None)
    with c:
        results = run_probe(c, TARGETS)
    assert len(results) == len(TARGETS)
    assert "RuntimeError: boom" in results[1].note


def test_table_formats() -> None:
    with client() as c:
        results = run_probe(c, TARGETS, clock=Clock())
    table = format_table(results)
    lines = table.splitlines()
    assert lines[0].split()[:3] == ["chain", "status", "bytes"]
    assert len(lines) == 2 + len(TARGETS)
    assert "ERR" in table and "403" in table and "NO" in table

    md = format_markdown(results)
    assert md.count("\n| ") == 1 + len(TARGETS)
    assert "2/5 sources returned 200 with the expected marker." in md


def test_main_writes_step_summary_and_returns_zero(tmp_path, monkeypatch, capsys) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    with client() as c:
        assert probe.main(client=c, targets=TARGETS) == 0
    assert "| good |" in summary.read_text(encoding="utf-8")
    assert "challenge" in capsys.readouterr().out


def test_main_without_summary_env(monkeypatch, capsys) -> None:
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    with client() as c:
        assert probe.main(client=c, targets=TARGETS) == 0
    assert "good" in capsys.readouterr().out


def test_default_targets_cover_all_sources() -> None:
    names = [t.name for t in probe.TARGETS]
    assert len(names) == 13 == len(set(names))
    assert "carrefoursa" not in names
    assert all(t.url.startswith("https://") for t in probe.TARGETS)
    assert next(t for t in probe.TARGETS if t.name == "tkkoop").timeout == 60
