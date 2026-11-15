from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from scraper.chains import CHAINS
from scraper.core.dates import DateRange, format_range
from scraper.core.media import MediaWriter
from scraper.core.pipeline import run
from scraper.core.source import SourceContext, SourceError
from scraper.sources.bonveno import PAGE_URL, BonvenoPdf, BonvenoSource, parse_pdfs, pdf_brochure
from scraper.tests.conftest import fixture_text, make_pdf, mock_http

TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
WEEK_PDF = "https://bonveno.com.tr/-/media/Project/Traders/TR_Bonveno/katalog/KASIM26/70x100_13-19KASIM-1.pdf"
POSTER_PDF = "https://bonveno.com.tr/-/media/Project/Traders/TR_Bonveno/katalog/EKIM-26/POSTER_QSR.pdf"
WEEK_ID = "bonveno-2026-11-13-70x100-13-19kasim-1"


def _html() -> str:
    return fixture_text("bonveno", "kampanyalarimiz.html")


def test_pdfs_are_listed_without_query_parameters() -> None:
    assert parse_pdfs(_html()) == [
        BonvenoPdf(WEEK_PDF, "70x100_13-19KASIM-1"),
        BonvenoPdf(POSTER_PDF, "POSTER_QSR"),
    ]


def test_dated_pdf_becomes_a_brochure() -> None:
    b = pdf_brochure(parse_pdfs(_html())[0], TODAY, NOW)
    assert b is not None
    assert b.id == WEEK_ID
    assert (b.valid_from, b.valid_to, b.date_label) == (date(2026, 11, 13), date(2026, 11, 19), "13-19 Kasım")
    assert b.source_url == WEEK_PDF


def test_undated_pdf_is_not_taken() -> None:
    assert pdf_brochure(parse_pdfs(_html())[1], TODAY, NOW) is None


def test_query_parameters_do_not_change_the_id() -> None:
    other = _html().replace("rev=726757b6440344acbf904c97af6ed523", "rev=ffffffffffffffffffffffffffffffff")
    assert other != _html()
    a = pdf_brochure(parse_pdfs(_html())[0], TODAY, NOW)
    b = pdf_brochure(parse_pdfs(other)[0], TODAY, NOW)
    assert a is not None and b is not None and a.id == b.id and a.source_url == b.source_url


def test_format_range() -> None:
    assert format_range(DateRange(date(2026, 10, 28), date(2026, 11, 3))) == "28 Ekim-3 Kasım"
    assert format_range(DateRange(date(2026, 11, 15), date(2026, 11, 15))) == "15 Kasım"


@pytest.mark.parametrize("html", ["", '<a href="/b.pdf">b</a><a href="/katalog/x.html">c</a>'])
def test_unrelated_html_raises(html: str) -> None:
    with pytest.raises(SourceError, match="layout"):
        parse_pdfs(html)


def test_only_undated_pdfs_is_a_source_error(tmp_path) -> None:
    html = f'<a href="{POSTER_PDF}">x</a>'
    ctx = SourceContext(http=mock_http({PAGE_URL: html}), today=TODAY, now=NOW, media=MediaWriter(tmp_path, None))
    with pytest.raises(SourceError, match="no PDF with a date"):
        BonvenoSource().collect(ctx)


def test_collect_renders_the_pdf(tmp_path) -> None:
    routes = {PAGE_URL: _html(), WEEK_PDF: make_pdf(1)}
    calls: list[str] = []
    ctx = SourceContext(http=mock_http(routes, calls), today=TODAY, now=NOW, media=MediaWriter(tmp_path, None))
    (b,) = BonvenoSource().collect(ctx).brochures
    assert calls == [PAGE_URL, WEEK_PDF]  # the undated poster is never downloaded
    assert [p.url for p in b.pages] == [f"media/bonveno/{WEEK_ID}/p01.webp"] and b.cover == b.pages[0]
    assert b.pages[0].w == 2000
    assert (tmp_path / b.pages[0].url).is_file()


def test_second_run_reuses_the_rendered_pdf(tmp_path) -> None:
    out = tmp_path / "out"
    calls: list[str] = []
    http = mock_http({PAGE_URL: _html(), WEEK_PDF: make_pdf(1)}, calls)
    assert run([BonvenoSource()], CHAINS, out, out, TODAY, NOW, http=http).exit_code == 0
    calls.clear()
    later = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)
    second = run([BonvenoSource()], CHAINS, out, out, TODAY, later, http=http)
    assert second.exit_code == 0 and calls == [PAGE_URL]
    catalog = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    assert [b["id"] for b in catalog["brochures"] if b["chain_id"] == "bonveno"] == [WEEK_ID]
