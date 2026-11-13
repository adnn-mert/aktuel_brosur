"""Turkish price text -> integer kuruş."""

from __future__ import annotations

import re

# "1.299,90", "25,", "429,00", "36.900", "7,5": dots group thousands, a comma starts kuruş.
_PRICE = re.compile(r"^(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{0,2}))?$")


def parse_price_minor(text: str | None) -> int | None:
    """Return the price in kuruş, or None when the text is not a plain price.

    Sites often split lira and kuruş into separate elements; pass them joined,
    e.g. ``"345," + "00"``. Currency signs and spaces are ignored.
    """
    if text is None:
        return None
    cleaned = re.sub(r"[\s₺]|TL", "", text, flags=re.IGNORECASE)
    m = _PRICE.match(cleaned)
    if not m:
        return None
    lira = int(m.group(1).replace(".", ""))
    kurus = (m.group(2) or "").ljust(2, "0")
    return lira * 100 + int(kurus)
