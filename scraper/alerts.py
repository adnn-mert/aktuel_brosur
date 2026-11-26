"""Open, update and close one GitHub issue per source that keeps failing.

Runs after a successful publish (see .github/workflows/scrape.yml)::

    python -m scraper.alerts --health out/health.json

The per-source failure streak is the ``consecutive_failures`` field the scraper already keeps
in ``health.json``. For each source:

- streak >= ``FAILURE_ALERT_THRESHOLD`` and no open issue: open "Source failing: <id>" with the
  ``source-failing`` label (created if missing);
- issue already open: nothing, unless the error text changed since it was last reported, then
  one comment. The last reported error lives in a hidden marker in the issue body, so no
  comment is posted on every run;
- source succeeded again (``ok``) and an issue is open: comment "recovered" and close it.

A failing source used to fail the whole job, which mailed the owner three times a day until it
was fixed; an issue says it once per incident. Alerts are a nice-to-have: this command always
exits 0. Without ``GITHUB_TOKEN``/``GITHUB_REPOSITORY`` (local runs) it logs "alerts disabled";
API errors are logged as warnings. Only ``health.json`` is read, so OCR problems never open
issues.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from scraper.core.http import user_agent
from scraper.core.pipeline import FAILURE_ALERT_THRESHOLD

TOKEN_ENV = "GITHUB_TOKEN"
REPOSITORY_ENV = "GITHUB_REPOSITORY"
API_URL_ENV = "GITHUB_API_URL"
DEFAULT_API_URL = "https://api.github.com"
LABEL = "source-failing"
LABEL_COLOR = "d73a4a"
LABEL_DESCRIPTION = "A scraper source has failed several runs in a row"
TITLE_PREFIX = "Source failing: "
REQUEST_TIMEOUT = 20.0
# Same courtesy as the scraper: at most one request per second to one host.
MIN_INTERVAL = 1.0
MAX_PAGES = 10
_MARKER_RE = re.compile(r"<!-- scraper-alert: (\{.*?\}) -->", re.DOTALL)
# Long digit runs are timestamps, ids or durations; a change there is not a new problem.
_VOLATILE_RE = re.compile(r"\d{4,}")


def log(line: str) -> None:
    print(f"alerts: {line}", flush=True)


# ---------------------------------------------------------------------------------------
# What to do (pure)


@dataclass(frozen=True, slots=True)
class SourceStatus:
    chain_id: str
    ok: bool
    consecutive_failures: int
    last_error: str | None


@dataclass(frozen=True, slots=True)
class Issue:
    number: int
    chain_id: str
    body: str

    @property
    def has_marker(self) -> bool:
        return read_marker(self.body)[0]

    @property
    def reported_error(self) -> str | None:
        return read_marker(self.body)[1]


@dataclass(frozen=True, slots=True)
class OpenIssue:
    chain_id: str
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class CommentError:
    issue: Issue
    comment: str
    # The issue body with its marker pointing at the new error.
    new_body: str


@dataclass(frozen=True, slots=True)
class CloseIssue:
    issue: Issue
    comment: str


Action = OpenIssue | CommentError | CloseIssue


def title_for(chain_id: str) -> str:
    return f"{TITLE_PREFIX}{chain_id}"


def chain_id_from_title(title: str) -> str | None:
    if not title.startswith(TITLE_PREFIX):
        return None
    chain_id = title[len(TITLE_PREFIX) :].strip()
    return chain_id or None


def marker(chain_id: str, error: str | None) -> str:
    data = json.dumps({"chain_id": chain_id, "last_error": error}, ensure_ascii=False, sort_keys=True)
    # ">" only occurs inside JSON strings; escaping it keeps "-->" from ending the comment early.
    data = data.replace(">", "\\u003e")
    return f"<!-- scraper-alert: {data} -->"


def read_marker(body: str | None) -> tuple[bool, str | None]:
    """(found, last reported error) from an issue body."""
    match = _MARKER_RE.search(body or "")
    if match is None:
        return False, None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return False, None
    error = data.get("last_error") if isinstance(data, dict) else None
    return True, error if isinstance(error, str) else None


def same_error(a: str | None, b: str | None) -> bool:
    def norm(text: str | None) -> str:
        return _VOLATILE_RE.sub("#", " ".join((text or "").split()))

    return norm(a) == norm(b)


def _error_block(error: str | None) -> str:
    # A fenced block keeps markdown and @mentions in a site's error text from rendering.
    return "```text\n" + (error or "(no error message)").replace("```", "'''") + "\n```"


def _run_line(run_url: str | None) -> str:
    return f"\n\nRun: {run_url}" if run_url else ""


def issue_body(status: SourceStatus, run_url: str | None) -> str:
    return (
        f"The scraper source `{status.chain_id}` has failed {status.consecutive_failures} runs in a row. "
        "Its last good brochures are still published and marked stale.\n\n"
        f"Last error:\n\n{_error_block(status.last_error)}"
        f"{_run_line(run_url)}\n\n"
        "This issue is updated only when the error changes and is closed automatically when the "
        "source succeeds again.\n\n"
        f"{marker(status.chain_id, status.last_error)}"
    )


def plan(
    statuses: Sequence[SourceStatus],
    open_issues: Mapping[str, Issue],
    *,
    threshold: int = FAILURE_ALERT_THRESHOLD,
    run_url: str | None = None,
) -> list[Action]:
    """Actions that bring the issues in line with ``health.json``.

    Issues of sources missing from ``health.json`` are left alone: without a status there is
    nothing to say about them.
    """
    actions: list[Action] = []
    for status in statuses:
        issue = open_issues.get(status.chain_id)
        if status.ok:
            if issue is not None:
                comment = f"Recovered: `{status.chain_id}` succeeded again. Closing.{_run_line(run_url)}"
                actions.append(CloseIssue(issue, comment))
            continue
        if status.consecutive_failures < threshold:
            continue
        if issue is None:
            actions.append(OpenIssue(status.chain_id, title_for(status.chain_id), issue_body(status, run_url)))
        # Without a marker (an issue opened by hand) there is no record of what was reported, so
        # commenting would repeat on every run.
        elif issue.has_marker and not same_error(issue.reported_error, status.last_error):
            new_body = _MARKER_RE.sub(lambda _: marker(status.chain_id, status.last_error), issue.body, count=1)
            comment = (
                f"Still failing ({status.consecutive_failures} runs in a row), now with a different error:\n\n"
                f"{_error_block(status.last_error)}{_run_line(run_url)}"
            )
            actions.append(CommentError(issue, comment, new_body))
    return actions


def load_health(path: Path) -> list[SourceStatus]:
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, list):
        raise ValueError(f"{path} has no sources list")
    statuses = []
    for s in sources:
        if not isinstance(s, dict) or not isinstance(s.get("chain_id"), str):
            raise ValueError(f"{path} has a source without chain_id")
        statuses.append(
            SourceStatus(
                chain_id=s["chain_id"],
                ok=s.get("ok") is True,
                consecutive_failures=int(s.get("consecutive_failures") or 0),
                last_error=s.get("last_error") if isinstance(s.get("last_error"), str) else None,
            )
        )
    return statuses


# ---------------------------------------------------------------------------------------
# GitHub REST API


class GitHubError(Exception):
    pass


class GitHub:
    """The few issue endpoints this needs, paced to one request per second."""

    def __init__(
        self,
        client: httpx.Client,
        repository: str,
        token: str,
        *,
        api_url: str = DEFAULT_API_URL,
        min_interval: float = MIN_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._base = f"{api_url.rstrip('/')}/repos/{repository}"
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": user_agent(),
        }
        self._min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def _request(self, method: str, path: str, *, ok: tuple[int, ...] = (), **kwargs: Any) -> httpx.Response:
        if self._last is not None:
            wait = self._min_interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        try:
            response = self._client.request(
                method, f"{self._base}{path}", headers=self._headers, timeout=REQUEST_TIMEOUT, **kwargs
            )
        except httpx.HTTPError as exc:
            raise GitHubError(f"{method} {path}: {type(exc).__name__}: {exc}") from exc
        finally:
            self._last = self._clock()
        if not response.is_success and response.status_code not in ok:
            raise GitHubError(f"{method} {path}: HTTP {response.status_code} {_short(response.text)}")
        return response

    def open_alert_issues(self) -> dict[str, Issue]:
        issues: dict[str, Issue] = {}
        for page in range(1, MAX_PAGES + 1):
            params = {"state": "open", "labels": LABEL, "per_page": 100, "page": page}
            items = self._request("GET", "/issues", params=params).json()
            if not isinstance(items, list):
                raise GitHubError("GET /issues: unexpected response")
            for item in items:
                if not isinstance(item, dict) or "pull_request" in item:
                    continue
                chain_id = chain_id_from_title(str(item.get("title") or ""))
                if chain_id is None or chain_id in issues:
                    continue
                issues[chain_id] = Issue(int(item["number"]), chain_id, str(item.get("body") or ""))
            if len(items) < 100:
                break
        return issues

    def ensure_label(self) -> None:
        if self._request("GET", f"/labels/{LABEL}", ok=(404,)).status_code != 404:
            return
        # 422: someone created it in the meantime.
        self._request(
            "POST",
            "/labels",
            ok=(422,),
            json={"name": LABEL, "color": LABEL_COLOR, "description": LABEL_DESCRIPTION},
        )

    def create_issue(self, title: str, body: str) -> int:
        response = self._request("POST", "/issues", json={"title": title, "body": body, "labels": [LABEL]})
        return int(response.json()["number"])

    def comment(self, number: int, body: str) -> None:
        self._request("POST", f"/issues/{number}/comments", json={"body": body})

    def update_body(self, number: int, body: str) -> None:
        self._request("PATCH", f"/issues/{number}", json={"body": body})

    def close(self, number: int) -> None:
        self._request("PATCH", f"/issues/{number}", json={"state": "closed", "state_reason": "completed"})


def _short(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


@dataclass
class AlertResult:
    done: int = 0
    failed: int = 0


def apply(actions: Sequence[Action], github: GitHub) -> AlertResult:
    """Carry out each action; one that fails is logged and the rest still run."""
    result = AlertResult()
    label_ready = False
    for action in actions:
        try:
            match action:
                case OpenIssue():
                    if not label_ready:
                        github.ensure_label()
                        label_ready = True
                    number = github.create_issue(action.title, action.body)
                    log(f"{action.chain_id}: opened issue #{number}")
                case CommentError():
                    github.comment(action.issue.number, action.comment)
                    github.update_body(action.issue.number, action.new_body)
                    log(f"{action.issue.chain_id}: error changed, commented on issue #{action.issue.number}")
                case CloseIssue():
                    github.comment(action.issue.number, action.comment)
                    github.close(action.issue.number)
                    log(f"{action.issue.chain_id}: recovered, closed issue #{action.issue.number}")
            result.done += 1
        except (GitHubError, KeyError, TypeError, ValueError) as exc:
            result.failed += 1
            print(f"::warning::alerts: {type(action).__name__} failed: {exc}", flush=True)
    return result


# ---------------------------------------------------------------------------------------
# Command line


def run_url_from_env(env: Mapping[str, str]) -> str | None:
    server, repo, run_id = env.get("GITHUB_SERVER_URL"), env.get(REPOSITORY_ENV), env.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server.rstrip('/')}/{repo}/actions/runs/{run_id}"
    return None


def alert(
    health_path: Path,
    *,
    env: Mapping[str, str],
    client_factory: Callable[[], httpx.Client] = lambda: httpx.Client(),
    sleep: Callable[[float], None] = time.sleep,
) -> AlertResult:
    statuses = load_health(health_path)
    failing = [s.chain_id for s in statuses if not s.ok and s.consecutive_failures >= FAILURE_ALERT_THRESHOLD]
    token, repository = env.get(TOKEN_ENV, "").strip(), env.get(REPOSITORY_ENV, "").strip()
    if not token or not repository:
        missing = TOKEN_ENV if not token else REPOSITORY_ENV
        what = f"failing {FAILURE_ALERT_THRESHOLD}+ runs in a row: {', '.join(failing)}" if failing else "no source failing"
        log(f"alerts disabled ({missing} not set); {what}")
        return AlertResult()
    with client_factory() as client:
        github = GitHub(client, repository, token, api_url=env.get(API_URL_ENV) or DEFAULT_API_URL, sleep=sleep)
        actions = plan(statuses, github.open_alert_issues(), run_url=run_url_from_env(env))
        if not actions:
            log(f"nothing to do ({len(failing)} source(s) failing {FAILURE_ALERT_THRESHOLD}+ runs in a row)")
            return AlertResult()
        return apply(actions, github)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m scraper.alerts", description=__doc__.split("\n\n")[0])
    parser.add_argument("--health", type=Path, required=True, help="health.json that was just published")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    client_factory: Callable[[], httpx.Client] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Always returns 0: an alerting problem must never fail the scrape/publish job."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        result = alert(
            args.health,
            env=os.environ if env is None else env,
            sleep=sleep,
            **({"client_factory": client_factory} if client_factory else {}),
        )
    except Exception as exc:  # noqa: BLE001 - nothing here may fail the job.
        print(f"::warning::alerts failed: {type(exc).__name__}: {_short(str(exc))}", flush=True)
        return 0
    if result.failed:
        print(f"::warning::{result.failed} alert action(s) failed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
