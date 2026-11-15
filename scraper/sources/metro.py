"""Metro: weekly brochures published with Publitas at brosurler.metro-tr.com.

The site's own listing service is unusable, so candidates come from two places: a fixed
list of slugs Metro reuses every week (the content behind a slug changes, which the
publication's ``cacheToken`` reveals) and the sitemap, narrowed to slugs naming the current
or an adjacent month. The quarterly "Metro Gastro" magazine ("sayi" slugs) is not taken.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, timedelta

import httpx

from scraper.core.models import Brochure
from scraper.core.source import SourceContext, SourceError, SourceResult, fetch
from scraper.core.text import fold_turkish
from scraper.sources.publitas import (
    TURKISH_MONTHS,
    data_source_date,
    parse_publication,
    parse_sitemap_slugs,
    publication_brochure,
)

CHAIN_ID = "metro"
ROOT = "https://brosurler.metro-tr.com"
SITEMAP_URL = f"{ROOT}/sitemap.xml"
WEB_URL = "https://www.metro-tr.com/promosyonlar"
KNOWN_SLUGS = (
    "profesyonel-mutfaklarin-haftalik-ihtiyaclari",
    "metroda-muhtesem-kasim-firsatlari",
)
MAX_CHECKED = 12
MAX_AGE_DAYS = 45
MAGAZINE_WORD = "sayi"
_MONTH_SUFFIX = re.compile(r"\s*\|\s*([^|]+?)\s*$")


def clean_title(title: str) -> str:
    """Drop a trailing " | Kasım" style month suffix (any Turkish month, optional year).

    The month is already shown as the brochure's dates; only the display title changes,
    never the id or the validity.
    """
    m = _MONTH_SUFFIX.search(title)
    if not m:
        return title
    words = fold_turkish(m.group(1)).split()
    if words and words[0] in TURKISH_MONTHS and (len(words) == 1 or (len(words) == 2 and words[1].isdigit())):
        return title[: m.start()].rstrip() or title
    return title


def candidate_slugs(sitemap_slugs: list[str], today: date) -> list[str]:
    """Slugs worth a ``data.json`` request: the fixed ones, then sitemap slugs naming a nearby month."""
    months = {TURKISH_MONTHS[(today.month - 1 + delta) % 12] for delta in (-1, 0, 1)}
    chosen: dict[str, None] = dict.fromkeys(KNOWN_SLUGS)
    for slug in sitemap_slugs:
        tokens = set(fold_turkish(slug).replace("_", "-").split("-"))
        if MAGAZINE_WORD in tokens or not tokens & months:
            continue
        chosen.setdefault(slug, None)
    return list(chosen)[:MAX_CHECKED]


class MetroSource:
    chain_id = CHAIN_ID

    def collect(self, ctx: SourceContext) -> SourceResult:
        warnings: list[str] = []
        try:
            sitemap = parse_sitemap_slugs(fetch(ctx.http, SITEMAP_URL).text, ROOT)
        except (SourceError, httpx.HTTPError) as exc:
            warnings.append(f"sitemap unavailable, fixed slugs only: {exc}")
            sitemap = []
        oldest = ctx.today - timedelta(days=MAX_AGE_DAYS)
        brochures: list[Brochure] = []
        for slug in candidate_slugs(sitemap, ctx.today):
            try:
                response = ctx.http.get(f"{ROOT}/{slug}/data.json")
                if response.status_code == 404:
                    continue  # a fixed slug that is not published right now
                if response.status_code != 200:
                    warnings.append(f"{slug}: HTTP {response.status_code}")
                    continue
                source_date = data_source_date(response.text)
                if source_date is None or source_date < oldest:
                    continue
                spreads = fetch(ctx.http, f"{ROOT}/{slug}/spreads.json").text
                pub = parse_publication(slug, response.text, spreads)
            except (SourceError, httpx.HTTPError) as exc:
                warnings.append(f"{slug}: {exc}")
                continue
            brochure = publication_brochure(CHAIN_ID, pub, source_url=f"{ROOT}/{slug}/", today=ctx.today, now=ctx.now)
            brochures.append(replace(brochure, title=clean_title(brochure.title)))
        if not brochures:
            raise SourceError(f"Metro: no publication found among {MAX_CHECKED} checked slugs; {'; '.join(warnings)}")
        return SourceResult(brochures=brochures, warnings=warnings)
