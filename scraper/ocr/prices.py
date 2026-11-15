"""Price text as a vision model writes it -> integer kuruş."""

from __future__ import annotations

import re

from scraper.core.prices import parse_price_minor

# Posters print kuruş as raised digits; models sometimes copy them as superscripts.
_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")

# "49 90" or "49 ,90": lira and kuruş printed as separate blocks on the poster.
_SPLIT = re.compile(r"^(\d{1,3}(?:\.\d{3})*|\d+)\s*[,.]?\s+[,.]?\s*(\d{2})$")
# "49.90": dot as the decimal mark, which is never a thousands group because it has two digits.
_DOT_DECIMAL = re.compile(r"^(\d+)\.(\d{2})$")
# "1,299.00" (English grouping) shows up when a model normalises numbers.
_EN_GROUPED = re.compile(r"^(\d{1,3}(?:,\d{3})+)\.(\d{2})$")


_RAISED_KURUS = re.compile(r"(\d)\s*([⁰¹²³⁴⁵⁶⁷⁸⁹]{2})\b")


def _strip(text: str) -> str:
    cleaned = _RAISED_KURUS.sub(lambda m: m.group(1) + "," + m.group(2).translate(_SUPERSCRIPTS), text)
    cleaned = cleaned.translate(_SUPERSCRIPTS)
    cleaned = re.sub(r"(?i)₺|\bTL\b|\bTRY\b|tl$", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_ocr_price(value: str | int | float | None) -> int | None:
    """Return the price in kuruş, or None when ``value`` does not read as one price."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value * 100 if value >= 0 else None
    if isinstance(value, float):
        return round(value * 100) if value >= 0 else None
    text = _strip(value)
    if not text:
        return None
    if (m := _SPLIT.match(text)) is not None:
        return int(m.group(1).replace(".", "")) * 100 + int(m.group(2))
    compact = text.replace(" ", "")
    if (m := _DOT_DECIMAL.match(compact)) is not None:
        return int(m.group(1)) * 100 + int(m.group(2))
    if (m := _EN_GROUPED.match(compact)) is not None:
        return int(m.group(1).replace(",", "")) * 100 + int(m.group(2))
    return parse_price_minor(compact)
