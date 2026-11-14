"""One scraper run: collect every source, merge with the previous output, publish atomically.

Rules (see PLAN.md, "Dayanıklılık kuralları"):
- each source runs in isolation; a failing source keeps its previous brochures and turns
  ``stale``, the others are published normally;
- an empty result is a failure, never "this chain has no brochures";
- nothing is published unless the whole output passes the schema and consistency checks,
  and every relative path in it points to a real file.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time
from pathlib import Path
from typing import Any

import httpx

from scraper.chains import ChainInfo
from scraper.core.http import HttpClient
from scraper.core.media import MEDIA_DIR, MediaWriter, is_local, local_paths
from scraper.core.models import (
    SCHEMA_VERSION,
    Brochure,
    Catalog,
    Chain,
    ChainKind,
    ChainStatus,
    HealthReport,
    ProductFile,
    SourceHealth,
    format_datetime,
)
from scraper.core.source import Source, SourceContext, SourceError, SourceResult, products_path
from scraper.core.validate import ContractError, validate_catalog, validate_health, validate_products

log = logging.getLogger(__name__)

MIN_APP_VERSION = 1
# The app shows the last four weeks; anything older is deleted with its files.
ARCHIVE_DAYS = 28
# Undated brochures cannot expire by date; they go once the source stops listing them.
UNDATED_MAX_AGE_DAYS = 35
# After this many failed runs in a row the job turns red so a human looks at the source.
FAILURE_ALERT_THRESHOLD = 3
MAX_ERROR_LENGTH = 300

PRODUCTS_DIR = "products"
CATALOG_FILE = "catalog.json"
HEALTH_FILE = "health.json"

EXIT_OK = 0
EXIT_NOT_WRITTEN = 1
EXIT_SOURCE_ALERT = 2


class OutputError(Exception):
    """The assembled output failed validation; nothing was published."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors[:5]) + (f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""))


# --- report ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SourceRun:
    chain_id: str
    ok: bool
    brochure_count: int
    new_count: int
    duration_ms: int
    error: str | None
    consecutive_failures: int
    warnings: tuple[str, ...] = ()


@dataclass(slots=True)
class RunReport:
    sources: list[SourceRun]
    new_brochure_ids: list[str]
    warnings: list[str]
    # True when the output passed every check (and, unless dry_run, replaced out_dir).
    output_ok: bool
    dry_run: bool
    # No previous catalog at all. ``new_brochure_ids`` never lists a chain's first-run
    # brochures (see ``backfill_first_seen``), so it is empty on such a run.
    first_run: bool
    output_error: str | None = None
    brochure_count: int = 0

    @property
    def written(self) -> bool:
        return self.output_ok and not self.dry_run

    @property
    def exit_code(self) -> int:
        if not self.output_ok:
            return EXIT_NOT_WRITTEN
        if any(s.consecutive_failures >= FAILURE_ALERT_THRESHOLD for s in self.sources):
            return EXIT_SOURCE_ALERT
        return EXIT_OK


# --- previous state --------------------------------------------------------------------


@dataclass(slots=True)
class PreviousState:
    root: Path | None
    catalog: Catalog | None = None
    health: dict[str, SourceHealth] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def brochures(self) -> tuple[Brochure, ...]:
        return self.catalog.brochures if self.catalog else ()

    def chain(self, chain_id: str) -> Chain | None:
        if self.catalog is None:
            return None
        return next((c for c in self.catalog.chains if c.id == chain_id), None)

    def products(self, brochure: Brochure) -> ProductFile | None:
        """Load the brochure's product file from the previous output, or None if unusable."""
        if self.root is None or brochure.products_url is None:
            return None
        try:
            data = json.loads((self.root / brochure.products_url).read_text(encoding="utf-8"))
            validate_products(data)
            products = ProductFile.from_dict(data)
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if products.brochure_id != brochure.id or len(products.products) != brochure.product_count:
            return None
        return products


def load_previous(state_dir: Path | None) -> PreviousState:
    """Read the previous catalog and health; a broken file is ignored with a warning."""
    if state_dir is None or not state_dir.is_dir():
        return PreviousState(root=None)
    state = PreviousState(root=state_dir)
    catalog_path = state_dir / CATALOG_FILE
    if catalog_path.is_file():
        try:
            data = json.loads(catalog_path.read_text(encoding="utf-8"))
            validate_catalog(data)
            state.catalog = Catalog.from_dict(data)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            state.warnings.append(f"previous {CATALOG_FILE} ignored: {_first_line(exc)}")
    health_path = state_dir / HEALTH_FILE
    if health_path.is_file():
        try:
            data = json.loads(health_path.read_text(encoding="utf-8"))
            validate_health(data)
            state.health = {s.chain_id: s for s in HealthReport.from_dict(data).sources}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            state.warnings.append(f"previous {HEALTH_FILE} ignored: {_first_line(exc)}")
    return state


# --- run -------------------------------------------------------------------------------


@dataclass(slots=True)
class _Entry:
    """A brochure headed for the output; ``fresh`` ones already have their files in staging."""

    brochure: Brochure
    products: ProductFile | None
    fresh: bool


def run(
    sources: Sequence[Source],
    chains: Sequence[ChainInfo],
    state_dir: Path | None,
    out_dir: Path,
    today: date,
    now: datetime,
    *,
    http: HttpClient | None = None,
    dry_run: bool = False,
    clock: Callable[[], float] = time.monotonic,
) -> RunReport:
    """Run ``sources`` and publish the merged result to ``out_dir`` (unless ``dry_run``)."""
    previous = load_previous(state_dir)
    out_dir = Path(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = out_dir.with_name(f"{out_dir.name}.staging-{uuid.uuid4().hex[:8]}")
    staging.mkdir()
    own_http = http is None
    client = http if http is not None else HttpClient()
    try:
        report = _Run(sources, chains, previous, staging, today, now, client, clock).execute()
        report.dry_run = dry_run
        if report.output_ok and not dry_run:
            _swap(staging, out_dir)
        return report
    finally:
        if own_http:
            client.close()
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


class _Run:
    def __init__(
        self,
        sources: Sequence[Source],
        chains: Sequence[ChainInfo],
        previous: PreviousState,
        staging: Path,
        today: date,
        now: datetime,
        http: HttpClient,
        clock: Callable[[], float],
    ) -> None:
        self.chains = sorted(chains, key=lambda c: (c.sort_order, c.id))
        self.previous = previous
        self.staging = staging
        self.today = today
        self.now = now
        self.http = http
        self.clock = clock
        self.media = MediaWriter(staging, previous.root)
        self.warnings: list[str] = list(previous.warnings)
        self.sources: dict[str, Source] = {}
        scraped = {c.id for c in chains if c.kind is ChainKind.SCRAPED}
        for source in sources:
            if source.chain_id in scraped:
                self.sources[source.chain_id] = source
            else:
                self.warnings.append(f"source {source.chain_id!r} skipped: not a scraped chain in the registry")

    def execute(self) -> RunReport:
        chain_records: list[Chain] = []
        health: list[SourceHealth] = []
        runs: list[SourceRun] = []
        entries: list[_Entry] = []
        visible: set[str] = set()
        fresh_ids: dict[str, list[str]] = {}

        for info in self.chains:
            if info.kind is ChainKind.WEBVIEW:
                chain_records.append(_chain(info, ChainStatus.OK, None))
                continue
            old = [b for b in self.previous.brochures if b.chain_id == info.id]
            source = self.sources.get(info.id)
            if source is None:
                # Not part of this run (e.g. --only): republish the previous state as it was.
                prev_chain = self.previous.chain(info.id)
                status = prev_chain.status if prev_chain else ChainStatus.STALE
                chain_records.append(_chain(info, status, prev_chain.last_ok_at if prev_chain else None))
                if info.id in self.previous.health:
                    health.append(self.previous.health[info.id])
                entries.extend(_Entry(b, None, fresh=False) for b in old)
                continue

            chain, source_health, run, chain_entries = self._run_source(info, source, old)
            chain_records.append(chain)
            health.append(source_health)
            runs.append(run)
            entries.extend(chain_entries)
            if run.ok:
                ids = [e.brochure.id for e in chain_entries if e.fresh]
                visible.update(ids)
                # A chain's first successful run fills in what is already out; that is not news.
                if old:
                    fresh_ids[info.id] = ids

        kept = self._prune(entries, visible)
        kept = self._carry_over(kept)
        known = {b.id for b in self.previous.brochures}
        kept_ids = {e.brochure.id for e in kept}
        new_ids = [i for ids in fresh_ids.values() for i in ids if i in kept_ids and i not in known]
        runs = [
            replace(r, new_count=sum(1 for i in fresh_ids.get(r.chain_id, ()) if i in new_ids)) for r in runs
        ]

        order = {c.id: (c.sort_order, c.id) for c in self.chains}
        kept.sort(key=lambda e: _brochure_sort_key(e.brochure, order))
        catalog = Catalog(
            generated_at=self.now,
            min_app_version=MIN_APP_VERSION,
            chains=chain_records,
            brochures=[e.brochure for e in kept],
        )
        report = HealthReport(generated_at=self.now, sources=health)
        products = {e.brochure.id: e.products for e in kept if e.products is not None}

        result = RunReport(
            sources=runs,
            new_brochure_ids=new_ids,
            warnings=self.warnings,
            output_ok=False,
            dry_run=False,
            first_run=self.previous.catalog is None,
            brochure_count=len(kept),
        )
        try:
            self._write(catalog, report, products)
            verify_output(self.staging)
        except OutputError as exc:
            result.output_error = str(exc)
            return result
        result.output_ok = True
        return result

    # -- one source ---------------------------------------------------------------------

    def _run_source(
        self, info: ChainInfo, source: Source, old: list[Brochure]
    ) -> tuple[Chain, SourceHealth, SourceRun, list[_Entry]]:
        prev_by_id = {b.id: b for b in old}
        ctx = SourceContext(
            http=self.http,
            today=self.today,
            now=self.now,
            media=self.media,
            previous=tuple(old),
            previous_products=lambda bid: self.previous.products(prev_by_id[bid]) if bid in prev_by_id else None,
        )
        started = self.clock()
        warnings: tuple[str, ...] = ()
        try:
            result = source.collect(ctx)
            warnings = tuple(result.warnings)
            check_source_result(_chain(info, ChainStatus.OK, self.now), result, self.media, self.now)
        except Exception as exc:  # Isolation: whatever one source does must not stop the run.
            error = short_error(exc)
            log.warning("source %s failed: %s", info.id, error)
            duration = _elapsed_ms(started, self.clock())
            self.media.discard_chain(info.id)
            prev_chain = self.previous.chain(info.id)
            prev_health = self.previous.health.get(info.id)
            last_ok = prev_chain.last_ok_at if prev_chain else (prev_health.last_ok_at if prev_health else None)
            failures = (prev_health.consecutive_failures if prev_health else 0) + 1
            return (
                _chain(info, ChainStatus.STALE, last_ok),
                SourceHealth(info.id, False, last_ok, error, failures, 0, duration),
                SourceRun(info.id, False, 0, 0, duration, error, failures, warnings),
                [_Entry(b, None, fresh=False) for b in old],
            )

        duration = _elapsed_ms(started, self.clock())
        entries: list[_Entry] = []
        returned: set[str] = set()
        chain_first_run = not old
        for brochure in result.brochures:
            products = result.product_files.get(brochure.id)
            before = prev_by_id.get(brochure.id)
            if before is None:
                seen = backfill_first_seen(brochure, self.today, self.now) if chain_first_run else self.now
                brochure = replace(brochure, first_seen=seen, updated_at=self.now)
            else:
                same = _content(before, self.previous.products(before)) == _content(brochure, products)
                brochure = replace(
                    brochure,
                    first_seen=before.first_seen,
                    updated_at=before.updated_at if same else self.now,
                )
            entries.append(_Entry(brochure, products, fresh=True))
            returned.add(brochure.id)
        # Brochures the site no longer lists stay as archive until they expire.
        entries.extend(_Entry(b, None, fresh=False) for b in old if b.id not in returned)
        count = len(result.brochures)
        return (
            _chain(info, ChainStatus.OK, self.now),
            SourceHealth(info.id, True, self.now, None, 0, count, duration),
            SourceRun(info.id, True, count, 0, duration, None, 0, warnings),
            entries,
        )

    # -- merge helpers ------------------------------------------------------------------

    def _prune(self, entries: list[_Entry], visible: set[str]) -> list[_Entry]:
        return [e for e in entries if not is_expired(e.brochure, visible, self.today, self.now)]

    def _carry_over(self, entries: list[_Entry]) -> list[_Entry]:
        """Copy files of brochures kept from the previous output; drop those whose files are gone."""
        out: list[_Entry] = []
        for entry in entries:
            if entry.fresh:
                out.append(entry)
                continue
            b = entry.brochure
            if not self.media.reuse(b):
                self.warnings.append(f"{b.id}: dropped, its media is missing from the previous output")
                continue
            products = None
            if b.products_url is not None:
                products = self.previous.products(b)
                if products is None:
                    self.warnings.append(f"{b.id}: dropped, its product file is missing or invalid")
                    continue
            out.append(_Entry(b, products, fresh=False))
        return out

    def _write(self, catalog: Catalog, health: HealthReport, products: dict[str, ProductFile]) -> None:
        _sweep_media(self.staging, catalog)
        write_json(self.staging / CATALOG_FILE, catalog.to_dict())
        write_json(self.staging / HEALTH_FILE, health.to_dict())
        for brochure in catalog.brochures:
            if brochure.products_url is not None:
                write_json(self.staging / brochure.products_url, products[brochure.id].to_dict())


# --- checks ----------------------------------------------------------------------------


def check_source_result(chain: Chain, result: SourceResult, media: MediaWriter, now: datetime) -> None:
    """Reject a source result that would break the contract, before it is merged."""
    if not result.brochures:
        raise SourceError("source returned no brochures (the page layout may have changed)")
    for b in result.brochures:
        if b.chain_id != chain.id:
            raise SourceError(f"brochure {b.id!r} belongs to chain {b.chain_id!r}, expected {chain.id!r}")
    # Checked as a one-chain catalog so ids, dates and kind rules use the published validator.
    document = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": format_datetime(now),
        "min_app_version": MIN_APP_VERSION,
        "chains": [chain.to_dict()],
        "brochures": [b.to_dict() for b in result.brochures],
    }
    try:
        validate_catalog(document)
    except ContractError as exc:
        raise SourceError("invalid brochure: " + "; ".join(exc.errors[:3])) from exc

    with_products = {b.id: b for b in result.brochures if b.products_url is not None}
    for extra in sorted(set(result.product_files) - set(with_products)):
        raise SourceError(f"product file for {extra!r} has no matching brochure with products_url")
    for b in with_products.values():
        if b.products_url != products_path(b.id):
            raise SourceError(f"{b.id}: products_url must be {products_path(b.id)!r}")
        products = result.product_files.get(b.id)
        if products is None:
            raise SourceError(f"{b.id}: products_url is set but no product file was returned")
        if products.brochure_id != b.id or len(products.products) != b.product_count:
            raise SourceError(f"{b.id}: product file does not match product_count {b.product_count}")
        try:
            validate_products(products.to_dict())
        except ContractError as exc:
            raise SourceError(f"{b.id}: invalid products: " + "; ".join(exc.errors[:3])) from exc
    for b in result.brochures:
        for rel in local_paths(b):
            if not media.exists(rel):
                raise SourceError(f"{b.id}: media file {rel} was not written")


def verify_output(root: Path) -> None:
    """Final gate before publishing: schemas, consistency and every referenced file."""
    errors: list[str] = []
    try:
        catalog = json.loads((root / CATALOG_FILE).read_text(encoding="utf-8"))
        validate_catalog(catalog)
        validate_health(json.loads((root / HEALTH_FILE).read_text(encoding="utf-8")))
    except ContractError as exc:
        raise OutputError([f"{exc.document}: {e}" for e in exc.errors]) from exc
    except (OSError, ValueError) as exc:
        raise OutputError([f"output cannot be read back: {_first_line(exc)}"]) from exc

    referenced: set[str] = set()
    for b in catalog["brochures"]:
        images = ([b["cover"]] if b["cover"] else []) + b["pages"]
        for image in images:
            if is_local(image["url"]) and not (root / image["url"]).is_file():
                errors.append(f"{b['id']}: missing file {image['url']}")
        if b["products_url"] is not None:
            referenced.add(b["products_url"])
            errors.extend(_check_product_file(root, b))
    for chain in catalog["chains"]:
        logo = chain.get("logo_url")
        if logo and is_local(logo) and not (root / logo).is_file():
            errors.append(f"chain {chain['id']}: missing logo {logo}")
    products_dir = root / PRODUCTS_DIR
    if products_dir.is_dir():
        for path in sorted(products_dir.iterdir()):
            rel = f"{PRODUCTS_DIR}/{path.name}"
            if rel not in referenced:
                errors.append(f"orphan product file {rel}")
    if errors:
        raise OutputError(errors)


def _check_product_file(root: Path, b: dict[str, Any]) -> list[str]:
    try:
        data = json.loads((root / b["products_url"]).read_text(encoding="utf-8"))
        validate_products(data)
    except ContractError as exc:
        return [f"{b['products_url']}: {e}" for e in exc.errors]
    except (OSError, ValueError) as exc:
        return [f"{b['products_url']}: {_first_line(exc)}"]
    if data["brochure_id"] != b["id"]:
        return [f"{b['products_url']}: brochure_id {data['brochure_id']!r} does not match {b['id']!r}"]
    if len(data["products"]) != b["product_count"]:
        return [f"{b['products_url']}: {len(data['products'])} products, catalog says {b['product_count']}"]
    return []


def backfill_first_seen(brochure: Brochure, today: date, now: datetime) -> datetime:
    """``first_seen`` for a brochure found on a chain's first run.

    The app marks brochures first seen in the last two days as "Yeni"; a newly added chain
    would otherwise show every brochure it already had out as new. A brochure that has
    already started counts as seen when it started (00:00 UTC that day, never after
    ``now``); one that has not started, or has no date, is seen now.
    """
    if brochure.valid_from is None or brochure.valid_from > today:
        return now
    return min(datetime.combine(brochure.valid_from, dt_time(0), tzinfo=UTC), now)


def is_expired(brochure: Brochure, visible: set[str], today: date, now: datetime) -> bool:
    if brochure.valid_to is not None:
        return (today - brochure.valid_to).days > ARCHIVE_DAYS
    if brochure.id in visible:
        return False
    return now - brochure.first_seen > timedelta(days=UNDATED_MAX_AGE_DAYS)


# --- small helpers ---------------------------------------------------------------------


def write_json(path: Path, data: Any) -> None:
    """Stable, diff-friendly JSON: fixed key order, two-space indent, LF line endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def short_error(exc: BaseException) -> str:
    """A one-line, human-readable reason for health.json (never a traceback)."""
    if isinstance(exc, SourceError):
        text = str(exc)
    elif isinstance(exc, httpx.TimeoutException):
        text = f"timeout: {exc}" if str(exc) else "timeout"
    elif isinstance(exc, httpx.HTTPError):
        text = f"network error ({type(exc).__name__}): {exc}"
    else:
        text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    text = " ".join(_first_line(text).split())
    return text if len(text) <= MAX_ERROR_LENGTH else text[: MAX_ERROR_LENGTH - 1] + "…"


def _first_line(value: object) -> str:
    text = str(value).strip()
    return text.splitlines()[0] if text else type(value).__name__


def _chain(info: ChainInfo, status: ChainStatus, last_ok_at: datetime | None) -> Chain:
    return Chain(
        id=info.id,
        name=info.name,
        country=info.country,
        kind=info.kind,
        web_url=info.web_url,
        status=status,
        last_ok_at=last_ok_at,
        sort_order=info.sort_order,
        brand_color=info.brand_color,
        logo_url=info.logo_url,
    )


def _content(brochure: Brochure, products: ProductFile | None) -> tuple[Any, ...]:
    """What counts as a change for ``updated_at``: everything except the timestamps."""
    data = brochure.to_dict()
    data.pop("first_seen")
    data.pop("updated_at")
    return (json.dumps(data, sort_keys=True), json.dumps(products.to_dict(), sort_keys=True) if products else None)


def _brochure_sort_key(b: Brochure, order: dict[str, tuple[int, str]]) -> tuple[Any, ...]:
    # Newest first within a chain; undated brochures after dated ones; id breaks ties.
    start = b.valid_from or b.valid_to
    return (order.get(b.chain_id, (1 << 30, b.chain_id)), start is None, -(start.toordinal() if start else 0), b.id)


def _elapsed_ms(started: float, ended: float) -> int:
    return max(0, round((ended - started) * 1000))


def _sweep_media(root: Path, catalog: Catalog) -> None:
    """Delete media nobody references (pruned brochures, failed sources, shrunk brochures)."""
    media_root = root / MEDIA_DIR
    if not media_root.is_dir():
        return
    wanted = {rel for b in catalog.brochures for rel in local_paths(b)}
    for path in sorted(media_root.rglob("*"), reverse=True):
        rel = path.relative_to(root).as_posix()
        if path.is_file() and rel not in wanted:
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    if not any(media_root.iterdir()):
        media_root.rmdir()


def _swap(staging: Path, out_dir: Path) -> None:
    """Replace ``out_dir`` with ``staging`` so readers never see a half-written folder."""
    backup = out_dir.with_name(f"{out_dir.name}.old-{uuid.uuid4().hex[:8]}")
    if out_dir.exists():
        os.replace(out_dir, backup)
    try:
        os.replace(staging, out_dir)
    except OSError:
        if backup.exists():
            os.replace(backup, out_dir)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def summary_rows(report: RunReport) -> Iterable[tuple[str, ...]]:
    for s in report.sources:
        yield (
            s.chain_id,
            "ok" if s.ok else f"FAILED ({s.consecutive_failures}x)",
            str(s.brochure_count),
            str(s.new_count),
            f"{s.duration_ms / 1000:.1f}s",
            s.error or "; ".join(s.warnings) or "",
        )
