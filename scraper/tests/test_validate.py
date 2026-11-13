from __future__ import annotations

from typing import Any

import pytest
from jsonschema import Draft202012Validator

from scraper.core.validate import (
    ContractError,
    load_schema,
    validate_catalog,
    validate_health,
    validate_products,
)


def _brochure(catalog: dict[str, Any], brochure_id: str) -> dict[str, Any]:
    return next(b for b in catalog["brochures"] if b["id"] == brochure_id)


def _errors(fn, data) -> str:
    with pytest.raises(ContractError) as info:
        fn(data)
    return "\n".join(info.value.errors)


@pytest.mark.parametrize("name", ["catalog", "products", "health"])
def test_schemas_are_valid_draft_2020_12(name: str) -> None:
    schema = load_schema(name)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)


def test_examples_pass(catalog, products, health) -> None:
    validate_catalog(catalog)
    validate_products(products)
    validate_health(health)


def test_example_catalog_covers_all_kinds_and_time_windows(catalog) -> None:
    kinds = {b["kind"] for b in catalog["brochures"]}
    assert kinds == {"pages", "products", "both"}
    today = "2026-11-13"
    assert any(b["valid_from"] <= today <= b["valid_to"] for b in catalog["brochures"])
    assert any(b["valid_from"] > today for b in catalog["brochures"])
    assert any(b["valid_to"] < today for b in catalog["brochures"])
    chains = {c["id"]: c["kind"] for c in catalog["chains"]}
    assert {"bim", "sok", "migros", "watsons"} <= {k for k, v in chains.items() if v == "scraped"}
    # A101 blocks automated access, so the app opens its own poster page instead.
    assert {"a101", "carrefoursa", "gratis"} <= {k for k, v in chains.items() if v == "webview"}
    assert not any(b["chain_id"] == "a101" for b in catalog["brochures"])
    assert any(p["url"].startswith("media/sok/") for b in catalog["brochures"] for p in b["pages"])


def test_example_products_match_migros_brochure(catalog, products) -> None:
    migros = _brochure(catalog, products["brochure_id"])
    assert migros["products_url"] == f"products/{products['brochure_id']}.json"
    assert migros["product_count"] == len(products["products"])


# --- schema rejections ---------------------------------------------------------------


def test_pages_kind_with_empty_pages_is_rejected(catalog) -> None:
    b = catalog["brochures"][0]
    b["kind"] = "pages"
    b["products_url"] = None
    b["product_count"] = 0
    b["pages"] = []
    assert "brochures[0].pages" in _errors(validate_catalog, catalog)


def test_both_kind_with_empty_pages_is_rejected(catalog) -> None:
    assert catalog["brochures"][0]["kind"] == "both"
    catalog["brochures"][0]["pages"] = []
    assert "brochures[0].pages" in _errors(validate_catalog, catalog)


def test_products_kind_without_products_url_is_rejected(catalog) -> None:
    b = _brochure(catalog, "migros-910")
    b["products_url"] = None
    errors = _errors(validate_catalog, catalog)
    assert "products_url" in errors
    assert "migros-910" in errors


def test_products_kind_with_zero_products_is_rejected(catalog) -> None:
    _brochure(catalog, "migros-910")["product_count"] = 0
    assert "product_count" in _errors(validate_catalog, catalog)


def test_products_kind_may_have_no_pages(catalog) -> None:
    assert _brochure(catalog, "migros-910")["pages"] == []
    validate_catalog(catalog)


def test_pages_kind_must_not_point_to_products(catalog) -> None:
    _brochure(catalog, "bim-2026-11-18-carsamba")["products_url"] = "products/x.json"
    assert "products_url" in _errors(validate_catalog, catalog)


@pytest.mark.parametrize("bad_id", ["BIM", "bim-market", "bim market", "", "şok"])
def test_bad_chain_id_is_rejected(catalog, bad_id: str) -> None:
    catalog["chains"][0]["id"] = bad_id
    errors = _errors(validate_catalog, catalog)
    assert "chains[0].id" in errors


def test_bad_brochure_id_is_rejected(catalog) -> None:
    catalog["brochures"][0]["id"] = "BIM 13 Kasım"
    assert "brochures[0].id" in _errors(validate_catalog, catalog)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cover", "http://cdn1.bim.com.tr/uploads/afisler/a.jpg"),
        ("page", "http://cdn1.bim.com.tr/uploads/afisler/a.jpg"),
        ("page", "media/sok/../../etc/p01.webp"),
        ("page", "/media/sok/p01.webp"),
        ("page", "ftp://example.com/p01.webp"),
        ("page", "media/sok/my page.webp"),
        ("page", "media\\sok\\p01.webp"),
    ],
)
def test_bad_image_url_is_rejected(catalog, field: str, value: str) -> None:
    b = catalog["brochures"][0]
    if field == "cover":
        b["cover"]["url"] = value
        expected = "brochures[0].cover.url"
    else:
        b["pages"][1]["url"] = value
        expected = "brochures[0].pages[1].url"
    errors = _errors(validate_catalog, catalog)
    assert expected in errors
    assert "bim-2026-11-13-cuma" in errors


def test_http_source_url_is_rejected(catalog) -> None:
    catalog["brochures"][2]["source_url"] = "http://www.bim.com.tr/"
    assert "brochures[2].source_url" in _errors(validate_catalog, catalog)


def test_http_web_url_is_rejected(catalog) -> None:
    catalog["chains"][1]["web_url"] = "http://www.a101.com.tr/"
    assert "chains[1].web_url" in _errors(validate_catalog, catalog)


def test_absolute_products_url_is_rejected(catalog) -> None:
    _brochure(catalog, "migros-910")["products_url"] = "https://example.com/products/migros-910.json"
    assert "products_url" in _errors(validate_catalog, catalog)


def test_relative_and_https_urls_are_accepted(catalog) -> None:
    b = catalog["brochures"][0]
    b["pages"][0]["url"] = "media/bim/bim-2026-11-13-cuma/p01.webp"
    b["pages"][1]["url"] = "https://cdn1.bim.com.tr/uploads/afisler/a.jpg?v=2"
    validate_catalog(catalog)


@pytest.mark.parametrize(
    ("path", "value", "field"),
    [
        (("schema_version",), 2, "schema_version"),
        (("generated_at",), "2026-11-13 09:00:12", "generated_at"),
        (("generated_at",), "2026-11-13T09:00:12+03:00", "generated_at"),
        (("generated_at",), "2026-13-45T09:00:12Z", "generated_at"),
        (("min_app_version",), 0, "min_app_version"),
        (("chains", 0, "country"), "tr", "chains[0].country"),
        (("chains", 0, "kind"), "scrape", "chains[0].kind"),
        (("chains", 0, "status"), "broken", "chains[0].status"),
        (("chains", 0, "brand_color"), "red", "chains[0].brand_color"),
        (("chains", 0, "sort_order"), 1.5, "chains[0].sort_order"),
        (("brochures", 0, "valid_from"), "13.11.2026", "brochures[0].valid_from"),
        (("brochures", 0, "valid_to"), "2026-02-30", "brochures[0].valid_to"),
        (("brochures", 0, "product_count"), -1, "brochures[0].product_count"),
        (("brochures", 0, "product_count"), 14.0, "brochures[0].product_count"),
        (("brochures", 0, "pages", 0, "w"), "940", "brochures[0].pages[0].w"),
        (("brochures", 0, "title"), "  ", "brochures[0].title"),
    ],
)
def test_wrong_field_values_are_rejected(catalog, path: tuple, value: Any, field: str) -> None:
    target = catalog
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert field in _errors(validate_catalog, catalog)


def test_missing_required_field_is_named(catalog) -> None:
    del catalog["brochures"][3]["source_url"]
    errors = _errors(validate_catalog, catalog)
    assert "brochures[3].source_url" in errors
    assert "required" in errors


def test_unknown_fields_are_allowed(catalog) -> None:
    catalog["future_root_field"] = {"x": 1}
    catalog["chains"][0]["future_field"] = True
    catalog["brochures"][0]["future_field"] = [1, 2]
    validate_catalog(catalog)


# --- consistency rules ---------------------------------------------------------------


def test_unknown_chain_id_is_rejected(catalog) -> None:
    catalog["brochures"][4]["chain_id"] = "file_market"
    errors = _errors(validate_catalog, catalog)
    assert "brochures[4]" in errors and ".chain_id" in errors and "file_market" in errors


def test_duplicate_brochure_id_is_rejected(catalog) -> None:
    catalog["brochures"][5]["id"] = catalog["brochures"][1]["id"]
    errors = _errors(validate_catalog, catalog)
    assert "brochures[5].id" in errors and "duplicate" in errors


def test_duplicate_chain_id_is_rejected(catalog) -> None:
    catalog["chains"][1]["id"] = "bim"
    assert "chains[1].id" in _errors(validate_catalog, catalog)


def test_valid_from_after_valid_to_is_rejected(catalog) -> None:
    b = catalog["brochures"][3]
    b["valid_from"], b["valid_to"] = "2026-11-20", "2026-11-19"
    errors = _errors(validate_catalog, catalog)
    assert "brochures[3]" in errors and ".valid_from" in errors


def test_open_ended_validity_is_accepted(catalog) -> None:
    catalog["brochures"][3]["valid_to"] = None
    catalog["brochures"][4]["valid_from"] = None
    validate_catalog(catalog)


def test_webview_chain_with_brochure_is_rejected(catalog) -> None:
    catalog["brochures"][0]["chain_id"] = "gratis"
    errors = _errors(validate_catalog, catalog)
    assert "brochures[0]" in errors and ".chain_id" in errors and "webview" in errors


def test_all_problems_are_reported_together(catalog) -> None:
    catalog["chains"][0]["id"] = "BIM"
    catalog["brochures"][0]["source_url"] = "http://x"
    with pytest.raises(ContractError) as info:
        validate_catalog(catalog)
    assert len(info.value.errors) == 2
    assert "chains[0].id" in str(info.value)


def test_non_object_root_is_rejected() -> None:
    assert "<root>" in _errors(validate_catalog, [])


# --- products and health -------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", None),
        ("price_minor", 149.5),
        ("price_minor", -1),
        ("price_minor", "149,50"),
        ("old_price_minor", 1.5),
        ("image", "http://example.com/a.jpg"),
        ("page_index", -1),
        ("source_url", "media/x"),
    ],
)
def test_bad_product_is_rejected(products, field: str, value: Any) -> None:
    products["products"][2][field] = value
    assert f"products[2].{field}" in _errors(validate_products, products)


@pytest.mark.parametrize(("field", "value"), [("currency", "tl"), ("schema_version", 2), ("brochure_id", "Migros 910")])
def test_bad_product_file_root_is_rejected(products, field: str, value: Any) -> None:
    products[field] = value
    assert field in _errors(validate_products, products)


def test_bad_health_is_rejected(health) -> None:
    health["sources"][0]["duration_ms"] = -5
    health["sources"][1]["ok"] = "yes"
    errors = _errors(validate_health, health)
    assert "sources[0].duration_ms" in errors
    assert "sources[1].ok" in errors


def test_health_consistency(health) -> None:
    failed = next(i for i, s in enumerate(health["sources"]) if not s["ok"])
    health["sources"][0]["consecutive_failures"] = 3
    health["sources"][failed]["last_error"] = None
    health["sources"][2]["chain_id"] = "bim"
    errors = _errors(validate_health, health)
    assert "consecutive_failures" in errors
    assert "last_error" in errors
    assert "sources[2].chain_id" in errors
