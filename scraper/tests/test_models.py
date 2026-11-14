from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from scraper.core.models import (
    Brochure,
    BrochureKind,
    Catalog,
    Chain,
    ChainKind,
    ChainStatus,
    HealthReport,
    Page,
    Product,
    ProductFile,
    SourceHealth,
    format_datetime,
    parse_datetime,
)
from scraper.core.validate import validate_catalog, validate_health, validate_products

NOW = datetime(2026, 11, 13, 9, 0, 12, tzinfo=UTC)


def _brochure(**overrides) -> Brochure:
    fields = dict(
        id="sok-2026-11-18-haftanin-firsatlari",
        chain_id="sok",
        title="Haftanın Fırsatları",
        date_label="18 - 24 Kasım 2026",
        valid_from=date(2026, 11, 18),
        valid_to=date(2026, 11, 24),
        kind=BrochureKind.PAGES,
        cover=Page("media/sok/sok-2026-11-18-haftanin-firsatlari/p01.webp", 1600, 2263),
        pages=(Page("media/sok/sok-2026-11-18-haftanin-firsatlari/p01.webp", 1600, 2263),),
        products_url=None,
        product_count=0,
        source_url="https://kurumsal.sokmarket.com.tr/uploads/pdf/x-18-24kasim.pdf",
        first_seen=NOW,
        updated_at=NOW,
    )
    fields.update(overrides)
    return Brochure(**fields)


def _catalog() -> Catalog:
    return Catalog(
        generated_at=NOW,
        min_app_version=1,
        chains=(
            Chain(
                id="sok",
                name="Şok",
                country="TR",
                kind=ChainKind.SCRAPED,
                web_url="https://kurumsal.sokmarket.com.tr/tr/firsatlar",
                status=ChainStatus.OK,
                last_ok_at=NOW,
                sort_order=30,
                brand_color="#FFD100",
            ),
            Chain(
                id="gratis",
                name="Gratis",
                country="TR",
                kind=ChainKind.WEBVIEW,
                web_url="https://www.gratis.com/gratis-katalog",
                status=ChainStatus.OK,
                last_ok_at=None,
                sort_order=70,
                logo_url="logos/gratis.png",
            ),
        ),
        brochures=(_brochure(), _brochure(id="sok-x", valid_from=None, valid_to=None, cover=None, date_label=None)),
    )


def test_catalog_round_trip() -> None:
    cat = _catalog()
    data = cat.to_dict()
    validate_catalog(data)
    assert Catalog.from_dict(data) == cat


def test_example_catalog_round_trip(catalog) -> None:
    model = Catalog.from_dict(catalog)
    out = model.to_dict()
    validate_catalog(out)
    assert out == catalog
    assert Catalog.from_dict(out) == model


def test_example_products_round_trip(products) -> None:
    model = ProductFile.from_dict(products)
    out = model.to_dict()
    validate_products(out)
    assert out == products
    assert ProductFile.from_dict(out) == model


def test_example_health_round_trip(health) -> None:
    model = HealthReport.from_dict(health)
    out = model.to_dict()
    validate_health(out)
    assert out == health
    assert HealthReport.from_dict(out) == model


def test_product_file_round_trip() -> None:
    pf = ProductFile(
        brochure_id="bim-2026-11-13-cuma",
        products=[
            Product(name="Çay 1 kg", price_minor=24950, brand="Çaykur", old_price_minor=27950),
            Product(name="Un", price_minor=8950, quantity_text="5 kg", page_index=0),
        ],
    )
    data = pf.to_dict()
    validate_products(data)
    assert ProductFile.from_dict(data) == pf
    assert isinstance(pf.products, tuple)


def test_member_price_round_trip() -> None:
    with_member = Product(name="Ekmek", price_minor=9995, member_price_minor=7795, member_price_label="Money ile")
    plain = Product(name="Su", price_minor=500)
    data = ProductFile("migros-migroskop-910", (with_member, plain)).to_dict()
    validate_products(data)
    first, second = data["products"]
    assert (first["member_price_minor"], first["member_price_label"]) == (7795, "Money ile")
    # Unset, the fields are left out, so files look exactly as before they existed.
    assert "member_price_minor" not in second and "member_price_label" not in second
    assert ProductFile.from_dict(data).products == (with_member, plain)


def test_product_without_member_fields_reads_as_none() -> None:
    old_style = {
        "name": "Çay",
        "brand": None,
        "quantity_text": None,
        "price_minor": 100,
        "old_price_minor": None,
        "image": None,
        "page_index": None,
        "source_url": None,
    }
    product = Product.from_dict(old_style)
    assert (product.member_price_minor, product.member_price_label) == (None, None)
    assert product.to_dict() == old_style


def test_source_health_round_trip() -> None:
    s = SourceHealth("bim", False, None, "HTTP 403", 1, 0, 1520)
    assert SourceHealth.from_dict(s.to_dict()) == s


def test_models_are_frozen() -> None:
    b = _brochure()
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.title = "x"  # type: ignore[misc]


def test_lists_become_tuples() -> None:
    b = _brochure(pages=[Page("https://a.example/p1.jpg")])
    assert isinstance(b.pages, tuple)
    hash(b)


def test_naive_or_non_utc_datetimes_are_refused() -> None:
    with pytest.raises(ValueError):
        _brochure(first_seen=datetime(2026, 11, 13, 9, 0))
    with pytest.raises(ValueError):
        _brochure(updated_at=datetime(2026, 11, 13, 12, 0, tzinfo=timezone(timedelta(hours=3))))


def test_datetime_format_and_parse() -> None:
    assert format_datetime(NOW) == "2026-11-13T09:00:12Z"
    assert parse_datetime("2026-11-13T09:00:12Z") == NOW
    # Offsets in input are normalised to UTC.
    assert parse_datetime("2026-11-13T12:00:12+03:00") == NOW
    with pytest.raises(ValueError):
        parse_datetime("2026-11-13T09:00:12")
    precise = NOW.replace(microsecond=250000)
    assert parse_datetime(format_datetime(precise)) == precise


def test_optional_chain_fields_are_omitted_when_none() -> None:
    data = _catalog().to_dict()
    assert "logo_url" not in data["chains"][0]
    assert data["chains"][0]["brand_color"] == "#FFD100"
    assert "brand_color" not in data["chains"][1]


def test_from_dict_ignores_unknown_fields(catalog) -> None:
    catalog["brochures"][0]["added_in_v2"] = "x"
    catalog["chains"][0]["added_in_v2"] = "x"
    model = Catalog.from_dict(catalog)
    assert "added_in_v2" not in model.to_dict()["brochures"][0]


def test_enums_serialise_as_plain_strings() -> None:
    data = _catalog().to_dict()
    assert type(data["chains"][0]["kind"]) is str
    assert type(data["brochures"][0]["kind"]) is str
