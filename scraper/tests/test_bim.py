from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from scraper.core.media import MediaWriter
from scraper.core.models import Brochure, BrochureKind, Page, Product, ProductFile
from scraper.core.source import SourceContext, SourceError
from scraper.sources import bim
from scraper.sources.bim import (
    POSTERS_URL,
    BimSource,
    build_brochures,
    parse_poster_groups,
    parse_product_tabs,
    parse_products,
)
from scraper.tests.conftest import fixture_text, mock_http

TODAY = date(2026, 11, 13)
NOW = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
TAB_URL = "https://www.bim.com.tr/Categories/100/aktuel-urunler.aspx?top=1&Bim_AktuelTarihKey={}"
FIXTURE_TABS = ("1705", "1711", "1709")
EMPTY_TAB = '<html><body><div class="productArea"><div class="row"></div></div></body></html>'


def _posters() -> str:
    return fixture_text("bim", "afisler.html")


def _tab(key: str) -> str:
    return fixture_text("bim", f"aktuel-urunler-{key}.html")


def _by_id(brochures: list[Brochure]) -> dict[str, Brochure]:
    return {b.id: b for b in brochures}


# --- poster page -----------------------------------------------------------------------


def test_poster_groups() -> None:
    groups = parse_poster_groups(_posters())
    assert len(groups) == 19
    assert [g.label for g in groups[:3]] == ["03 Kasım Salı", "04 Kasım Çarşamba", "06 Kasım Cuma"]
    assert {g.section for g in groups} == {"aktuel", "indirim"}
    friday = next(g for g in groups if g.label == "13 Kasım Cuma")
    assert friday.section == "aktuel"
    assert friday.pages == (
        "https://cdn1.bim.com.tr/uploads/afisler/aaf9e731-9b7b-416f-891e-94f7d7ef6b74.jpg",
        "https://cdn1.bim.com.tr/uploads/afisler/7d055993-4554-46e6-a33a-d2b9e308bca8.jpg",
        "https://cdn1.bim.com.tr/uploads/afisler/b6626da9-7499-4cf7-94b1-a903503c57c0.jpg",
        "https://cdn1.bim.com.tr/uploads/afisler/8b852d1f-ad34-4656-85a8-8deff0f59b49.jpg",
    )
    assert friday.thumbnails[0] == "https://cdn1.bim.com.tr/uploads/afisler/k_aaf9e731-9b7b-416f-891e-94f7d7ef6b74.jpg"


def test_empty_poster_slots_are_skipped() -> None:
    groups = {g.label: g for g in parse_poster_groups(_posters())}
    # The site renders a not-yet-uploaded poster as ".../uploads/afisler/" with no file.
    assert groups["18 Kasım Çarşamba"].pages == ()
    assert len(groups["20 Kasım Cuma"].pages) == 3


def test_product_tabs_from_header_menu() -> None:
    tabs = parse_product_tabs(_posters())
    assert len(tabs) == 14
    assert sum(t.section == "indirim" for t in tabs) == 2
    friday = next(t for t in tabs if t.label == "13 Kasım Cuma")
    assert (friday.section, friday.url) == ("aktuel", TAB_URL.format("1705"))
    discount = next(t for t in tabs if t.url.endswith("1709"))
    assert (discount.section, discount.label) == ("indirim", "07-13 Kasım")


# --- product tabs ----------------------------------------------------------------------


def test_products_of_a_tab() -> None:
    parsed = parse_products(_tab("1705"))
    assert parsed.skipped == 0
    # 76 cards, two of which are image-only adverts.
    assert len(parsed.products) == 74
    first = parsed.products[0]
    assert first == Product(
        name="TEK FİYAT PLASTİK ÜRÜNLER",
        price_minor=2500,
        brand="HOBBY LİFE",
        quantity_text=None,
        old_price_minor=None,
        image="https://cdn1.bim.com.tr/uploads/aktuel-urunler/1705_kucuk_543X467_5247_1_0016_vector-smart-object.jpg",
        page_index=None,
        source_url="https://www.bim.com.tr/aktuel-urunler/tek-fiyat-plastik-urunler-6-11/aktuel.aspx",
    )
    kettle = next(p for p in parsed.products if p.name == "ÇAYDANLIK")
    assert (kettle.brand, kettle.price_minor) == ("BONERA", 99900)
    # Lazy-loaded cards keep the address in "xsrc".
    assert kettle.image and kettle.image.endswith("1705_kucuk_543X467_3923_1_0010_vector-smart-object.jpg")
    box = next(p for p in parsed.products if p.name == "DONDURUCU SAKLAMA KABI")
    assert (box.quantity_text, box.brand) == ("1.4 L", None)


def test_thousands_separator() -> None:
    fridge = parse_products(_tab("1711")).products[0]
    assert (fridge.name, fridge.brand, fridge.price_minor) == ("NOFROST BUZDOLABI KEY 490 NFS", "KEYSMART", 3690000)


def test_discount_tab_has_old_prices() -> None:
    products = parse_products(_tab("1709")).products
    assert len(products) == 36
    tea = products[0]
    assert (tea.brand, tea.name, tea.quantity_text) == ("Lipton", "Siyah Çay Doğu Karadeniz", "1000 g")
    assert (tea.price_minor, tea.old_price_minor) == (34500, 42900)
    lavash = next(p for p in products if p.name == "Lavaş Tortilla")
    assert (lavash.price_minor, lavash.old_price_minor) == (6250, 7950)


def test_unreadable_prices_are_counted() -> None:
    card = (
        '<div class="product"><h2 class="title">{name}</h2><div class="priceArea">'
        '<a class="gButton"><div class="text quantify">{price}</div>'
        '<div class="kusurArea"><span class="number">00</span></div></a></div></div>'
    )
    html = '<div class="productArea">' + card.format(name="Su", price="5,") + card.format(name="Çay", price="?") + "</div>"
    parsed = parse_products(html)
    assert [p.name for p in parsed.products] == ["Su"]
    assert parsed.skipped == 1


@pytest.mark.parametrize("html", ["", "<html><body><p>Bakım çalışması</p></body></html>"])
def test_unrelated_html_raises(html: str) -> None:
    with pytest.raises(SourceError, match="layout"):
        parse_poster_groups(html)
    with pytest.raises(SourceError, match="layout"):
        parse_products(html)
    assert parse_product_tabs(html) == []


# --- joining posters and products ------------------------------------------------------


def _build() -> tuple[dict[str, Brochure], dict[str, ProductFile]]:
    tabs = {t.url: t for t in parse_product_tabs(_posters())}
    tab_products = [(tabs[TAB_URL.format(k)], parse_products(_tab(k)).products) for k in FIXTURE_TABS]
    brochures, files = build_brochures(parse_poster_groups(_posters()), tab_products, TODAY, NOW)
    return _by_id(brochures), files


def test_build_brochures() -> None:
    brochures, files = _build()
    assert len(brochures) == 19
    friday = brochures["bim-aktuel-2026-11-13"]
    assert friday.kind is BrochureKind.BOTH
    assert (friday.title, friday.date_label) == ("13 Kasım Cuma", "13 Kasım Cuma")
    # Sales start on the 13th; the goods stay on the shelf for the week.
    assert (friday.valid_from, friday.valid_to) == (date(2026, 11, 13), date(2026, 11, 19))
    assert len(friday.pages) == 4 and friday.pages[0].w is None
    assert friday.cover == Page("https://cdn1.bim.com.tr/uploads/afisler/k_aaf9e731-9b7b-416f-891e-94f7d7ef6b74.jpg")
    assert friday.products_url == "products/bim-aktuel-2026-11-13.json"
    assert friday.product_count == 74 == len(files[friday.id].products)
    assert friday.source_url == POSTERS_URL

    # A product tab without posters (the poster slot is still empty).
    wednesday = brochures["bim-aktuel-2026-11-18"]
    assert (wednesday.kind, wednesday.product_count, wednesday.pages, wednesday.cover) == (
        BrochureKind.PRODUCTS,
        17,
        (),
        None,
    )
    assert wednesday.source_url == TAB_URL.format("1711")

    discount = brochures["bim-indirim-2026-11-07-2026-11-13"]
    assert (discount.kind, discount.product_count, len(discount.pages)) == (BrochureKind.BOTH, 36, 2)

    # Posters only: their product tab was not part of this build.
    tuesday = brochures["bim-aktuel-2026-11-03"]
    assert (tuesday.kind, tuesday.products_url, tuesday.product_count) == (BrochureKind.PAGES, None, 0)

    assert (tuesday.valid_from, tuesday.valid_to) == (date(2026, 11, 3), date(2026, 11, 9))
    assert (wednesday.valid_from, wednesday.valid_to) == (date(2026, 11, 18), date(2026, 11, 24))
    # İndirim ranges are printed with their real end date and stay untouched.
    assert (discount.valid_from, discount.valid_to) == (date(2026, 11, 7), date(2026, 11, 13))
    assert brochures["bim-indirim-2026-11-13-2026-11-16"].valid_to == date(2026, 11, 16)

    undated = brochures["bim-indirim-cok-al-az-ode"]
    assert (undated.valid_from, undated.valid_to, undated.date_label) == (None, None, "ÇOK AL AZ ÖDE")
    assert len(undated.pages) == 2

    year_long = brochures["bim-indirim-2026-03-24-2026-12-31"]
    assert (year_long.valid_from, year_long.valid_to) == (date(2026, 3, 24), date(2026, 12, 31))
    assert set(files) == {friday.id, wednesday.id, discount.id}


@pytest.mark.parametrize(
    ("section", "label", "expected"),
    [
        ("aktuel", "13 Kasım Cuma", (date(2026, 11, 13), date(2026, 11, 19))),
        ("aktuel", "29 Aralık Salı", (date(2026, 12, 29), date(2027, 1, 4))),
        ("aktuel", "03-30 Kasım", (date(2026, 11, 3), date(2026, 11, 30))),
        ("indirim", "13 Kasım Cuma", (date(2026, 11, 13), date(2026, 11, 13))),
        ("indirim", "13-19 Kasım", (date(2026, 11, 13), date(2026, 11, 19))),
        ("aktuel", "ÇOK AL AZ ÖDE", None),
    ],
)
def test_validity(section: str, label: str, expected) -> None:
    assert bim.validity(section, label, TODAY) == expected
    # Ids keep using the printed date, so extending validity never renames a brochure.
    assert bim.bim_brochure_id("aktuel", "13 Kasım Cuma", TODAY) == "bim-aktuel-2026-11-13"


# --- collect (network mocked) ----------------------------------------------------------


def _routes() -> dict[str, str]:
    routes = {POSTERS_URL: _posters()}
    for tab in parse_product_tabs(_posters()):
        key = tab.url.rsplit("=", 1)[1]
        routes[tab.url] = _tab(key) if key in FIXTURE_TABS else EMPTY_TAB
    return routes


def _ctx(tmp_path, http, previous=(), previous_products=lambda _id: None) -> SourceContext:
    return SourceContext(
        http=http,
        today=TODAY,
        now=NOW,
        media=MediaWriter(tmp_path, None),
        previous=tuple(previous),
        previous_products=previous_products,
    )


def test_collect(tmp_path) -> None:
    calls: list[str] = []
    result = BimSource().collect(_ctx(tmp_path, mock_http(_routes(), calls)))
    # One poster page plus one request per product tab, then one per cover thumbnail.
    assert len([c for c in calls if "/k_" not in c]) == 1 + 14
    assert len([c for c in calls if "/k_" in c]) == 18
    # The mocked CDN answers 404, so the sizes stay unknown and the run still succeeds.
    assert "18 cover sizes could not be read" in result.warnings
    assert len(result.brochures) == 19
    assert set(result.product_files) == {
        "bim-aktuel-2026-11-13",
        "bim-aktuel-2026-11-18",
        "bim-indirim-2026-11-07-2026-11-13",
    }


def test_collect_reuses_past_product_tabs(tmp_path) -> None:
    calls: list[str] = []
    old_products = ProductFile("bim-aktuel-2026-11-03", (Product(name="Eski ürün", price_minor=100),))
    old = Brochure(
        id="bim-aktuel-2026-11-03",
        chain_id="bim",
        title="03 Kasım Salı",
        date_label="03 Kasım Salı",
        valid_from=date(2026, 11, 3),
        valid_to=date(2026, 11, 3),
        kind=BrochureKind.BOTH,
        cover=None,
        pages=(Page("https://cdn1.bim.com.tr/uploads/afisler/x.jpg"),),
        products_url="products/bim-aktuel-2026-11-03.json",
        product_count=1,
        source_url=POSTERS_URL,
        first_seen=NOW,
        updated_at=NOW,
    )
    ctx = _ctx(tmp_path, mock_http(_routes(), calls), [old], {old.id: old_products}.get)
    result = BimSource().collect(ctx)
    assert TAB_URL.format("1697") not in calls
    assert len([c for c in calls if "/k_" not in c]) == 14
    assert result.product_files[old.id].products == old_products.products
    assert "1 past product tabs reused" in result.warnings


# --- cover sizes -----------------------------------------------------------------------

THUMB = "https://cdn1.bim.com.tr/uploads/afisler/k_aaf9e731-9b7b-416f-891e-94f7d7ef6b74.jpg"
POSTER = "https://cdn1.bim.com.tr/uploads/afisler/aaf9e731-9b7b-416f-891e-94f7d7ef6b74.jpg"


def _covered(bid: str, cover: Page | None) -> Brochure:
    return Brochure(
        id=bid,
        chain_id="bim",
        title=bid,
        date_label=None,
        valid_from=None,
        valid_to=None,
        kind=BrochureKind.PAGES,
        cover=cover,
        pages=(Page(POSTER),),
        products_url=None,
        product_count=0,
        source_url=POSTERS_URL,
        first_seen=NOW,
        updated_at=NOW,
    )


def test_add_cover_sizes() -> None:
    measured: list[str] = []

    def measure(url: str) -> tuple[int, int] | None:
        measured.append(url)
        return None if "broken" in url else (258, 387)

    known_url = THUMB.replace("aaf9", "0000")
    brochures = [
        _covered("a", Page(THUMB)),
        _covered("same-thumb", Page(THUMB)),
        _covered("known", Page(known_url)),
        _covered("poster-cover", Page(POSTER)),
        _covered("no-cover", None),
        _covered("broken", Page(THUMB.replace("aaf9", "broken"))),
    ]
    out, missing = bim.add_cover_sizes(brochures, {known_url: (300, 450)}, measure)
    by_id = _by_id(out)
    assert by_id["a"].cover == Page(THUMB, 258, 387)
    assert by_id["same-thumb"].cover == Page(THUMB, 258, 387)
    assert by_id["known"].cover == Page(known_url, 300, 450)
    # Full-size posters are never downloaded just to learn their size.
    assert by_id["poster-cover"].cover == Page(POSTER)
    assert by_id["poster-cover"].pages == (Page(POSTER),)
    assert by_id["no-cover"].cover is None
    assert by_id["broken"].cover.w is None and missing == 1
    # One request per distinct unknown thumbnail.
    assert measured == [THUMB, THUMB.replace("aaf9", "broken")]


def test_collect_measures_covers_once(tmp_path) -> None:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (258, 387)).save(buffer, format="JPEG")
    routes: dict[str, object] = dict(_routes())
    thumbs = [b.cover.url for b in build_brochures(parse_poster_groups(_posters()), [], TODAY, NOW)[0] if b.cover]
    for url in thumbs:
        routes[url] = buffer.getvalue()

    calls: list[str] = []
    first = BimSource().collect(_ctx(tmp_path, mock_http(routes, calls)))
    friday = _by_id(first.brochures)["bim-aktuel-2026-11-13"]
    assert (friday.cover.w, friday.cover.h) == (258, 387)
    assert all(b.cover.w == 258 for b in first.brochures if b.cover and "/k_" in b.cover.url)
    assert not any("cover sizes" in w for w in first.warnings)
    # Poster pages keep unknown sizes and are never requested.
    assert all(p.w is None for b in first.brochures for p in b.pages)
    assert not any(c in calls for b in first.brochures for c in (p.url for p in b.pages))

    # Next run: sizes come from the previous output, no image is requested again.
    calls.clear()
    BimSource().collect(_ctx(tmp_path, mock_http(routes, calls), previous=first.brochures))
    assert [c for c in calls if "/k_" in c] == []


def test_collect_blocked_site(tmp_path) -> None:
    http = mock_http({POSTERS_URL: (403, "Access denied")})
    with pytest.raises(SourceError, match="HTTP 403"):
        BimSource().collect(_ctx(tmp_path, http))


def test_collect_fails_when_most_prices_are_unreadable(tmp_path, monkeypatch) -> None:
    routes = _routes()
    broken = bim.ParsedProducts(products=(Product(name="x", price_minor=1),), skipped=5)
    monkeypatch.setattr(bim, "parse_products", lambda _html: broken)
    with pytest.raises(SourceError, match="no readable price"):
        BimSource().collect(_ctx(tmp_path, mock_http(routes)))
