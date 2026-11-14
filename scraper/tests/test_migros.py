from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from scraper.chains import CHAINS
from scraper.core.dates import DateRange
from scraper.core.media import MediaWriter
from scraper.core.models import BrochureKind, Product
from scraper.core.pipeline import run
from scraper.core.source import SourceContext, SourceError
from scraper.core.validate import validate_catalog, validate_products
from scraper.sources import migros
from scraper.sources.migros import (
    FIVE_M,
    MIGROSKOP,
    NO_PRICE,
    PER_KG_NOTE,
    UNKNOWN_BADGE,
    UNKNOWN_LAYOUT,
    UNKNOWN_UNIT,
    UNREADABLE_PRICE,
    MigrosSource,
    ViewerIssue,
    build_brochure,
    check_same_issue,
    issue_brochure_id,
    parse_card,
    parse_products,
    parse_viewer_issue,
)
from scraper.sources.money import heading_names, parse_current_issue, size_from_name
from scraper.tests.conftest import fixture_text, mock_http

TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
NOV_5_18 = DateRange(date(2026, 11, 5), date(2026, 11, 18))
COVER_910 = (
    "https://migroskop-assets.migros.com.tr/migrosdigitalinsert/910MIGROSKOP72YIL_migroskop_kapak1/Cover/"
    "183b2f00-a36e-4f86-ad87-507620ede1dd_743x1024.jpg"
)
COVER_286 = (
    "https://migroskop-assets.migros.com.tr/migrosdigitalinsert/286%205M%20MIGROSKOP72YIL_migroskop_kapak1/Cover/"
    "703ec860-9438-44fe-a698-2c6ddca4c351_743x1024.jpg"
)


def _page(name: str) -> str:
    return fixture_text("migros", name)


def _routes() -> dict[str, object]:
    return {
        MIGROSKOP.listing_url: _page("migroskop-dijital.html"),
        MIGROSKOP.viewer_url: _page("migroskop.html"),
        FIVE_M.listing_url: _page("5m-migroskop-dijital.html"),
        FIVE_M.viewer_url: _page("5m-migroskop.html"),
    }


def _card(price_content: str, *, title: str = "Deneme Ürün 1 kg", extra: str = "") -> str:
    return (
        '<div class="page"><div class="content"><div class="product">'
        '<div class="image"><img data-src="https://migroskop-assets.migros.com.tr/x/Product/a_10x10.png"></div>'
        f'<h1 class="title">{title}</h1>{price_content}'
        f'<small class="stock-info">Stok Adedi: 1.000</small>{extra}</div></div></div>'
    )


def _price(lira: str, kurus: str, unit: str = "") -> str:
    return (
        f'<div class="price-text"><div class="first"><span>₺</span><span>{lira}</span></div>'
        f'<div class="second"><span>{kurus}</span><span>{unit}</span></div></div>'
    )


def _one(html: str) -> Product | str:
    from selectolax.lexbor import LexborHTMLParser

    result = parse_card(LexborHTMLParser(html).css_first("div.product"), 0)
    return result if isinstance(result, str) else result[0]


# --- money.com.tr ----------------------------------------------------------------------


def test_current_issue_migroskop() -> None:
    issue = parse_current_issue(_page("migroskop-dijital.html"))
    assert issue.heading == "Güncel Migroskop Dijital"
    assert (issue.issue, issue.date_text) == ("910", "5 - 18 Kasım 2026")
    assert issue.viewer_url == MIGROSKOP.viewer_url
    assert issue.pdf_url is None
    assert issue.cover_url and "issue_cover_thumbnail_250" in issue.cover_url
    assert heading_names(issue.heading, "Migroskop") and not heading_names(issue.heading, "5M Migroskop")


def test_current_issue_5m() -> None:
    issue = parse_current_issue(_page("5m-migroskop-dijital.html"))
    assert (issue.heading, issue.issue, issue.date_text) == ("Güncel 5M Migroskop Dijital", "286", "5 - 18 Kasım 2026")
    assert issue.viewer_url == FIVE_M.viewer_url
    assert heading_names(issue.heading, "5M Migroskop") and not heading_names(issue.heading, "Migroskop")


@pytest.mark.parametrize("html", ["", "<html><body><h1>Bakım çalışması</h1></body></html>"])
def test_unrelated_listing_raises(html: str) -> None:
    with pytest.raises(SourceError, match="layout"):
        parse_current_issue(html)


def test_size_from_name() -> None:
    assert size_from_name(COVER_910) == (743, 1024)
    assert size_from_name("https://x.example/a_330x307.png?t=1") == (330, 307)
    assert size_from_name("https://x.example/kapak.jpg") is None


# --- viewer ----------------------------------------------------------------------------


def test_viewer_issue() -> None:
    viewer = parse_viewer_issue(_page("migroskop.html"), TODAY)
    assert (viewer.issue, viewer.cover_url) == ("910", COVER_910)
    # Ad folders such as "910 5-18 KASIM MIGROSKOP TERS" carry the dates too.
    assert NOV_5_18 in viewer.folder_dates
    five_m = parse_viewer_issue(_page("5m-migroskop.html"), TODAY)
    # The folder name has spaces; the URL is published percent-encoded.
    assert (five_m.issue, five_m.cover_url) == ("286", COVER_286)


def test_products_of_the_viewer() -> None:
    parsed = parse_products(_page("migroskop.html"))
    assert parsed.page_count == 124
    assert len(parsed.products) == 242
    assert parsed.skipped == {NO_PRICE: 21}
    assert parsed.member_priced == 172
    by_name = {p.name: p for p in parsed.products}

    first = parsed.products[0]
    assert first == Product(
        name="Migros Üçgen Peynir 120 g",
        price_minor=5495,
        brand=None,
        quantity_text="Stok Adedi: 100.000",
        old_price_minor=None,
        image="https://migroskop-assets.migros.com.tr/migrosdigitalinsert/10302124/Product/b03ae66d-360f-4f54-911c-f4cb20b9b677_509x512.png",
        page_index=5,
        source_url=None,
    )
    # "₺ 135," + "00", "₺ 123," + "95", "₺ 33," + "00": split prices joined.
    assert by_name["Migros Keçiboynuzu Pekmezi 800 g"].price_minor == 13500
    assert by_name["Migros Süzme Çiçek Balı 270 g"].price_minor == 12395
    gazoz = by_name["Migros Gazoz Pet 1.5 l"]
    assert (gazoz.price_minor, gazoz.page_index) == (3300, 6)
    # Thousands separator: "₺ 1.399," + "95".
    hipp = by_name["Hipp Organik Combıotıc 2/3 Avantaj Paket 600 g+350 g"]
    assert (hipp.price_minor, hipp.page_index) == (139995, 67)
    # A title split with <br> keeps its words apart.
    assert by_name["Tadım Kavrulmuş Siyah Ayçekirdeği 180 g"].price_minor == 4995


def test_member_price_is_left_out() -> None:
    by_name = {p.name: p for p in parse_products(_page("migroskop.html")).products}
    # Printed: ₺ 99,95 and, under "MONEY'Lİ FİYAT", ₺ 77,95. Only Money members pay 77,95,
    # so the published price is the one everyone pays, and nothing is shown as "old".
    bread = by_name["Untad Tam Buğday Ekmeği 400 g"]
    assert (bread.price_minor, bread.old_price_minor, bread.page_index) == (9995, None, 18)
    assert bread.quantity_text == "Stok Adedi: 15.000"
    # Same rule in the "indirimli-fiyat-1" layout variant: ₺ 159,95 and Money ₺ 99,95.
    towels = by_name["Sleepy Natural Kişisel Bakım Havlusu 100'lü"]
    assert (towels.price_minor, towels.page_index) == (15995, 67)
    # The site prints no struck-through "old" prices at all.
    assert all(p.old_price_minor is None for p in by_name.values())


def test_per_kg_prices_say_so() -> None:
    by_name = {p.name: p for p in parse_products(_page("migroskop.html")).products}
    sucuk = by_name["Torku Fermente Kangal Sucuk"]
    assert (sucuk.price_minor, sucuk.quantity_text) == (99900, f"{PER_KG_NOTE} · Stok Miktarı: 5.000 kg")
    assert sum(1 for p in by_name.values() if (p.quantity_text or "").startswith(PER_KG_NOTE)) == 19


def test_harmless_badges_keep_the_product() -> None:
    by_name = {p.name: p for p in parse_products(_page("migroskop.html")).products}
    # "1 ALANA 1 HEDİYE": the printed price is still the price of one bag.
    assert by_name["Fropie Cips Ürünleri"].price_minor == 7490
    # "İlk kez Migros'ta" badge.
    assert by_name["Premialle Yüksek Proteinli Puding Çeşitleri 200 g"].price_minor == 7500


def test_badge_only_cards_are_skipped() -> None:
    names = {p.name for p in parse_products(_page("migroskop.html")).products}
    # "% 25 indirim" with no price, and "2.si %70 iNDiRiMLi" with no price.
    assert "Pol's Ürünlerinde" not in names
    assert "Omo Sıvı Bebek Deterjanı 1.5 l/Yumoş Bebek Yumuşatıcı 1.2 l" not in names


@pytest.mark.parametrize(
    ("price_content", "extra", "expected"),
    [
        ('<div class="price-content">' + _price("12,", "50", "Lt") + "</div>", "", UNKNOWN_UNIT),
        ('<div class="price-content">' + _price("12", "50") + "</div>", "", UNREADABLE_PRICE),
        ('<div class="price-content">' + _price("12,", "5") + "</div>", "", UNREADABLE_PRICE),
        # A member price that is not lower means the card was misread.
        ('<div class="price-content">' + _price("10,", "00") + "<h6>MONEY'Lİ FİYAT</h6>" + _price("12,", "00") + "</div>", "", UNKNOWN_LAYOUT),
        # Two prices without the Money label: unknown meaning.
        ('<div class="price-content">' + _price("10,", "00") + _price("8,", "00") + "</div>", "", UNKNOWN_LAYOUT),
        ('<div class="price-content">' + _price("10,", "00") + "<h6>2 ADET</h6>" + _price("8,", "00") + "</div>", "", UNKNOWN_LAYOUT),
        ('<div class="price-content">' + _price("10,", "00") + "</div>", '<div class="mbadge" name="x-al-y-ode"></div>', UNKNOWN_BADGE),
        ("", "", UNKNOWN_LAYOUT),
    ],
)
def test_doubtful_cards_are_skipped(price_content: str, extra: str, expected: str) -> None:
    assert _one(_card(price_content, extra=extra)) == expected


def test_plain_synthetic_card() -> None:
    product = _one(_card('<div class="price-content">' + _price("1.249,", "90", "Adet") + "</div>"))
    assert isinstance(product, Product)
    assert (product.price_minor, product.quantity_text) == (124990, "Stok Adedi: 1.000")


@pytest.mark.parametrize("html", ["", "<html><body><p>Bakım çalışması</p></body></html>"])
def test_unrelated_viewer_raises(html: str) -> None:
    with pytest.raises(SourceError, match="layout"):
        parse_products(html)
    with pytest.raises(SourceError, match="layout"):
        parse_viewer_issue(html, TODAY)


def test_viewer_without_product_cards_raises() -> None:
    with pytest.raises(SourceError, match="no product cards"):
        parse_products('<div class="page"><div class="ad"><img src="https://x.example/a.jpg"></div></div>')


# --- matching the issue ----------------------------------------------------------------


def test_build_brochure() -> None:
    listing = parse_current_issue(_page("migroskop-dijital.html"))
    viewer = parse_viewer_issue(_page("migroskop.html"), TODAY)
    brochure, products = build_brochure(MIGROSKOP, listing, viewer, parse_products(_page("migroskop.html")), TODAY, NOW)
    assert brochure.id == "migros-migroskop-910"
    assert (brochure.title, brochure.date_label) == ("Migroskop", "5 - 18 Kasım 2026")
    assert (brochure.valid_from, brochure.valid_to) == (date(2026, 11, 5), date(2026, 11, 18))
    assert brochure.kind is BrochureKind.PRODUCTS and brochure.pages == ()
    assert (brochure.cover.url, brochure.cover.w, brochure.cover.h) == (COVER_910, 743, 1024)
    assert brochure.source_url == "https://migroskop.migros.com.tr/migroskop"
    assert (brochure.products_url, brochure.product_count) == ("products/migros-migroskop-910.json", 242)
    assert products.brochure_id == brochure.id and len(products.products) == 242


def test_mismatched_issue_is_a_source_error() -> None:
    listing = replace(parse_current_issue(_page("migroskop-dijital.html")), issue="911")
    viewer = parse_viewer_issue(_page("migroskop.html"), TODAY)
    with pytest.raises(SourceError, match="viewer shows issue 910 but money.com.tr lists issue 911"):
        build_brochure(MIGROSKOP, listing, viewer, parse_products(_page("migroskop.html")), TODAY, NOW)


def test_without_issue_numbers_the_dates_must_match() -> None:
    listing = replace(parse_current_issue(_page("migroskop-dijital.html")), issue=None)
    viewer = ViewerIssue(issue=None, cover_url=None, folder_dates=frozenset({NOV_5_18}))
    check_same_issue(listing, NOV_5_18, viewer)
    other = DateRange(date(2026, 11, 19), date(2026, 12, 2))
    with pytest.raises(SourceError, match="cannot confirm"):
        check_same_issue(listing, other, viewer)
    with pytest.raises(SourceError, match="cannot confirm"):
        check_same_issue(listing, NOV_5_18, ViewerIssue("910", None, frozenset()))


def test_unreadable_dates_are_a_source_error() -> None:
    listing = replace(parse_current_issue(_page("migroskop-dijital.html")), date_text="Yakında")
    viewer = parse_viewer_issue(_page("migroskop.html"), TODAY)
    with pytest.raises(SourceError, match="no readable dates"):
        build_brochure(MIGROSKOP, listing, viewer, parse_products(_page("migroskop.html")), TODAY, NOW)


def test_brochure_ids() -> None:
    assert issue_brochure_id(MIGROSKOP, "910", NOV_5_18) == "migros-migroskop-910"
    assert issue_brochure_id(FIVE_M, "286", NOV_5_18) == "migros-5m-286"
    assert issue_brochure_id(FIVE_M, None, NOV_5_18) == "migros-5m-2026-11-05-2026-11-18"
    assert issue_brochure_id(MIGROSKOP, "Kasım", NOV_5_18) == "migros-migroskop-2026-11-05-2026-11-18"


# --- collect (network mocked) ----------------------------------------------------------


def _ctx(tmp_path, http) -> SourceContext:
    return SourceContext(http=http, today=TODAY, now=NOW, media=MediaWriter(tmp_path, None))


def test_collect(tmp_path) -> None:
    calls: list[str] = []
    result = MigrosSource().collect(_ctx(tmp_path, mock_http(_routes(), calls)))
    # Two requests per publication: the money.com.tr page and the viewer.
    assert calls == [MIGROSKOP.listing_url, MIGROSKOP.viewer_url, FIVE_M.listing_url, FIVE_M.viewer_url]
    migroskop, five_m = result.brochures
    assert (migroskop.id, five_m.id) == ("migros-migroskop-910", "migros-5m-286")
    assert (five_m.title, five_m.valid_from, five_m.valid_to) == ("5M Migroskop", date(2026, 11, 5), date(2026, 11, 18))
    assert five_m.cover.url == COVER_286 and five_m.source_url == FIVE_M.viewer_url
    # The 5M fixture is trimmed to 41 pages (see fixtures/migros/NOTES.md).
    assert (migroskop.product_count, five_m.product_count) == (242, 96)
    assert set(result.product_files) == {migroskop.id, five_m.id}
    assert "Migroskop: 21 products skipped (21 no price, only a discount badge)" in result.warnings
    assert "Migroskop: 172 Money member prices left out" in result.warnings


def test_collect_rejects_the_wrong_publication(tmp_path) -> None:
    routes = _routes()
    routes[MIGROSKOP.listing_url] = _page("5m-migroskop-dijital.html")
    with pytest.raises(SourceError, match="expected Migroskop"):
        MigrosSource().collect(_ctx(tmp_path, mock_http(routes)))


def test_collect_rejects_a_viewer_showing_another_issue(tmp_path) -> None:
    routes = _routes()
    # money.com.tr lists 5M issue 286, but the viewer serves the Migroskop issue 910.
    routes[FIVE_M.viewer_url] = _page("migroskop.html")
    with pytest.raises(SourceError, match="viewer shows issue 910 but money.com.tr lists issue 286"):
        MigrosSource().collect(_ctx(tmp_path, mock_http(routes)))


def test_collect_fails_when_most_products_are_skipped(tmp_path, monkeypatch) -> None:
    real = migros.parse_products

    def mostly_skipped(html: str):
        parsed = real(html)
        return replace(parsed, skipped=parsed.skipped + Counter({NO_PRICE: 1000}))

    monkeypatch.setattr(migros, "parse_products", mostly_skipped)
    with pytest.raises(SourceError, match="products skipped"):
        MigrosSource().collect(_ctx(tmp_path, mock_http(_routes())))


def test_collect_reports_a_blocked_site(tmp_path) -> None:
    routes = _routes()
    routes[MIGROSKOP.viewer_url] = (403, "Access denied")
    with pytest.raises(SourceError, match="HTTP 403"):
        MigrosSource().collect(_ctx(tmp_path, mock_http(routes)))


def test_first_run_through_the_pipeline(tmp_path) -> None:
    out = tmp_path / "out"
    report = run([MigrosSource()], CHAINS, out, out, TODAY, NOW, http=mock_http(_routes()))
    assert report.exit_code == 0
    catalog = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    validate_catalog(catalog)
    brochures = {b["id"]: b for b in catalog["brochures"]}
    # A chain's first run: the issues started on 5 November, so they are not "new" today.
    assert brochures["migros-migroskop-910"]["first_seen"] == "2026-11-05T00:00:00Z"
    assert report.new_brochure_ids == []
    products = json.loads((out / "products/migros-5m-286.json").read_text(encoding="utf-8"))
    validate_products(products)
    assert products["products"][0]["name"] == "Migros Üçgen Peynir 120 g"
    chain = next(c for c in catalog["chains"] if c["id"] == "migros")
    assert (chain["status"], chain["brand_color"], chain["web_url"]) == (
        "ok",
        "#FF8300",
        "https://www.money.com.tr/migroskop-dijital",
    )
