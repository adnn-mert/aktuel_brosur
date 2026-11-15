"""Measure Gemini poster OCR against BİM's written product list.

    python -m scraper.ocr.evaluate --max-images 3 --out <folder outside the repo>

Every download and every Gemini answer is cached under ``--out``, so a second run with
the same options sends no requests at all.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scraper.core.http import HttpClient
from scraper.ocr.gemini import (
    DEFAULT_MIN_INTERVAL,
    DEFAULT_MODEL,
    PROMPT_VERSION,
    GeminiClient,
    GeminiError,
    MissingApiKey,
    OcrResult,
    Usage,
    load_api_key,
    parse_response,
)
from scraper.ocr.matching import DEFAULT_THRESHOLD
from scraper.ocr.metrics import BrochureResult, Poster, Summary, evaluate_brochure, summarize

DEFAULT_BASE_URL = "https://adnn-mert.github.io/aktuel_brosur/"
DEFAULT_OUT = Path(tempfile.gettempdir()) / "aktuel_brosur_ocr"
CHAIN = "bim"


def digest(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def select_brochures(catalog: dict[str, Any], max_images: int) -> list[dict[str, Any]]:
    """Whole brochures only: brochure-level recall is meaningless if some posters were skipped."""
    chosen: list[dict[str, Any]] = []
    total = 0
    for b in catalog.get("brochures", []):
        if b.get("chain_id") != CHAIN or not b.get("pages") or not b.get("products_url"):
            continue
        n = len(b["pages"])
        if total + n > max_images:
            continue
        chosen.append(b)
        total += n
    return chosen


class Store:
    """Snapshot of the inputs plus the Gemini cache, all under one folder."""

    def __init__(self, root: Path, http: HttpClient | None, refresh: bool = False) -> None:
        self.root = root
        self.http = http
        self.refresh = refresh
        self.downloads = 0
        root.mkdir(parents=True, exist_ok=True)

    def _fetch(self, url: str) -> bytes:
        if self.http is None:
            raise RuntimeError(f"offline and not cached: {url}")
        response = self.http.get(url)
        self.downloads += 1
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code} for {url}")
        return response.content

    def cached_bytes(self, url: str, sub: str, suffix: str, refresh: bool = False) -> bytes:
        path = self.root / sub / f"{digest(url)}{suffix}"
        if path.exists() and not refresh:
            return path.read_bytes()
        data = self._fetch(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data

    def json(self, url: str, sub: str, refresh: bool = False) -> Any:
        return json.loads(self.cached_bytes(url, sub, ".json", refresh).decode("utf-8"))


def gemini_cache_path(root: Path, url: str, model: str, media_resolution: str | None, thinking: str | None) -> Path:
    # Every option that changes the answer is in the key, so runs with different settings never mix.
    key = f"{model}|{PROMPT_VERSION}|{media_resolution or '-'}|{(thinking or '-').upper()}"
    return root / "gemini" / digest(key, 8) / f"{digest(url)}.json"


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
) -> str:
    posters = max(summary.posters, 1)
    latency = f"{sum(latencies) / len(latencies):.1f}s over {len(latencies)}" if latencies else "n/a (not recorded)"
    lines = [
        f"model: {model}  thinking level: {thinking_level or 'model default'}",
        f"mean request latency per poster: {latency}",
        f"brochures: {summary.brochures}  posters: {summary.posters}",
        f"live Gemini requests this run (incl. retries): {live}",
        f"tokens (all evaluated posters): in {usage.prompt_tokens}, out {usage.output_tokens}, "
        f"thinking {usage.thought_tokens}; paid-tier cost estimate ${usage.cost_usd:.4f} "
        f"(${usage.cost_usd / posters:.4f} per poster)",
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scraper.ocr.evaluate", description=__doc__.split("\n\n")[0])
    p.add_argument("--max-images", type=int, default=3, help="upper bound on posters (whole brochures only)")
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
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="name similarity needed to pair")
    p.add_argument("--refresh-catalog", action="store_true", help="re-download catalog.json and product lists")
    p.add_argument("--offline", action="store_true", help="use only cached data; never touch the network")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    out: Path = args.out
    http = None if args.offline else HttpClient()
    gemini: GeminiClient | None = None
    try:
        store = Store(out / "data", http)
        base = args.base_url.rstrip("/") + "/"
        catalog = store.json(base + "catalog.json", "catalog", refresh=args.refresh_catalog)
        brochures = select_brochures(catalog, args.max_images)
        if not brochures:
            print("no BİM brochure with both pages and products fits --max-images", file=sys.stderr)
            return 1
        if not args.offline:
            try:
                key = load_api_key()
            except MissingApiKey as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            gemini = GeminiClient(
                key,
                model=args.model,
                min_interval=args.interval,
                media_resolution=args.media_resolution,
                thinking_level=args.thinking_level,
                log=lambda msg: print(msg, file=sys.stderr, flush=True),
            )
            del key

        results: list[BrochureResult] = []
        usage = Usage()
        latencies: list[float] = []
        failures: list[str] = []
        for b in brochures:
            written = store.json(base + b["products_url"], "products", refresh=args.refresh_catalog)["products"]
            posters: list[Poster] = []
            try:
                for page in b["pages"]:
                    path = gemini_cache_path(out, page["url"], args.model, args.media_resolution, args.thinking_level)
                    result, live, elapsed = read_poster(page["url"], store, gemini, path)
                    if elapsed is not None:
                        latencies.append(elapsed)
                    source = "live " if live else "cache"
                    print(f"{source} {b['id']} {page['url']} -> {len(result.products)} products", flush=True)
                    posters.append(Poster(url=page["url"], products=result.products))
                    usage = Usage(
                        usage.prompt_tokens + result.usage.prompt_tokens,
                        usage.output_tokens + result.usage.output_tokens,
                        usage.thought_tokens + result.usage.thought_tokens,
                    )
            except (GeminiError, RuntimeError) as exc:
                failures.append(f"{b['id']}: {exc}")
                print(f"skip {b['id']}: {exc}", file=sys.stderr)
                continue
            results.append(evaluate_brochure(b["id"], written, posters, args.threshold))

        if not results:
            print("nothing evaluated", file=sys.stderr)
            return 1
        summary = summarize(results)
        live = gemini.requests_sent if gemini else 0
        text = render_text(summary, results, usage, live, args.model, args.thinking_level, latencies)
        if failures:
            text += "\nskipped brochures:\n" + "\n".join(f"  {f}" for f in failures) + "\n"
        report = {
            "model": args.model,
            "prompt_version": PROMPT_VERSION,
            "options": {
                "media_resolution": args.media_resolution,
                "thinking_level": args.thinking_level,
                "threshold": args.threshold,
            },
            "summary": asdict(summary)
            | {
                "match_rate": summary.match_rate,
                "price_accuracy": summary.price_accuracy,
                "poster_match_rate": summary.poster_match_rate,
            },
            "usage": asdict(usage) | {"cost_usd_paid_tier": usage.cost_usd},
            "latencies_s": latencies,
            "live_requests": live,
            "downloads": store.downloads,
            "failures": failures,
            "pairs": [asdict(p) for r in results for p in r.pairs],
            "unmatched_ocr": {r.brochure_id: r.unmatched_ocr for r in results},
            "unmatched_written": {r.brochure_id: [w.get("name") for w in r.unmatched_written] for r in results},
        }
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "report.txt").write_text(text, encoding="utf-8")
        print()
        print(text)
        print(f"report: {out / 'report.txt'}")
        return 0
    finally:
        if gemini is not None:
            gemini.close()
        if http is not None:
            http.close()


if __name__ == "__main__":
    raise SystemExit(main())
