"""Hakmar: the "İndirim" page shows one image carousel per campaign, under a date heading.

Every carousel is one brochure; its slides are the pages in page order. Slides link the
full image directly (the ``-scaled`` file where WordPress made one), so nothing is copied.
The cover is the 768 px copy WordPress shows in the carousel; its size is in the file name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from posixpath import basename, splitext
from urllib.parse import unquote, urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from scraper.core.dates import parse_date_label
from scraper.core.ids import brochure_id
from scraper.core.models import Brochure, BrochureKind, Page
from scraper.core.source import SourceContext, SourceError, SourceResult, fetch

CHAIN_ID = "hakmar"
PAGE_URL = "https://hakmar.com.tr/indirim/"

_IMAGE = re.compile(r"\.(?:jpe?g|png|webp)$", re.IGNORECASE)
_SIZE_SUFFIX = re.compile(r"-(\d+)x(\d+)$")


@dataclass(frozen=True, slots=True)
class HakmarGroup:
    heading: str
    pages: tuple[str, ...]
    cover: Page | None


# --- parsing (pure) --------------------------------------------------------------------


def parse_groups(html: str) -> list[HakmarGroup]:
    """Campaign carousels in page order; a heading without images is ignored."""
    tree = LexborHTMLParser(html)
    groups: list[HakmarGroup] = []
    for heading in tree.css("h2.elementor-heading-title"):
        container = _carousel_container(heading)
        if container is None:
            continue
        pages: dict[str, None] = {}
        thumb: str | None = None
        for link in container.css(".swiper-slide a[href]"):
            href = (link.attributes.get("href") or "").strip()
            if not _IMAGE.search(urlsplit(href).path):
                continue
            url = urljoin(PAGE_URL, href)
            if url not in pages and thumb is None:
                img = link.css_first("img[src]")
                thumb = urljoin(PAGE_URL, img.attributes.get("src") or "") if img else None
            pages.setdefault(url, None)
        text = " ".join(heading.text(deep=True).split())
        if pages and text:
            groups.append(HakmarGroup(text, tuple(pages), _cover(thumb, next(iter(pages)))))
    if not groups:
        raise SourceError("Hakmar page has no campaign carousels (page layout may have changed)")
    return groups


def group_brochure(group: HakmarGroup, today: date, now: datetime) -> Brochure:
    dates = parse_date_label(group.heading, today) or parse_date_label(_stem(group.pages[0]), today)
    parts: list[str | date] = [dates.valid_from] if dates else [_stem(group.pages[0])]
    return Brochure(
        id=brochure_id(CHAIN_ID, *parts, group.heading),
        chain_id=CHAIN_ID,
        title=group.heading,
        date_label=group.heading,
        valid_from=dates.valid_from if dates else None,
        valid_to=dates.valid_to if dates else None,
        kind=BrochureKind.PAGES,
        cover=group.cover,
        pages=tuple(Page(url) for url in group.pages),
        products_url=None,
        product_count=0,
        source_url=PAGE_URL,
        first_seen=now,
        updated_at=now,
    )


def _carousel_container(heading: LexborNode) -> LexborNode | None:
    """The nearest ancestor that also holds the heading's carousel."""
    node = heading.parent
    while node is not None and node.tag not in ("body", "html"):
        if node.css_first(".swiper-slide") is not None:
            return node
        node = node.parent
    return None


def _cover(thumb: str | None, first_page: str) -> Page:
    if thumb:
        m = _SIZE_SUFFIX.search(splitext(basename(urlsplit(thumb).path))[0])
        if m:
            return Page(thumb, int(m.group(1)), int(m.group(2)))
    return Page(first_page)


def _stem(url: str) -> str:
    return splitext(basename(unquote(urlsplit(url).path)))[0]


# --- network ---------------------------------------------------------------------------


class HakmarSource:
    chain_id = CHAIN_ID

    def collect(self, ctx: SourceContext) -> SourceResult:
        groups = parse_groups(fetch(ctx.http, PAGE_URL).text)
        return SourceResult(brochures=[group_brochure(g, ctx.today, ctx.now) for g in groups])
