from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from scraper.core.media import MediaWriter
from scraper.core.source import SourceContext, SourceError
from scraper.sources.hakmar import PAGE_URL, HakmarSource, group_brochure, parse_groups
from scraper.tests.conftest import fixture_text, mock_http

TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
UPLOADS = "https://hakmar.com.tr/wp-content/uploads/2026"


def _html() -> str:
    return fixture_text("hakmar", "indirim.html")


def test_groups_follow_the_page_order() -> None:
    groups = parse_groups(_html())
    assert [(g.heading, len(g.pages)) for g in groups] == [("13-15 Kasım", 1), ("10-23 Kasım", 8), ("16 Ekim-15 Kasım", 1)]
    week = groups[1]
    assert week.pages[0] == f"{UPLOADS}/11/10-23-KASIM-2026_Insert-1-8-scaled.jpg"
    assert week.pages[-1] == f"{UPLOADS}/11/10-23-KASIM-2026_Insert-8-8-scaled.jpg"
    # The page order is the slide order, not alphabetical.
    assert [p.rsplit("Insert-", 1)[1][:1] for p in week.pages] == list("12345678")


def test_brochures_dates_and_covers() -> None:
    first, second, third = (group_brochure(g, TODAY, NOW) for g in parse_groups(_html()))
    assert [(b.valid_from, b.valid_to) for b in (first, second, third)] == [
        (date(2026, 11, 13), date(2026, 11, 15)),
        (date(2026, 11, 10), date(2026, 11, 23)),
        (date(2026, 10, 16), date(2026, 11, 15)),
    ]
    assert second.id == "hakmar-2026-11-10-10-23-kasim"
    assert (second.title, second.date_label) == ("10-23 Kasım", "10-23 Kasım")
    assert second.cover is not None
    assert (second.cover.url, second.cover.w, second.cover.h) == (f"{UPLOADS}/11/10-23-KASIM-2026_Insert-1-8-768x1077.jpg", 768, 1077)
    assert all(p.w is None for p in second.pages)
    assert len({b.id for b in (first, second, third)}) == 3


def test_ids_are_stable_across_runs() -> None:
    later = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)
    ids = [group_brochure(g, TODAY, NOW).id for g in parse_groups(_html())]
    assert ids == [group_brochure(g, date(2026, 11, 15), later).id for g in parse_groups(_html())]


@pytest.mark.parametrize("html", ["", "<html><body><h2 class='elementor-heading-title'>13-15 Kasım</h2></body></html>"])
def test_unrelated_html_raises(html: str) -> None:
    with pytest.raises(SourceError, match="layout"):
        parse_groups(html)


def test_collect(tmp_path) -> None:
    ctx = SourceContext(http=mock_http({PAGE_URL: _html()}), today=TODAY, now=NOW, media=MediaWriter(tmp_path, None))
    result = HakmarSource().collect(ctx)
    assert [b.id for b in result.brochures] == [
        "hakmar-2026-11-13-13-15-kasim",
        "hakmar-2026-11-10-10-23-kasim",
        "hakmar-2026-10-16-16-ekim-15-kasim",
    ]
