"""``python -m scraper run``: run the sources, publish the output folder, print a summary."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

from scraper.chains import CHAINS, ChainInfo
from scraper.core.http import HttpClient
from scraper.core.pipeline import EXIT_NOT_WRITTEN, RunReport, run, summary_rows
from scraper.core.source import Source

SUMMARY_ENV = "GITHUB_STEP_SUMMARY"
DEFAULT_OUT = Path("scraper/out")
# Brochure dates are Turkish calendar days; Turkey has stayed on UTC+3 all year since 2016.
TURKEY = timezone(timedelta(hours=3))

_COLUMNS = ("chain", "result", "brochures", "new", "time", "error / notes")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--only", help="comma separated chain ids to run, e.g. bim,sok (default: all)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output folder (default: {DEFAULT_OUT})")
    parser.add_argument("--state-dir", type=Path, help="previous output to merge with (default: --out)")
    parser.add_argument("--today", type=date.fromisoformat, help="pretend today is YYYY-MM-DD (Turkish date)")
    parser.add_argument("--dry-run", action="store_true", help="do everything except replacing --out")


def select_sources(sources: Sequence[Source], only: str | None) -> list[Source]:
    if not only:
        return list(sources)
    wanted = [s.strip() for s in only.split(",") if s.strip()]
    known = {s.chain_id: s for s in sources}
    unknown = [w for w in wanted if w not in known]
    if unknown:
        raise ValueError(f"unknown source(s): {', '.join(unknown)}; available: {', '.join(sorted(known))}")
    return [known[w] for w in dict.fromkeys(wanted)]


def main(
    args: argparse.Namespace,
    *,
    sources: Sequence[Source] | None = None,
    chains: Sequence[ChainInfo] = CHAINS,
    http: HttpClient | None = None,
    now: datetime | None = None,
) -> int:
    if sources is None:
        from scraper.sources import SOURCES

        sources = SOURCES
    try:
        selected = select_sources(sources, args.only)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_NOT_WRITTEN

    now = now or datetime.now(UTC).replace(microsecond=0)
    today = args.today or now.astimezone(TURKEY).date()
    out_dir: Path = args.out
    state_dir: Path = args.state_dir or out_dir
    try:
        report = run(selected, chains, state_dir, out_dir, today, now, http=http, dry_run=args.dry_run)
    except Exception as exc:  # The summary must still say why nothing was published.
        print(f"error: run aborted, nothing written: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_NOT_WRITTEN

    print(format_table(report))
    for line in _footer(report, out_dir):
        print(line)
    summary = os.environ.get(SUMMARY_ENV)
    if summary:
        try:
            with Path(summary).open("a", encoding="utf-8") as fh:
                fh.write(format_markdown(report, out_dir))
        except OSError as exc:
            print(f"could not write step summary: {exc}", file=sys.stderr)
    return report.exit_code


def format_table(report: RunReport) -> str:
    rows = [_COLUMNS, *summary_rows(report)]
    widths = [max(len(row[i]) for row in rows) for i in range(len(_COLUMNS))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip() for row in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def format_markdown(report: RunReport, out_dir: Path) -> str:
    def cell(text: str) -> str:
        return text.replace("|", "\\|") or " "

    out = [
        "## Scraper run",
        "",
        "| " + " | ".join(_COLUMNS) + " |",
        "|" + "|".join("---" for _ in _COLUMNS) + "|",
    ]
    out += ["| " + " | ".join(cell(c) for c in row) + " |" for row in summary_rows(report)]
    out += ["", *(f"- {line}" for line in _footer(report, out_dir))]
    return "\n".join(out) + "\n"


def _footer(report: RunReport, out_dir: Path) -> list[str]:
    lines = [f"warning: {w}" for w in report.warnings]
    if not report.output_ok:
        lines.append(f"NOT PUBLISHED: {report.output_error}")
    elif report.dry_run:
        lines.append(f"dry run: output valid ({report.brochure_count} brochures), {out_dir} left untouched")
    else:
        lines.append(f"published {report.brochure_count} brochures to {out_dir}")
    if report.new_brochure_ids:
        prefix = "new brochures (first run)" if report.first_run else "new brochures"
        lines.append(f"{prefix}: {', '.join(report.new_brochure_ids)}")
    return lines
