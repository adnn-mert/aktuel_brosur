from __future__ import annotations

import re
from datetime import date

import pytest

from scraper.core.ids import MAX_ID_LENGTH, brochure_id, slugify
from scraper.core.validate import load_schema

PATTERN = re.compile(load_schema("catalog")["$defs"]["brochureId"]["pattern"])


def test_readable_id() -> None:
    assert brochure_id("sok", date(2026, 11, 18), "Haftanın Fırsatları") == "sok-2026-11-18-haftanin-firsatlari"


def test_stable() -> None:
    a = brochure_id("a101", "Aldın Aldın", "Xk4pT9wLqZ", "Rb7nM2cVfH")
    b = brochure_id("a101", "Aldın Aldın", "Xk4pT9wLqZ", "Rb7nM2cVfH")
    assert a == b
    assert a != brochure_id("a101", "Aldın Aldın", "Xk4pT9wLqZ", "Jq1sD8yGtE")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ÇOK AL AZ ÖDE", "cok-al-az-ode"),
        ("İNDİRİM ışığı", "indirim-isigi"),
        ("Şok Gönül Üzüm", "sok-gonul-uzum"),
        ("KASIM", "kasim"),
        ("  --Çay & Şeker!!  ", "cay-seker"),
    ],
)
def test_turkish_characters_are_folded(text: str, expected: str) -> None:
    assert slugify(text) == expected


@pytest.mark.parametrize(
    "parts",
    [
        ("13 Kasım Cuma",),
        (date(2026, 11, 13), "İndirim Günleri / Özel!"),
        (910,),
        ("???",),
        ("x" * 300,),
        ("Haftanın Fırsatları", "a" * 90, date(2026, 11, 18)),
    ],
)
def test_ids_match_schema_pattern(parts) -> None:
    bid = brochure_id("migros_5m", *parts)
    assert PATTERN.fullmatch(bid)
    assert len(bid) <= MAX_ID_LENGTH
    assert bid.startswith("migros_5m-")


def test_long_ids_stay_distinct() -> None:
    a = brochure_id("bim", "x" * 200 + "a")
    b = brochure_id("bim", "x" * 200 + "b")
    assert a != b
    assert len(a) == len(b) <= MAX_ID_LENGTH


def test_non_ascii_only_parts_get_digest() -> None:
    a = brochure_id("bim", "★")
    b = brochure_id("bim", "☆")
    assert a != b
    assert PATTERN.fullmatch(a)


@pytest.mark.parametrize("chain", ["BIM", "bim-market", "", "şok"])
def test_invalid_chain_id_is_refused(chain: str) -> None:
    with pytest.raises(ValueError):
        brochure_id(chain, "x")


def test_parts_are_required() -> None:
    with pytest.raises(ValueError):
        brochure_id("bim")
