from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from scraper.chains import CHAINS
from scraper.core.dates import DateRange
from scraper.core.media import MediaWriter
from scraper.core.models import Brochure, BrochureKind, Page, Product, ProductFile
from scraper.core.pipeline import run
from scraper.core.source import SourceContext, SourceError, products_path
from scraper.core.validate import validate_catalog, validate_products
from scraper.sources import migros
from scraper.sources.migros import (
    MEMBER_NOT_LOWER,
    MEMBER_PRICE_LABEL,
    MIGROSKOP,
    NO_PRICE,
    PER_KG_NOTE,
    PUBLICATIONS,
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
    retired_brochure_ids,
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
FIVE_M_LISTING = "https://www.money.com.tr/mc/kataloglarimiz/5m-migroskop-dijital/84"
FIVE_M_VIEWER = "https://migroskop.migros.com.tr/5m-migroskop"


def _page(name: str) -> str:
    return fixture_text("migros", name)


def _routes() -> dict[str, object]:
    return {MIGROSKOP.listing_url: _page("migroskop-dijital.html"), MIGROSKOP.viewer_url: _page("migroskop.html")}


def _products() -> dict[str, Product]:
    return {p.name: p for p in parse_products(_page("migroskop.html")).products}


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


def _money(shelf: str, member: str) -> str:
    return f'<div class="price-content" name="indirimli-fiyat">{shelf}<h6>MONEY\'Lİ FİYAT</h6>{member}</div>'


def _parse(html: str) -> tuple[Product, str | None] | str:
    from selectolax.lexbor import LexborHTMLParser

    return parse_card(LexborHTMLParser(html).css_first("div.product"), 0)


# --- money.com.tr ----------------------------------------------------------------------


def test_current_issue_migroskop() -> None:
    issue = parse_current_issue(_page("migroskop-dijital.html"))
    assert issue.heading == "Güncel Migroskop Dijital"
    assert (issue.issue, issue.date_text) == ("910", "5 - 18 Kasım 2026")
    assert issue.viewer_url == MIGROSKOP.viewer_url
    assert issue.pdf_url is None
    assert issue.cover_url and "issue_cover_thumbnail_250" in issue.cover_url
    assert heading_names(issue.heading, "Migroskop") and not heading_names(issue.heading, "5M Migroskop")
    assert heading_names("Güncel 5M Migroskop Dijital", "5M Migroskop")
    assert not heading_names("Güncel 5M Migroskop Dijital", "Migroskop")


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


def test_products_of_the_viewer() -> None:
    parsed = parse_products(_page("migroskop.html"))
    assert parsed.page_count == 124
    assert len(parsed.products) == 242
    assert parsed.skipped == {NO_PRICE: 21}
    assert parsed.member_priced == 172 and parsed.member_dropped == Counter()
    by_name = {p.name: p for p in parsed.products}

    assert parsed.products[0] == Product(
        name="Migros Üçgen Peynir 120 g",
        price_minor=5495,
        brand=None,
        quantity_text=None,
        old_price_minor=None,
        image="https://migroskop-assets.migros.com.tr/migrosdigitalinsert/10302124/Product/b03ae66d-360f-4f54-911c-f4cb20b9b677_509x512.png",
        page_index=5,
        source_url=None,
        member_price_minor=None,
        member_price_label=None,
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
    # The site prints no struck-through "old" prices at all.
    assert all(p.old_price_minor is None for p in parsed.products)


@pytest.mark.parametrize(
    ("name", "shelf", "member", "page"),
    [
        # Printed: ₺ 99,95 and, under "MONEY'Lİ FİYAT", ₺ 77,95 ("&nbsp;95").
        ("Untad Tam Buğday Ekmeği 400 g", 9995, 7795, 18),
        # The "indirimli-fiyat-1" layout variant.
        ("Sleepy Natural Kişisel Bakım Havlusu 100'lü", 15995, 9995, 67),
        # Thousands separator and a per-kg price on both lines.
        ("Siirt Fıstığı Tuzlu Kavrulmuş", 179900, 149990, 21),
    ],
)
def test_money_price_is_a_labelled_member_price(name: str, shelf: int, member: int, page: int) -> None:
    p = _products()[name]
    # price_minor stays what everyone pays; the Money price is a separate, labelled field.
    assert (p.price_minor, p.member_price_minor, p.member_price_label) == (shelf, member, MEMBER_PRICE_LABEL)
    assert (p.old_price_minor, p.page_index) == (None, page)


def test_quantity_text_is_only_the_per_kg_note() -> None:
    products = _products()
    sucuk = products["Torku Fermente Kangal Sucuk"]
    assert (sucuk.price_minor, sucuk.quantity_text) == (99900, PER_KG_NOTE)
    assert products["Siirt Fıstığı Tuzlu Kavrulmuş"].quantity_text == "kg fiyatı"
    assert Counter(p.quantity_text for p in products.values()) == {None: 223, PER_KG_NOTE: 19}
    # Stock lines ("Stok Adedi: 100.000", "Stoklarla Sınırlıdır.") are not published.
    assert not any("Stok" in (p.quantity_text or "") for p in products.values())


def test_harmless_badges_keep_the_product() -> None:
    products = _products()
    # "1 ALANA 1 HEDİYE": the printed price is still the price of one bag.
    assert products["Fropie Cips Ürünleri"].price_minor == 7490
    # "İlk kez Migros'ta" badge.
    assert products["Premialle Yüksek Proteinli Puding Çeşitleri 200 g"].price_minor == 7500


def test_badge_only_cards_are_skipped() -> None:
    names = set(_products())
    # "% 25 indirim" with no price, and "2.si %70 iNDiRiMLi" with no price.
    assert "Pol's Ürünlerinde" not in names
    assert "Omo Sıvı Bebek Deterjanı 1.5 l/Yumoş Bebek Yumuşatıcı 1.2 l" not in names


@pytest.mark.parametrize(
    ("price_content", "extra", "expected"),
    [
        ('<div class="price-content">' + _price("12,", "50", "Lt") + "</div>", "", UNKNOWN_UNIT),
        ('<div class="price-content">' + _price("12", "50") + "</div>", "", UNREADABLE_PRICE),
        ('<div class="price-content">' + _price("12,", "5") + "</div>", "", UNREADABLE_PRICE),
        # Two prices without the Money label: which one is the shelf price is unknown.
        ('<div class="price-content">' + _price("10,", "00") + _price("8,", "00") + "</div>", "", UNKNOWN_LAYOUT),
        ('<div class="price-content">' + _price("10,", "00") + "<h6>2 ADET</h6>" + _price("8,", "00") + "</div>", "", UNKNOWN_LAYOUT),
        ('<div class="price-content">' + _price("10,", "00") + "</div>", '<div class="mbadge" name="x-al-y-ode"></div>', UNKNOWN_BADGE),
        ("", "", UNKNOWN_LAYOUT),
    ],
)
def test_doubtful_cards_are_skipped(price_content: str, extra: str, expected: str) -> None:
    assert _parse(_card(price_content, extra=extra)) == expected


def test_member_price_not_lower_is_dropped_but_the_product_stays() -> None:
    product, dropped = _parse(_card(_money(_price("10,", "00"), _price("12,", "00"))))
    assert (product.price_minor, product.member_price_minor, product.member_price_label) == (1000, None, None)
    assert dropped == MEMBER_NOT_LOWER
    product, dropped = _parse(_card(_money(_price("10,", "00"), _price("10,", "00"))))
    assert (product.member_price_minor, dropped) == (None, MEMBER_NOT_LOWER)


def test_plain_synthetic_card() -> None:
    product, dropped = _parse(_card('<div class="price-content">' + _price("1.249,", "90", "Adet") + "</div>"))
    assert (product.price_minor, product.quantity_text, product.member_price_minor, dropped) == (124990, None, None, None)


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
    validate_products(products.to_dict())


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
    assert issue_brochure_id(MIGROSKOP, None, NOV_5_18) == "migros-migroskop-2026-11-05-2026-11-18"
    assert issue_brochure_id(MIGROSKOP, "Kasım", NOV_5_18) == "migros-migroskop-2026-11-05-2026-11-18"


# --- 5M is not taken -------------------------------------------------------------------


def test_only_migroskop_is_taken() -> None:
    assert PUBLICATIONS == (MIGROSKOP,)


def _old(bid: str) -> Brochure:
    return Brochure(
        id=bid,
        chain_id="migros",
        title="5M Migroskop",
        date_label="5 - 18 Kasım 2026",
        valid_from=date(2026, 11, 5),
        valid_to=date(2026, 11, 18),
        kind=BrochureKind.PRODUCTS,
        cover=Page(COVER_910, 743, 1024),
        pages=(),
        products_url=products_path(bid),
        product_count=1,
        source_url=FIVE_M_VIEWER,
        first_seen=NOW,
        updated_at=NOW,
    )


def test_retired_brochure_ids() -> None:
    previous = (_old("migros-5m-286"), _old("migros-migroskop-909"), _old("migros-migroskop-2026-10-22-2026-11-04"))
    assert retired_brochure_ids(previous, PUBLICATIONS) == {"migros-5m-286"}


# --- collect (network mocked) ----------------------------------------------------------


def _ctx(tmp_path, http) -> SourceContext:
    return SourceContext(http=http, today=TODAY, now=NOW, media=MediaWriter(tmp_path, None))


def test_collect(tmp_path) -> None:
    calls: list[str] = []
    result = MigrosSource().collect(_ctx(tmp_path, mock_http(_routes(), calls)))
    # Two requests: the money.com.tr page and the viewer. Nothing for 5M.
    assert calls == [MIGROSKOP.listing_url, MIGROSKOP.viewer_url]
    assert FIVE_M_LISTING not in calls and FIVE_M_VIEWER not in calls
    (migroskop,) = result.brochures
    assert migroskop.id == "migros-migroskop-910" and migroskop.product_count == 242
    assert set(result.product_files) == {migroskop.id}
    assert result.retired_ids == frozenset()
    assert "Migroskop: 21 products skipped (21 no price, only a discount badge)" in result.warnings
    assert "Migroskop: 172 Money prices" in result.warnings


def test_collect_rejects_the_wrong_publication(tmp_path) -> None:
    routes = _routes()
    routes[MIGROSKOP.listing_url] = _page("migroskop-dijital.html").replace("Güncel Migroskop", "Güncel 5M Migroskop")
    with pytest.raises(SourceError, match="expected Migroskop"):
        MigrosSource().collect(_ctx(tmp_path, mock_http(routes)))


def test_collect_rejects_a_viewer_showing_another_issue(tmp_path) -> None:
    routes = _routes()
    routes[MIGROSKOP.listing_url] = _page("migroskop-dijital.html").replace("<b>910</b>", "<b>911</b>")
    with pytest.raises(SourceError, match="viewer shows issue 910 but money.com.tr lists issue 911"):
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
    # A chain's first run: the issue started on 5 November, so it is not "new" today.
    assert brochures["migros-migroskop-910"]["first_seen"] == "2026-11-05T00:00:00Z"
    assert report.new_brochure_ids == []
    products = json.loads((out / "products/migros-migroskop-910.json").read_text(encoding="utf-8"))
    validate_products(products)
    first, bread = products["products"][0], next(p for p in products["products"] if p["name"].startswith("Untad"))
    # Without a member price the fields are left out entirely; with one both are written.
    assert "member_price_minor" not in first and "member_price_label" not in first
    assert (bread["price_minor"], bread["member_price_minor"], bread["member_price_label"]) == (9995, 7795, "Money ile")
    chain = next(c for c in catalog["chains"] if c["id"] == "migros")
    assert (chain["status"], chain["brand_color"], chain["web_url"]) == (
        "ok",
        "#FF8300",
        "https://www.money.com.tr/migroskop-dijital",
    )


def test_old_5m_brochure_is_dropped_on_the_next_run(tmp_path) -> None:
    out = tmp_path / "out"
    # The previous output, written while 5M was still taken: Migroskop 910 and 5M 286.
    five_m = _old("migros-5m-286")
    five_m_products = ProductFile(five_m.id, (Product(name="Migros Üçgen Peynir 120 g", price_minor=5495),))

    class Previous:
        chain_id = "migros"

        def collect(self, ctx: SourceContext):
            real = MigrosSource().collect(ctx)
            real.brochures.append(five_m)
            real.product_files[five_m.id] = five_m_products
            return real

    run([Previous()], CHAINS, out, out, TODAY, NOW, http=mock_http(_routes()))
    assert (out / "products/migros-5m-286.json").is_file()

    report = run([MigrosSource()], CHAINS, out, out, TODAY, NOW + timedelta(hours=6), http=mock_http(_routes()))
    assert report.exit_code == 0
    catalog = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    assert [b["id"] for b in catalog["brochures"] if b["chain_id"] == "migros"] == ["migros-migroskop-910"]
    assert not (out / "products/migros-5m-286.json").exists()
    assert "retired 1 brochures of publications no longer taken" in report.sources[0].warnings


def test_retired_brochures_stay_when_the_source_fails(tmp_path) -> None:
    out = tmp_path / "out"
    five_m = _old("migros-5m-286")

    class Previous:
        chain_id = "migros"

        def collect(self, ctx: SourceContext):
            real = MigrosSource().collect(ctx)
            real.brochures.append(five_m)
            real.product_files[five_m.id] = ProductFile(five_m.id, (Product(name="Su", price_minor=500),))
            return real

    run([Previous()], CHAINS, out, out, TODAY, NOW, http=mock_http(_routes()))
    broken = {MIGROSKOP.listing_url: "<html></html>"}
    report = run([MigrosSource()], CHAINS, out, out, TODAY, NOW + timedelta(hours=6), http=mock_http(broken))
    assert not report.sources[0].ok
    ids = [b["id"] for b in json.loads((out / "catalog.json").read_text(encoding="utf-8"))["brochures"]]
    # A failed run keeps the previous state untouched, 5M included.
    assert "migros-5m-286" in ids and "migros-migroskop-910" in ids
