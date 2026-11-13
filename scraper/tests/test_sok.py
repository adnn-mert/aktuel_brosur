from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from scraper.chains import CHAINS
from scraper.core.media import MediaWriter
from scraper.core.pipeline import run
from scraper.core.source import SourceContext, SourceError
from scraper.sources.sok import PAGE_URL, SokCard, SokSource, card_brochure, parse_cards, pdf_stem
from scraper.tests.conftest import fixture_text, make_pdf, mock_http

TODAY = date(2026, 11, 13)
NOW = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
PDF_WEEK = "https://kurumsal.sokmarket.com.tr/uploads/pdf/mwajrdpq-18-24kasim.pdf"
PDF_WEEKEND = "https://kurumsal.sokmarket.com.tr/uploads/pdf/mwajlev6-21-24kasim.pdf"
ID_WEEK = "sok-2026-11-18-haftanin-firsatlari-mwajrdpq-18-24kasim"
ID_WEEKEND = "sok-2026-11-21-hafta-sonu-firsatlari-mwajlev6-21-24kasim"


def _page() -> str:
    return fixture_text("sok", "firsatlar.html")


def test_parse_cards() -> None:
    cards = parse_cards(_page())
    assert cards == [
        SokCard(
            title="Haftanın Fırsatları",
            date_text="18 - 24 Kasım 2026",
            pdf_url=PDF_WEEK,
            image_url="https://kurumsal.sokmarket.com.tr/uploads/firsatlar/mwakcr02-18-24kasim.webp",
        ),
        SokCard(
            title="Hafta Sonu Fırsatları",
            date_text="21 - 24 Kasım 2026",
            pdf_url=PDF_WEEKEND,
            image_url="https://kurumsal.sokmarket.com.tr/uploads/firsatlar/mwajkvmt-21-24kasim.webp",
        ),
    ]


def test_card_brochure() -> None:
    b = card_brochure(parse_cards(_page())[0], TODAY, NOW)
    assert b.id == ID_WEEK
    assert (b.valid_from, b.valid_to) == (date(2026, 11, 18), date(2026, 11, 24))
    assert (b.title, b.date_label, b.source_url) == ("Haftanın Fırsatları", "18 - 24 Kasım 2026", PDF_WEEK)


def test_dates_fall_back_to_the_file_name() -> None:
    card = SokCard("Fırsatlar", None, "https://kurumsal.sokmarket.com.tr/uploads/pdf/abc12-28ekim-03kasim.pdf", None)
    b = card_brochure(card, TODAY, NOW)
    assert (b.valid_from, b.valid_to) == (date(2026, 10, 28), date(2026, 11, 3))
    assert pdf_stem(card.pdf_url) == "abc12-28ekim-03kasim"
    assert b.id == "sok-2026-10-28-firsatlar-abc12-28ekim-03kasim"


def test_new_pdf_address_is_a_new_brochure() -> None:
    card = parse_cards(_page())[0]
    moved = SokCard(card.title, card.date_text, PDF_WEEK.replace("mwajrdpq", "zz99"), card.image_url)
    assert card_brochure(card, TODAY, NOW).id != card_brochure(moved, TODAY, NOW).id


@pytest.mark.parametrize("html", ["", "<html><body><div class='bc-aktual-card'>no link</div></body></html>"])
def test_unrelated_html_raises(html: str) -> None:
    with pytest.raises(SourceError, match="layout"):
        parse_cards(html)


def _routes() -> dict[str, object]:
    return {PAGE_URL: _page(), PDF_WEEK: make_pdf(3), PDF_WEEKEND: make_pdf(2)}


def test_collect_renders_pdf_pages(tmp_path) -> None:
    ctx = SourceContext(http=mock_http(_routes()), today=TODAY, now=NOW, media=MediaWriter(tmp_path, None))
    result = SokSource().collect(ctx)
    week, weekend = result.brochures
    assert (week.id, weekend.id) == (ID_WEEK, ID_WEEKEND)
    assert [p.url for p in week.pages] == [f"media/sok/{ID_WEEK}/p0{i}.webp" for i in (1, 2, 3)]
    assert all(p.w == 1600 and p.h == round(842 * 1600 / 595) for p in week.pages)
    assert week.cover == week.pages[0]
    assert len(weekend.pages) == 2
    assert (tmp_path / f"media/sok/{ID_WEEKEND}/p02.webp").is_file()


def test_collect_reports_a_missing_pdf(tmp_path) -> None:
    routes = _routes()
    del routes[PDF_WEEKEND]
    ctx = SourceContext(http=mock_http(routes), today=TODAY, now=NOW, media=MediaWriter(tmp_path, None))
    with pytest.raises(SourceError, match="HTTP 404"):
        SokSource().collect(ctx)


def test_second_run_does_not_download_pdfs_again(tmp_path) -> None:
    out = tmp_path / "out"
    calls: list[str] = []
    http = mock_http(_routes(), calls)
    first = run([SokSource()], CHAINS, out, out, TODAY, NOW, http=http)
    assert first.exit_code == 0
    assert calls == [PAGE_URL, PDF_WEEK, PDF_WEEKEND]
    catalog_before = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    page_before = (out / f"media/sok/{ID_WEEK}/p01.webp").read_bytes()

    calls.clear()
    later = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
    second = run([SokSource()], CHAINS, out, out, TODAY, later, http=http)
    assert second.exit_code == 0
    assert calls == [PAGE_URL]
    assert second.new_brochure_ids == []
    assert "2 PDFs reused from the previous run" in second.sources[0].warnings

    catalog_after = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    assert (out / f"media/sok/{ID_WEEK}/p01.webp").read_bytes() == page_before
    # Only the run timestamps move; brochures (first_seen, updated_at, pages) stay identical.
    assert catalog_after["brochures"] == catalog_before["brochures"]
    assert catalog_after["generated_at"] == "2026-11-13T15:00:00Z"
