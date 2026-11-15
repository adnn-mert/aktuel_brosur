"""Tarım Kredi Market: the weekly campaign blocks on the home page, each with a "BÜLTENİ İNDİR" PDF.

The site is slow (about 20 s per page), so requests get a long timeout. Dates are printed in
the block ("10 Kasım - 16 Kasım") and repeated in the PDF file name. PDF pages are rendered
to WebP like Şok's; a PDF already rendered in the previous run is reused. Product cards
(``/haftalik-kampanyalar/<slug>``) are not read here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from posixpath import basename, splitext
from urllib.parse import unquote, urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from scraper.core.dates import parse_date_label
from scraper.core.ids import brochure_id
from scraper.core.media import local_paths
from scraper.core.models import Brochure, BrochureKind
from scraper.core.pdf import matches_render_width, render_pdf_pages
from scraper.core.source import SourceContext, SourceError, SourceResult, fetch

CHAIN_ID = "tkkoop"
BASE_URL = "https://www.tkkoop.com.tr/"
PAGE_URL = "https://www.tkkoop.com.tr/"
PAGE_TIMEOUT = 60.0
PDF_TIMEOUT = 180.0
# The site writes campaign slugs without Turkish letters; these are the known ones restored.
KNOWN_TITLES = {
    "kat-kat-firsat": "Kat Kat Fırsat",
    "firsat-dolu-haftasonu": "Fırsat Dolu Haftasonu",
}


@dataclass(frozen=True, slots=True)
class Campaign:
    slug: str
    date_text: str | None
    pdf_url: str


# --- parsing (pure) --------------------------------------------------------------------


def parse_campaigns(html: str) -> list[Campaign]:
    """Campaign blocks that offer a PDF, in page order, one per distinct PDF."""
    tree = LexborHTMLParser(html)
    found: dict[str, Campaign] = {}
    for block in tree.css(".yeni_1"):
        pdf = _pdf_link(block)
        if pdf is None:
            continue
        date_node = block.css_first(".yeni_2a3")
        text = " ".join(date_node.text(deep=True).split()) if date_node else ""
        found.setdefault(pdf, Campaign(_slug(block, pdf), text or None, pdf))
    if not found:
        raise SourceError("Tarım Kredi home page has no campaign with a PDF (page layout may have changed)")
    return list(found.values())


def campaign_brochure(campaign: Campaign, today: date, now: datetime) -> Brochure:
    """The brochure for ``campaign`` without pages; pages come from the PDF or the previous run."""
    stem = pdf_stem(campaign.pdf_url)
    dates = parse_date_label(campaign.date_text or "", today) or parse_date_label(stem, today)
    parts: list[str | date] = [dates.valid_from] if dates else []
    return Brochure(
        id=brochure_id(CHAIN_ID, *parts, stem),
        chain_id=CHAIN_ID,
        title=KNOWN_TITLES.get(campaign.slug, campaign.slug.replace("-", " ").capitalize()),
        date_label=campaign.date_text,
        valid_from=dates.valid_from if dates else None,
        valid_to=dates.valid_to if dates else None,
        kind=BrochureKind.PAGES,
        cover=None,
        pages=(),
        products_url=None,
        product_count=0,
        source_url=campaign.pdf_url,
        first_seen=now,
        updated_at=now,
    )


def pdf_stem(pdf_url: str) -> str:
    return splitext(basename(unquote(urlsplit(pdf_url).path)))[0]


def _pdf_link(block: LexborNode) -> str | None:
    for a in block.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if urlsplit(href).path.lower().endswith(".pdf"):
            return urljoin(BASE_URL, href)
    return None


def _slug(block: LexborNode, pdf_url: str) -> str:
    titled = block.css_first("a[title]")
    if titled is not None and (titled.attributes.get("title") or "").strip():
        return (titled.attributes["title"] or "").strip()
    return pdf_stem(pdf_url).rsplit("_", 1)[0]


# --- network ---------------------------------------------------------------------------


class TkkoopSource:
    chain_id = CHAIN_ID

    def collect(self, ctx: SourceContext) -> SourceResult:
        campaigns = parse_campaigns(fetch(ctx.http, PAGE_URL, timeout=PAGE_TIMEOUT).text)
        previous = ctx.previous_by_id()
        brochures: list[Brochure] = []
        reused = 0
        for campaign in campaigns:
            draft = campaign_brochure(campaign, ctx.today, ctx.now)
            old = previous.get(draft.id)
            if old is not None and local_paths(old) and matches_render_width(old.pages) and ctx.media.reuse(old):
                brochures.append(replace(draft, pages=old.pages, cover=old.cover))
                reused += 1
                continue
            pdf = fetch(ctx.http, campaign.pdf_url, timeout=PDF_TIMEOUT).content
            pages = ctx.media.write_pages(CHAIN_ID, draft.id, render_pdf_pages(pdf))
            brochures.append(replace(draft, pages=tuple(pages), cover=pages[0]))
        warnings = [f"{reused} PDFs reused from the previous run"] if reused else []
        return SourceResult(brochures=brochures, warnings=warnings)
