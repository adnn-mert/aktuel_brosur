"""Written price lists that OCR answers are scored against, for chains whose catalog has none.

BİM publishes its product list in our own data (``products/<id>.json``). Tarım Kredi does
not: the scraper only renders its PDF bulletin. Its site, however, lists the same
campaign as product cards at ``/haftalik-kampanyalar/<slug>``, and the home page block that
links the PDF also links that card page, which is how a brochure finds its cards here.

Measurement only: nothing in this module changes what the scraper publishes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser

from scraper.core.dates import DateRange, parse_date_label
from scraper.core.prices import parse_price_minor
from scraper.core.source import SourceError
from scraper.sources.tkkoop import BASE_URL as TKKOOP_BASE_URL
from scraper.sources.tkkoop import Campaign, parse_campaigns


class WrittenListError(RuntimeError):
    """The written list for a brochure cannot be found or trusted; the brochure is skipped."""


@dataclass(frozen=True)
class CardPage:
    title: str
    products: list[dict[str, Any]]
    # Cards that carried no readable price; they are left out of the truth.
    unreadable: int


def tkkoop_card_url(slug: str) -> str:
    return urljoin(TKKOOP_BASE_URL, f"haftalik-kampanyalar/{slug}")


def campaign_for_pdf(home_html: str, pdf_url: str) -> Campaign:
    """The home page campaign whose "BÜLTENİ İNDİR" link is ``pdf_url``.

    The PDF and the card page are linked from the same block, so this is the one link
    between a published brochure (whose ``source_url`` is the PDF) and its cards.
    """
    try:
        campaigns = parse_campaigns(home_html)
    except SourceError as exc:
        raise WrittenListError(str(exc)) from None
    for campaign in campaigns:
        if campaign.pdf_url == pdf_url:
            return campaign
    raise WrittenListError(f"the home page no longer links {pdf_url}; its product cards cannot be found")


def parse_card_page(html: str) -> CardPage:
    """Product cards of one campaign page: full name from the link title, price in kuruş."""
    tree = LexborHTMLParser(html)
    title_node = tree.css_first("title")
    title = " ".join(title_node.text().split()) if title_node else ""
    products: list[dict[str, Any]] = []
    unreadable = 0
    for card in tree.css(".ss_urun_area div.product-card"):
        link = card.css_first("a[title]")
        name = " ".join((link.attributes.get("title") or "").split()) if link else ""
        if not name:
            shown = card.css_first(".product-title")
            name = " ".join(shown.text().split()) if shown else ""
        price_node = card.css_first(".ss_urun52")
        # "<div>79,<span>90</span><div>TL</div></div>": joined without spaces it reads "79,90TL".
        price = parse_price_minor(price_node.text(deep=True, separator="")) if price_node else None
        if not name or price is None:
            unreadable += 1
            continue
        image = card.css_first(".product-image img")
        products.append(
            {
                "name": name,
                "brand": None,
                "quantity_text": None,
                "price_minor": price,
                "old_price_minor": None,
                "image": (image.attributes.get("src") or None) if image else None,
            }
        )
    if not products:
        raise WrittenListError("campaign page has no priced product cards (page layout may have changed)")
    return CardPage(title=title, products=products, unreadable=unreadable)


def check_card_dates(page_title: str, brochure: dict[str, Any]) -> None:
    """Refuse a card page whose title dates another week than the brochure.

    Slugs such as ``kat-kat-firsat`` come back every few weeks; a cached home page with a
    freshly fetched card page could otherwise score one week's PDF against another's prices.
    Titles without a readable date ("14 - 16 Fırsat Dolu Haftasonu") pass: the home page
    block already ties the two together.
    """
    valid_from = brochure.get("valid_from")
    if not valid_from:
        return
    reference = date.fromisoformat(valid_from)
    found = parse_date_label(page_title, reference)
    if found is None:
        return
    expected = DateRange(reference, date.fromisoformat(brochure.get("valid_to") or valid_from))
    if found != expected:
        raise WrittenListError(
            f"card page {page_title!r} is for {found.valid_from}..{found.valid_to}, "
            f"the brochure for {expected.valid_from}..{expected.valid_to}"
        )


def card_page_products(html: str, brochure: dict[str, Any]) -> list[dict[str, Any]]:
    page = parse_card_page(html)
    check_card_dates(page.title, brochure)
    return page.products
