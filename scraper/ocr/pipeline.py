"""OCR step of the scrape job: ``python -m scraper ocr --state-dir state --out out``.

Runs after ``python -m scraper run`` has written ``out/`` and before it is published. Chains
on the allow list print their prices only in the page images; their new brochures are read
with Gemini and the products are published as ``products_ocr/<id>.json``, linked from the
brochure by the optional ``ocr_products_url`` field.

Rules (PLAN.md, Aşama 3B):
- Apps that predate OCR must never show its prices unlabelled, so ``kind``, ``products_url``
  and ``product_count`` of a brochure are never touched; only the new field is added.
- Each brochure is read once. The page fingerprint read last time is kept in
  ``ocr_state.json``; when it still matches, the earlier product file is carried over from
  the previous output and no request is sent.
- The free tier allows about 20 requests a day, retries included. This step sends at most
  ``RUN_REQUEST_LIMIT`` per run and ``DAILY_REQUEST_LIMIT`` per quota day, stops at the first
  HTTP 429, retries a 5xx at most once, and gives up on a brochure after
  ``MAX_FAILED_ATTEMPTS`` failed reads.
- Nothing here may fail the job or the publication: every problem is logged, the exit code
  is always 0, and the output is checked after each change; a change that breaks the check
  is rolled back so ``out/`` is published as it was without that brochure's OCR.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from scraper.core.http import HttpClient
from scraper.core.media import is_local
from scraper.core.models import Product, ProductFile
from scraper.core.pipeline import (
    CATALOG_FILE,
    OCR_PRODUCTS_DIR,
    OutputError,
    check_ocr_products,
    short_error,
    verify_output,
)
from scraper.core.validate import ContractError, validate_products
from scraper.ocr.evaluate import chunk_pages, image_mime
from scraper.ocr.gemini import (
    API_KEY_ENV,
    BROCHURE_PROMPT_VERSION,
    BROCHURE_STORES,
    DEFAULT_MODEL,
    MAX_INLINE_REQUEST_BYTES,
    GeminiClient,
    GeminiError,
    OcrResult,
    brochure_timeout,
)
from scraper.ocr.prices import parse_ocr_price
from scraper.ocr.state import STATE_FILE, Budget, BrochureRecord, OcrState, Reading, load_state, quota_day
from scraper.runner import SUMMARY_ENV, TURKEY

__all__ = ["API_KEY_ENV", "add_arguments", "main"]

# --- settings (the only place to change them) ------------------------------------------

# Chains whose prices are printed only in the page images. BİM and Migros publish written
# prices and webview chains have no pages, so they never belong here. Each id needs a store
# name in gemini.BROCHURE_STORES for the prompt.
OCR_CHAINS: tuple[str, ...] = ("sok", "hakmar")

MODEL = DEFAULT_MODEL
THINKING_LEVEL = "LOW"
# The page prompt is gemini._pages_prompt; it has no version of its own yet.
PROMPT_VERSION = f"pages-{BROCHURE_PROMPT_VERSION}"

# Free tier: ~20 requests a day per project, retries included. 15 leaves room for manual
# measurements; 5 per run spreads the day over the three scheduled runs.
DAILY_REQUEST_LIMIT = 15
RUN_REQUEST_LIMIT = 5
MAX_FAILED_ATTEMPTS = 3
SERVER_ERROR_RETRIES = 1
SERVER_ERROR_BACKOFF = 30.0

MAX_PAGES_PER_REQUEST = 10
# Inline images are sent base64-encoded (4/3 larger) and the whole request may be 20 MB;
# keep half a megabyte for the prompt and the JSON around it.
MAX_IMAGE_BYTES_PER_REQUEST = MAX_INLINE_REQUEST_BYTES * 3 // 4 - 512 * 1024

# Fewer usable products than this means the answer is not a reading of the brochure (a
# refused, truncated or confused answer): Şok and Hakmar pages print several priced products
# each. One per page on average, never fewer than five.
MIN_PRODUCTS = 5

# Wall-clock budget for Gemini requests. A request may take up to its timeout
# (gemini.brochure_timeout, ~23 min for 8 pages), so a brochure is only started when all its
# requests fit. The workflow step's own timeout is a little longer (scrape.yml).
TIME_BUDGET = 50 * 60.0
IMAGE_TIMEOUT = 60.0


def ocr_products_path(brochure_id: str) -> str:
    return f"{OCR_PRODUCTS_DIR}/{brochure_id}.json"


# --- pure helpers ----------------------------------------------------------------------


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def page_fingerprint(pages: Sequence[dict[str, Any]], digests: Sequence[str | None]) -> str:
    """What was read: page addresses and sizes in order, plus content digests of our own files.

    A chain's own image URL is trusted to change with its content (Hakmar's file names carry
    the dates); for pages we render ourselves the bytes are hashed, because their paths are
    reused.
    """
    items = [[p["url"], p.get("w"), p.get("h"), d] for p, d in zip(pages, digests, strict=True)]
    return hashlib.sha256(json.dumps(items, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def validity(brochure: dict[str, Any], today: date) -> str:
    """"expired", "upcoming" or "current" (undated brochures count as current)."""
    valid_from, valid_to = brochure.get("valid_from"), brochure.get("valid_to")
    if valid_to and date.fromisoformat(valid_to) < today:
        return "expired"
    if valid_from and date.fromisoformat(valid_from) > today:
        return "upcoming"
    return "current"


def read_order_key(brochure: dict[str, Any], today: date) -> tuple[Any, ...]:
    """Current before upcoming; within each, the newest start first, undated last."""
    start = brochure.get("valid_from")
    ordinal = date.fromisoformat(start).toordinal() if start else 0
    return (validity(brochure, today) != "current", start is None, -ordinal, brochure["id"])


def plan_requests(
    sizes: Sequence[int],
    max_pages: int = MAX_PAGES_PER_REQUEST,
    max_bytes: int = MAX_IMAGE_BYTES_PER_REQUEST,
) -> list[list[int]]:
    """Page indices per request: as few requests as the page and byte limits allow.

    Uses the evaluator's even split (11 pages -> 6 + 5), shrinking the chunk size until
    every chunk's images fit the inline request limit.
    """
    for i, size in enumerate(sizes):
        if size > max_bytes:
            raise ValueError(f"page {i + 1} is {size / 1_048_576:.1f} MB, more than one request can carry")
    indices = list(range(len(sizes)))
    for per_request in range(min(max_pages, len(sizes)), 0, -1):
        chunks = chunk_pages(indices, per_request)
        if all(sum(sizes[i] for i in chunk) <= max_bytes for chunk in chunks):
            return chunks
    return []


def _clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return " ".join(value.split()) or None


def _price(value: Any) -> int | None:
    return parse_ocr_price(value) if isinstance(value, str | int | float) else None


def convert_products(raw: Sequence[dict[str, Any]], offset: int, page_count: int) -> tuple[list[Product], int]:
    """Turn one request's answer into products; returns them and how many were dropped.

    ``page_index`` in ``raw`` is relative to the request (already checked against its image
    count by ``parse_brochure_response``); ``offset`` turns it into the brochure's page.
    """
    kept: list[Product] = []
    dropped = 0
    for item in raw:
        name = _clean(item.get("name"))
        index = item.get("page_index")
        price = _price(item.get("price"))
        page = offset + index if isinstance(index, int) and not isinstance(index, bool) else None
        if name is None or price is None or price <= 0 or page is None or not 0 <= page < page_count:
            dropped += 1
            continue
        old = _price(item.get("old_price"))
        kept.append(
            Product(
                name=name,
                price_minor=price,
                brand=_clean(item.get("brand")),
                # Tells apart same-named products ("2 cm" / "3 cm"), so it is always kept.
                quantity_text=_clean(item.get("quantity_text")),
                # An "old" price that is not higher is a misread, not a discount.
                old_price_minor=old if old is not None and old > price else None,
                page_index=page,
                source="ocr",
            )
        )
    return kept, dropped


def rejection(kept: int, dropped: int, page_count: int) -> str | None:
    """Why a reading must not be published, or None."""
    needed = max(MIN_PRODUCTS, page_count)
    if kept < needed:
        return f"only {kept} usable products, need {needed}"
    if dropped > kept:
        return f"{dropped} of {kept + dropped} products unusable"
    return None


# --- output ----------------------------------------------------------------------------


def _dump(data: Any) -> bytes:
    # Same layout as scraper.core.pipeline.write_json, so files stay diff-friendly.
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write_atomic(path: Path, content: bytes) -> None:
    """Readers (and a step killed by its timeout) see the old file or the new one, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, path)


class Output:
    """Writes OCR results into an output folder whose catalog the scrape step already checked."""

    def __init__(self, root: Path, base_catalog: dict[str, Any]) -> None:
        self.root = root
        self.base_catalog = base_catalog

    def write_state(self, data: dict[str, Any]) -> None:
        _write_atomic(self.root / STATE_FILE, _dump(data))

    def commit(self, files: dict[str, dict[str, Any]]) -> None:
        """Publish exactly ``files`` (brochure id -> product file); raise OutputError if the result is invalid."""
        folder = self.root / OCR_PRODUCTS_DIR
        for brochure_id, data in files.items():
            _write_atomic(self.root / ocr_products_path(brochure_id), _dump(data))
        catalog = copy.deepcopy(self.base_catalog)
        for brochure in catalog["brochures"]:
            if brochure["id"] in files:
                brochure["ocr_products_url"] = ocr_products_path(brochure["id"])
        _write_atomic(self.root / CATALOG_FILE, _dump(catalog))
        if folder.is_dir():
            wanted = {f"{bid}.json" for bid in files}
            for path in folder.iterdir():
                if path.name not in wanted:
                    path.unlink()
            if not any(folder.iterdir()):
                folder.rmdir()
        verify_output(self.root)

    def restore(self) -> None:
        """Back to the scrape step's output: no OCR products at all."""
        _write_atomic(self.root / CATALOG_FILE, _dump(self.base_catalog))
        shutil.rmtree(self.root / OCR_PRODUCTS_DIR, ignore_errors=True)


# --- the step --------------------------------------------------------------------------


class Reader(Protocol):
    requests_sent: int

    def read_brochure(
        self, images: Sequence[bytes], mime_type: str = ..., chain: str = ...
    ) -> tuple[OcrResult, dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class Target:
    brochure: dict[str, Any]
    fingerprint: str

    @property
    def id(self) -> str:
        return self.brochure["id"]

    @property
    def pages(self) -> list[dict[str, Any]]:
        return self.brochure["pages"]


@dataclass(slots=True)
class Outcome:
    brochure_id: str
    result: str
    detail: str = ""


@dataclass(slots=True)
class OcrReport:
    outcomes: list[Outcome] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    requests: int = 0
    used_today: int = 0
    run_limit: int = RUN_REQUEST_LIMIT
    disabled: bool = False
    dry_run: bool = False
    stopped: str | None = None

    def add(self, brochure_id: str, result: str, detail: str = "") -> None:
        self.outcomes.append(Outcome(brochure_id, result, detail))


class _QuotaStop(Exception):
    pass


class _Failed(Exception):
    """A read failed in a way that counts against the brochure."""


class _Skipped(Exception):
    """Not tried this run (budget, time, download); does not count against the brochure."""


class OcrStep:
    def __init__(
        self,
        out_dir: Path,
        state_dir: Path,
        *,
        now: datetime,
        today: date,
        reader: Reader | None,
        http: HttpClient | None = None,
        dry_run: bool = False,
        run_limit: int = RUN_REQUEST_LIMIT,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        log: Callable[[str], None] = lambda _msg: None,
    ) -> None:
        self.out = out_dir
        self.state_dir = state_dir
        self.now = now
        self.today = today
        self.reader = reader
        self.http = http
        self.dry_run = dry_run
        self.run_limit = min(run_limit, RUN_REQUEST_LIMIT)
        self.clock = clock
        self.sleep = sleep
        self.log = log
        self.started = clock()
        self.report = OcrReport(dry_run=dry_run, run_limit=self.run_limit)
        self.state = OcrState()
        self.budget = Budget(quota_day(now), 0, self.run_limit, DAILY_REQUEST_LIMIT)
        self.output: Output | None = None
        self.published: dict[str, dict[str, Any]] = {}

    # -- orchestration ------------------------------------------------------------------

    def execute(self) -> OcrReport:
        catalog_path = self.out / CATALOG_FILE
        if not catalog_path.is_file():
            self.report.notes.append(f"no {CATALOG_FILE} in {self.out} (scrape not written); nothing to do")
            return self.report
        base = json.loads(catalog_path.read_text(encoding="utf-8"))
        # A rerun on the same folder starts from the scrape output again.
        for brochure in base["brochures"]:
            brochure.pop("ocr_products_url", None)

        loaded = load_state(self.state_dir / STATE_FILE)
        previous = loaded.state
        day = quota_day(self.now)
        used = previous.attempts_on(day)
        if loaded.error:
            # The request counter is lost with the file; assume today's quota is gone.
            self.report.notes.append(f"{loaded.error}; no requests until the next quota day")
            used = DAILY_REQUEST_LIMIT
        self.budget = Budget(day, used, self.run_limit, DAILY_REQUEST_LIMIT)
        self.state = OcrState(quota_day=day, attempts=used)

        targets = self._targets(base)
        self._carry_over(targets, previous)
        candidates = self._candidates(targets)
        if self.dry_run:
            self._plan(candidates)
            return self._finish()

        self.output = Output(self.out, base)
        if not self._commit():
            self.report.notes.append("earlier readings dropped: the output check failed with them")
            for bid in list(self.published):
                self.report.add(bid, "dropped", "output check failed")
            self.published.clear()
            if not self._commit():
                self.report.notes.append("the scrape output itself fails the check; OCR skipped")
                self.output.restore()
                return self._finish()
        if self.reader is None:
            self.report.disabled = True
            self.report.notes.append(f"OCR disabled: {API_KEY_ENV} is not set; earlier readings carried over only")
            for t in candidates:
                self.report.add(t.id, "not read", "OCR disabled")
            return self._finish()

        for t in candidates:
            self._try(t)
        return self._finish()

    def recover(self) -> str:
        """After an unexpected error: leave ``out/`` valid, with whatever OCR still passes the check."""
        if self.output is None:
            return "out/ left as the scrape step wrote it"
        try:
            if self._commit():
                self._save_state()
                return f"out/ keeps {len(self.published)} OCR reading(s)"
            self.output.restore()
            return "OCR removed from out/"
        except Exception as exc:  # Last resort; nothing more can be done here.
            return f"recovery failed: {type(exc).__name__}"

    def _finish(self) -> OcrReport:
        self.report.used_today = self.budget.used_today
        self.report.requests = self.budget.used_this_run
        if not self.dry_run and self.output is not None:
            self._save_state()
        return self.report

    def _targets(self, catalog: dict[str, Any]) -> list[Target]:
        targets: list[Target] = []
        for b in catalog["brochures"]:
            # A written product list is better than OCR; such brochures are never read.
            if b["chain_id"] not in OCR_CHAINS or b["products_url"] is not None or not b["pages"]:
                continue
            try:
                digests = [file_digest(self.out / p["url"]) if is_local(p["url"]) else None for p in b["pages"]]
            except OSError as exc:
                self.report.notes.append(f"{b['id']}: skipped, page file unreadable: {exc}")
                continue
            targets.append(Target(b, page_fingerprint(b["pages"], digests)))
        return targets

    def _carry_over(self, targets: Sequence[Target], previous: OcrState) -> None:
        """Keep records of brochures still listed with unchanged pages; everything else is pruned."""
        for t in targets:
            record = previous.brochures.get(t.id)
            if record is None or record.fingerprint != t.fingerprint:
                continue
            if record.reading is not None:
                try:
                    self.published[t.id] = self._load_previous(t, record.reading)
                    reading = record.reading
                    self.report.add(t.id, "cached", f"{reading.product_count} products, read {_stamp(reading.read_at)}")
                except ValueError as exc:
                    self.report.notes.append(f"{t.id}: earlier reading not reused ({exc}); it will be read again")
                    record = replace(record, reading=None)
            self.state.brochures[t.id] = record

    def _load_previous(self, t: Target, reading: Reading) -> dict[str, Any]:
        path = self.state_dir / reading.products_url
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            validate_products(data)
        except ContractError as exc:
            raise ValueError("; ".join(exc.errors[:2])) from None
        except (OSError, ValueError) as exc:
            raise ValueError(f"{reading.products_url}: {type(exc).__name__}") from None
        errors = check_ocr_products(data, t.brochure, reading.products_url)
        if errors:
            raise ValueError("; ".join(errors[:2]))
        return data

    def _candidates(self, targets: Sequence[Target]) -> list[Target]:
        out: list[Target] = []
        for t in sorted(targets, key=lambda t: read_order_key(t.brochure, self.today)):
            if t.id in self.published:
                continue
            record = self.state.brochures.get(t.id)
            if record is not None and record.failed_attempts >= MAX_FAILED_ATTEMPTS:
                self.report.add(t.id, "given up", f"failed {record.failed_attempts} times: {record.last_error or ''}")
            elif validity(t.brochure, self.today) == "expired":
                self.report.add(t.id, "not read", "expired")
            else:
                out.append(t)
        return out

    def _plan(self, candidates: Sequence[Target]) -> None:
        remaining = self.budget.remaining
        for t in candidates:
            local = all(is_local(p["url"]) for p in t.pages)
            sizes = [(self.out / p["url"]).stat().st_size if is_local(p["url"]) else 0 for p in t.pages]
            try:
                requests = len(plan_requests(sizes))
            except ValueError as exc:
                self.report.add(t.id, "would fail", str(exc))
                continue
            note = "" if local else " (remote pages: the byte limit may add requests)"
            if requests <= remaining:
                remaining -= requests
                self.report.add(t.id, "would read", f"{len(t.pages)} pages in {requests} request(s){note}")
            else:
                self.report.add(t.id, "would wait", f"needs {requests} request(s), {remaining} left{note}")

    # -- one brochure -------------------------------------------------------------------

    def _try(self, t: Target) -> None:
        if self.report.stopped:
            self.report.add(t.id, "not read", self.report.stopped)
            return
        try:
            data, requests = self._read_guarded(t)
        except _QuotaStop as exc:
            self.report.stopped = "stopped after HTTP 429"
            self.report.add(t.id, "stopped", f"HTTP 429 (quota): {_one_line(exc)}")
            self._save_state()
            return
        except _Skipped as exc:
            self.report.add(t.id, "not read", str(exc))
            return
        except _Failed as exc:
            self._fail(t, str(exc))
            return
        self.published[t.id] = data
        reading = Reading(
            products_url=ocr_products_path(t.id),
            product_count=len(data["products"]),
            read_at=self.now,
            model=MODEL,
            thinking_level=THINKING_LEVEL,
            prompt_version=PROMPT_VERSION,
            requests=requests,
        )
        if self._commit():
            self.state.brochures[t.id] = BrochureRecord(t.fingerprint, reading, 0, None, self.now)
            self._save_state()
            self.report.add(t.id, "read", f"{len(data['products'])} products, {requests} request(s)")
            return
        del self.published[t.id]
        self._fail(t, "output check failed with this reading")
        if not self._commit():
            self.report.notes.append("output check failed even without the new reading; OCR removed from this output")
            self.published.clear()
            self._commit()

    def _fail(self, t: Target, error: str) -> None:
        record = self.state.brochures.get(t.id)
        if record is None or record.fingerprint != t.fingerprint:
            record = BrochureRecord(t.fingerprint)
        error = _one_line(error)
        self.state.brochures[t.id] = record.failed(error, self.now)
        self.report.add(t.id, "failed", f"attempt {record.failed_attempts + 1}/{MAX_FAILED_ATTEMPTS}: {error}")
        self._save_state()

    def _read_guarded(self, t: Target) -> tuple[dict[str, Any], int]:
        try:
            return self._read(t)
        except (_QuotaStop, _Skipped, _Failed):
            raise
        except Exception as exc:  # A bug must cost this brochure an attempt, not the whole step.
            raise _Failed(f"internal error: {type(exc).__name__}: {exc}") from exc

    def _read(self, t: Target) -> tuple[dict[str, Any], int]:
        page_count = len(t.pages)
        # Before downloading anything: the fewest requests the page count allows must fit.
        by_count = [len(c) for c in plan_requests([0] * page_count)]
        if self.budget.remaining < len(by_count):
            raise _Skipped(self._budget_text())
        if not self._time_left_for(by_count):
            raise _Skipped("time budget spent")
        images = self._images(t)
        try:
            plan = plan_requests([len(i) for i in images])
        except ValueError as exc:
            raise _Failed(str(exc)) from None
        if self.budget.remaining < len(plan):
            raise _Skipped(self._budget_text())
        if not self._time_left_for([len(c) for c in plan]):
            raise _Skipped("time budget spent")

        products: list[Product] = []
        dropped = 0
        requests_before = self.budget.used_this_run
        for chunk in plan:
            chunk_images = [images[i] for i in chunk]
            mimes = {image_mime(i) for i in chunk_images}
            if len(mimes) != 1:
                raise _Failed(f"pages mix image types: {', '.join(sorted(mimes))}")
            result = self._request(chunk_images, mimes.pop(), t.brochure["chain_id"])
            kept, lost = convert_products(result.products, chunk[0], page_count)
            products += kept
            dropped += lost
        requests = self.budget.used_this_run - requests_before
        reason = rejection(len(products), dropped, page_count)
        if reason:
            raise _Failed(reason)
        products.sort(key=lambda p: p.page_index or 0)
        data = ProductFile(t.id, tuple(products)).to_dict()
        try:
            validate_products(data)
        except ContractError as exc:
            raise _Failed("invalid products: " + "; ".join(exc.errors[:2])) from None
        errors = check_ocr_products(data, t.brochure, ocr_products_path(t.id))
        if errors:
            raise _Failed("; ".join(errors[:2]))
        return data, requests

    def _request(self, images: list[bytes], mime: str, chain: str) -> OcrResult:
        assert self.reader is not None
        retries = 0
        while True:
            if self.budget.remaining < 1:
                raise _Failed("server error and no request left to retry it")
            # Counted (and saved) before sending: a step killed mid-request still paid for it.
            self.budget.spend()
            self._save_state()
            sent_before = self.reader.requests_sent
            try:
                result, _raw = self.reader.read_brochure(images, mime, chain=chain)
                return result
            except GeminiError as exc:
                if self.reader.requests_sent == sent_before:
                    self.budget.refund()
                    self._save_state()
                if exc.status == 429:
                    raise _QuotaStop(str(exc)) from None
                server_error = exc.status is not None and exc.status >= 500
                if server_error and retries < SERVER_ERROR_RETRIES and self._time_left_for([len(images)]):
                    retries += 1
                    self.log(f"ocr: {_one_line(exc)}; retrying once in {SERVER_ERROR_BACKOFF:.0f}s")
                    self.sleep(SERVER_ERROR_BACKOFF)
                    continue
                raise _Failed(_one_line(exc)) from None

    def _images(self, t: Target) -> list[bytes]:
        images: list[bytes] = []
        for page in t.pages:
            url = page["url"]
            if is_local(url):
                images.append((self.out / url).read_bytes())
                continue
            if self.http is None:
                self.http = HttpClient(timeout=IMAGE_TIMEOUT)
            try:
                response = self.http.get(url, timeout=IMAGE_TIMEOUT)
            except Exception as exc:  # A network hiccup is not the brochure's fault.
                raise _Skipped(f"page download failed: {short_error(exc)}") from None
            if response.status_code != 200:
                raise _Skipped(f"page download failed: HTTP {response.status_code} for {url}")
            images.append(response.content)
        return images

    # -- small helpers ------------------------------------------------------------------

    def _time_left_for(self, chunk_sizes: Sequence[int]) -> bool:
        worst = sum(brochure_timeout(min(n, MAX_PAGES_PER_REQUEST)) for n in chunk_sizes)
        return self.clock() - self.started + worst <= TIME_BUDGET

    def _budget_text(self) -> str:
        return (
            f"request budget spent (today {self.budget.used_today}/{DAILY_REQUEST_LIMIT}, "
            f"this run {self.budget.used_this_run}/{self.run_limit})"
        )

    def _commit(self) -> bool:
        assert self.output is not None
        try:
            self.output.commit(self.published)
            return True
        except OutputError as exc:
            self.report.notes.append(f"output check failed: {_one_line(exc)}")
            return False

    def _save_state(self) -> None:
        if self.output is None:
            return
        self.state.quota_day = self.budget.day
        self.state.attempts = self.budget.used_today
        self.output.write_state(self.state.to_dict(self.now, MODEL, THINKING_LEVEL))


def _one_line(value: BaseException | str) -> str:
    text = " ".join(str(value).split())
    return (text if len(text) <= 300 else text[:299] + "…") or type(value).__name__


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


# --- command line ----------------------------------------------------------------------


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", type=Path, default=Path("scraper/out"), help="output folder of `scraper run`")
    parser.add_argument("--state-dir", type=Path, help="previous published output (default: --out)")
    parser.add_argument("--today", type=date.fromisoformat, help="pretend today is YYYY-MM-DD (Turkish date)")
    parser.add_argument(
        "--dry-run", action="store_true", help="print what would be read; no Gemini request, no download, no write"
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=RUN_REQUEST_LIMIT,
        help=f"lower the per-run request limit (at most {RUN_REQUEST_LIMIT})",
    )


def main(
    args: argparse.Namespace,
    *,
    reader: Reader | None = None,
    http: HttpClient | None = None,
    now: datetime | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    environ: dict[str, str] | None = None,
) -> int:
    """Run the step; the exit code is 0 whatever happens, so the job always goes on to publish."""
    env = os.environ if environ is None else environ
    key = (env.get(API_KEY_ENV) or "").strip()

    def scrub(text: str) -> str:
        return text.replace(key, "[redacted]") if key else text

    def log(message: str) -> None:
        print(scrub(message), flush=True)

    now = now or datetime.now(UTC).replace(microsecond=0)
    today = args.today or now.astimezone(TURKEY).date()
    own_client: GeminiClient | None = None
    if reader is None and key and not args.dry_run:
        own_client = GeminiClient(
            key, model=MODEL, thinking_level=THINKING_LEVEL, max_retries=0, sleep=sleep, clock=clock, log=log
        )
        reader = own_client
    step: OcrStep | None = None
    try:
        step = OcrStep(
            args.out,
            args.state_dir or args.out,
            now=now,
            today=today,
            reader=None if args.dry_run else reader,
            http=http,
            dry_run=args.dry_run,
            run_limit=max(0, args.max_requests),
            clock=clock,
            sleep=sleep,
            log=log,
        )
        report = step.execute()
    except Exception as exc:  # The step must never stop the job from publishing.
        message = f"OCR step aborted: {type(exc).__name__}: {exc}"
        if step is not None:
            message += "; " + step.recover()
        message = scrub(message)
        print(message, file=sys.stderr)
        _append_summary(f"## OCR\n\n- {message}\n")
        return 0
    finally:
        if own_client is not None:
            own_client.close()
        if step is not None and step.http is not None and http is None:
            step.http.close()

    if args.dry_run:
        report.notes.append(f"{API_KEY_ENV} is {'set' if key else 'not set'}")
    for line in format_lines(report):
        log(line)
    _append_summary(scrub(format_markdown(report)))
    return 0


def _header(report: OcrReport) -> str:
    mode = "dry run" if report.dry_run else ("disabled" if report.disabled else "live")
    return (
        f"OCR ({mode}, {MODEL}, thinking {THINKING_LEVEL}): {report.requests} request(s) this run, "
        f"{report.used_today}/{DAILY_REQUEST_LIMIT} on this quota day"
    )


def format_lines(report: OcrReport) -> list[str]:
    lines = [_header(report)]
    lines += [f"  {o.brochure_id}: {o.result}" + (f" - {o.detail}" if o.detail else "") for o in report.outcomes]
    lines += [f"note: {n}" for n in report.notes]
    return lines


def format_markdown(report: OcrReport) -> str:
    def cell(text: str) -> str:
        return text.replace("|", "\\|") or " "

    out = ["## OCR", "", _header(report), ""]
    if report.outcomes:
        out += ["| brochure | result | detail |", "|---|---|---|"]
        out += [f"| {cell(o.brochure_id)} | {cell(o.result)} | {cell(o.detail)} |" for o in report.outcomes]
        out.append("")
    out += [f"- {n}" for n in report.notes]
    return "\n".join(out) + "\n"


def _append_summary(text: str) -> None:
    path = os.environ.get(SUMMARY_ENV)
    if not path:
        return
    try:
        with Path(path).open("a", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as exc:
        print(f"could not write step summary: {exc}", file=sys.stderr)
