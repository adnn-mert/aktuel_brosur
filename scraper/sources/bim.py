"""BİM: poster images from afisler.aspx plus priced product cards from the aktüel tabs.

The poster page lists every current poster group under a date heading ("13 Kasım Cuma",
"13-19 Kasım") or a campaign name ("ÇOK AL AZ ÖDE"), split into an "Aktüel" and an
"İndirim" section. Its header menu also links one product tab per date. Posters and
product tabs with the same section and date become one brochure.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from posixpath import basename
from urllib.parse import urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from scraper.core.dates import DateRange, parse_date_label
from scraper.core.ids import brochure_id, slugify
from scraper.core.images import fetch_image_size
from scraper.core.models import Brochure, BrochureKind, Page, Product, ProductFile
from scraper.core.prices import parse_price_minor
from scraper.core.source import SourceContext, SourceError, SourceResult, fetch, products_path
from scraper.core.text import fold_turkish

CHAIN_ID = "bim"
BASE_URL = "https://www.bim.com.tr/"
POSTERS_URL = "https://www.bim.com.tr/Categories/680/afisler.aspx"

_IMAGE_URL = re.compile(r"^https://[^\s]+\.(?:jpe?g|png|webp)$", re.IGNORECASE)
_GROUP_CLASS = re.compile(r"\bgrup(\d+)\b")
# Small poster copies are the full-size file name with this prefix (about 40 KB each).
THUMBNAIL_PREFIX = "k_"

AKTUEL_SECTION = "aktuel"
# A one-day Aktüel heading ("13 Kasım Cuma") is the day sales start, not the only day:
# the goods stay on the shelf for the week, so the brochure must not turn "past" next day.
AKTUEL_EXTRA_DAYS = 6


@dataclass(frozen=True, slots=True)
class PosterGroup:
    section: str
    label: str
    pages: tuple[str, ...]
    thumbnails: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProductTab:
    section: str
    label: str
    url: str


@dataclass(frozen=True, slots=True)
class ParsedProducts:
    products: tuple[Product, ...]
    # Cards that looked like products but had no readable price.
    skipped: int


# --- parsing (pure) --------------------------------------------------------------------


def parse_poster_groups(html: str) -> list[PosterGroup]:
    """Every poster group on afisler.aspx, in page order; groups may have no usable image."""
    tree = LexborHTMLParser(html)
    nodes = tree.css("div.genelgrup")
    if not nodes:
        raise SourceError("BİM poster page has no poster groups (page layout may have changed)")
    tab_names = [_section(_text(n)) for n in tree.css(".posterArea .tabButtonArea .gButton .text")]

    groups: list[PosterGroup] = []
    for node in nodes:
        m = _GROUP_CLASS.search(node.attributes.get("class") or "")
        index = int(m.group(1)) if m else 0
        section = tab_names[index - 1] if 0 < index <= len(tab_names) else f"grup{index}"
        label_node = node.css_first(".subTabArea .text")
        label = _text(label_node) if label_node else ""
        pages: dict[str, None] = {}
        thumbs: dict[str, None] = {}
        for a in node.css("[data-bigimg]"):
            big = (a.attributes.get("data-bigimg") or "").strip()
            # Empty slots render as ".../uploads/afisler/" with no file name.
            if not _IMAGE_URL.match(big):
                continue
            pages.setdefault(big, None)
            small = (a.attributes.get("data-img") or "").strip()
            if _IMAGE_URL.match(small):
                thumbs.setdefault(small, None)
        if label:
            groups.append(PosterGroup(section, label, tuple(pages), tuple(thumbs)))
    return groups


def parse_product_tabs(html: str) -> list[ProductTab]:
    """Product tab links from the header menu; columns are the Aktüel and İndirim sections."""
    tree = LexborHTMLParser(html)
    table = tree.css_first(".aktuelsubmenu table")
    if table is None:
        return []
    headers = [_section(_text(th)) for th in table.css("th")]
    tabs: dict[str, ProductTab] = {}
    for row in table.css("tr"):
        for i, cell in enumerate(row.css("td")):
            a = cell.css_first("a[href]")
            href = (a.attributes.get("href") or "").strip() if a else ""
            label = _text(a) if a else ""
            if "Bim_AktuelTarihKey" not in href or not label:
                continue
            section = headers[i] if i < len(headers) else f"column{i + 1}"
            url = urljoin(BASE_URL, href)
            tabs.setdefault(url, ProductTab(section, label, url))
    return list(tabs.values())


def parse_products(html: str) -> ParsedProducts:
    """Priced product cards of one aktüel tab; image-only advert cards are ignored."""
    tree = LexborHTMLParser(html)
    area = tree.css_first(".productArea")
    if area is None:
        raise SourceError("BİM product page has no product area (page layout may have changed)")
    products: list[Product] = []
    skipped = 0
    for card in area.css("div.product"):
        if "justImage" in (card.attributes.get("class") or ""):
            continue
        title = card.css_first("h2.title")
        name = _text(title) if title else ""
        if not name:
            continue
        price = _card_price(card)
        if price is None:
            skipped += 1
            continue
        old = card.css_first(".priceArea .strikethrough .quantify")
        brand = card.css_first("h2.subTitle")
        quantity = card.css_first(".textArea .gramajadet")
        image = card.css_first(".imageArea img")
        link = card.css_first(".imageArea a[href]")
        products.append(
            Product(
                name=name,
                price_minor=price,
                brand=(_text(brand) if brand else "") or None,
                quantity_text=(_text(quantity).lstrip("•").strip() if quantity else "") or None,
                old_price_minor=parse_price_minor(_text(old)) if old else None,
                image=_https(_first_attr(image, "src", "xsrc", "data-src")) if image else None,
                source_url=_https(link.attributes.get("href")) if link else None,
            )
        )
    return ParsedProducts(tuple(products), skipped)


def build_brochures(
    groups: list[PosterGroup],
    tab_products: list[tuple[ProductTab, tuple[Product, ...]]],
    today: date,
    now: datetime,
) -> tuple[list[Brochure], dict[str, ProductFile]]:
    """Join posters and product tabs that share a section and a date into brochures."""
    drafts: dict[tuple[object, ...], _Draft] = {}
    for g in groups:
        draft = drafts.setdefault(_key(g.section, g.label, today), _Draft(g.section, g.label, today))
        draft.pages.extend(p for p in g.pages if p not in draft.pages)
        draft.thumbnails.extend(t for t in g.thumbnails if t not in draft.thumbnails)
    for tab, products in tab_products:
        draft = drafts.setdefault(_key(tab.section, tab.label, today), _Draft(tab.section, tab.label, today))
        draft.products.extend(products)
        draft.tab_url = draft.tab_url or tab.url

    brochures: list[Brochure] = []
    files: dict[str, ProductFile] = {}
    for draft in drafts.values():
        if not draft.pages and not draft.products:
            continue
        b = draft.to_brochure(now)
        brochures.append(b)
        if draft.products:
            files[b.id] = ProductFile(brochure_id=b.id, products=tuple(draft.products))
    return brochures, files


def bim_brochure_id(section: str, label: str, today: date) -> str:
    dates = parse_date_label(label, today)
    if dates is None:
        return brochure_id(CHAIN_ID, section, label)
    parts: list[str | date] = [section, dates.valid_from]
    if dates.valid_to != dates.valid_from:
        parts.append(dates.valid_to)
    return brochure_id(CHAIN_ID, *parts)


@dataclass(slots=True)
class _Draft:
    section: str
    label: str
    today: date
    pages: list[str] = field(default_factory=list)
    thumbnails: list[str] = field(default_factory=list)
    products: list[Product] = field(default_factory=list)
    tab_url: str | None = None

    def to_brochure(self, now: datetime) -> Brochure:
        dates = validity(self.section, self.label, self.today)
        if self.pages and self.products:
            kind = BrochureKind.BOTH
        elif self.pages:
            kind = BrochureKind.PAGES
        else:
            kind = BrochureKind.PRODUCTS
        bid = bim_brochure_id(self.section, self.label, self.today)
        cover_url = self.thumbnails[0] if self.thumbnails else (self.pages[0] if self.pages else None)
        return Brochure(
            id=bid,
            chain_id=CHAIN_ID,
            title=self.label,
            date_label=self.label,
            valid_from=dates.valid_from if dates else None,
            valid_to=dates.valid_to if dates else None,
            kind=kind,
            cover=Page(cover_url) if cover_url else None,
            pages=tuple(Page(p) for p in self.pages),
            products_url=products_path(bid) if self.products else None,
            product_count=len(self.products),
            source_url=POSTERS_URL if self.pages else (self.tab_url or POSTERS_URL),
            first_seen=now,
            updated_at=now,
        )


def known_cover_sizes(previous: Iterable[Brochure]) -> dict[str, tuple[int, int]]:
    """Cover sizes already measured in the previous run, by URL; those are not requested again."""
    return {b.cover.url: (b.cover.w, b.cover.h) for b in previous if b.cover and b.cover.w and b.cover.h}


def add_cover_sizes(
    brochures: list[Brochure],
    known: dict[str, tuple[int, int]],
    measure: Callable[[str], tuple[int, int] | None],
) -> tuple[list[Brochure], int]:
    """Fill in ``w``/``h`` of ``k_`` thumbnail covers; returns the brochures and how many stay unknown.

    Full-size posters (used as pages, or as a cover when a group has no thumbnail) are never
    measured: that would mean one more large download per poster on every new set.
    """
    sizes: dict[str, tuple[int, int] | None] = dict(known)
    out: list[Brochure] = []
    missing = 0
    for b in brochures:
        cover = b.cover
        if cover is None or cover.w is not None or not _is_thumbnail(cover.url):
            out.append(b)
            continue
        if cover.url not in sizes:
            sizes[cover.url] = measure(cover.url)
        size = sizes[cover.url]
        if size is None:
            missing += 1
            out.append(b)
        else:
            out.append(replace(b, cover=Page(cover.url, *size)))
    return out, missing


def _is_thumbnail(url: str) -> bool:
    return basename(urlsplit(url).path).startswith(THUMBNAIL_PREFIX)


def validity(section: str, label: str, today: date) -> DateRange | None:
    """Validity of a brochure: the label's dates, with one-day Aktüel starts extended."""
    dates = parse_date_label(label, today)
    if dates is not None and section == AKTUEL_SECTION and dates.valid_from == dates.valid_to:
        return DateRange(dates.valid_from, dates.valid_from + timedelta(days=AKTUEL_EXTRA_DAYS))
    return dates


def _key(section: str, label: str, today: date) -> tuple[object, ...]:
    dates = parse_date_label(label, today)
    return (section, dates) if dates else (section, fold_turkish(" ".join(label.split())))


def _section(text: str) -> str:
    folded = fold_turkish(text)
    if "indirim" in folded:
        return "indirim"
    if "aktuel" in folded:
        return AKTUEL_SECTION
    return slugify(text) or "other"


def _card_price(card: LexborNode) -> int | None:
    button = card.css_first(".priceArea a.gButton")
    if button is None:
        return None
    lira = button.css_first(".quantify")
    kurus = button.css_first(".kusurArea .number")
    if lira is None:
        return None
    return parse_price_minor(_text(lira) + (_text(kurus) if kurus else ""))


def _text(node: LexborNode) -> str:
    return " ".join(node.text(deep=True, separator=" ").split())


def _first_attr(node: LexborNode, *names: str) -> str | None:
    for name in names:
        value = (node.attributes.get(name) or "").strip()
        if value:
            return value
    return None


def _https(href: str | None) -> str | None:
    if not href:
        return None
    url = urljoin(BASE_URL, href.strip())
    return url if url.startswith("https://") and " " not in url else None


# --- network ---------------------------------------------------------------------------


class BimSource:
    chain_id = CHAIN_ID

    def collect(self, ctx: SourceContext) -> SourceResult:
        html = fetch(ctx.http, POSTERS_URL).text
        groups = parse_poster_groups(html)
        tabs = parse_product_tabs(html)
        warnings: list[str] = []
        if not tabs:
            warnings.append("no product tabs found; brochures have posters only")

        previous = ctx.previous_by_id()
        tab_products: list[tuple[ProductTab, tuple[Product, ...]]] = []
        parsed_count = skipped = reused = 0
        for tab in tabs:
            reusable = self._reusable_products(ctx, previous, tab)
            if reusable is not None:
                # Past tabs never change, so they are not downloaded again.
                tab_products.append((tab, reusable))
                reused += 1
                continue
            parsed = parse_products(fetch(ctx.http, tab.url).text)
            tab_products.append((tab, parsed.products))
            parsed_count += len(parsed.products)
            skipped += parsed.skipped

        if skipped and skipped * 2 > parsed_count + skipped:
            raise SourceError(f"{skipped} of {parsed_count + skipped} products have no readable price")
        if skipped:
            warnings.append(f"{skipped} products skipped (unreadable price)")
        if reused:
            warnings.append(f"{reused} past product tabs reused")
        brochures, files = build_brochures(groups, tab_products, ctx.today, ctx.now)
        sizes = known_cover_sizes(ctx.previous)
        brochures, missing = add_cover_sizes(brochures, sizes, lambda url: fetch_image_size(ctx.http, url))
        if missing:
            warnings.append(f"{missing} cover sizes could not be read")
        return SourceResult(brochures=brochures, product_files=files, warnings=warnings)

    @staticmethod
    def _reusable_products(
        ctx: SourceContext, previous: dict[str, Brochure], tab: ProductTab
    ) -> tuple[Product, ...] | None:
        dates = parse_date_label(tab.label, ctx.today)
        if dates is None or dates.valid_to >= ctx.today:
            return None
        old = previous.get(bim_brochure_id(tab.section, tab.label, ctx.today))
        if old is None or old.products_url is None:
            return None
        products = ctx.previous_products(old.id)
        return products.products if products else None
