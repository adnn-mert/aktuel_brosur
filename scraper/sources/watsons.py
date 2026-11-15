"""Watsons: monthly catalogue published with Publitas at katalog.watsons.com.tr.

The sitemap lists the current catalogue(s); each one is read from its ``data.json`` and
``spreads.json``. Pages are linked directly.
"""

from __future__ import annotations

from scraper.core.models import Brochure
from scraper.core.source import SourceContext, SourceError, SourceResult, fetch
from scraper.sources.publitas import (
    Publication,
    parse_publication,
    parse_sitemap_slugs,
    publication_brochure,
)

CHAIN_ID = "watsons"
ROOT = "https://katalog.watsons.com.tr"
SITEMAP_URL = f"{ROOT}/sitemap.xml"
# The sitemap normally holds one catalogue; a cap keeps a changed site from costing dozens of requests.
MAX_PUBLICATIONS = 4


class WatsonsSource:
    chain_id = CHAIN_ID

    def collect(self, ctx: SourceContext) -> SourceResult:
        slugs = parse_sitemap_slugs(fetch(ctx.http, SITEMAP_URL).text, ROOT)[:MAX_PUBLICATIONS]
        brochures: list[Brochure] = []
        for slug in slugs:
            data = fetch(ctx.http, f"{ROOT}/{slug}/data.json").text
            spreads = fetch(ctx.http, f"{ROOT}/{slug}/spreads.json").text
            pub: Publication = parse_publication(slug, data, spreads)
            brochures.append(
                publication_brochure(CHAIN_ID, pub, source_url=f"{ROOT}/{slug}/", today=ctx.today, now=ctx.now, token_in_id=False)
            )
        if not brochures:
            raise SourceError("Watsons sitemap yielded no catalogues")
        return SourceResult(brochures=brochures)
