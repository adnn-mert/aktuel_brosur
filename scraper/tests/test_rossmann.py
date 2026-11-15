from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from scraper.core.media import MediaWriter
from scraper.core.source import SourceContext, SourceError
from scraper.sources.rossmann import (
    LIST_URL,
    CatalogRef,
    RossmannSource,
    catalog_brochure,
    current_refs,
    parse_catalog_refs,
    parse_settings,
)
from scraper.tests.conftest import fixture_text, mock_http

TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
NOVEMBER = [
    "kasim-guzellik-katalogu",
    "kasim-kisisel-bakim-katalogu",
    "kasim-ev-ve-yasam-katalogu",
    "temizlik-festivali-katalogu",
    "trends-for-you",
]
BASE = "https://katalog.rossmann.com.tr/2026/11-kasim"


def _list() -> str:
    return fixture_text("rossmann", "kataloglar.html")


def test_list_page_refs_are_unique_and_in_page_order() -> None:
    refs = parse_catalog_refs(_list())
    assert len(refs) == 9  # the cleaning festival is embedded twice (desktop and mobile)
    assert [r.slug for r in refs[:5]] == NOVEMBER
    assert refs[0].url == f"{BASE}/kasim-guzellik-katalogu/"


def test_only_this_and_the_previous_month_are_taken() -> None:
    refs = parse_catalog_refs(_list())
    assert [r.slug for r in current_refs(refs, TODAY)] == NOVEMBER  # the September ones are dropped
    assert [r.month for r in current_refs(refs, date(2026, 10, 3))] == [9, 9, 9, 9]
    assert len(current_refs([CatalogRef(2026, 11, "kasim", f"s{i}") for i in range(20)], TODAY)) == 10
    assert [r.year for r in current_refs([CatalogRef(2025, 12, "aralik", "x")], date(2026, 1, 5))] == [2025]


def test_settings_and_brochure() -> None:
    ref = parse_catalog_refs(_list())[0]
    settings = parse_settings(fixture_text("rossmann", f"{ref.slug}.html"))
    assert (settings.title, len(settings.pages), settings.normal, settings.zoom) == (
        "Kasim Guzellik Katalogu",
        26,
        (707, 990),
        (1149, 1609),
    )
    b = catalog_brochure(ref, settings, TODAY, NOW)
    assert b.id == "rossmann-2026-11-kasim-guzellik-katalogu"
    assert (b.valid_from, b.valid_to, b.date_label) == (date(2026, 11, 1), date(2026, 11, 30), "Kasım 2026")
    assert b.pages[0].url == f"{BASE}/kasim-guzellik-katalogu/Image.ashx?PageNumber=1&ImageType=Zoom"
    assert b.pages[-1].url.endswith("Image.ashx?PageNumber=26&ImageType=Zoom")
    assert (b.pages[0].w, b.pages[0].h) == (1149, 1609)
    assert b.cover is not None
    assert (b.cover.url, b.cover.w, b.cover.h) == (
        f"{BASE}/kasim-guzellik-katalogu/Image.ashx?PageNumber=1&ImageType=Normal",
        707,
        990,
    )
    # Only the permanent redirecting address is stored, never a signed CDN address.
    assert all("Image.ashx" in p.url and "cdn" not in p.url for p in b.pages)


def test_catalogue_with_other_image_sizes() -> None:
    settings = parse_settings(fixture_text("rossmann", "temizlik-festivali-katalogu.html"))
    assert (settings.zoom, settings.normal) == ((1143, 1617), (703, 995))


@pytest.mark.parametrize("html", ["", "<html><body><iframe src='https://example.com/x/'></iframe></body></html>"])
def test_unrelated_list_page_raises(html: str) -> None:
    with pytest.raises(SourceError, match="layout"):
        parse_catalog_refs(html)


def test_unrelated_catalogue_page_raises() -> None:
    with pytest.raises(SourceError, match="layout"):
        parse_settings("<html><body>nothing</body></html>")


def _routes() -> dict[str, object]:
    routes: dict[str, object] = {LIST_URL: _list()}
    for slug in NOVEMBER:
        routes[f"{BASE}/{slug}/"] = fixture_text("rossmann", f"{slug}.html")
    return routes


def test_collect_makes_one_request_per_catalogue(tmp_path) -> None:
    calls: list[str] = []
    ctx = SourceContext(http=mock_http(_routes(), calls), today=TODAY, now=NOW, media=MediaWriter(tmp_path, None))
    result = RossmannSource().collect(ctx)
    assert [b.title for b in result.brochures][-1] == "Trends for You"
    assert [len(b.pages) for b in result.brochures] == [26, 34, 18, 26, 14]
    assert len(calls) == 1 + 5 and len(set(calls)) == 6


def test_old_catalogues_only_is_a_source_error(tmp_path) -> None:
    ctx = SourceContext(
        http=mock_http(_routes()), today=date(2027, 3, 1), now=NOW, media=MediaWriter(tmp_path, None)
    )
    with pytest.raises(SourceError, match="no catalogue"):
        RossmannSource().collect(ctx)
