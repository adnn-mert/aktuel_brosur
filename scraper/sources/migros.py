"""Migros: the current Migroskop issue as a priced product list.

Dates and the issue number come from money.com.tr; the products come from the Migroskop
viewer (server-rendered HTML with one ``div.product`` card per product). The viewer itself
carries no dates, so its cover image (whose folder name starts with the issue number,
e.g. ``910MIGROSKOP72YIL_migroskop_kapak1``) is checked against the issue money.com.tr
lists; when they disagree the source fails rather than publish products under the wrong
dates.

The 5M Migroskop issue is not taken: its product cards are exactly the Migroskop ones, and
two identical lists would only confuse. Brochures of publications no longer taken are
retired from the previous output instead of lingering as archive.

Prices: a card prints either one shelf price, or the shelf price plus a lower
"MONEY'Lİ FİYAT" that only Money members pay. ``price_minor`` is always the shelf price
everyone pays; the Money price goes to ``member_price_minor`` labelled "Money ile". Cards
without a price (only a "%25 indirim" or "2.si %50" badge) and cards with an unknown
layout, unit or badge are skipped and counted.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from posixpath import dirname
from urllib.parse import unquote, urlsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from scraper.core.dates import DateRange, parse_date_label
from scraper.core.ids import brochure_id
from scraper.core.models import Brochure, BrochureKind, Page, Product, ProductFile
from scraper.core.prices import parse_price_minor
from scraper.core.source import SourceContext, SourceError, SourceResult, fetch, products_path
from scraper.core.text import fold_turkish
from scraper.sources.money import (
    CurrentIssue,
    first_attr,
    heading_names,
    https_url,
    parse_current_issue,
    size_from_name,
    text_of,
)

CHAIN_ID = "migros"


@dataclass(frozen=True, slots=True)
class Publication:
    key: str
    title: str
    listing_url: str
    viewer_url: str


MIGROSKOP = Publication(
    key="migroskop",
    title="Migroskop",
    listing_url="https://www.money.com.tr/migroskop-dijital",
    viewer_url="https://migroskop.migros.com.tr/migroskop",
)
PUBLICATIONS: tuple[Publication, ...] = (MIGROSKOP,)

# Units printed after the kuruş. A per-item price needs no note; a per-kg price does,
# otherwise "999,00 ₺" next to a sausage reads as the price of the pack. This note is the
# only quantity text: the stock lines ("Stok Adedi: 100.000") tell a shopper nothing and
# the weight is already in the product name.
_PER_ITEM_UNITS = frozenset({"", "adet", "paket", "set"})
_PER_KG_UNITS = frozenset({"kg"})
PER_KG_NOTE = "kg fiyatı"
MEMBER_PRICE_LABEL = "Money ile"
# Badges that do not change what the printed price means. "1 ALANA 1 HEDİYE" gives a
# second item free, but the printed price is still the price of one.
_HARMLESS_BADGES = frozenset(
    {"ilk-kez-migrosta", "cografi-isaret-ve-geleneksel-urun-adi", "x-bebe-money", "x-alana-x-hediye"}
)
_MEMBER_PRICE_LABEL = "money"
_LIRA = re.compile(r"^(\d{1,3}(?:\.\d{3})+|\d+),$")
_KURUS = re.compile(r"^\d{2}$")
_LEADING_NUMBER = re.compile(r"^(\d+)(?!\d)")

# Skip reasons, shown in the run summary.
NO_PRICE = "no price, only a discount badge"
UNREADABLE_PRICE = "unreadable price"
UNKNOWN_LAYOUT = "unknown price layout"
UNKNOWN_UNIT = "unknown price unit"
UNKNOWN_BADGE = "unknown badge"
NO_NAME = "no name"
# Member price not written (the product itself is kept with its shelf price).
MEMBER_NOT_LOWER = "Money price not lower than the shelf price"


@dataclass(frozen=True, slots=True)
class ViewerIssue:
    # Leading number of the cover image's folder, e.g. "910"; None when it has none.
    issue: str | None
    cover_url: str | None
    # Date ranges written in asset folder names ("910 5-18 KASIM MIGROSKOP TERS").
    folder_dates: frozenset[DateRange]


@dataclass(frozen=True, slots=True)
class ParsedProducts:
    products: tuple[Product, ...]
    skipped: Counter[str]
    # Products published with a Money member price.
    member_priced: int
    # Member prices printed but not published, by reason (the products are kept).
    member_dropped: Counter[str]
    page_count: int


# --- parsing (pure) --------------------------------------------------------------------


def parse_viewer_issue(html: str, today: date) -> ViewerIssue:
    """Which issue the viewer shows, read from its cover image and asset folder names."""
    tree = LexborHTMLParser(html)
    if not tree.css("div.page"):
        raise SourceError("Migroskop viewer has no pages (page layout may have changed)")
    cover_node = tree.css_first("div.page div.cover img")
    cover_url = https_url(first_attr(cover_node, "src", "data-src")) if cover_node else None
    issue = None
    if cover_url:
        m = _LEADING_NUMBER.match(_asset_folder(cover_url))
        issue = m.group(1) if m else None
    dates: set[DateRange] = set()
    for img in tree.css("div.page div.cover img, div.page div.ad img"):
        url = first_attr(img, "src", "data-src")
        if url and (found := parse_date_label(_asset_folder(url), today)):
            dates.add(found)
    return ViewerIssue(issue, cover_url, frozenset(dates))


def check_same_issue(listing: CurrentIssue, listing_dates: DateRange, viewer: ViewerIssue) -> None:
    """Fail unless the viewer shows the issue money.com.tr dates; never guess."""
    listed = _issue_number(listing.issue)
    if listed and viewer.issue:
        if listed != viewer.issue:
            raise SourceError(
                f"viewer shows issue {viewer.issue} but money.com.tr lists issue {listed}; dates cannot be trusted"
            )
        return
    if listing_dates in viewer.folder_dates:
        return
    raise SourceError("cannot confirm that the viewer shows the issue money.com.tr dates (no issue number match)")


def parse_products(html: str) -> ParsedProducts:
    """Priced product cards of the viewer, with the 0-based index of the page they are on."""
    tree = LexborHTMLParser(html)
    pages = tree.css("div.page")
    if not pages:
        raise SourceError("Migroskop viewer has no pages (page layout may have changed)")
    products: list[Product] = []
    skipped: Counter[str] = Counter()
    dropped: Counter[str] = Counter()
    for index, page in enumerate(pages):
        for card in page.css("div.product"):
            parsed = parse_card(card, index)
            if isinstance(parsed, str):
                skipped[parsed] += 1
                continue
            product, dropped_member_price = parsed
            products.append(product)
            if dropped_member_price:
                dropped[dropped_member_price] += 1
    if not products and not skipped:
        raise SourceError("Migroskop viewer has no product cards (page layout may have changed)")
    member_priced = sum(1 for p in products if p.member_price_minor is not None)
    return ParsedProducts(tuple(products), skipped, member_priced, dropped, len(pages))


def parse_card(card: LexborNode, page_index: int) -> tuple[Product, str | None] | str:
    """The product and why its printed member price was not kept (None if nothing was
    dropped), or the reason the whole card is skipped."""
    title = card.css_first("h1.title")
    name = text_of(title) if title else ""
    if not name:
        return NO_NAME
    for badge in card.css("div.mbadge"):
        if (badge.attributes.get("name") or "") not in _HARMLESS_BADGES:
            return UNKNOWN_BADGE
    box = card.css_first("div.price-content")
    blocks = box.css("div.price-text") if box else []
    if not blocks:
        return NO_PRICE if box is not None and box.css_first(".badge-content") else UNKNOWN_LAYOUT

    labels = [fold_turkish(text_of(h)) for h in box.css("h6")] if box else []
    if len(blocks) == 1 and not labels:
        has_member_price = False
    elif len(blocks) == 2 and len(labels) == 1 and _MEMBER_PRICE_LABEL in labels[0]:
        has_member_price = True
    else:
        # Two prices without the Money label: which one is the shelf price is unknown.
        return UNKNOWN_LAYOUT

    read = [_read_price(b) for b in blocks]
    if any(r is None for r in read):
        return UNREADABLE_PRICE
    prices = [r[0] for r in read if r]
    units = {r[1] for r in read if r}
    if units <= _PER_ITEM_UNITS:
        unit_note = None
    elif units <= _PER_KG_UNITS | {""}:
        unit_note = PER_KG_NOTE
    else:
        return UNKNOWN_UNIT

    member_price: int | None = None
    dropped: str | None = None
    if has_member_price:
        # A member price that is not lower means we misread it: keep only the shelf price.
        if prices[1] < prices[0]:
            member_price = prices[1]
        else:
            dropped = MEMBER_NOT_LOWER
    image = card.css_first("div.image img")
    product = Product(
        name=name,
        price_minor=prices[0],
        brand=None,
        quantity_text=unit_note,
        old_price_minor=None,
        image=https_url(first_attr(image, "data-src", "src")) if image else None,
        page_index=page_index,
        source_url=None,
        member_price_minor=member_price,
        member_price_label=MEMBER_PRICE_LABEL if member_price is not None else None,
    )
    return product, dropped


def build_brochure(
    pub: Publication,
    listing: CurrentIssue,
    viewer: ViewerIssue,
    products: ParsedProducts,
    today: date,
    now: datetime,
) -> tuple[Brochure, ProductFile]:
    dates = listing_dates(listing, today)
    check_same_issue(listing, dates, viewer)
    if not products.products:
        raise SourceError(f"{pub.title}: no product has a readable price")
    bid = issue_brochure_id(pub, listing.issue, dates)
    # The viewer's cover is the flat printed cover; money.com.tr only has a small 3D mock-up.
    cover_url = viewer.cover_url or listing.cover_url
    cover = Page(cover_url, *(size_from_name(cover_url) or (None, None))) if cover_url else None
    brochure = Brochure(
        id=bid,
        chain_id=CHAIN_ID,
        title=pub.title,
        date_label=listing.date_text,
        valid_from=dates.valid_from,
        valid_to=dates.valid_to,
        kind=BrochureKind.PRODUCTS,
        cover=cover,
        pages=(),
        products_url=products_path(bid),
        product_count=len(products.products),
        source_url=pub.viewer_url,
        first_seen=now,
        updated_at=now,
    )
    return brochure, ProductFile(brochure_id=bid, products=products.products)


def listing_dates(listing: CurrentIssue, today: date) -> DateRange:
    dates = parse_date_label(listing.date_text or "", today)
    if dates is None:
        raise SourceError(f"money.com.tr current issue has no readable dates ({listing.date_text!r})")
    return dates


def issue_brochure_id(pub: Publication, issue: str | None, dates: DateRange) -> str:
    """``migros-migroskop-910``; from the dates when the issue number is unreadable."""
    number = _issue_number(issue)
    if number:
        return brochure_id(CHAIN_ID, pub.key, number)
    return brochure_id(CHAIN_ID, pub.key, dates.valid_from, dates.valid_to)


def _issue_number(issue: str | None) -> str | None:
    text = (issue or "").strip()
    return text if text.isdigit() else None


def _read_price(block: LexborNode) -> tuple[int, str] | None:
    """(kuruş, folded unit) from ``<div.first>₺ 54,</div><div.second>95 Adet</div>``."""
    first = [text_of(s) for s in block.css("div.first span")]
    second = [text_of(s).replace("\xa0", "") for s in block.css("div.second span")]
    lira = "".join(t for t in first if t != "₺").replace("\xa0", "")
    if not _LIRA.match(lira) or not second or not _KURUS.match(second[0]):
        return None
    price = parse_price_minor(lira + second[0])
    if price is None:
        return None
    return price, fold_turkish(" ".join(t for t in second[1:] if t))


def _asset_folder(url: str) -> str:
    """``.../migrosdigitalinsert/910 ACIK ET/Ad/x.jpg`` -> ``910 ACIK ET``."""
    return unquote(dirname(dirname(urlsplit(url).path))).rsplit("/", 1)[-1]


# --- network ---------------------------------------------------------------------------


class MigrosSource:
    chain_id = CHAIN_ID

    def __init__(self, publications: tuple[Publication, ...] = PUBLICATIONS) -> None:
        self.publications = publications

    def collect(self, ctx: SourceContext) -> SourceResult:
        brochures: list[Brochure] = []
        files: dict[str, ProductFile] = {}
        warnings: list[str] = []
        for pub in self.publications:
            listing = parse_current_issue(fetch(ctx.http, pub.listing_url).text)
            if not heading_names(listing.heading, pub.title):
                raise SourceError(f"{pub.listing_url} shows {listing.heading!r}, expected {pub.title}")
            html = fetch(ctx.http, pub.viewer_url).text
            viewer = parse_viewer_issue(html, ctx.today)
            parsed = parse_products(html)
            total = len(parsed.products) + sum(parsed.skipped.values())
            if sum(parsed.skipped.values()) * 2 > total:
                raise SourceError(f"{pub.title}: {sum(parsed.skipped.values())} of {total} products skipped")
            brochure, products = build_brochure(pub, listing, viewer, parsed, ctx.today, ctx.now)
            brochures.append(brochure)
            files[brochure.id] = products
            if parsed.skipped:
                reasons = ", ".join(f"{n} {why}" for why, n in sorted(parsed.skipped.items()))
                warnings.append(f"{pub.title}: {sum(parsed.skipped.values())} products skipped ({reasons})")
            if parsed.member_priced:
                warnings.append(f"{pub.title}: {parsed.member_priced} Money prices")
            if parsed.member_dropped:
                reasons = ", ".join(f"{n} {why}" for why, n in sorted(parsed.member_dropped.items()))
                warnings.append(f"{pub.title}: Money price not written for {reasons}")
        retired = retired_brochure_ids(ctx.previous, self.publications)
        if retired:
            warnings.append(f"retired {len(retired)} brochures of publications no longer taken")
        return SourceResult(brochures=brochures, product_files=files, warnings=warnings, retired_ids=retired)


def retired_brochure_ids(previous: tuple[Brochure, ...], publications: tuple[Publication, ...]) -> frozenset[str]:
    """Previous brochures of publications no longer taken (e.g. ``migros-5m-286``).

    Without this the pipeline would keep them as archive for four more weeks.
    """
    prefixes = tuple(f"{CHAIN_ID}-{p.key}-" for p in publications)
    return frozenset(b.id for b in previous if not b.id.startswith(prefixes))
