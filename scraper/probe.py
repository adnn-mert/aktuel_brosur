"""Reachability probe: one GET per source, printed as a table.

Run on the GitHub Actions runner to see which sites answer a datacenter address and
which ones serve a block page instead. It is a report, so it never fails the job.
"""

from __future__ import annotations

import html
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from scraper.core.http import HttpClient

SUMMARY_ENV = "GITHUB_STEP_SUMMARY"


@dataclass(frozen=True, slots=True)
class ProbeTarget:
    name: str
    url: str
    # A substring only real content contains; a block page returns 200 without it.
    marker: str
    timeout: float = 30.0


TARGETS: tuple[ProbeTarget, ...] = (
    ProbeTarget("bim", "https://www.bim.com.tr/Categories/680/afisler.aspx", "data-bigimg"),
    ProbeTarget(
        "a101",
        "https://rio.a101.com.tr/dbmk89vnr/CALL/poster/list/default?__culture=tr-TR&__platform=web",
        "seoTitle",
    ),
    ProbeTarget("sok", "https://kurumsal.sokmarket.com.tr/tr/firsatlar", ".pdf"),
    ProbeTarget("migros_list", "https://www.money.com.tr/migroskop-dijital", "mcdate"),
    ProbeTarget("migros_viewer", "https://migroskop.migros.com.tr/migroskop", 'class="product'),
    ProbeTarget("macrocenter", "https://www.money.com.tr/macrostyle-dijital", "mcdate"),
    ProbeTarget("bonveno", "https://bonveno.com.tr/Kampanyalarimiz", ".pdf"),
    ProbeTarget("hakmar", "https://hakmar.com.tr/indirim/", "wp-content/uploads"),
    ProbeTarget(
        "tkkoop",
        "https://www.tkkoop.com.tr/haftalik-kampanyalar/kat-kat-firsat",
        "kampanya",
        timeout=60.0,
    ),
    ProbeTarget("rossmann", "https://www.rossmann.com.tr/kataloglar", "ipaper"),
    ProbeTarget(
        "metro",
        "https://brosurler.metro-tr.com/profesyonel-mutfaklarin-haftalik-ihtiyaclari/data.json",
        "numPages",
    ),
    ProbeTarget("watsons", "https://katalog.watsons.com.tr/sitemap.xml", "<loc>"),
    ProbeTarget("gratis", "https://www.gratis.com/gratis-katalog", "catalogUrl"),
)


@dataclass(frozen=True, slots=True)
class ProbeResult:
    name: str
    url: str
    status: int | None
    size: int | None
    content_type: str | None
    duration_ms: int
    marker_found: bool | None
    note: str


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_NOTE_LIMIT = 70


def _short(text: str, limit: int = _NOTE_LIMIT) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _body_hint(body: str) -> str:
    """A short clue to what was served instead of real content (usually the page title)."""
    if m := _TITLE_RE.search(body):
        return "title: " + _short(html.unescape(m.group(1)))
    return "body: " + _short(body)


def probe_one(
    client: HttpClient, target: ProbeTarget, clock: Callable[[], float] = time.monotonic
) -> ProbeResult:
    started = clock()
    try:
        response = client.get(target.url, timeout=target.timeout)
        body = response.text
    except Exception as exc:  # noqa: BLE001 - a probe must survive anything a site does
        return ProbeResult(
            name=target.name,
            url=target.url,
            status=None,
            size=None,
            content_type=None,
            duration_ms=int((clock() - started) * 1000),
            marker_found=None,
            note=_short(f"{type(exc).__name__}: {exc}"),
        )
    duration_ms = int((clock() - started) * 1000)
    found = target.marker.lower() in body.lower()
    note = "" if found and response.status_code == 200 else _body_hint(body)
    if str(response.url) != target.url:
        note = _short(f"-> {response.url} {note}".strip(), 120)
    return ProbeResult(
        name=target.name,
        url=target.url,
        status=response.status_code,
        size=len(response.content),
        content_type=(response.headers.get("content-type") or "").split(";")[0].strip() or None,
        duration_ms=duration_ms,
        marker_found=found,
        note=note,
    )


def run_probe(
    client: HttpClient,
    targets: Sequence[ProbeTarget] = TARGETS,
    clock: Callable[[], float] = time.monotonic,
) -> list[ProbeResult]:
    return [probe_one(client, t, clock) for t in targets]


_COLUMNS = ("chain", "status", "bytes", "content-type", "ms", "marker", "note")


def _row(r: ProbeResult) -> tuple[str, ...]:
    marker = {True: "yes", False: "NO", None: "-"}[r.marker_found]
    return (
        r.name,
        str(r.status) if r.status is not None else "ERR",
        str(r.size) if r.size is not None else "-",
        r.content_type or "-",
        str(r.duration_ms),
        marker,
        r.note,
    )


def format_table(results: Sequence[ProbeResult]) -> str:
    rows = [_COLUMNS, *(_row(r) for r in results)]
    widths = [max(len(row[i]) for row in rows) for i in range(len(_COLUMNS))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip() for row in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def format_markdown(results: Sequence[ProbeResult]) -> str:
    def cell(text: str) -> str:
        return text.replace("|", "\\|") or " "

    out = [
        "## Source probe",
        "",
        "| " + " | ".join(_COLUMNS) + " |",
        "|" + "|".join("---" for _ in _COLUMNS) + "|",
    ]
    out += ["| " + " | ".join(cell(c) for c in _row(r)) + " |" for r in results]
    ok = sum(1 for r in results if r.status == 200 and r.marker_found)
    out += ["", f"{ok}/{len(results)} sources returned 200 with the expected marker."]
    return "\n".join(out) + "\n"


def main(client: HttpClient | None = None, targets: Sequence[ProbeTarget] = TARGETS) -> int:
    # Exactly one request per source: no retries in a probe.
    own_client = client is None
    client = client or HttpClient(max_retries=0)
    try:
        results = run_probe(client, targets)
    finally:
        if own_client:
            client.close()

    print(format_table(results))
    summary = os.environ.get(SUMMARY_ENV)
    if summary:
        try:
            with Path(summary).open("a", encoding="utf-8") as fh:
                fh.write(format_markdown(results))
        except OSError as exc:
            print(f"could not write step summary: {exc}")
    return 0
