"""Send "new brochure" push notifications through Firebase Cloud Messaging (HTTP v1).

Runs after a successful publish (see .github/workflows/scrape.yml)::

    python -m scraper.notify --previous state/catalog.json --current out/catalog.json

New brochures are the ids in the current catalog that the previously published catalog did
not have. Each chain with something new gets at most one message, sent to the topic
``chain-<chain_id>``; the app subscribes to the topics of the user's favourite chains. No
device tokens are stored anywhere.

Notifications are a nice-to-have: this step never fails the job. Without the
``FIREBASE_SERVICE_ACCOUNT`` secret (the service account JSON content) it logs one line and
exits 0; send errors are logged and the exit code is still 0. ``--dry-run`` never sends and
prints the messages that would be sent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

SERVICE_ACCOUNT_ENV = "FIREBASE_SERVICE_ACCOUNT"
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
TOPIC_PREFIX = "chain-"
# Must match the channel the app creates (app/android/.../MainActivity and notifications.dart).
ANDROID_CHANNEL_ID = "new_brochures"
SEND_TIMEOUT = 20.0
# Brochure dates are Turkish calendar days (same rule as scraper.runner).
TURKEY = timezone(timedelta(hours=3))

MONTHS_TR = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)  # fmt: skip

Catalog = Mapping[str, Any]
Brochure = Mapping[str, Any]
Message = dict[str, Any]


def log(line: str) -> None:
    print(f"notify: {line}", flush=True)


# ---------------------------------------------------------------------------------------
# What to send (pure)


def topic_for(chain_id: str) -> str:
    return f"{TOPIC_PREFIX}{chain_id}"


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def new_brochures(previous: Catalog | None, current: Catalog, today: date) -> dict[str, list[Brochure]]:
    """Newly published brochures per chain id, newest first.

    Nothing on the very first run (no previous catalog) and nothing for a chain the previous
    catalog did not have: its whole back catalogue would look "new". Web-view chains and
    brochures that already ended are ignored.
    """
    if previous is None:
        return {}
    previous_ids = {b.get("id") for b in previous.get("brochures", [])}
    previous_chains = {c.get("id") for c in previous.get("chains", [])}
    chains = {c.get("id"): c for c in current.get("chains", [])}
    found: dict[str, list[Brochure]] = {}
    for brochure in current.get("brochures", []):
        chain_id = brochure.get("chain_id")
        chain = chains.get(chain_id)
        if chain is None or chain.get("kind") == "webview" or chain_id not in previous_chains:
            continue
        if brochure.get("id") in previous_ids:
            continue
        valid_to = _parse_date(brochure.get("valid_to"))
        if valid_to is not None and valid_to < today:
            continue
        found.setdefault(chain_id, []).append(brochure)
    for items in found.values():
        items.sort(key=_newest_first_key, reverse=True)
    return dict(sorted(found.items()))


def _newest_first_key(brochure: Brochure) -> tuple[date, str, str]:
    return (
        _parse_date(brochure.get("valid_from")) or date.min,
        str(brochure.get("first_seen") or ""),
        str(brochure.get("id") or ""),
    )


def _day_month(d: date, with_year: bool) -> str:
    text = f"{d.day} {MONTHS_TR[d.month - 1]}"
    return f"{text} {d.year}" if with_year else text


def date_text(brochure: Brochure, today: date) -> str | None:
    """Short Turkish date like the app's card: "13–19 Kasım", "22 Ekim – 4 Kasım".

    Falls back to the brochure's own ``date_label`` when the dates are incomplete.
    """
    start = _parse_date(brochure.get("valid_from"))
    end = _parse_date(brochure.get("valid_to"))
    if start is not None and end is not None and start <= end:
        if start.year != end.year:
            return f"{_day_month(start, True)} – {_day_month(end, True)}"
        with_year = end.year != today.year
        if start == end:
            return _day_month(start, with_year)
        if start.month == end.month:
            year = f" {end.year}" if with_year else ""
            return f"{start.day}–{end.day} {MONTHS_TR[end.month - 1]}{year}"
        return f"{_day_month(start, False)} – {_day_month(end, with_year)}"
    label = brochure.get("date_label")
    if isinstance(label, str) and label.strip():
        return " ".join(label.split())
    return None


def build_message(chain: Mapping[str, Any], brochures: Sequence[Brochure], today: date) -> Message:
    """The FCM ``message`` object for one chain; ``brochures`` is newest first, non-empty."""
    newest = brochures[0]
    if len(brochures) > 1:
        body = f"{len(brochures)} yeni broşür yayında"
    else:
        label = date_text(newest, today)
        body = f"{label} broşürü yayında" if label else "Yeni broşür yayında"
    chain_id = str(chain["id"])
    return {
        "topic": topic_for(chain_id),
        "notification": {"title": f"{chain.get('name') or chain_id}: yeni broşür", "body": body},
        # FCM data values must be strings.
        "data": {"chain_id": chain_id, "brochure_id": str(newest["id"])},
        "android": {"priority": "HIGH", "notification": {"channel_id": ANDROID_CHANNEL_ID}},
    }


def build_messages(previous: Catalog | None, current: Catalog, today: date) -> list[Message]:
    chains = {c.get("id"): c for c in current.get("chains", [])}
    return [
        build_message(chains[chain_id], brochures, today)
        for chain_id, brochures in new_brochures(previous, current, today).items()
    ]


# ---------------------------------------------------------------------------------------
# Sending


class NotifyConfigError(Exception):
    """The service account secret is unusable. The message never contains its content."""


@dataclass(frozen=True)
class ServiceAccount:
    project_id: str
    info: Mapping[str, Any]


def service_account_from_env(env: Mapping[str, str]) -> ServiceAccount | None:
    """None when the secret is not set; raises NotifyConfigError when it is set but broken."""
    raw = env.get(SERVICE_ACCOUNT_ENV, "").strip()
    if not raw:
        return None
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        raise NotifyConfigError(f"{SERVICE_ACCOUNT_ENV} is not valid JSON") from None
    if not isinstance(info, dict):
        raise NotifyConfigError(f"{SERVICE_ACCOUNT_ENV} is not a JSON object")
    missing = [k for k in ("project_id", "client_email", "private_key", "token_uri") if not info.get(k)]
    if missing:
        raise NotifyConfigError(f"{SERVICE_ACCOUNT_ENV} lacks {', '.join(missing)}")
    return ServiceAccount(project_id=str(info["project_id"]), info=info)


class _HttpxAuthResponse:
    """``google.auth.transport.Response`` on top of an httpx response."""

    def __init__(self, response: httpx.Response) -> None:
        self.status = response.status_code
        self.headers = dict(response.headers)
        self.data = response.content


class HttpxAuthRequest:
    """``google.auth.transport.Request`` on top of httpx, so google-auth needs no ``requests``."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
        **_kwargs: Any,
    ) -> _HttpxAuthResponse:
        from google.auth import exceptions

        try:
            response = self._client.request(
                method, url, content=body, headers=dict(headers or {}), timeout=timeout or SEND_TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise exceptions.TransportError(f"{type(exc).__name__}: {exc}") from exc
        return _HttpxAuthResponse(response)


def access_token(account: ServiceAccount, client: httpx.Client) -> str:
    """OAuth2 access token for FCM, minted from the service account key."""
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_info(dict(account.info), scopes=[FCM_SCOPE])
    credentials.refresh(HttpxAuthRequest(client))
    return str(credentials.token)


@dataclass
class SendResult:
    sent: int = 0
    failed: int = 0


def send_messages(
    messages: Sequence[Message],
    project_id: str,
    token: str,
    client: httpx.Client,
) -> SendResult:
    """POST each message; a failure is logged and the rest are still sent."""
    url = FCM_SEND_URL.format(project_id=project_id)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    result = SendResult()
    for message in messages:
        topic = message.get("topic")
        try:
            response = client.post(url, json={"message": message}, headers=headers, timeout=SEND_TIMEOUT)
        except httpx.HTTPError as exc:
            result.failed += 1
            log(f"{topic}: send failed: {type(exc).__name__}: {exc}")
            continue
        if response.is_success:
            result.sent += 1
            log(f"{topic}: sent")
        else:
            result.failed += 1
            log(f"{topic}: send failed: HTTP {response.status_code} {_short(response.text)}")
    return result


def _short(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------------------------------------------------------------------------------------
# Command line


def load_catalog(path: Path) -> dict[str, Any] | None:
    """The catalog at ``path``; None when the file does not exist (first run)."""
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def notify(
    previous_path: Path,
    current_path: Path,
    *,
    today: date,
    dry_run: bool,
    env: Mapping[str, str],
    client_factory: Callable[[], httpx.Client] = lambda: httpx.Client(),
) -> SendResult:
    current = load_catalog(current_path)
    if current is None:
        log(f"{current_path} not found; nothing to notify")
        return SendResult()
    previous = load_catalog(previous_path)
    if previous is None:
        log("no previous catalog (first run); nothing to notify")
        return SendResult()
    messages = build_messages(previous, current, today)
    if not messages:
        log("no new brochures; nothing to notify")
        return SendResult()
    if dry_run:
        log(f"dry run: would send {len(messages)} message(s)")
        for message in messages:
            print(json.dumps({"message": message}, ensure_ascii=False, indent=2))
        return SendResult()
    account = service_account_from_env(env)
    if account is None:
        log(f"notifications disabled ({SERVICE_ACCOUNT_ENV} not set); {len(messages)} message(s) not sent")
        return SendResult()
    with client_factory() as client:
        token = access_token(account, client)
        return send_messages(messages, account.project_id, token, client)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m scraper.notify", description=__doc__.split("\n\n")[0])
    parser.add_argument("--previous", type=Path, required=True, help="previously published catalog.json")
    parser.add_argument("--current", type=Path, required=True, help="catalog.json that was just published")
    parser.add_argument("--today", type=date.fromisoformat, help="pretend today is YYYY-MM-DD (Turkish date)")
    parser.add_argument("--dry-run", action="store_true", help="print the messages instead of sending them")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    client_factory: Callable[[], httpx.Client] | None = None,
) -> int:
    """Always returns 0: a notification problem must never fail the scrape/publish job."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    today = args.today or datetime.now(UTC).astimezone(TURKEY).date()
    try:
        result = notify(
            args.previous,
            args.current,
            today=today,
            dry_run=args.dry_run,
            env=os.environ if env is None else env,
            **({"client_factory": client_factory} if client_factory else {}),
        )
    except NotifyConfigError as exc:
        log(f"notifications disabled: {exc}")
        return 0
    except Exception as exc:  # noqa: BLE001 - nothing here may fail the job.
        # The exception text of google-auth never contains the private key; keep it short anyway.
        log(f"::warning::notifications failed: {type(exc).__name__}: {_short(str(exc))}")
        return 0
    if result.sent or result.failed:
        log(f"done: {result.sent} sent, {result.failed} failed")
        if result.failed:
            print(f"::warning::{result.failed} notification(s) could not be sent", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
