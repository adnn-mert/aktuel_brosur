"""Pair OCR products with written products by name only.

Prices are deliberately left out of the score: matching on price would make the price
accuracy metric measure the matcher instead of the OCR.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

from scraper.core.text import fold_turkish

DEFAULT_THRESHOLD = 0.5

# Words that appear on almost every BİM card and say nothing about which product it is.
# "li"/"lu" are what is left of count suffixes ("6'lı", "3LÜ") once digits are split off.
_STOPWORDS = frozenset({"adet", "set", "tek", "fiyat", "li", "lu", "cesitleri", "cesit", "ve"})
# Same quantity, different spelling between poster and product card.
_UNIT_SYNONYMS = {"cc": "ml", "lt": "l", "gr": "g"}


def normalize_name(text: str | None) -> str:
    """Fold Turkish case and letters, drop punctuation and collapse spaces."""
    if not text:
        return ""
    folded = fold_turkish(text)
    # "26,5x16" keeps its digits together as "26 5 x 16" -> numbers 26, 5, 16.
    folded = re.sub(r"[^0-9a-z]+", " ", folded)
    folded = re.sub(r"(\d)([a-z])", r"\1 \2", folded)
    folded = re.sub(r"([a-z])(\d)", r"\1 \2", folded)
    return " ".join(folded.split())


def tokens(text: str | None) -> list[str]:
    return [_UNIT_SYNONYMS.get(t, t) for t in normalize_name(text).split() if t not in _STOPWORDS]


def _token_equal(a: str, b: str) -> bool:
    if a == b:
        return True
    if a.isdigit() or b.isdigit():
        return False
    # Posters abbreviate and models drop suffixes: "bardak" ~ "bardagi", "kav." ~ "kavanoz".
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= 4 and longer.startswith(shorter):
        return True
    return len(shorter) >= 5 and SequenceMatcher(None, a, b).ratio() >= 0.85


def _overlap(a: Sequence[str], b: Sequence[str]) -> int:
    used = [False] * len(b)
    count = 0
    for tok in a:
        for j, other in enumerate(b):
            if not used[j] and _token_equal(tok, other):
                used[j] = True
                count += 1
                break
    return count


def similarity(ocr_text: str, written_text: str) -> float:
    """Score in [0, 1]; token Dice blended with a character ratio, damped on number clashes."""
    a, b = tokens(ocr_text), tokens(written_text)
    if not a or not b:
        return 0.0
    dice = 2 * _overlap(a, b) / (len(a) + len(b))
    chars = SequenceMatcher(None, " ".join(a), " ".join(b)).ratio()
    score = 0.7 * dice + 0.3 * chars
    nums_a = {t for t in a if t.isdigit()}
    nums_b = {t for t in b if t.isdigit()}
    # Sizes tell sibling products apart ("Kavanoz 575 cc" vs "Kavanoz 1050 cc").
    if nums_a and nums_b and not nums_a & nums_b:
        score *= 0.8
    return score


@dataclass(frozen=True)
class Match:
    ocr_index: int
    written_index: int
    score: float


def _written_variants(written: dict) -> list[str]:
    name = written.get("name") or ""
    brand = written.get("brand") or ""
    qty = written.get("quantity_text") or ""
    return [name, f"{brand} {name}", f"{name} {qty}", f"{brand} {name} {qty}"]


def _ocr_variants(ocr: dict) -> list[str]:
    name = ocr.get("name") or ""
    brand = ocr.get("brand") or ""
    qty = ocr.get("quantity_text") or ""
    return [name, f"{brand} {name}", f"{name} {qty}", f"{brand} {name} {qty}"]


def pair_score(ocr: dict, written: dict) -> float:
    """Best score over name/brand/quantity combinations, since either side may omit any of them."""
    return max(
        similarity(o, w) for o in _ocr_variants(ocr) for w in _written_variants(written) if o.strip() and w.strip()
    )


def match_products(
    ocr_products: Sequence[dict],
    written_products: Sequence[dict],
    threshold: float = DEFAULT_THRESHOLD,
) -> list[Match]:
    """Greedy one-to-one assignment, best scores first; ties keep input order for determinism."""
    candidates = [
        (pair_score(o, w), i, j)
        for i, o in enumerate(ocr_products)
        for j, w in enumerate(written_products)
    ]
    candidates = [c for c in candidates if c[0] >= threshold]
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
    used_ocr: set[int] = set()
    used_written: set[int] = set()
    matches: list[Match] = []
    for score, i, j in candidates:
        if i in used_ocr or j in used_written:
            continue
        used_ocr.add(i)
        used_written.add(j)
        matches.append(Match(ocr_index=i, written_index=j, score=round(score, 4)))
    return matches
