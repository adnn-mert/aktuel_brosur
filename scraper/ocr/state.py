"""What the OCR step remembers between runs: ``ocr_state.json`` next to ``catalog.json``.

The file is published on the ``data`` branch with the rest of the output, so the next run
restores it with ``fetch-state``. It records, per brochure, the page fingerprint that was
read (so a brochure is read once) or how often reading it failed (so a broken brochure
cannot eat the quota), plus how many Gemini requests were spent on the current quota day.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time, timedelta
from functools import cache
from pathlib import Path
from typing import Any, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from scraper.core.models import format_datetime, parse_datetime
from scraper.core.validate import ContractError, validate_ocr_state

STATE_FILE = "ocr_state.json"
STATE_VERSION = 1

# The free tier's daily request quota resets at midnight Pacific time.
QUOTA_TIME_ZONE = "America/Los_Angeles"


# --- quota day -------------------------------------------------------------------------


@cache
def _pacific_zone() -> ZoneInfo | None:
    try:
        return ZoneInfo(QUOTA_TIME_ZONE)
    except ZoneInfoNotFoundError:
        # Windows has no system time zone database and tzdata is not a dependency.
        return None


def _nth_sunday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(6 - first.weekday()) % 7, weeks=n - 1)


def us_pacific_offset(moment: datetime) -> timedelta:
    """UTC offset of US Pacific time under the federal rule in force since 2007.

    Daylight time runs from 02:00 PST on the second Sunday of March (10:00 UTC) to 02:00 PDT
    on the first Sunday of November (09:00 UTC).
    """
    utc = moment.astimezone(UTC)
    start = datetime.combine(_nth_sunday(utc.year, 3, 2), time(10), tzinfo=UTC)
    end = datetime.combine(_nth_sunday(utc.year, 11, 1), time(9), tzinfo=UTC)
    return timedelta(hours=-7) if start <= utc < end else timedelta(hours=-8)


def quota_day(moment: datetime) -> date:
    """The Gemini quota day ``moment`` falls on (the America/Los_Angeles calendar day)."""
    zone = _pacific_zone()
    if zone is not None:
        return moment.astimezone(zone).date()
    return (moment.astimezone(UTC) + us_pacific_offset(moment)).date()


# --- records ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Reading:
    """A successful read whose products are published."""

    products_url: str
    product_count: int
    read_at: datetime
    model: str
    thinking_level: str
    prompt_version: str
    requests: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "products_url": self.products_url,
            "product_count": self.product_count,
            "read_at": format_datetime(self.read_at),
            "model": self.model,
            "thinking_level": self.thinking_level,
            "prompt_version": self.prompt_version,
            "requests": self.requests,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            products_url=data["products_url"],
            product_count=data["product_count"],
            read_at=parse_datetime(data["read_at"]),
            model=data["model"],
            thinking_level=data["thinking_level"],
            prompt_version=data["prompt_version"],
            requests=data["requests"],
        )


@dataclass(frozen=True, slots=True)
class BrochureRecord:
    """One brochure's OCR history for one page fingerprint; a new fingerprint starts afresh."""

    fingerprint: str
    reading: Reading | None = None
    failed_attempts: int = 0
    last_error: str | None = None
    last_attempt_at: datetime | None = None

    def failed(self, error: str, at: datetime) -> BrochureRecord:
        return replace(
            self, reading=None, failed_attempts=self.failed_attempts + 1, last_error=error, last_attempt_at=at
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"fingerprint": self.fingerprint, "failed_attempts": self.failed_attempts}
        if self.reading is not None:
            out["reading"] = self.reading.to_dict()
        if self.last_error is not None:
            out["last_error"] = self.last_error
        if self.last_attempt_at is not None:
            out["last_attempt_at"] = format_datetime(self.last_attempt_at)
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        reading = data.get("reading")
        attempted = data.get("last_attempt_at")
        return cls(
            fingerprint=data["fingerprint"],
            reading=Reading.from_dict(reading) if reading else None,
            failed_attempts=data["failed_attempts"],
            last_error=data.get("last_error"),
            last_attempt_at=parse_datetime(attempted) if attempted else None,
        )


@dataclass(slots=True)
class OcrState:
    quota_day: date | None = None
    attempts: int = 0
    brochures: dict[str, BrochureRecord] = field(default_factory=dict)

    def attempts_on(self, day: date) -> int:
        return self.attempts if self.quota_day == day else 0

    def to_dict(self, generated_at: datetime, model: str, thinking_level: str) -> dict[str, Any]:
        return {
            "schema_version": STATE_VERSION,
            "generated_at": format_datetime(generated_at),
            "model": model,
            "thinking_level": thinking_level,
            "usage": {
                "quota_day": self.quota_day.isoformat() if self.quota_day else None,
                "attempts": self.attempts,
            },
            "brochures": {bid: self.brochures[bid].to_dict() for bid in sorted(self.brochures)},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        usage = data["usage"]
        day = usage["quota_day"]
        return cls(
            quota_day=date.fromisoformat(day) if day else None,
            attempts=usage["attempts"],
            brochures={bid: BrochureRecord.from_dict(r) for bid, r in data["brochures"].items()},
        )


@dataclass(frozen=True, slots=True)
class LoadedState:
    state: OcrState
    # Set when a state file existed but could not be used; the caller must then assume the
    # day's quota is spent, because the request counter is gone with it.
    error: str | None = None


def load_state(path: Path) -> LoadedState:
    if not path.is_file():
        return LoadedState(OcrState())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        validate_ocr_state(data)
        return LoadedState(OcrState.from_dict(data))
    except ContractError as exc:
        return LoadedState(OcrState(), f"{path.name} ignored: {'; '.join(exc.errors[:3])}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return LoadedState(OcrState(), f"{path.name} ignored: {type(exc).__name__}: {exc}")


# --- budget ----------------------------------------------------------------------------


@dataclass(slots=True)
class Budget:
    """Gemini requests this run may still send. Every request counts, retries included."""

    day: date
    used_today: int
    run_limit: int
    daily_limit: int
    used_this_run: int = 0

    @property
    def remaining(self) -> int:
        return max(0, min(self.run_limit - self.used_this_run, self.daily_limit - self.used_today))

    def spend(self) -> None:
        self.used_today += 1
        self.used_this_run += 1

    def refund(self) -> None:
        self.used_today -= 1
        self.used_this_run -= 1
