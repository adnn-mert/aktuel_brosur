from __future__ import annotations

import json

import pytest

from scraper.__main__ import main
from scraper.tests.conftest import EXAMPLES


def test_validate_example_catalog(capsys) -> None:
    assert main(["validate", str(EXAMPLES / "catalog.example.json")]) == 0
    assert "valid catalog" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("kind", "name"),
    [("products", "products.example.json"), ("health", "health.example.json")],
)
def test_validate_other_examples(kind: str, name: str) -> None:
    assert main(["validate", "--type", kind, str(EXAMPLES / name)]) == 0


def test_validate_broken_catalog(tmp_path, catalog, capsys) -> None:
    catalog["brochures"][0]["pages"] = []
    catalog["brochures"][1]["chain_id"] = "nope"
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    assert main(["validate", str(path)]) == 1
    err = capsys.readouterr().err
    assert "brochures[0].pages" in err


def test_validate_reports_consistency_errors(tmp_path, catalog, capsys) -> None:
    catalog["brochures"][1]["chain_id"] = "nope"
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    assert main(["validate", str(path)]) == 1
    assert "brochures[1].chain_id" in capsys.readouterr().err


def test_validate_invalid_json(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text("{not json", encoding="utf-8")
    assert main(["validate", str(path)]) == 1


def test_validate_missing_file(tmp_path) -> None:
    assert main(["validate", str(tmp_path / "missing.json")]) == 2
