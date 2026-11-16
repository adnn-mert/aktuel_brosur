"""Measure Gemini brochure OCR against a chain's own written price list.

    python -m scraper.ocr.evaluate --max-images 3 --out <folder outside the repo>
    python -m scraper.ocr.evaluate --batch brochure --max-brochures 8 [--thinking-level LOW]
    python -m scraper.ocr.evaluate --compare
    python -m scraper.ocr.evaluate --chain tkkoop --batch brochure --thinking-level LOW --dry-run

Every download and every Gemini answer is cached under ``--out``, so a second run with
the same options sends no requests at all. ``--batch poster`` (default) sends one request
per poster; ``--batch brochure`` sends all posters of a brochure in one request.
``--compare`` prints cached poster and brochure runs side by side and never touches the network.
``--dry-run`` prints how many brochures and Gemini requests a run would take, from the cache
only; ``--prefetch`` downloads the inputs (catalog, written list, page images) without Gemini.

Chains: ``bim`` (default) scores BİM posters against BİM's product list in our published
data; ``tkkoop`` scores Tarım Kredi's PDF pages against the product cards of the same
campaign on tkkoop.com.tr (see ``scraper.ocr.written``). Migros is not offered: its
Migroskop product cards and its full-page images are different pages of the viewer, so the
written list and the images do not show the same products.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from posixpath import splitext
from typing import Any
from urllib.parse import urljoin, urlsplit

from scraper.core.http import HttpClient
from scraper.ocr.gemini import (
    BROCHURE_PROMPT_VERSION,
    DEFAULT_MIN_INTERVAL,
    DEFAULT_MODEL,
    MAX_RETRIES,
    PROMPT_VERSION,
    GeminiClient,
    GeminiError,
    MissingApiKey,
    OcrResult,
    Usage,
    load_api_key,
    parse_brochure_response,
    parse_response,
)
from scraper.ocr.matching import DEFAULT_THRESHOLD
from scraper.ocr.metrics import BrochureResult, Poster, Summary, evaluate_brochure, summarize
from scraper.ocr.written import campaign_for_pdf, card_page_products, tkkoop_card_url
from scraper.sources.tkkoop import PAGE_TIMEOUT as TKKOOP_TIMEOUT
from scraper.sources.tkkoop import PAGE_URL as TKKOOP_HOME_URL

DEFAULT_BASE_URL = "https://adnn-mert.github.io/aktuel_brosur/"
DEFAULT_OUT = Path(tempfile.gettempdir()) / "aktuel_brosur_ocr"
CHAIN = "bim"
DEFAULT_POSTER_MAX_IMAGES = 3
DEFAULT_MAX_BROCHURES = 8
DEFAULT_MAX_PAGES_PER_REQUEST = 10
# BİM's discount brochures print kuruş; they are the hardest price test, so they are picked first.
PRIORITY_PREFIX = "bim-indirim-"
UNASSIGNED = "#unassigned"
_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})
_PNG_SIGNATURE = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])


@dataclass(frozen=True)
class ChainSpec:
    id: str
    name: str
    # Brochures whose id starts with this are read first (None: catalog order).
    priority_prefix: str | None
    modes: tuple[str, ...]


CHAINS: dict[str, ChainSpec] = {
    "bim": ChainSpec("bim", "BİM", PRIORITY_PREFIX, ("poster", "brochure")),
    # Only brochure mode: the poster prompt and its cache predate other chains and say "BİM".
    "tkkoop": ChainSpec("tkkoop", "Tarım Kredi", None, ("brochure",)),
}


def digest(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _has_written_list(brochure: dict[str, Any], chain: str) -> bool:
    if chain == "bim":
        return bool(brochure.get("products_url"))
    # Tarım Kredi brochures are rendered from the PDF the home page links next to the cards.
    return urlsplit(str(brochure.get("source_url") or "")).path.lower().endswith(".pdf")


def _eligible(catalog: dict[str, Any], chain: str = CHAIN) -> list[dict[str, Any]]:
    return [
        b
        for b in catalog.get("brochures", [])
        if b.get("chain_id") == chain and b.get("pages") and _has_written_list(b, chain)
    ]


def page_urls(brochure: dict[str, Any], base: str) -> list[str]:
    """Absolute page URLs; BİM's are absolute already, pages we render live under ``base``."""
    return [urljoin(base, p["url"]) for p in brochure["pages"]]


def image_suffix(url: str) -> str:
    """Cache file suffix; BİM posters keep ``.jpg`` so the existing image cache still matches."""
    suffix = splitext(urlsplit(url).path)[1].lower()
    return suffix if suffix in _IMAGE_SUFFIXES else ".jpg"


def image_mime(data: bytes) -> str:
    """MIME type from the file's own signature, so a WebP page is never sent as JPEG."""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:8] == _PNG_SIGNATURE:
        return "image/png"
    return "image/jpeg"


def select_brochures(catalog: dict[str, Any], max_images: int, chain: str = CHAIN) -> list[dict[str, Any]]:
    """Whole brochures only: brochure-level recall is meaningless if some posters were skipped."""
    chosen: list[dict[str, Any]] = []
    total = 0
    for b in _eligible(catalog, chain):
        n = len(b["pages"])
        if total + n > max_images:
            continue
        chosen.append(b)
        total += n
    return chosen


def select_brochures_for_batch(
    catalog: dict[str, Any], max_brochures: int, max_images: int | None = None, chain: str = CHAIN
) -> list[dict[str, Any]]:
    """Up to ``max_brochures`` whole brochures, the chain's priority ones (``bim-indirim-``) first."""
    ordered = _eligible(catalog, chain)
    prefix = CHAINS[chain].priority_prefix
    if prefix:
        ordered = [b for b in ordered if str(b.get("id", "")).startswith(prefix)] + [
            b for b in ordered if not str(b.get("id", "")).startswith(prefix)
        ]
    chosen: list[dict[str, Any]] = []
    total = 0
    for b in ordered:
        if len(chosen) >= max_brochures:
            break
        if max_images is not None and total + len(b["pages"]) > max_images:
            continue
        chosen.append(b)
        total += len(b["pages"])
    return chosen


def chunk_pages(items: Sequence[Any], max_per_request: int) -> list[list[Any]]:
    """Split in order into the fewest chunks of at most ``max_per_request``, sized evenly.

    Even sizes (11 pages -> 6 + 5, not 10 + 1) keep each request comparable in cost and avoid
    a lone page whose index and context the model would see in isolation.
    """
    if max_per_request < 1:
        raise ValueError("max_per_request must be at least 1")
    if not items:
        return []
    count = math.ceil(len(items) / max_per_request)
    size, extra = divmod(len(items), count)
    chunks: list[list[Any]] = []
    start = 0
    for i in range(count):
        end = start + size + (1 if i < extra else 0)
        chunks.append(list(items[start:end]))
        start = end
    return chunks


class Store:
    """Snapshot of the inputs plus the Gemini cache, all under one folder."""

    def __init__(self, root: Path, http: HttpClient | None, refresh: bool = False) -> None:
        self.root = root
        self.http = http
        self.refresh = refresh
        self.downloads = 0
        # A refresh re-downloads each URL once per run, not once per brochure that needs it
        # (every Tarım Kredi brochure reads the same home page).
        self._refreshed: set[str] = set()
        root.mkdir(parents=True, exist_ok=True)

    def _fetch(self, url: str, timeout: float | None = None) -> bytes:
        if self.http is None:
            raise RuntimeError(f"offline and not cached: {url}")
        response = self.http.get(url, timeout=timeout)
        self.downloads += 1
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code} for {url}")
        return response.content

    def path(self, url: str, sub: str, suffix: str) -> Path:
        return self.root / sub / f"{digest(url)}{suffix}"

    def cached_bytes(
        self, url: str, sub: str, suffix: str, refresh: bool = False, timeout: float | None = None
    ) -> bytes:
        path = self.path(url, sub, suffix)
        if path.exists() and not (refresh and url not in self._refreshed):
            return path.read_bytes()
        data = self._fetch(url, timeout)
        self._refreshed.add(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data

    def json(self, url: str, sub: str, refresh: bool = False) -> Any:
        return json.loads(self.cached_bytes(url, sub, ".json", refresh).decode("utf-8"))

    def text(self, url: str, sub: str, suffix: str, refresh: bool = False, timeout: float | None = None) -> str:
        return self.cached_bytes(url, sub, suffix, refresh, timeout).decode("utf-8")


def catalog_sub(chain: str) -> str:
    """BİM keeps the catalog snapshot it was measured with; other chains get their own.

    Refreshing the catalog for one chain must not swap the brochures another chain's cached
    answers belong to.
    """
    return "catalog" if chain == "bim" else f"catalog/{chain}"


def load_written(
    chain: str, brochure: dict[str, Any], store: Store, base: str, refresh: bool = False
) -> list[dict[str, Any]]:
    """The written product list ``brochure`` is scored against (see the module docstring)."""
    if chain == "bim":
        return store.json(base + brochure["products_url"], "products", refresh=refresh)["products"]
    home = store.text(TKKOOP_HOME_URL, "tkkoop", ".html", refresh, TKKOOP_TIMEOUT)
    campaign = campaign_for_pdf(home, brochure["source_url"])
    html = store.text(tkkoop_card_url(campaign.slug), "tkkoop", ".html", refresh, TKKOOP_TIMEOUT)
    return card_page_products(html, brochure)


def gemini_cache_path(root: Path, url: str, model: str, media_resolution: str | None, thinking: str | None) -> Path:
    # Every option that changes the answer is in the key, so runs with different settings never mix.
    # This key predates brochure mode and must not change, or the poster cache would be orphaned.
    key = f"{model}|{PROMPT_VERSION}|{media_resolution or '-'}|{(thinking or '-').upper()}"
    return root / "gemini" / digest(key, 8) / f"{digest(url)}.json"


def gemini_brochure_cache_path(
    root: Path,
    urls: Sequence[str],
    chunk_index: int,
    chunk_count: int,
    model: str,
    media_resolution: str | None,
    thinking: str | None,
    chain: str = CHAIN,
) -> Path:
    """Brochure answers live beside poster answers but can never collide with them.

    The folder key starts with the literal ``brochure`` and carries the brochure prompt
    version; the file name hashes the exact image list and the chunk position, so changing
    ``--max-pages-per-request`` (a different split) reads and writes different files. Other
    chains use another prompt, so their folder key names the chain; BİM's key is unchanged.
    """
    kind = "brochure" if chain == "bim" else f"brochure:{chain}"
    key = f"{kind}|{model}|{BROCHURE_PROMPT_VERSION}|{media_resolution or '-'}|{(thinking or '-').upper()}"
    name = digest(f"{chunk_index}/{chunk_count}|" + "\n".join(urls))
    return root / "gemini" / digest(key, 8) / f"{name}.json"


def read_poster(
    url: str,
    store: Store,
    gemini: GeminiClient | None,
    cache_path: Path,
) -> tuple[OcrResult, bool, float | None]:
    """Return the OCR result, whether a live Gemini request was made, and its latency if known."""
    if cache_path.exists():
        body = json.loads(cache_path.read_text(encoding="utf-8"))
        return parse_response(body["response"]), False, body.get("elapsed_s")
    if gemini is None:
        raise GeminiError(f"not cached and no Gemini client: {url}")
    image = store.cached_bytes(url, "images", ".jpg")
    result, raw = gemini.read_poster(image, "image/jpeg")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "image_url": url,
                "model": gemini.model,
                "thinking_level": gemini.thinking_level,
                "elapsed_s": gemini.last_elapsed,
                "response": raw,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return result, True, gemini.last_elapsed


def read_brochure_chunk(
    urls: Sequence[str],
    store: Store,
    gemini: GeminiClient | None,
    cache_path: Path,
    chain: str = CHAIN,
) -> tuple[OcrResult, bool, float | None]:
    """Like ``read_poster`` for several images in one request; ``page_index`` is relative to ``urls``."""
    if cache_path.exists():
        body = json.loads(cache_path.read_text(encoding="utf-8"))
        return parse_brochure_response(body["response"], len(urls)), False, body.get("elapsed_s")
    if gemini is None:
        raise GeminiError(f"not cached and no Gemini client: {urls[0]} (+{len(urls) - 1} more)")
    images = [store.cached_bytes(u, "images", image_suffix(u)) for u in urls]
    result, raw = gemini.read_brochure(images, image_mime(images[0]), chain=chain)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "image_urls": list(urls),
                "chain": chain,
                "model": gemini.model,
                "thinking_level": gemini.thinking_level,
                "elapsed_s": gemini.last_elapsed,
                "response": raw,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return result, True, gemini.last_elapsed


def posters_from_chunk(urls: Sequence[str], products: Sequence[dict[str, Any]]) -> list[Poster]:
    """One Poster per image, filled by ``page_index``; products with no valid index go to an extra Poster."""
    by_page: list[list[dict[str, Any]]] = [[] for _ in urls]
    stray: list[dict[str, Any]] = []
    for item in products:
        index = item.get("page_index")
        if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(urls):
            by_page[index].append(item)
        else:
            stray.append(item)
    posters = [Poster(url=u, products=items) for u, items in zip(urls, by_page, strict=True)]
    if stray:
        posters.append(Poster(url=urls[0] + UNASSIGNED, products=stray))
    return posters


def _add_usage(a: Usage, b: Usage) -> Usage:
    return Usage(
        a.prompt_tokens + b.prompt_tokens,
        a.output_tokens + b.output_tokens,
        a.thought_tokens + b.thought_tokens,
    )


@dataclass
class Run:
    """Everything one configuration (mode and thinking level) produced."""

    mode: str
    thinking_level: str | None
    results: list[BrochureResult] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    latencies: list[float] = field(default_factory=list)
    # Requests the evaluated answers stand for (cached ones included), not live traffic.
    reads: int = 0
    failures: list[str] = field(default_factory=list)
    unassigned_products: int = 0

    @property
    def label(self) -> str:
        return f"{self.mode}/{self.thinking_level or 'default'}"


def run_brochures(
    brochures: Sequence[dict[str, Any]],
    *,
    mode: str,
    base: str,
    out: Path,
    store: Store,
    gemini: GeminiClient | None,
    model: str,
    media_resolution: str | None,
    thinking_level: str | None,
    threshold: float,
    max_pages: int,
    refresh: bool = False,
    log: Any = print,
    chain: str = CHAIN,
) -> Run:
    run = Run(mode=mode, thinking_level=thinking_level)
    for b in brochures:
        posters: list[Poster] = []
        # Counted only when the whole brochure was read, so a skipped brochure cannot inflate
        # the request, token and cost figures that the match rates are compared against.
        part = Run(mode=mode, thinking_level=thinking_level)
        try:
            written = load_written(chain, b, store, base, refresh)
            if mode == "poster":
                for page in b["pages"]:
                    path = gemini_cache_path(out, page["url"], model, media_resolution, thinking_level)
                    result, live, elapsed = read_poster(page["url"], store, gemini, path)
                    _record(part, result, live, elapsed, log, b["id"], page["url"])
                    posters.append(Poster(url=page["url"], products=result.products))
            else:
                urls = page_urls(b, base)
                chunks = chunk_pages(urls, max_pages)
                for index, chunk in enumerate(chunks):
                    path = gemini_brochure_cache_path(
                        out, chunk, index, len(chunks), model, media_resolution, thinking_level, chain
                    )
                    result, live, elapsed = read_brochure_chunk(chunk, store, gemini, path, chain)
                    _record(part, result, live, elapsed, log, b["id"], f"chunk {index + 1}/{len(chunks)}")
                    posters.extend(posters_from_chunk(chunk, result.products))
        except (GeminiError, RuntimeError) as exc:
            run.failures.append(f"{b['id']}: {exc}")
            log(f"skip {b['id']}: {exc}", file=sys.stderr)
            continue
        run.reads += part.reads
        run.latencies.extend(part.latencies)
        run.usage = _add_usage(run.usage, part.usage)
        run.unassigned_products += sum(len(p.products) for p in posters if p.url.endswith(UNASSIGNED))
        result = evaluate_brochure(b["id"], written, posters, threshold)
        # The catch-all poster is bookkeeping, not a page: keep it out of the poster counts.
        result.poster_recall = [pr for pr in result.poster_recall if not pr[0].endswith(UNASSIGNED)]
        run.results.append(result)
    return run


@dataclass(frozen=True)
class PlannedBrochure:
    brochure_id: str
    pages: int
    requests: int
    cached: int
    images_cached: int
    written: str

    @property
    def to_send(self) -> int:
        return self.requests - self.cached


def _request_cache_paths(
    b: dict[str, Any], *, chain: str, mode: str, base: str, out: Path, model: str,
    media_resolution: str | None, thinking_level: str | None, max_pages: int,
) -> tuple[list[str], list[Path]]:
    """Image URLs and the Gemini cache file of every request ``run_brochures`` would make."""
    if mode == "poster":
        urls = [page["url"] for page in b["pages"]]
        return urls, [gemini_cache_path(out, u, model, media_resolution, thinking_level) for u in urls]
    urls = page_urls(b, base)
    chunks = chunk_pages(urls, max_pages)
    paths = [
        gemini_brochure_cache_path(out, c, i, len(chunks), model, media_resolution, thinking_level, chain)
        for i, c in enumerate(chunks)
    ]
    return urls, paths


def plan_brochures(
    brochures: Sequence[dict[str, Any]],
    *,
    chain: str,
    mode: str,
    base: str,
    out: Path,
    model: str,
    media_resolution: str | None,
    thinking_level: str | None,
    max_pages: int,
) -> list[PlannedBrochure]:
    """What a run would send, read from the cache alone: this never opens a connection."""
    store = Store(out / "data", None)
    planned: list[PlannedBrochure] = []
    for b in brochures:
        urls, paths = _request_cache_paths(
            b, chain=chain, mode=mode, base=base, out=out, model=model,
            media_resolution=media_resolution, thinking_level=thinking_level, max_pages=max_pages,
        )
        try:
            written = f"written list cached ({len(load_written(chain, b, store, base))} products)"
        except RuntimeError as exc:
            written = f"written list not ready ({exc})"
        planned.append(
            PlannedBrochure(
                brochure_id=b["id"],
                pages=len(urls),
                requests=len(paths),
                cached=sum(1 for path in paths if path.exists()),
                images_cached=sum(1 for u in urls if store.path(u, "images", image_suffix(u)).exists()),
                written=written,
            )
        )
    return planned


def render_plan(
    planned: Sequence[PlannedBrochure],
    *,
    chain: str,
    mode: str,
    model: str,
    thinking_level: str | None,
    max_pages: int,
    max_retries: int,
) -> str:
    to_send = sum(p.to_send for p in planned)
    split = f", up to {max_pages} pages per request" if mode == "brochure" else ""
    lines = [
        f"plan (nothing sent): chain {chain}, mode {mode}{split}, model {model}, "
        f"thinking level {thinking_level or 'model default'}",
        "",
    ]
    for p in planned:
        lines.append(
            f"  {p.brochure_id}: {p.pages} pages -> {p.requests} request(s), {p.cached} cached; "
            f"images cached {p.images_cached}/{p.pages}; {p.written}"
        )
    lines += [
        "",
        f"total: {len(planned)} brochures, {sum(p.pages for p in planned)} pages, "
        f"{to_send} Gemini request(s) to send ({sum(p.cached for p in planned)} already cached)",
        f"each request may be retried up to {max_retries} times on HTTP 429/5xx (brochure requests at most once "
        "after a timeout); the free tier counts every attempt",
    ]
    return "\n".join(lines) + "\n"


def prefetch_inputs(
    brochures: Sequence[dict[str, Any]],
    *,
    chain: str,
    mode: str,
    base: str,
    store: Store,
    refresh: bool,
    log: Any = print,
) -> list[str]:
    """Download the written list and page images of each brochure; never calls Gemini.

    Tarım Kredi's card pages change with each campaign, so snapshotting them on the day the
    brochure is valid keeps the truth matched to the pages even if Gemini is read later.
    """
    failures: list[str] = []
    for b in brochures:
        try:
            written = load_written(chain, b, store, base, refresh)
            urls = page_urls(b, base) if mode == "brochure" else [page["url"] for page in b["pages"]]
            for url in urls:
                store.cached_bytes(url, "images", image_suffix(url))
        except RuntimeError as exc:
            failures.append(f"{b['id']}: {exc}")
            log(f"skip {b['id']}: {exc}", file=sys.stderr)
            continue
        log(f"inputs {b['id']}: {len(written)} written products, {len(urls)} images", flush=True)
    return failures


def _record(run: Run, result: OcrResult, live: bool, elapsed: float | None, log: Any, brochure_id: str, what: str) -> None:
    run.reads += 1
    if elapsed is not None:
        run.latencies.append(elapsed)
    run.usage = _add_usage(run.usage, result.usage)
    log(f"{'live ' if live else 'cache'} {brochure_id} {what} -> {len(result.products)} products", flush=True)


def _price(minor: int | None) -> str:
    if minor is None:
        return "-"
    return f"{minor // 100},{minor % 100:02d}"


def render_text(
    summary: Summary,
    results: Sequence[BrochureResult],
    usage: Usage,
    live: int,
    model: str,
    thinking_level: str | None = None,
    latencies: Sequence[float] = (),
    *,
    mode: str = "poster",
    requests: int | None = None,
    max_pages: int | None = None,
    unassigned: int | None = None,
    chain: str = CHAIN,
) -> str:
    posters = max(summary.posters, 1)
    unit = "poster" if mode == "poster" else "brochure request"
    latency = f"{sum(latencies) / len(latencies):.1f}s over {len(latencies)}" if latencies else "n/a (not recorded)"
    requests = requests if requests is not None else summary.posters
    mode_line = f"mode: {mode}" + (f" (up to {max_pages} pages per request)" if mode == "brochure" else "")
    lines = [
        f"chain: {chain}",
        f"model: {model}  thinking level: {thinking_level or 'model default'}",
        mode_line,
        f"requests behind these results (cached included): {requests}",
        f"mean request latency per {unit}: {latency}",
        f"brochures: {summary.brochures}  posters: {summary.posters}",
        f"live Gemini requests this run (incl. retries): {live}",
        f"tokens (all evaluated posters): in {usage.prompt_tokens}, out {usage.output_tokens}, "
        f"thinking {usage.thought_tokens}; paid-tier cost estimate ${usage.cost_usd:.4f} "
        f"(${usage.cost_usd / posters:.4f} per poster, ${usage.cost_usd / max(requests, 1):.4f} per request)",
    ]
    if unassigned is not None:
        lines.append(f"OCR products without a valid page_index: {unassigned}")
    lines += [
        "",
        f"(a) product match rate, brochure level: {summary.matched}/{summary.written_expected} "
        f"= {summary.match_rate:.1%}",
        "    poster level (inferred groups, heuristic): "
        + (
            f"{summary.poster_matched}/{summary.poster_expected} = {summary.poster_match_rate:.1%}"
            if summary.poster_expected
            else "n/a (card image names carry no poster number)"
        ),
        f"(b) price accuracy on matches: {summary.price_correct}/{summary.matched} = {summary.price_accuracy:.2%}",
        f"(c) OCR products without a written counterpart: {summary.ocr_extra} of {summary.ocr_products}",
        f"    OCR products without a parseable price: {summary.ocr_without_price}",
        f"error kinds: {summary.error_kinds}",
        "",
        "per brochure (written / ocr / matched / price ok):",
    ]
    for r in results:
        ok = sum(1 for p in r.pairs if p.correct)
        lines.append(f"  {r.brochure_id}: {r.written_count} / {r.ocr_count} / {len(r.pairs)} / {ok}")
    errors = [p for r in results for p in r.pairs if not p.correct]
    lines += ["", f"price errors ({len(errors)}):"]
    for p in errors:
        lines.append(
            f"  [{p.error_kind}] OCR '{p.ocr_name}' {p.ocr_price_text!r} -> {_price(p.ocr_price_minor)} | "
            f"written '{p.written_name}' {_price(p.true_price_minor)}"
            f" (old {_price(p.true_old_price_minor)}) | score {p.score:.2f} | {p.image_url}"
        )
    lines += ["", "OCR products with no written counterpart:"]
    for r in results:
        for item in r.unmatched_ocr:
            lines.append(f"  {r.brochure_id}: '{item.get('name')}' {item.get('price')!r}")
    lines += ["", "written products not found by OCR:"]
    for r in results:
        for w in r.unmatched_written:
            lines.append(f"  {r.brochure_id}: '{w.get('name')}' {_price(w.get('price_minor'))}")
    return "\n".join(lines) + "\n"


def render_comparison(runs: Sequence[Run], brochure_ids: Sequence[str]) -> str:
    """Side-by-side table of cached runs; a dash means that run has no complete answer for the brochure."""
    by_run = [{r.brochure_id: r for r in run.results} for run in runs]
    labels = [run.label for run in runs]
    id_width = max([len(i) for i in brochure_ids] + [len("brochure")])
    width = max([len(label) for label in labels] + [13])

    def row(first: str, cells: Sequence[str]) -> str:
        return f"{first:<{id_width}}  " + "  ".join(f"{c:>{width}}" for c in cells)

    lines = [
        "comparison from cached answers (no network)",
        "cell = matched/written  price-correct/matched; '-' = not cached for this run",
        "",
        row("brochure", labels),
    ]
    for bid in brochure_ids:
        cells = []
        for lookup in by_run:
            r = lookup.get(bid)
            cells.append("-" if r is None else f"{len(r.pairs)}/{r.written_count} {sum(1 for p in r.pairs if p.correct)}/{len(r.pairs)}")
        lines.append(row(bid, cells))

    def totals(title: str, ids: set[str] | None) -> None:
        lines.extend(["", title])
        for run in runs:
            chosen = [r for r in run.results if ids is None or r.brochure_id in ids]
            if not chosen:
                lines.append(f"  {run.label}: no brochures")
                continue
            s = summarize(chosen)
            lines.append(
                f"  {run.label}: brochures {s.brochures}, match {s.matched}/{s.written_expected} = {s.match_rate:.1%}, "
                f"price {s.price_correct}/{s.matched} = {s.price_accuracy:.2%}"
            )

    totals("totals over every brochure each run has", None)
    common = set.intersection(*(set(lookup) for lookup in by_run)) if by_run else set()
    if common and any(set(lookup) != common for lookup in by_run):
        totals(f"totals over the {len(common)} brochure(s) every run has (like for like)", common)

    lines += ["", "cost and speed (all brochures each run has):"]
    for run in runs:
        mean = f"{sum(run.latencies) / len(run.latencies):.1f}s" if run.latencies else "n/a"
        lines.append(
            f"  {run.label}: requests {run.reads}, mean latency {mean}, tokens in {run.usage.prompt_tokens} "
            f"out {run.usage.output_tokens} thinking {run.usage.thought_tokens}, cost ${run.usage.cost_usd:.4f}"
        )
    return "\n".join(lines) + "\n"


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def _non_negative_int(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def parse_levels(text: str) -> list[str | None]:
    """``"-,LOW"`` -> ``[None, "LOW"]``; ``-`` is the model's own default level."""
    levels = [part.strip().upper() for part in text.split(",") if part.strip()]
    return [None if level == "-" else level for level in levels]


def report_stem(chain: str, mode: str, thinking_level: str | None) -> str:
    """Report file name without extension; one file per chain, mode and thinking level.

    BİM keeps the names its earlier reports were written under.
    """
    if mode == "poster":
        return "report" if chain == "bim" else f"report_{chain}"
    level = (thinking_level or "default").lower()
    return f"report_brochure_{level}" if chain == "bim" else f"report_{chain}_brochure_{level}"


def compare_name(chain: str) -> str:
    return "compare.txt" if chain == "bim" else f"compare_{chain}.txt"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scraper.ocr.evaluate", description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--chain",
        choices=sorted(CHAINS),
        default=CHAIN,
        help="whose brochures and written list to use (default bim; tkkoop needs --batch brochure)",
    )
    p.add_argument(
        "--batch",
        choices=("poster", "brochure"),
        default="poster",
        help="poster: one request per poster (default). brochure: one request per brochure (or chunk of it)",
    )
    p.add_argument(
        "--max-images",
        type=int,
        default=None,
        help=f"upper bound on posters, whole brochures only (poster mode default {DEFAULT_POSTER_MAX_IMAGES}; "
        "in brochure mode only applied when given)",
    )
    p.add_argument(
        "--max-brochures",
        type=_positive_int,
        default=DEFAULT_MAX_BROCHURES,
        help=f"brochure/compare mode: how many brochures to read, bim-indirim first (default {DEFAULT_MAX_BROCHURES})",
    )
    p.add_argument(
        "--max-pages-per-request",
        type=_positive_int,
        default=DEFAULT_MAX_PAGES_PER_REQUEST,
        help=f"brochure mode: split brochures with more pages into sequential requests (default {DEFAULT_MAX_PAGES_PER_REQUEST})",
    )
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"cache and report folder (default {DEFAULT_OUT})")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, help="published data root holding catalog.json")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--media-resolution", default=None, help="e.g. MEDIA_RESOLUTION_HIGH (default: model default)")
    p.add_argument(
        "--thinking-level",
        type=str.upper,
        default=None,
        help="LOW, MEDIUM or HIGH for gemini-3.8-flash (default: the model's own, MEDIUM)",
    )
    p.add_argument("--interval", type=float, default=DEFAULT_MIN_INTERVAL, help="seconds between Gemini requests")
    p.add_argument(
        "--max-retries",
        type=_non_negative_int,
        default=MAX_RETRIES,
        help=f"Gemini retries per request on HTTP 429/5xx (default {MAX_RETRIES}); every attempt uses quota",
    )
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="name similarity needed to pair")
    p.add_argument(
        "--refresh-catalog", action="store_true", help="re-download catalog.json and the written product lists"
    )
    p.add_argument("--offline", action="store_true", help="use only cached data; never touch the network")
    only = p.add_mutually_exclusive_group()
    only.add_argument(
        "--compare",
        action="store_true",
        help="print cached poster and brochure runs side by side (implies --offline; no Gemini, no downloads)",
    )
    only.add_argument(
        "--dry-run",
        action="store_true",
        help="print how many brochures and Gemini requests the run would take, from the cache only "
        "(implies --offline; no Gemini, no downloads)",
    )
    only.add_argument(
        "--prefetch",
        action="store_true",
        help="download the catalog, written lists and page images of the selected brochures, then print "
        "the plan; never calls Gemini",
    )
    p.add_argument(
        "--compare-levels",
        type=parse_levels,
        default=[None, "LOW"],
        help="thinking levels to compare, comma separated; '-' is the model default (default '-,LOW')",
    )
    return p


def _log(msg: str, file: Any = None, flush: bool = False) -> None:
    print(msg, file=file or sys.stdout, flush=flush)


def _compare(args: argparse.Namespace, store: Store, base: str, catalog: dict[str, Any]) -> int:
    spec = CHAINS[args.chain]
    brochures = select_brochures_for_batch(catalog, args.max_brochures, args.max_images, args.chain)
    if not brochures:
        print(f"no {spec.name} brochure with both pages and a written list", file=sys.stderr)
        return 1
    runs = [
        run_brochures(
            brochures,
            mode=mode,
            base=base,
            out=args.out,
            store=store,
            gemini=None,
            model=args.model,
            media_resolution=args.media_resolution,
            thinking_level=level,
            threshold=args.threshold,
            max_pages=args.max_pages_per_request,
            log=lambda *_a, **_k: None,
            chain=args.chain,
        )
        for level in args.compare_levels
        for mode in spec.modes
    ]
    if not any(run.results for run in runs):
        print("no cached results for any run", file=sys.stderr)
        return 1
    text = render_comparison(runs, [b["id"] for b in brochures])
    path = args.out / compare_name(args.chain)
    path.write_text(text, encoding="utf-8")
    print(text)
    print(f"report: {path}")
    return 0


def _select(args: argparse.Namespace, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    if args.batch == "brochure":
        return select_brochures_for_batch(catalog, args.max_brochures, args.max_images, args.chain)
    limit = DEFAULT_POSTER_MAX_IMAGES if args.max_images is None else args.max_images
    return select_brochures(catalog, limit, args.chain)


def _plan_text(args: argparse.Namespace, brochures: Sequence[dict[str, Any]], base: str) -> str:
    planned = plan_brochures(
        brochures,
        chain=args.chain,
        mode=args.batch,
        base=base,
        out=args.out,
        model=args.model,
        media_resolution=args.media_resolution,
        thinking_level=args.thinking_level,
        max_pages=args.max_pages_per_request,
    )
    return render_plan(
        planned,
        chain=args.chain,
        mode=args.batch,
        model=args.model,
        thinking_level=args.thinking_level,
        max_pages=args.max_pages_per_request,
        max_retries=args.max_retries,
    )


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    spec = CHAINS[args.chain]
    if not args.compare and args.batch not in spec.modes:
        parser.error(f"--chain {args.chain} supports --batch {' or '.join(spec.modes)} only")
    if args.prefetch and args.offline:
        parser.error("--prefetch downloads inputs and cannot be combined with --offline")
    out: Path = args.out
    offline = args.offline or args.compare or args.dry_run
    http = None if offline else HttpClient()
    gemini: GeminiClient | None = None
    try:
        store = Store(out / "data", http)
        base = args.base_url.rstrip("/") + "/"
        catalog_url = base + "catalog.json"
        sub = catalog_sub(args.chain)
        if offline and not store.path(catalog_url, sub, ".json").exists():
            print(
                f"catalog for {args.chain} is not cached under {out}; run once with --prefetch "
                "(downloads inputs only, no Gemini)",
                file=sys.stderr,
            )
            return 1
        catalog = store.json(catalog_url, sub, refresh=args.refresh_catalog and not offline)
        if args.compare:
            return _compare(args, store, base, catalog)
        brochures = _select(args, catalog)
        if not brochures:
            print(
                f"no {spec.name} brochure with both pages and a written list fits the selection limits",
                file=sys.stderr,
            )
            return 1
        if args.dry_run:
            print(_plan_text(args, brochures, base))
            return 0
        if args.prefetch:
            failures = prefetch_inputs(
                brochures, chain=args.chain, mode=args.batch, base=base, store=store,
                refresh=args.refresh_catalog, log=_log,
            )
            print()
            print(_plan_text(args, brochures, base))
            return 1 if failures else 0
        if not offline:
            try:
                key = load_api_key()
            except MissingApiKey as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            gemini = GeminiClient(
                key,
                model=args.model,
                min_interval=args.interval,
                max_retries=args.max_retries,
                media_resolution=args.media_resolution,
                thinking_level=args.thinking_level,
                log=lambda msg: print(msg, file=sys.stderr, flush=True),
            )
            del key

        run = run_brochures(
            brochures,
            mode=args.batch,
            base=base,
            out=out,
            store=store,
            gemini=gemini,
            model=args.model,
            media_resolution=args.media_resolution,
            thinking_level=args.thinking_level,
            threshold=args.threshold,
            max_pages=args.max_pages_per_request,
            refresh=args.refresh_catalog,
            log=_log,
            chain=args.chain,
        )
        if not run.results:
            print("nothing evaluated", file=sys.stderr)
            return 1
        summary = summarize(run.results)
        live = gemini.requests_sent if gemini else 0
        brochure_mode = args.batch == "brochure"
        text = render_text(
            summary,
            run.results,
            run.usage,
            live,
            args.model,
            args.thinking_level,
            run.latencies,
            mode=args.batch,
            requests=run.reads,
            max_pages=args.max_pages_per_request if brochure_mode else None,
            unassigned=run.unassigned_products if brochure_mode else None,
            chain=args.chain,
        )
        if run.failures:
            text += "\nskipped brochures:\n" + "\n".join(f"  {f}" for f in run.failures) + "\n"
        prompt_version = BROCHURE_PROMPT_VERSION if brochure_mode else PROMPT_VERSION
        report = {
            "chain": args.chain,
            "model": args.model,
            "prompt_version": prompt_version if args.chain == "bim" else f"{prompt_version}:{args.chain}",
            "mode": args.batch,
            "options": {
                "media_resolution": args.media_resolution,
                "thinking_level": args.thinking_level,
                "threshold": args.threshold,
                "max_pages_per_request": args.max_pages_per_request if brochure_mode else None,
            },
            "summary": asdict(summary)
            | {
                "match_rate": summary.match_rate,
                "price_accuracy": summary.price_accuracy,
                "poster_match_rate": summary.poster_match_rate,
            },
            "usage": asdict(run.usage) | {"cost_usd_paid_tier": run.usage.cost_usd},
            "latencies_s": run.latencies,
            "requests_evaluated": run.reads,
            "live_requests": live,
            "downloads": store.downloads,
            "unassigned_products": run.unassigned_products,
            "failures": run.failures,
            "pairs": [asdict(p) for r in run.results for p in r.pairs],
            "unmatched_ocr": {r.brochure_id: r.unmatched_ocr for r in run.results},
            "unmatched_written": {r.brochure_id: [w.get("name") for w in r.unmatched_written] for r in run.results},
        }
        # One file per chain, mode and thinking level, so a later run never overwrites another.
        stem = report_stem(args.chain, args.batch, args.thinking_level)
        (out / f"{stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / f"{stem}.txt").write_text(text, encoding="utf-8")
        print()
        print(text)
        print(f"report: {out / f'{stem}.txt'}")
        return 0
    finally:
        if gemini is not None:
            gemini.close()
        if http is not None:
            http.close()


if __name__ == "__main__":
    raise SystemExit(main())
