from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from scraper.core.media import MediaWriter
from scraper.core.source import SourceContext, SourceError
from scraper.sources.metro import KNOWN_SLUGS, ROOT, SITEMAP_URL, MetroSource, candidate_slugs
from scraper.sources.publitas import parse_sitemap_slugs
from scraper.tests.conftest import fixture_text, mock_http

TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
WEEKLY = "profesyonel-mutfaklarin-haftalik-ihtiyaclari"
MONTHLY = "metroda-muhtesem-kasim-firsatlari"
BASICS = "isletmenizin-temel-urunleri-metroda-cok-ozel-fiyatlarla-kasim"


def _routes(*slugs: str) -> dict[str, object]:
    routes: dict[str, object] = {SITEMAP_URL: fixture_text("metro", "sitemap.xml")}
    for slug in slugs:
        routes[f"{ROOT}/{slug}/data.json"] = fixture_text("metro", f"{slug}.data.json")
        routes[f"{ROOT}/{slug}/spreads.json"] = fixture_text("metro", f"{slug}.spreads.json")
    return routes


def _ctx(http, tmp_path, today: date = TODAY) -> SourceContext:
    return SourceContext(http=http, today=today, now=NOW, media=MediaWriter(tmp_path, None))


def test_candidates_are_fixed_slugs_plus_nearby_months_without_the_magazine() -> None:
    slugs = parse_sitemap_slugs(fixture_text("metro", "sitemap.xml"), ROOT)
    assert len(slugs) == 198
    assert candidate_slugs(slugs, TODAY) == [*KNOWN_SLUGS, BASICS]
    # "sayi" issues name the quarter's months too, but are never candidates.
    assert not any(s.startswith("sayi-") for s in candidate_slugs(slugs, date(2026, 12, 3)))
    assert len(candidate_slugs([f"x-kasim-{i}" for i in range(40)], TODAY)) == 12


def test_collect_takes_recent_publications(tmp_path) -> None:
    calls: list[str] = []
    result = MetroSource().collect(_ctx(mock_http(_routes(WEEKLY, MONTHLY, BASICS), calls), tmp_path))
    weekly, monthly, basics = result.brochures
    assert weekly.id == "metro-profesyonel-mutfaklarin-haftalik-ihtiyaclari-2719513-322792"
    assert (weekly.valid_from, weekly.valid_to, weekly.date_label) == (date(2026, 11, 11), None, None)
    assert (monthly.valid_from, monthly.valid_to) == (date(2026, 11, 1), date(2026, 11, 30))
    assert monthly.title == "Metro'da Muhteşem Kasım Fırsatları"
    assert (len(weekly.pages), len(monthly.pages), len(basics.pages)) == (4, 3, 10)
    assert (monthly.pages[0].w, monthly.pages[0].h) == (1800, 3200)
    assert len(calls) == 1 + 3 * 2 and calls[0] == SITEMAP_URL


def test_a_missing_fixed_slug_is_skipped_without_a_warning(tmp_path) -> None:
    result = MetroSource().collect(_ctx(mock_http(_routes(WEEKLY, BASICS)), tmp_path))
    assert len(result.brochures) == 2 and result.warnings == []


def test_publications_older_than_45_days_are_left_out(tmp_path) -> None:
    # Weekly is dated 11 Nov, basics 13 Nov, monthly 11 Nov: on 1 Jan all are older than 45 days.
    routes = _routes(WEEKLY, MONTHLY, BASICS)
    with pytest.raises(SourceError, match="no publication"):
        MetroSource().collect(_ctx(mock_http(routes), tmp_path, date(2027, 1, 1)))


def test_nothing_found_is_a_source_error(tmp_path) -> None:
    with pytest.raises(SourceError, match="no publication"):
        MetroSource().collect(_ctx(mock_http({SITEMAP_URL: fixture_text("metro", "sitemap.xml")}), tmp_path))


def test_a_broken_sitemap_still_uses_the_fixed_slugs(tmp_path) -> None:
    routes = _routes(WEEKLY)
    routes[SITEMAP_URL] = (500, "oops")
    result = MetroSource().collect(_ctx(mock_http(routes), tmp_path))
    assert len(result.brochures) == 1 and "sitemap unavailable" in result.warnings[0]


def test_changed_content_under_the_same_slug_is_a_new_brochure(tmp_path) -> None:
    routes = _routes(WEEKLY)
    first = MetroSource().collect(_ctx(mock_http(routes), tmp_path)).brochures[0]
    routes[f"{ROOT}/{WEEKLY}/data.json"] = routes[f"{ROOT}/{WEEKLY}/data.json"].replace(
        "ODk0ZWM4YzhkOThkNDkx", "QUFBQUFBQUFBQUFBQUFB"
    )
    second = MetroSource().collect(_ctx(mock_http(routes), tmp_path)).brochures[0]
    assert first.id != second.id and first.pages == second.pages
