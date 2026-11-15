from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from scraper.core.media import MediaWriter
from scraper.core.source import SourceContext, SourceError
from scraper.sources.watsons import ROOT, SITEMAP_URL, WatsonsSource
from scraper.tests.conftest import fixture_text, mock_http

TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
SLUG = "kasim-katalog-2026"


def _routes() -> dict[str, object]:
    return {
        SITEMAP_URL: fixture_text("watsons", "sitemap.xml"),
        f"{ROOT}/{SLUG}/data.json": fixture_text("watsons", f"{SLUG}.data.json"),
        f"{ROOT}/{SLUG}/spreads.json": fixture_text("watsons", f"{SLUG}.spreads.json"),
    }


def _ctx(http, tmp_path) -> SourceContext:
    return SourceContext(http=http, today=TODAY, now=NOW, media=MediaWriter(tmp_path, None))


def test_collect(tmp_path) -> None:
    calls: list[str] = []
    (b,) = WatsonsSource().collect(_ctx(mock_http(_routes(), calls), tmp_path)).brochures
    assert b.id == "watsons-kasim-katalog-2026-3499121"
    assert (b.valid_from, b.valid_to) == (date(2026, 11, 1), date(2026, 11, 30))
    assert len(b.pages) == 46 and b.source_url == f"{ROOT}/{SLUG}/"
    assert calls == [SITEMAP_URL, f"{ROOT}/{SLUG}/data.json", f"{ROOT}/{SLUG}/spreads.json"]


def test_a_changed_cache_token_does_not_change_the_id(tmp_path) -> None:
    routes = _routes()
    first = WatsonsSource().collect(_ctx(mock_http(routes), tmp_path)).brochures[0]
    key = f"{ROOT}/{SLUG}/data.json"
    routes[key] = routes[key].replace("ZWI0NTlkMGUz", "QUFBQUFBQUFB")
    assert WatsonsSource().collect(_ctx(mock_http(routes), tmp_path)).brochures[0].id == first.id


def test_missing_sitemap_is_a_source_error(tmp_path) -> None:
    with pytest.raises(SourceError, match="HTTP 404"):
        WatsonsSource().collect(_ctx(mock_http({}), tmp_path))


def test_empty_sitemap_is_a_source_error(tmp_path) -> None:
    with pytest.raises(SourceError, match="sitemap"):
        WatsonsSource().collect(_ctx(mock_http({SITEMAP_URL: "<urlset/>"}), tmp_path))
