from __future__ import annotations

from datetime import date

import pytest

from scraper.core.dates import DateRange, parse_date_label

TODAY = date(2026, 11, 13)


def d(text: str) -> date:
    return date.fromisoformat(text)


@pytest.mark.parametrize(
    ("label", "today", "expected"),
    [
        ("13 Kasım Cuma", TODAY, ("2026-11-13", "2026-11-13")),
        ("03 Kasım Salı", TODAY, ("2026-11-03", "2026-11-03")),
        ("13-19 Kasım", TODAY, ("2026-11-13", "2026-11-19")),
        ("7 - 13 Kasım", TODAY, ("2026-11-07", "2026-11-13")),
        ("22 Ekim - 04 Kasım 2026", TODAY, ("2026-10-22", "2026-11-04")),
        ("1 - 30 Kasım 2026", TODAY, ("2026-11-01", "2026-11-30")),
        ("16 Ekim-15 Kasım", TODAY, ("2026-10-16", "2026-11-15")),
        ("18-24kasim", TODAY, ("2026-11-18", "2026-11-24")),
        ("13-19KASIM", TODAY, ("2026-11-13", "2026-11-19")),
        ("10-23-KASIM-2026_Insert-1-8-scaled", TODAY, ("2026-11-10", "2026-11-23")),
        ("Haftanın Fırsatları 18 - 24 Kasım 2026", TODAY, ("2026-11-18", "2026-11-24")),
        ("Kasım 2026", TODAY, ("2026-11-01", "2026-11-30")),
        ("16 - 29 Nisan 2026", TODAY, ("2026-04-16", "2026-04-29")),
        # Year boundary: the year closest to today wins.
        ("30 Aralık - 5 Ocak", date(2026, 12, 29), ("2026-12-30", "2027-01-05")),
        ("29 Aralık", date(2027, 1, 2), ("2026-12-29", "2026-12-29")),
        # Extra coverage beyond the required table.
        ("Gratis Kasım Kataloğu", TODAY, ("2026-11-01", "2026-11-30")),
        ("13–19 Kasım", TODAY, ("2026-11-13", "2026-11-19")),
        ("13 — 19 Kasım", TODAY, ("2026-11-13", "2026-11-19")),
        ("13-19 kasım", TODAY, ("2026-11-13", "2026-11-19")),
        ("13-19 KASIM", TODAY, ("2026-11-13", "2026-11-19")),
        ("29 ARALIK - 4 OCAK", date(2026, 12, 20), ("2026-12-29", "2027-01-04")),
        ("29 Aralık 2026 - 4 Ocak 2027", TODAY, ("2026-12-29", "2027-01-04")),
        ("28 Aralık - 3 Ocak 2027", TODAY, ("2026-12-28", "2027-01-03")),
        ("ŞUBAT 2027", TODAY, ("2027-02-01", "2027-02-28")),
        ("İNDİRİM 1-7 Eylül", date(2026, 9, 1), ("2026-09-01", "2026-09-07")),
        ("Ağustos", date(2026, 8, 20), ("2026-08-01", "2026-08-31")),
        ("Aralık", date(2027, 1, 3), ("2026-12-01", "2026-12-31")),
        ("Ocak", date(2026, 12, 30), ("2027-01-01", "2027-01-31")),
        ("x7Kq2m-18-24kasim.pdf", TODAY, ("2026-11-18", "2026-11-24")),
        ("01 Mayıs Cuma", date(2026, 4, 28), ("2026-05-01", "2026-05-01")),
    ],
)
def test_parse_date_label(label: str, today: date, expected: tuple[str, str]) -> None:
    assert parse_date_label(label, today) == DateRange(d(expected[0]), d(expected[1]))


@pytest.mark.parametrize(
    "label",
    [
        "ÇOK AL AZ ÖDE",
        "",
        "32 Kasım",
        "31 Kasım",
        "19-13 Kasım",
        "Hekim önerisi",
        "Smart TV",
        "Haftanın Fırsatları",
    ],
)
def test_unparseable_labels_return_none(label: str) -> None:
    assert parse_date_label(label, TODAY) is None


def test_result_unpacks_as_tuple() -> None:
    start, end = parse_date_label("13-19 Kasım", TODAY)
    assert (start, end) == (date(2026, 11, 13), date(2026, 11, 19))


def test_leap_day_without_year_picks_a_leap_year() -> None:
    assert parse_date_label("29 Şubat", date(2028, 2, 10)) == DateRange(date(2028, 2, 29), date(2028, 2, 29))
