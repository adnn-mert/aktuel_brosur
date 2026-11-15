"""Shared adapter for Publitas publications (Watsons, Metro).

A publication lives at ``<root>/<slug>/``; ``data.json`` describes it (id, page count,
``cacheToken``, per-size pixel dimensions) and ``spreads.json`` lists its pages as images
named ``at200`` ... ``at2400`` (paths relative to ``https://view.publitas.com``). Pages are
linked directly, nothing is copied. Everything here is pure; the sources do the downloading.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlsplit

from scraper.core.dates import parse_date_label
from scraper.core.ids import brochure_id
from scraper.core.models import Brochure, BrochureKind, Page
from scraper.core.source import SourceError
from scraper.core.text import fold_turkish

IMAGE_ROOT = "https://view.publitas.com"
PAGE_SIZE_KEY = "at2400"
COVER_SIZE_KEY = "at600"

_SIZE_KEY = re.compile(r"^at(\d+)$")
_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_YEAR = re.compile(r"(?<!\d)(20\d\d)(?!\d)")
_ENGLISH_MONTHS = (
    "january february march april may june july august september october november december".split()
)
# "November 11, 2026 12:33": Publitas always prints the source document time in English.
_SOURCE_DATE = re.compile(r"^\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})")
TURKISH_MONTHS = "ocak subat mart nisan mayis haziran temmuz agustos eylul ekim kasim aralik".split()
_TURKISH_MONTH = re.compile(r"(?<![a-z])(" + "|".join(TURKISH_MONTHS) + r")(?![a-z])")


@dataclass(frozen=True, slots=True)
class Publication:
    slug: str
    publication_id: int
    cache_token: str
    title: str
    source_date: date | None
    cover: Page | None
    pages: tuple[Page, ...]


# --- parsing (pure) --------------------------------------------------------------------


def parse_sitemap_slugs(xml: str, root: str) -> list[str]:
    """First path segments of the sitemap's ``<loc>`` entries under ``root``, in order, unique."""
    host = urlsplit(root).netloc
    slugs: dict[str, None] = {}
    for loc in _LOC.findall(xml):
        parts = urlsplit(loc)
        segments = [s for s in parts.path.split("/") if s]
        if parts.netloc == host and len(segments) == 1:
            slugs.setdefault(segments[0], None)
    if not slugs:
        raise SourceError(f"{root} sitemap lists no publications (format may have changed)")
    return list(slugs)


def parse_source_date(text: str | None) -> date | None:
    """Date of ``sourceDocumentTitle`` ("November 11, 2026 12:33"); None when it is not that shape."""
    m = _SOURCE_DATE.match(text or "")
    if not m or m.group(1).lower() not in _ENGLISH_MONTHS:
        return None
    try:
        return date(int(m.group(3)), _ENGLISH_MONTHS.index(m.group(1).lower()) + 1, int(m.group(2)))
    except ValueError:
        return None


def data_source_date(data_text: str) -> date | None:
    """Source document date of a ``data.json`` body; None when unreadable."""
    try:
        data = json.loads(data_text)
    except ValueError:
        return None
    return parse_source_date(data.get("sourceDocumentTitle")) if isinstance(data, dict) else None


def month_label(text: str) -> str | None:
    """"Kasım 2026" style label for text naming a month (and maybe a year); None without a month.

    The year is carried over when the text has one: a "kasim-katalog-2026" slug must not
    turn into next year's November just because the page is still listed a year later.
    """
    folded = fold_turkish(text)
    m = _TURKISH_MONTH.search(folded)
    if not m:
        return None
    year = _YEAR.search(folded)
    return f"{m.group(1)} {year.group(1)}" if year else m.group(1)


def parse_publication(slug: str, data_text: str, spreads_text: str) -> Publication:
    """A publication from its ``data.json`` and ``spreads.json`` bodies."""
    data = _load(data_text, f"{slug}/data.json")
    spreads = _load(spreads_text, f"{slug}/spreads.json")
    if not isinstance(data, dict) or not isinstance(spreads, list):
        raise SourceError(f"Publitas {slug} has unexpected JSON (format may have changed)")
    pub_id = data.get("id")
    token = data.get("cacheToken")
    if not isinstance(pub_id, int) or not isinstance(token, str) or not token:
        raise SourceError(f"Publitas {slug} data.json has no id / cacheToken (format may have changed)")
    sizes = data.get("sizes") if isinstance(data.get("sizes"), dict) else {}

    pages: list[Page] = []
    first_images: dict[str, str] | None = None
    for spread in spreads:
        for page in spread.get("pages", []) if isinstance(spread, dict) else []:
            images = page.get("images") if isinstance(page, dict) else None
            if not isinstance(images, dict):
                continue
            key = _pick_key(images, PAGE_SIZE_KEY, prefer_larger=True)
            if key is None:
                continue
            if first_images is None:
                first_images = images
            pages.append(_page(images[key], sizes.get(key)))
    if not pages or first_images is None:
        raise SourceError(f"Publitas {slug} has no page images (format may have changed)")
    cover_key = _pick_key(first_images, COVER_SIZE_KEY, prefer_larger=False)
    assert cover_key is not None
    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    return Publication(
        slug=slug,
        publication_id=pub_id,
        cache_token=token,
        title=_title(config, slug),
        source_date=parse_source_date(data.get("sourceDocumentTitle")),
        cover=_page(first_images[cover_key], sizes.get(cover_key)),
        pages=tuple(pages),
    )


def publication_brochure_id(chain_id: str, pub: Publication, *, with_token: bool = True) -> str:
    """Stable id that changes when the content does.

    Metro republishes its weekly brochure under the same slug; ``cacheToken`` changes with
    the content, so a changed publication becomes a new brochure.
    """
    if not with_token:
        return brochure_id(chain_id, pub.slug, pub.publication_id)
    digest = hashlib.sha256(pub.cache_token.encode("utf-8")).hexdigest()[:6]
    return brochure_id(chain_id, pub.slug, pub.publication_id, digest)


def publication_brochure(
    chain_id: str, pub: Publication, *, source_url: str, today: date, now: datetime, token_in_id: bool = True
) -> Brochure:
    """The brochure for ``pub``.

    Dates come from a month named in the slug or title ("kasim-katalog-2026"); without one the
    validity starts on the source document's date and has no end, and ``date_label`` stays
    empty: nothing is guessed. ``token_in_id=False`` is for publications whose slug already
    names the month (Watsons): their ``cacheToken`` changed from one day to the next without
    any visible change, which would otherwise publish the same catalogue twice.
    """
    dates = None
    for text in (pub.title, pub.slug):
        label = month_label(text)
        if label and (dates := parse_date_label(label, today)):
            break
    valid_from = dates.valid_from if dates else pub.source_date
    return Brochure(
        id=publication_brochure_id(chain_id, pub, with_token=token_in_id),
        chain_id=chain_id,
        title=pub.title,
        date_label=None,
        valid_from=valid_from,
        valid_to=dates.valid_to if dates else None,
        kind=BrochureKind.PAGES,
        cover=pub.cover,
        pages=pub.pages,
        products_url=None,
        product_count=0,
        source_url=source_url,
        first_seen=now,
        updated_at=now,
    )


# --- helpers ---------------------------------------------------------------------------


def _load(text: str, what: str):
    try:
        return json.loads(text)
    except ValueError as exc:
        raise SourceError(f"Publitas {what} is not JSON (format may have changed)") from exc


def _pick_key(images: dict[str, str], wanted: str, *, prefer_larger: bool) -> str | None:
    """``wanted`` if present, else the nearest size on the preferred side, else any size."""
    sizes = {int(m.group(1)): k for k in images if (m := _SIZE_KEY.match(k)) and isinstance(images[k], str)}
    if not sizes:
        return None
    if wanted in images and isinstance(images[wanted], str):
        return wanted
    target = int(wanted[2:])
    smaller = [s for s in sizes if s < target]
    larger = [s for s in sizes if s > target]
    # Pages: the biggest available. Cover: the closest below, else the smallest above.
    if prefer_larger:
        return sizes[max(sizes)]
    if smaller:
        return sizes[max(smaller)]
    return sizes[min(larger)]


def _page(path: str, size) -> Page:
    url = path if "://" in path else IMAGE_ROOT + (path if path.startswith("/") else "/" + path)
    if isinstance(size, dict) and isinstance(size.get("width"), int) and isinstance(size.get("height"), int):
        return Page(url, size["width"], size["height"])
    return Page(url)


def _title(config: dict, slug: str) -> str:
    raw = config.get("publicationOriginalTitle") or config.get("publicationTitle") or ""
    title = " ".join(str(raw).split())
    # Metro prefixes every title with its brand ("METRO TR - ...").
    title = re.sub(r"^METRO TR\s*-\s*", "", title, flags=re.IGNORECASE)
    return title or slug.replace("-", " ").capitalize()
