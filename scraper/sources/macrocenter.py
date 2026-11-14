"""Macrocenter: the current monthly MacroStyle magazine, a PDF linked from money.com.tr.

The PDF is rendered to WebP like Şok's. Its button carries the validity in ``mcdate``, so
the dates and the file always belong to the same issue. The brochure id is derived from
the PDF address: an unchanged PDF is reused from the previous output, a new one is a new
brochure. Past issues listed below the current one are not taken.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from posixpath import basename, splitext
from urllib.parse import unquote, urlsplit

from scraper.core.dates import parse_date_label
from scraper.core.ids import brochure_id
from scraper.core.media import local_paths
from scraper.core.models import Brochure, BrochureKind
from scraper.core.pdf import matches_render_width, render_pdf_pages
from scraper.core.source import SourceContext, SourceError, SourceResult, fetch
from scraper.sources.money import CurrentIssue, heading_names, parse_current_issue

CHAIN_ID = "macrocenter"
PAGE_URL = "https://www.money.com.tr/macrostyle-dijital"
TITLE = "MacroStyle"
PDF_TIMEOUT = 180.0


# --- parsing (pure) --------------------------------------------------------------------


def issue_brochure(issue: CurrentIssue, today: date, now: datetime) -> Brochure:
    """The brochure for the current issue without pages; pages come from the PDF or the previous run."""
    if not heading_names(issue.heading, TITLE):
        raise SourceError(f"{PAGE_URL} shows {issue.heading!r}, expected {TITLE}")
    if not issue.pdf_url or not urlsplit(issue.pdf_url).path.lower().endswith(".pdf"):
        raise SourceError("MacroStyle current issue has no PDF link (page layout may have changed)")
    dates = parse_date_label(issue.date_text or "", today)
    if dates is None:
        raise SourceError(f"MacroStyle current issue has no readable dates ({issue.date_text!r})")
    return Brochure(
        id=brochure_id(CHAIN_ID, pdf_stem(issue.pdf_url)),
        chain_id=CHAIN_ID,
        title=TITLE,
        date_label=issue.date_text,
        valid_from=dates.valid_from,
        valid_to=dates.valid_to,
        kind=BrochureKind.PAGES,
        cover=None,
        pages=(),
        products_url=None,
        product_count=0,
        source_url=issue.pdf_url,
        first_seen=now,
        updated_at=now,
    )


def pdf_stem(pdf_url: str) -> str:
    return splitext(basename(unquote(urlsplit(pdf_url).path)))[0]


# --- network ---------------------------------------------------------------------------


class MacrocenterSource:
    chain_id = CHAIN_ID

    def collect(self, ctx: SourceContext) -> SourceResult:
        issue = parse_current_issue(fetch(ctx.http, PAGE_URL).text)
        draft = issue_brochure(issue, ctx.today, ctx.now)
        old = ctx.previous_by_id().get(draft.id)
        if old is not None and local_paths(old) and matches_render_width(old.pages) and ctx.media.reuse(old):
            reused = replace(draft, pages=old.pages, cover=old.cover)
            return SourceResult([reused], warnings=["PDF reused from the previous run"])
        pdf = fetch(ctx.http, draft.source_url, timeout=PDF_TIMEOUT).content
        pages = ctx.media.write_pages(CHAIN_ID, draft.id, render_pdf_pages(pdf))
        return SourceResult([replace(draft, pages=tuple(pages), cover=pages[0])])
