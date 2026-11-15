"""bonVeno: weekly single-page vector PDFs linked from the "Kampanyalarımız" page.

The only date is in the file name ("70x100_13-19KASIM-1.pdf"); a PDF without one (the QSR
poster) is not a weekly brochure and is skipped. The links carry ``?rev=...&hash=...``;
those change without the content changing, so they are dropped: they must not enter the
id, and the PDF opens without them. PDF pages are rendered to WebP like Şok's, and a PDF
already rendered in the previous run is reused.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from posixpath import basename, splitext
from urllib.parse import unquote, urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser

from scraper.core.dates import format_range, parse_date_label
from scraper.core.ids import brochure_id
from scraper.core.media import local_paths
from scraper.core.models import Brochure, BrochureKind
from scraper.core.pdf import matches_render_width, render_pdf_pages
from scraper.core.source import SourceContext, SourceError, SourceResult, fetch

CHAIN_ID = "bonveno"
BASE_URL = "https://bonveno.com.tr/"
PAGE_URL = "https://bonveno.com.tr/Kampanyalarimiz"
TITLE = "bonVeno Haftalık Fırsatlar"
PDF_TIMEOUT = 180.0
CATALOG_SEGMENT = "/katalog/"


@dataclass(frozen=True, slots=True)
class BonvenoPdf:
    url: str  # without the rev / hash query
    stem: str


# --- parsing (pure) --------------------------------------------------------------------


def parse_pdfs(html: str) -> list[BonvenoPdf]:
    """Every PDF under ``/katalog/`` on the page, query stripped, unique, in page order."""
    tree = LexborHTMLParser(html)
    found: dict[str, BonvenoPdf] = {}
    for a in tree.css("a[href]"):
        parts = urlsplit(urljoin(BASE_URL, (a.attributes.get("href") or "").strip()))
        if CATALOG_SEGMENT not in parts.path.lower() or not parts.path.lower().endswith(".pdf"):
            continue
        url = parts._replace(query="", fragment="").geturl()
        found.setdefault(url, BonvenoPdf(url, splitext(basename(unquote(parts.path)))[0]))
    if not found:
        raise SourceError("bonVeno page links no PDF under /katalog/ (page layout may have changed)")
    return list(found.values())


def pdf_brochure(pdf: BonvenoPdf, today: date, now: datetime) -> Brochure | None:
    """The brochure for ``pdf`` without pages, or None when the file name carries no date."""
    dates = parse_date_label(pdf.stem, today)
    if dates is None:
        return None
    return Brochure(
        id=brochure_id(CHAIN_ID, dates.valid_from, pdf.stem),
        chain_id=CHAIN_ID,
        title=TITLE,
        date_label=format_range(dates),
        valid_from=dates.valid_from,
        valid_to=dates.valid_to,
        kind=BrochureKind.PAGES,
        cover=None,
        pages=(),
        products_url=None,
        product_count=0,
        source_url=pdf.url,
        first_seen=now,
        updated_at=now,
    )


# --- network ---------------------------------------------------------------------------


class BonvenoSource:
    chain_id = CHAIN_ID

    def collect(self, ctx: SourceContext) -> SourceResult:
        pdfs = parse_pdfs(fetch(ctx.http, PAGE_URL).text)
        drafts = [(p, d) for p in pdfs if (d := pdf_brochure(p, ctx.today, ctx.now)) is not None]
        if not drafts:
            raise SourceError("bonVeno: no PDF with a date in its file name (page layout may have changed)")
        previous = ctx.previous_by_id()
        brochures: list[Brochure] = []
        reused = 0
        for pdf, draft in drafts:
            old = previous.get(draft.id)
            if old is not None and local_paths(old) and matches_render_width(old.pages) and ctx.media.reuse(old):
                brochures.append(replace(draft, pages=old.pages, cover=old.cover))
                reused += 1
                continue
            data = fetch(ctx.http, pdf.url, timeout=PDF_TIMEOUT).content
            pages = ctx.media.write_pages(CHAIN_ID, draft.id, render_pdf_pages(data))
            brochures.append(replace(draft, pages=tuple(pages), cover=pages[0]))
        warnings = [f"{reused} PDFs reused from the previous run"] if reused else []
        return SourceResult(brochures=brochures, warnings=warnings)
