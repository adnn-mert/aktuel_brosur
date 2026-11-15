"""Rossmann: iPaper catalogues listed on rossmann.com.tr/kataloglar.

The list page embeds one iPaper viewer per catalogue (``viewer.ipaper.io/rossmann-tr/2026/11-kasim/<slug>/``);
the same path under ``katalog.rossmann.com.tr`` is a plain page whose embedded JSON settings
give the title, the page numbers and the image sizes. Page images are the permanent
``Image.ashx`` addresses (they redirect to a signed CDN address; the signed one is never
stored). The only date is the month in the path. Only the current and the previous month
are taken: older catalogues stay on the list page for a long time.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime

from selectolax.lexbor import LexborHTMLParser

from scraper.core.dates import month_name, parse_date_label
from scraper.core.ids import brochure_id
from scraper.core.models import Brochure, BrochureKind, Page
from scraper.core.source import SourceContext, SourceError, SourceResult, fetch

CHAIN_ID = "rossmann"
LIST_URL = "https://www.rossmann.com.tr/kataloglar"
CATALOG_ROOT = "https://katalog.rossmann.com.tr"
MAX_CATALOGS = 10

_VIEWER = re.compile(r"viewer\.ipaper\.io/rossmann-tr/(\d{4})/(\d{1,2})-([a-z]+)/([a-z0-9-]+)/", re.IGNORECASE)
_PAGE_TITLE = re.compile(r'"pageTitle":("(?:[^"\\]|\\.)*")')
_PAGES = re.compile(r'"pages":(\[[0-9,\s]*\])')
_IMAGE = re.compile(
    r'"normalWidth":(\d+),"normalHeight":(\d+),"thumbWidth":\d+,"zoomWidth":(\d+),"zoomHeight":(\d+)'
)


@dataclass(frozen=True, slots=True)
class CatalogRef:
    year: int
    month: int
    month_name: str
    slug: str

    @property
    def url(self) -> str:
        return f"{CATALOG_ROOT}/{self.year}/{self.month}-{self.month_name}/{self.slug}/"


@dataclass(frozen=True, slots=True)
class CatalogSettings:
    title: str
    pages: tuple[int, ...]
    normal: tuple[int, int]
    zoom: tuple[int, int]


# --- parsing (pure) --------------------------------------------------------------------


def parse_catalog_refs(html: str) -> list[CatalogRef]:
    """Catalogues embedded on the list page, in page order, each once."""
    tree = LexborHTMLParser(html)
    refs: dict[tuple[int, int, str], CatalogRef] = {}
    for frame in tree.css("iframe[src]"):
        m = _VIEWER.search(frame.attributes.get("src") or "")
        if not m:
            continue
        ref = CatalogRef(int(m.group(1)), int(m.group(2)), m.group(3).lower(), m.group(4).lower())
        refs.setdefault((ref.year, ref.month, ref.slug), ref)
    if not refs:
        raise SourceError("Rossmann list page embeds no iPaper catalogues (page layout may have changed)")
    return list(refs.values())


def current_refs(refs: list[CatalogRef], today: date) -> list[CatalogRef]:
    """Catalogues of this month and the previous one, at most ``MAX_CATALOGS``."""
    previous = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    keep = {(today.year, today.month), previous}
    return [r for r in refs if (r.year, r.month) in keep][:MAX_CATALOGS]


def parse_settings(html: str) -> CatalogSettings:
    """Title, page numbers and image sizes from the JSON settings embedded in a catalogue page."""
    title = _PAGE_TITLE.search(html)
    pages = _PAGES.search(html)
    image = _IMAGE.search(html)
    if not (title and pages and image):
        raise SourceError("Rossmann catalogue page has no settings (page layout may have changed)")
    numbers = tuple(int(n) for n in json.loads(pages.group(1)))
    if not numbers:
        raise SourceError("Rossmann catalogue lists no pages (page layout may have changed)")
    nw, nh, zw, zh = (int(g) for g in image.groups())
    return CatalogSettings(" ".join(json.loads(title.group(1)).split()), numbers, (nw, nh), (zw, zh))


def image_url(ref: CatalogRef, page: int, kind: str) -> str:
    """The permanent redirecting address of a page image (``kind``: "Zoom" or "Normal")."""
    return f"{ref.url}Image.ashx?PageNumber={page}&ImageType={kind}"


def catalog_brochure(ref: CatalogRef, settings: CatalogSettings, today: date, now: datetime) -> Brochure:
    dates = parse_date_label(f"{ref.month_name} {ref.year}", today)
    if dates is None:
        raise SourceError(f"Rossmann catalogue path has an unreadable month: {ref.url}")
    cover = Page(image_url(ref, settings.pages[0], "Normal"), *settings.normal)
    return Brochure(
        id=brochure_id(CHAIN_ID, ref.year, ref.month, ref.slug),
        chain_id=CHAIN_ID,
        title=settings.title,
        # The month is the only date there is; a range label would claim more than the page says.
        date_label=f"{month_name(dates.valid_from.month)} {ref.year}",
        valid_from=dates.valid_from,
        valid_to=dates.valid_to,
        kind=BrochureKind.PAGES,
        cover=cover,
        pages=tuple(Page(image_url(ref, n, "Zoom"), *settings.zoom) for n in settings.pages),
        products_url=None,
        product_count=0,
        source_url=ref.url,
        first_seen=now,
        updated_at=now,
    )


# --- network ---------------------------------------------------------------------------


class RossmannSource:
    chain_id = CHAIN_ID

    def collect(self, ctx: SourceContext) -> SourceResult:
        refs = current_refs(parse_catalog_refs(fetch(ctx.http, LIST_URL).text), ctx.today)
        if not refs:
            raise SourceError("Rossmann list page has no catalogue of this or the previous month")
        brochures = [
            catalog_brochure(ref, parse_settings(fetch(ctx.http, ref.url).text), ctx.today, ctx.now) for ref in refs
        ]
        return SourceResult(brochures=brochures)
