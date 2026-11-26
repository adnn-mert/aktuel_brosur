from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from scraper.chains import CHAINS
from scraper.core.media import MediaWriter
from scraper.core.pipeline import run
from scraper.core.source import SourceContext, SourceError
from scraper.sources.tkkoop import PAGE_URL, Campaign, TkkoopSource, campaign_brochure, parse_campaigns
from scraper.tests.conftest import fixture_text, make_pdf, mock_http

TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
PDF_WEEKEND = "https://www.tkkoop.com.tr/assets/images/kampanya/14-16-firsat-dolu-haftasonu_1794402490.pdf"
PDF_WEEK = "https://www.tkkoop.com.tr/assets/images/kampanya/10-16-kasim-kat-kat-firsat_1794209881.pdf"
ID_WEEK = "tkkoop-2026-11-10-10-16-kasim-kat-kat-firsat-1794209881"


def _html() -> str:
    return fixture_text("tkkoop", "anasayfa.html")


def test_campaigns_with_a_pdf() -> None:
    assert parse_campaigns(_html()) == [
        Campaign("firsat-dolu-haftasonu", "14 Kasım - 16 Kasım", PDF_WEEKEND),
        Campaign("kat-kat-firsat", "10 Kasım - 16 Kasım", PDF_WEEK),
    ]


def test_brochures() -> None:
    weekend, week = (campaign_brochure(c, TODAY, NOW) for c in parse_campaigns(_html()))
    assert week.id == ID_WEEK
    assert (week.title, week.date_label) == ("Kat Kat Fırsat", "10 Kasım - 16 Kasım")
    assert (week.valid_from, week.valid_to) == (date(2026, 11, 10), date(2026, 11, 16))
    assert (weekend.valid_from, weekend.valid_to) == (date(2026, 11, 14), date(2026, 11, 16))
    assert weekend.title == "Fırsat Dolu Haftasonu" and weekend.source_url == PDF_WEEKEND


def test_dates_fall_back_to_the_file_name_and_stay_empty_when_unknown() -> None:
    no_text = campaign_brochure(Campaign("kat-kat-firsat", None, PDF_WEEK), TODAY, NOW)
    assert (no_text.valid_from, no_text.valid_to) == (date(2026, 11, 10), date(2026, 11, 16))
    unknown = campaign_brochure(Campaign("x", None, "https://www.tkkoop.com.tr/a/x_1.pdf"), TODAY, NOW)
    assert (unknown.valid_from, unknown.valid_to, unknown.date_label) == (None, None, None)


def test_new_pdf_is_a_new_brochure() -> None:
    old = campaign_brochure(Campaign("kat-kat-firsat", "10 Kasım - 16 Kasım", PDF_WEEK), TODAY, NOW)
    new = campaign_brochure(Campaign("kat-kat-firsat", "10 Kasım - 16 Kasım", PDF_WEEK.replace("1794209881", "1794999999")), TODAY, NOW)
    assert old.id != new.id


@pytest.mark.parametrize("html", ["<html></html>", '<div class="koop"><a href="/x.pdf">KVKK</a></div>'])
def test_unrelated_html_raises(html: str) -> None:
    with pytest.raises(SourceError, match="layout"):
        parse_campaigns(html)


def test_week_without_a_pdf_bulletin_is_reported_as_such() -> None:
    # Recorded 2026-11-26: one campaign with product cards only; the footer's KVKK PDFs must not count.
    with pytest.raises(SourceError) as error:
        parse_campaigns(fixture_text("tkkoop", "anasayfa-pdfsiz.html"))
    message = str(error.value)
    assert "no PDF bulletin this week" in message and "layout" not in message
    assert "yildonumu-kampanyasi (24 Kasım - 30 Kasım)" in message


def test_a_block_without_a_pdf_does_not_hide_one_with_a_pdf() -> None:
    no_pdf = '<div class="yeni_1"><a href="/haftalik-kampanyalar/x" title="x">ÜRÜNLERİNİ GÖR</a></div>'
    campaigns = parse_campaigns(no_pdf + _html())
    assert [c.slug for c in campaigns] == ["firsat-dolu-haftasonu", "kat-kat-firsat"]


def _routes() -> dict[str, object]:
    return {PAGE_URL: _html(), PDF_WEEKEND: make_pdf(2), PDF_WEEK: make_pdf(3)}


def test_collect_renders_pdf_pages(tmp_path) -> None:
    ctx = SourceContext(http=mock_http(_routes()), today=TODAY, now=NOW, media=MediaWriter(tmp_path, None))
    weekend, week = TkkoopSource().collect(ctx).brochures
    assert (len(weekend.pages), len(week.pages)) == (2, 3)
    assert week.pages[0].url == f"media/tkkoop/{ID_WEEK}/p01.webp" and week.cover == week.pages[0]
    assert (tmp_path / week.pages[2].url).is_file()


def test_second_run_does_not_download_pdfs_again(tmp_path) -> None:
    out = tmp_path / "out"
    calls: list[str] = []
    http = mock_http(_routes(), calls)
    assert run([TkkoopSource()], CHAINS, out, out, TODAY, NOW, http=http).exit_code == 0
    assert calls == [PAGE_URL, PDF_WEEKEND, PDF_WEEK]
    calls.clear()
    later = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)
    assert run([TkkoopSource()], CHAINS, out, out, TODAY, later, http=http).exit_code == 0
    assert calls == [PAGE_URL]
    catalog = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    assert len([b for b in catalog["brochures"] if b["chain_id"] == "tkkoop"]) == 2
