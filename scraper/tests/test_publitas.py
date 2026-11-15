from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from scraper.core.source import SourceError
from scraper.sources.publitas import (
    month_label,
    parse_publication,
    parse_sitemap_slugs,
    parse_source_date,
    publication_brochure,
    publication_brochure_id,
)
from scraper.tests.conftest import fixture_text

TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
SLUG = "kasim-katalog-2026"


def _watsons():
    return parse_publication(
        SLUG, fixture_text("watsons", f"{SLUG}.data.json"), fixture_text("watsons", f"{SLUG}.spreads.json")
    )


def test_pages_use_the_largest_image_and_data_json_sizes() -> None:
    pub = _watsons()
    assert len(pub.pages) == 46  # 24 spreads, one or two pages each
    assert pub.pages[0].url == (
        "https://view.publitas.com/223/3499121/pages/6b75122a-dd8b-4c63-abd2-544cfda8506c-at2400.jpg"
    )
    assert (pub.pages[0].w, pub.pages[0].h) == (1960, 2940)
    assert pub.pages[-1].url.endswith("8bc2700c-5fe8-4885-a31b-7961568a835c-at2400.jpg")


def test_cover_is_the_600_px_image_of_the_first_page() -> None:
    pub = _watsons()
    assert pub.cover is not None
    assert pub.cover.url.endswith("6b75122a-dd8b-4c63-abd2-544cfda8506c-at600.jpg")
    assert (pub.cover.w, pub.cover.h) == (490, 735)


def test_missing_sizes_fall_back_to_the_nearest_available() -> None:
    data = json.dumps({"id": 1, "cacheToken": "t", "sizes": {}, "config": {}})
    images = {"at200": "/a-at200.jpg", "at1600": "/a-at1600.jpg", "at1000": "/a-at1000.jpg"}
    pub = parse_publication("x", data, json.dumps([{"pages": [{"images": images}]}]))
    assert pub.pages[0].url == "https://view.publitas.com/a-at1600.jpg"
    assert pub.cover is not None and pub.cover.url.endswith("a-at200.jpg")
    assert pub.pages[0].w is None and pub.cover.w is None  # unknown sizes stay null
    only_big = json.dumps([{"pages": [{"images": {"at1000": "/b-at1000.jpg"}}]}])
    cover = parse_publication("x", data, only_big).cover
    assert cover is not None and cover.url.endswith("b-at1000.jpg")


def test_brochure_id_changes_with_the_cache_token() -> None:
    data = json.loads(fixture_text("watsons", f"{SLUG}.data.json"))
    spreads = fixture_text("watsons", f"{SLUG}.spreads.json")
    first = parse_publication(SLUG, json.dumps(data), spreads)
    assert publication_brochure_id("watsons", first) == publication_brochure_id("watsons", _watsons())
    data["cacheToken"] = "another-token"
    changed = parse_publication(SLUG, json.dumps(data), spreads)
    assert publication_brochure_id("watsons", changed) != publication_brochure_id("watsons", first)


def test_dates_come_from_the_month_in_the_slug_or_title() -> None:
    b = publication_brochure("watsons", _watsons(), source_url="u", today=TODAY, now=NOW)
    assert (b.valid_from, b.valid_to) == (date(2026, 11, 1), date(2026, 11, 30))
    assert b.date_label is None and b.title == "Kasım Katalog 2026"


def test_year_in_the_slug_is_kept_a_year_later() -> None:
    b = publication_brochure("watsons", _watsons(), source_url="u", today=date(2027, 11, 20), now=NOW)
    assert (b.valid_from, b.valid_to) == (date(2026, 11, 1), date(2026, 11, 30))


def test_without_a_month_validity_starts_at_the_source_date_and_never_ends() -> None:
    data = json.loads(fixture_text("watsons", f"{SLUG}.data.json"))
    data["config"]["publicationOriginalTitle"] = "Haftalik Liste"
    spreads = fixture_text("watsons", f"{SLUG}.spreads.json")
    pub = parse_publication("haftalik-liste", json.dumps(data), spreads)
    b = publication_brochure("metro", pub, source_url="u", today=TODAY, now=NOW)
    assert (b.valid_from, b.valid_to, b.date_label) == (date(2026, 11, 9), None, None)


def test_source_dates_and_month_labels() -> None:
    assert parse_source_date("November 11, 2026 12:33") == date(2026, 11, 11)
    assert parse_source_date("garbage") is None and parse_source_date(None) is None
    assert month_label("Kasım Katalog 2026") == "kasim 2026"
    assert month_label("haftalik-liste") is None


def test_sitemap_slugs() -> None:
    xml = fixture_text("watsons", "sitemap.xml")
    assert parse_sitemap_slugs(xml, "https://katalog.watsons.com.tr") == [SLUG]
    with pytest.raises(SourceError, match="sitemap"):
        parse_sitemap_slugs("<urlset></urlset>", "https://katalog.watsons.com.tr")


@pytest.mark.parametrize(
    "data,spreads", [("", "[]"), ("{}", "[]"), ('{"id": 1, "cacheToken": "t"}', "[]"), ("[]", "[]")]
)
def test_unusable_json_raises(data: str, spreads: str) -> None:
    with pytest.raises(SourceError, match="format"):
        parse_publication("x", data, spreads)
