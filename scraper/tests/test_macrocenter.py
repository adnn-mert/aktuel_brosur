from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from scraper.chains import CHAINS
from scraper.core.media import MediaWriter
from scraper.core.models import BrochureKind
from scraper.core.pipeline import run
from scraper.core.source import SourceContext, SourceError
from scraper.core.validate import validate_catalog
from scraper.sources.macrocenter import PAGE_URL, MacrocenterSource, issue_brochure, pdf_stem
from scraper.sources.money import parse_current_issue
from scraper.tests.conftest import fixture_text, make_pdf, mock_http

TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
PDF = "https://moneyclubkart.azureedge.net/mcstage/mac-2026-2262-kasim-639289517091175055.pdf"
BID = "macrocenter-mac-2026-2262-kasim-639289517091175055"


def _page() -> str:
    return fixture_text("macrocenter", "macrostyle-dijital.html")


def _ctx(tmp_path, http) -> SourceContext:
    return SourceContext(http=http, today=TODAY, now=NOW, media=MediaWriter(tmp_path, None))


def test_current_issue() -> None:
    issue = parse_current_issue(_page())
    assert issue.heading == "Güncel MacroStyle Dijital"
    assert (issue.issue, issue.date_text, issue.pdf_url) == ("Kasım 2026", "1 - 30 Kasım 2026", PDF)
    assert issue.viewer_url is None


def test_issue_brochure() -> None:
    b = issue_brochure(parse_current_issue(_page()), TODAY, NOW)
    assert b.id == BID
    assert (b.title, b.date_label, b.kind) == ("MacroStyle", "1 - 30 Kasım 2026", BrochureKind.PAGES)
    assert (b.valid_from, b.valid_to) == (date(2026, 11, 1), date(2026, 11, 30))
    assert b.source_url == PDF
    assert pdf_stem(PDF) == "mac-2026-2262-kasim-639289517091175055"


def test_a_new_pdf_is_a_new_brochure() -> None:
    issue = parse_current_issue(_page())
    moved = replace(issue, pdf_url=PDF.replace("639289517091175055", "639299999999999999"))
    assert issue_brochure(issue, TODAY, NOW).id != issue_brochure(moved, TODAY, NOW).id


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"pdf_url": None}, "no PDF link"),
        ({"pdf_url": "https://moneyclubkart.azureedge.net/mcstage/kapak.png"}, "no PDF link"),
        ({"date_text": None}, "no readable dates"),
        ({"heading": "Güncel Migroskop Dijital"}, "expected MacroStyle"),
    ],
)
def test_doubtful_issue_is_a_source_error(change: dict, message: str) -> None:
    with pytest.raises(SourceError, match=message):
        issue_brochure(replace(parse_current_issue(_page()), **change), TODAY, NOW)


@pytest.mark.parametrize("html", ["", "<html><body><p>Bakım çalışması</p></body></html>"])
def test_unrelated_html_raises(html: str, tmp_path) -> None:
    with pytest.raises(SourceError, match="layout"):
        MacrocenterSource().collect(_ctx(tmp_path, mock_http({PAGE_URL: html})))


def test_collect_renders_pdf_pages(tmp_path) -> None:
    calls: list[str] = []
    result = MacrocenterSource().collect(_ctx(tmp_path, mock_http({PAGE_URL: _page(), PDF: make_pdf(3)}, calls)))
    assert calls == [PAGE_URL, PDF]
    (b,) = result.brochures
    assert [p.url for p in b.pages] == [f"media/macrocenter/{BID}/p0{i}.webp" for i in (1, 2, 3)]
    assert all(p.w == 2000 for p in b.pages)
    assert b.cover == b.pages[0]
    assert (tmp_path / f"media/macrocenter/{BID}/p03.webp").is_file()


def test_collect_reports_a_missing_pdf(tmp_path) -> None:
    with pytest.raises(SourceError, match="HTTP 404"):
        MacrocenterSource().collect(_ctx(tmp_path, mock_http({PAGE_URL: _page()})))


def test_runs_through_the_pipeline_and_reuses_the_pdf(tmp_path) -> None:
    out = tmp_path / "out"
    calls: list[str] = []
    http = mock_http({PAGE_URL: _page(), PDF: make_pdf(2)}, calls)
    first = run([MacrocenterSource()], CHAINS, out, out, TODAY, NOW, http=http)
    assert first.exit_code == 0 and first.new_brochure_ids == []
    catalog = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    validate_catalog(catalog)
    (b,) = [x for x in catalog["brochures"] if x["chain_id"] == "macrocenter"]
    # The chain's first run: the issue started on 1 November.
    assert b["first_seen"] == "2026-11-01T00:00:00Z"
    chain = next(c for c in catalog["chains"] if c["id"] == "macrocenter")
    assert (chain["status"], chain["web_url"]) == ("ok", "https://www.money.com.tr/macrostyle-dijital")
    assert "brand_color" not in chain

    calls.clear()
    later = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)
    second = run([MacrocenterSource()], CHAINS, out, out, TODAY, later, http=http)
    assert second.exit_code == 0 and second.new_brochure_ids == []
    assert calls == [PAGE_URL]
    assert "PDF reused from the previous run" in second.sources[0].warnings
    after = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    assert after["brochures"] == catalog["brochures"]
