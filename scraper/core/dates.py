"""Parsing of the free-form Turkish date labels printed on brochures.

Labels come from page headings, button attributes and file names, e.g.
"13-19 Kasım", "22 Ekim - 04 Kasım 2026" or "10-23-KASIM-2026_Insert-1-8-scaled".
Unparseable input yields ``None``: a missing date is normal, never an error.
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from typing import NamedTuple

from scraper.core.text import fold_turkish, normalize_dashes


class DateRange(NamedTuple):
    valid_from: date
    valid_to: date


_MONTHS: dict[str, int] = {
    "ocak": 1,
    "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "agustos": 8,
    "eylul": 9,
    "ekim": 10,
    "kasim": 11,
    "aralik": 12,
}

# Word boundaries on the month keep "hekim" or "smart" from matching.
_MONTH = r"(?<![a-z])(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")(?![a-z])"
_DAY = r"(?<!\d)(\d{1,2})(?!\d)"
_YEAR = r"(?:\s*-?\s*(?<!\d)(\d{4})(?!\d))?"
_SEP = r"\s*-\s*"

# Most specific pattern first; the first one that matches decides the result.
_CROSS_MONTH = re.compile(_DAY + r"\s*\.?\s*" + _MONTH + _YEAR + _SEP + _DAY + r"\s*\.?\s*" + _MONTH + _YEAR)
_SAME_MONTH = re.compile(_DAY + _SEP + _DAY + r"\s*-?\s*" + _MONTH + _YEAR)
_SINGLE_DAY = re.compile(_DAY + r"\s*\.?\s*-?\s*" + _MONTH + _YEAR)
_MONTH_ONLY = re.compile(_MONTH + _YEAR)


def parse_date_label(label: str, today: date) -> DateRange | None:
    """Turn a Turkish date label into an inclusive date range.

    When the label has no year, the year that puts the range closest to ``today``
    is chosen, so labels around New Year resolve correctly in both directions.
    """
    if not label:
        return None
    text = normalize_dashes(fold_turkish(label))

    if m := _CROSS_MONTH.search(text):
        d1, m1, y1, d2, m2, y2 = m.groups()
        return _cross_month(int(d1), _MONTHS[m1], _int(y1), int(d2), _MONTHS[m2], _int(y2), today)
    if m := _SAME_MONTH.search(text):
        d1, d2, mon, year = m.groups()
        month = _MONTHS[mon]
        return _resolve(lambda y: _range(y, month, int(d1), y, month, int(d2)), _int(year), today)
    if m := _SINGLE_DAY.search(text):
        day, mon, year = m.groups()
        month = _MONTHS[mon]
        return _resolve(lambda y: _range(y, month, int(day), y, month, int(day)), _int(year), today)
    if m := _MONTH_ONLY.search(text):
        mon, year = m.groups()
        month = _MONTHS[mon]
        return _resolve(
            lambda y: _range(y, month, 1, y, month, calendar.monthrange(y, month)[1]),
            _int(year),
            today,
        )
    return None


def _cross_month(
    d1: int, m1: int, y1: int | None, d2: int, m2: int, y2: int | None, today: date
) -> DateRange | None:
    # A range that runs from a later month into an earlier one crosses New Year.
    wraps = m2 < m1
    if y1 is not None and y2 is not None:
        return _range(y1, m1, d1, y2, m2, d2)
    if y2 is not None:
        return _range(y2 - 1 if wraps else y2, m1, d1, y2, m2, d2)
    if y1 is not None:
        return _range(y1, m1, d1, y1 + 1 if wraps else y1, m2, d2)
    return _resolve(lambda y: _range(y, m1, d1, y + 1 if wraps else y, m2, d2), None, today)


def _resolve(build, year: int | None, today: date) -> DateRange | None:
    """Build the range for ``year``, or for the year nearest to ``today``."""
    if year is not None:
        return build(year)
    candidates = [r for y in (today.year - 1, today.year, today.year + 1) if (r := build(y))]
    if not candidates:
        return None
    # On a tie prefer the later range: brochures are announced ahead of time.
    return min(candidates, key=lambda r: (_distance(r, today), -r.valid_from.toordinal()))


def _distance(r: DateRange, today: date) -> int:
    if r.valid_from <= today <= r.valid_to:
        return 0
    return min(abs((r.valid_from - today).days), abs((r.valid_to - today).days))


def _range(y1: int, m1: int, d1: int, y2: int, m2: int, d2: int) -> DateRange | None:
    try:
        start = date(y1, m1, d1)
        end = date(y2, m2, d2)
    except ValueError:
        return None
    if start > end:
        return None
    return DateRange(start, end)


def _int(value: str | None) -> int | None:
    return int(value) if value is not None else None
