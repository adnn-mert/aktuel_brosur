from __future__ import annotations

import copy
import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schema" / "examples"


@cache
def _load(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


@pytest.fixture
def catalog() -> dict[str, Any]:
    return copy.deepcopy(_load("catalog.example.json"))


@pytest.fixture
def products() -> dict[str, Any]:
    return copy.deepcopy(_load("products.example.json"))


@pytest.fixture
def health() -> dict[str, Any]:
    return copy.deepcopy(_load("health.example.json"))
