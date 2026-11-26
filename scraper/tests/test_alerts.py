"""One GitHub issue per failing source, against a fake GitHub API (no network)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from scraper import alerts
from scraper.alerts import (
    LABEL,
    CloseIssue,
    CommentError,
    Issue,
    OpenIssue,
    SourceStatus,
    issue_body,
    main,
    marker,
    plan,
    read_marker,
    same_error,
)

API = "https://api.github.com/repos/owner/repo"
ENV = {
    "GITHUB_TOKEN": "ghs_test-token",
    "GITHUB_REPOSITORY": "owner/repo",
    "GITHUB_SERVER_URL": "https://github.com",
    "GITHUB_RUN_ID": "42",
}
RUN_URL = "https://github.com/owner/repo/actions/runs/42"


def health(*sources: dict[str, Any]) -> dict[str, Any]:
    return {"generated_at": "2026-11-26T09:00:00Z", "sources": list(sources)}


def source(chain_id: str, failures: int, error: str | None = "timeout") -> dict[str, Any]:
    ok = failures == 0
    return {
        "chain_id": chain_id,
        "ok": ok,
        "last_ok_at": None,
        "last_error": None if ok else error,
        "consecutive_failures": failures,
        "brochure_count": 3 if ok else 0,
        "duration_ms": 100,
    }


def bot_issue(number: int, chain_id: str, error: str | None, **extra: Any) -> dict[str, Any]:
    status = SourceStatus(chain_id, False, 3, error)
    return {"number": number, "title": f"Source failing: {chain_id}", "body": issue_body(status, None), **extra}


class FakeGitHub:
    def __init__(
        self,
        issues: list[dict[str, Any]] | None = None,
        *,
        label_exists: bool = True,
        fail: dict[tuple[str, str], int] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.issues = issues or []
        self.label_exists = label_exists
        self.fail = fail or {}
        self.error = error
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        path = request.url.path.removeprefix("/repos/owner/repo")
        status = self.fail.get((request.method, path))
        if status is not None:
            return httpx.Response(status, json={"message": "Server Error"})
        if request.method == "GET" and path == "/issues":
            return httpx.Response(200, json=self.issues)
        if request.method == "GET" and path == f"/labels/{LABEL}":
            return httpx.Response(200 if self.label_exists else 404, json={"name": LABEL})
        if request.method == "POST" and path == "/labels":
            return httpx.Response(201, json=json.loads(request.content))
        if request.method == "POST" and path == "/issues":
            return httpx.Response(201, json={"number": 7})
        if request.method in ("POST", "PATCH") and path.startswith("/issues/"):
            return httpx.Response(200, json={})
        return httpx.Response(404, json={"message": "Not Found"})

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))

    def writes(self) -> list[tuple[str, str, dict[str, Any]]]:
        return [
            (r.method, r.url.path.removeprefix("/repos/owner/repo"), json.loads(r.content))
            for r in self.requests
            if r.method != "GET"
        ]


def run(tmp_path: Path, server: FakeGitHub, data: dict[str, Any], env: dict[str, str] | None = None) -> int:
    path = tmp_path / "health.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return main(
        ["--health", str(path)],
        env=ENV if env is None else env,
        client_factory=server.client,
        sleep=lambda _s: None,
    )


# --- planning (pure) -------------------------------------------------------------------


def status(chain_id: str, failures: int, error: str | None = "timeout") -> SourceStatus:
    return SourceStatus(chain_id, failures == 0, failures, None if failures == 0 else error)


def issue(chain_id: str, error: str | None, number: int = 5) -> Issue:
    return Issue(number, chain_id, issue_body(status(chain_id, 3, error), None))


def test_plan_opens_only_at_the_threshold() -> None:
    actions = plan([status("bim", 0), status("sok", 2), status("tkkoop", 3)], {})
    assert [type(a) for a in actions] == [OpenIssue]
    assert actions[0].title == "Source failing: tkkoop"


def test_plan_does_nothing_while_the_same_error_continues() -> None:
    assert plan([status("tkkoop", 9, "timeout")], {"tkkoop": issue("tkkoop", "timeout")}) == []


def test_plan_comments_once_when_the_error_changes() -> None:
    [action] = plan([status("tkkoop", 4, "HTTP 403")], {"tkkoop": issue("tkkoop", "timeout")}, run_url=RUN_URL)
    assert isinstance(action, CommentError)
    assert "HTTP 403" in action.comment and RUN_URL in action.comment
    # The body now records the new error, so the next run with it says nothing.
    assert read_marker(action.new_body) == (True, "HTTP 403")
    assert action.new_body.count("scraper-alert") == 1
    assert plan([status("tkkoop", 5, "HTTP 403")], {"tkkoop": Issue(5, "tkkoop", action.new_body)}) == []


def test_plan_ignores_volatile_numbers_in_errors() -> None:
    assert same_error("timeout after 30123 ms", "timeout after 30871 ms")
    assert not same_error("HTTP 403", "HTTP 503")


def test_plan_never_comments_on_an_issue_without_a_marker() -> None:
    manual = Issue(5, "tkkoop", "opened by hand")
    assert plan([status("tkkoop", 5, "anything")], {"tkkoop": manual}) == []


def test_plan_closes_on_recovery_and_leaves_unknown_sources_alone() -> None:
    open_issues = {"tkkoop": issue("tkkoop", "x", 5), "gone": issue("gone", "x", 6)}
    [action] = plan([status("tkkoop", 0)], open_issues)
    assert isinstance(action, CloseIssue) and action.issue.number == 5
    assert "Recovered" in action.comment


def test_marker_survives_comment_terminators_and_quotes() -> None:
    error = 'bad --> "html" <b>'
    assert read_marker(f"text\n{marker('x', error)}\n") == (True, error)
    assert read_marker("no marker") == (False, None)


# --- against the API -------------------------------------------------------------------


def test_opens_a_new_issue_with_label(tmp_path, capsys) -> None:
    server = FakeGitHub(label_exists=False)
    data = health(source("bim", 0), source("tkkoop", 3, "network error (ConnectError): refused"))
    assert run(tmp_path, server, data) == 0
    writes = server.writes()
    assert [(m, p) for m, p, _ in writes] == [("POST", "/labels"), ("POST", "/issues")]
    assert writes[0][2]["name"] == LABEL
    created = writes[1][2]
    assert created["title"] == "Source failing: tkkoop" and created["labels"] == [LABEL]
    assert "ConnectError" in created["body"] and RUN_URL in created["body"]
    assert "opened issue #7" in capsys.readouterr().out
    listing = server.requests[0]
    assert listing.url.params["state"] == "open" and listing.url.params["labels"] == LABEL
    assert listing.headers["Authorization"] == "Bearer ghs_test-token"
    assert listing.headers["User-Agent"].startswith("AktuelBrosurBot/")


def test_existing_label_is_not_recreated(tmp_path) -> None:
    server = FakeGitHub(label_exists=True)
    assert run(tmp_path, server, health(source("tkkoop", 3), source("sok", 4))) == 0
    assert [(m, p) for m, p, _ in server.writes()] == [("POST", "/issues"), ("POST", "/issues")]


def test_already_open_issue_is_not_duplicated(tmp_path, capsys) -> None:
    server = FakeGitHub([bot_issue(5, "tkkoop", "timeout")])
    assert run(tmp_path, server, health(source("tkkoop", 6, "timeout"))) == 0
    assert server.writes() == []
    assert "nothing to do" in capsys.readouterr().out


def test_changed_error_comments_and_updates_the_marker(tmp_path) -> None:
    server = FakeGitHub([bot_issue(5, "tkkoop", "timeout")])
    assert run(tmp_path, server, health(source("tkkoop", 4, "HTTP 403"))) == 0
    writes = server.writes()
    assert [(m, p) for m, p, _ in writes] == [("POST", "/issues/5/comments"), ("PATCH", "/issues/5")]
    assert "HTTP 403" in writes[0][2]["body"]
    assert read_marker(writes[1][2]["body"]) == (True, "HTTP 403")


def test_recovered_source_closes_its_issue(tmp_path, capsys) -> None:
    pull = {"number": 9, "title": "Source failing: bim", "body": "", "pull_request": {}}
    server = FakeGitHub([bot_issue(5, "tkkoop", "timeout"), pull])
    assert run(tmp_path, server, health(source("tkkoop", 0), source("bim", 0))) == 0
    writes = server.writes()
    assert [(m, p) for m, p, _ in writes] == [("POST", "/issues/5/comments"), ("PATCH", "/issues/5")]
    assert "Recovered" in writes[0][2]["body"]
    assert writes[1][2] == {"state": "closed", "state_reason": "completed"}
    assert "closed issue #5" in capsys.readouterr().out


@pytest.mark.parametrize("missing", ["GITHUB_TOKEN", "GITHUB_REPOSITORY"])
def test_without_token_alerts_are_disabled(tmp_path, capsys, missing: str) -> None:
    server = FakeGitHub()
    env = {k: v for k, v in ENV.items() if k != missing}
    assert run(tmp_path, server, health(source("tkkoop", 3)), env=env) == 0
    assert server.requests == []
    out = capsys.readouterr().out
    assert f"alerts disabled ({missing} not set)" in out and "tkkoop" in out


def test_api_error_on_listing_is_a_warning(tmp_path, capsys) -> None:
    server = FakeGitHub(fail={("GET", "/issues"): 500})
    assert run(tmp_path, server, health(source("tkkoop", 3))) == 0
    out = capsys.readouterr().out
    assert "::warning::alerts failed" in out and "HTTP 500" in out
    assert server.writes() == []


def test_one_failed_action_does_not_stop_the_others(tmp_path, capsys) -> None:
    server = FakeGitHub([bot_issue(5, "bim", "x")], fail={("POST", "/issues"): 403})
    assert run(tmp_path, server, health(source("tkkoop", 3), source("bim", 0))) == 0
    # Opening tkkoop's issue failed; bim's recovery was still handled.
    assert ("PATCH", "/issues/5") in [(m, p) for m, p, _ in server.writes()]
    out = capsys.readouterr().out
    assert "::warning::alerts: OpenIssue failed" in out and "1 alert action(s) failed" in out


def test_network_error_never_raises(tmp_path, capsys) -> None:
    server = FakeGitHub(error=httpx.ConnectError("refused"))
    assert run(tmp_path, server, health(source("tkkoop", 3))) == 0
    assert "::warning::alerts failed" in capsys.readouterr().out


def test_broken_or_missing_health_never_raises(tmp_path, capsys) -> None:
    server = FakeGitHub()
    assert main(["--health", str(tmp_path / "none.json")], env=ENV, client_factory=server.client) == 0
    assert run(tmp_path, server, {"sources": "nope"}) == 0
    assert capsys.readouterr().out.count("::warning::alerts failed") == 2
    assert server.requests == []


def test_requests_are_paced_to_one_per_second() -> None:
    now = [0.0]
    waits: list[float] = []
    server = FakeGitHub(label_exists=False)
    with server.client() as client:
        github = alerts.GitHub(client, "owner/repo", "t", clock=lambda: now[0], sleep=waits.append)
        github.open_alert_issues()
        github.ensure_label()
    # Three requests at a frozen clock: the second and third each wait a full second.
    assert len(server.requests) == 3 and waits == [1.0, 1.0]
