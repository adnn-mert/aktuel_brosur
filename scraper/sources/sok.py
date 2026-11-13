"""Şok: one card per brochure on the "Fırsatlar" page, each linking a vector PDF.

PDF pages are rendered to WebP and published by us. The brochure id contains the PDF's
file name, so a replaced PDF becomes a new brochure while an unchanged one is reused
from the previous output without downloading 20+ MB again.
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
from scraper.core.pdf import render_pdf_pages
from scraper.core.source import SourceContext, SourceError, SourceResult, fetch

CHAIN_ID = "sok"
BASE_URL = "https://kurumsal.sokmarket.com.tr/"
PAGE_URL = "https://kurumsal.sokmarket.com.tr/tr/firsatlar"
# A 22 MB PDF on a slow connection needs far longer than an HTML page.
PDF_TIMEOUT = 180.0


@dataclass(frozen=True, slots=True)
class SokCard:
    title: str
    date_text: str | None
    pdf_url: str
    image_url: str | None


# --- parsing (pure) --------------------------------------------------------------------


def parse_cards(html: str) -> list[SokCard]:
    """Brochure cards on the Fırsatlar page, in page order, one per distinct PDF."""
    tree = LexborHTMLParser(html)
    cards: dict[str, SokCard] = {}
    for node in tree.css(".bc-aktual-card"):
        link = node if node.tag == "a" else node.css_first("a[href]")
        href = (link.attributes.get("href") or "").strip() if link else ""
        if not href.lower().split("?")[0].endswith(".pdf"):
            continue
        pdf_url = urljoin(BASE_URL, href)
        title_node = node.css_first(".aktual-card-title")
        title = _text(title_node) if title_node else ""
        img = node.css_first("img")
        if not title and img is not None:
            title = (img.attributes.get("alt") or "").strip()
        date_node = node.css_first(".aktual-card-date")
        image = (img.attributes.get("src") or "").strip() if img else ""
        cards.setdefault(
            pdf_url,
            SokCard(
                title=title or "Şok Fırsatları",
                date_text=(_text(date_node) if date_node else "") or None,
                pdf_url=pdf_url,
                image_url=urljoin(BASE_URL, image) if image else None,
            ),
        )
    if not cards:
        raise SourceError("Şok page has no brochure cards with a PDF link (page layout may have changed)")
    return list(cards.values())


def pdf_stem(pdf_url: str) -> str:
    return splitext(basename(unquote(urlsplit(pdf_url).path)))[0]


def card_brochure(card: SokCard, today: date, now: datetime) -> Brochure:
    """The brochure for ``card`` without pages yet; pages come from the PDF or the previous run."""
    stem = pdf_stem(card.pdf_url)
    dates = (
        (parse_date_label(card.date_text, today) if card.date_text else None)
        or parse_date_label(card.title, today)
        or parse_date_label(stem, today)
    )
    parts: list[str | date] = [dates.valid_from] if dates else []
    bid = brochure_id(CHAIN_ID, *parts, card.title, stem)
    return Brochure(
        id=bid,
        chain_id=CHAIN_ID,
        title=card.title,
        date_label=card.date_text,
        valid_from=dates.valid_from if dates else None,
        valid_to=dates.valid_to if dates else None,
        kind=BrochureKind.PAGES,
        cover=None,
        pages=(),
        products_url=None,
        product_count=0,
        source_url=card.pdf_url,
        first_seen=now,
        updated_at=now,
    )


def _text(node: LexborNode) -> str:
    # The title is split with <br>; a separator keeps "Haftanın" and "Fırsatları" apart.
    return " ".join(node.text(deep=True, separator=" ").split())


# --- network ---------------------------------------------------------------------------


class SokSource:
    chain_id = CHAIN_ID

    def collect(self, ctx: SourceContext) -> SourceResult:
        cards = parse_cards(fetch(ctx.http, PAGE_URL).text)
        previous = ctx.previous_by_id()
        brochures: list[Brochure] = []
        reused = 0
        for card in cards:
            draft = card_brochure(card, ctx.today, ctx.now)
            old = previous.get(draft.id)
            if old is not None and old.pages and local_paths(old) and ctx.media.reuse(old):
                brochures.append(replace(draft, pages=old.pages, cover=old.cover))
                reused += 1
                continue
            pdf = fetch(ctx.http, card.pdf_url, timeout=PDF_TIMEOUT).content
            pages = ctx.media.write_pages(CHAIN_ID, draft.id, render_pdf_pages(pdf))
            brochures.append(replace(draft, pages=tuple(pages), cover=pages[0]))
        warnings = [f"{reused} PDFs reused from the previous run"] if reused else []
        return SourceResult(brochures=brochures, warnings=warnings)
