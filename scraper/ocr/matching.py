"""Pair OCR products with written products by name.

Prices are deliberately left out of the score: matching on price would make the price
accuracy metric measure the matcher instead of the OCR. The one exception is a tie: when
names cannot tell two or more candidates apart (two "LASTİK" cards, one 2 cm and one 3 cm,
with nothing else written), any pairing is a guess, and a caller may pass ``tie_cost`` to
pick the pairing with the lowest total cost among those guesses only.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
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


# Scores are compared at this many decimals: closer than that, two names are the same name.
SCORE_DIGITS = 4

# Cost layers for the tie assignment, each large enough that no sum of the layer below can
# outweigh one step of it: a missing pair, then the full-text name score, then ``tie_cost``.
_TIE_COST_LIMIT = 10**12
_NAME_STEP = 10**16
_FORBIDDEN = 10**24

TieCost = Callable[[dict, dict], int]


def _full_text(item: dict) -> str:
    return " ".join(str(item.get(k) or "") for k in ("brand", "name", "quantity_text")).strip()


def match_products(
    ocr_products: Sequence[dict],
    written_products: Sequence[dict],
    threshold: float = DEFAULT_THRESHOLD,
    tie_cost: TieCost | None = None,
) -> list[Match]:
    """One-to-one assignment by name score, best scores first.

    Candidates with the same score (to ``SCORE_DIGITS``) are assigned together: within each
    connected group the assignment keeps as many pairs as possible, then prefers the pairs
    whose brand + name + quantity texts agree best (so "Black Bruin" still goes to "Black
    Bruin" when the bare names tie), and only then the lowest total ``tie_cost``. A pair the
    names already rank lower is never chosen over a better-named one, whatever it costs, so
    a misread price cannot make itself look right by stealing another product's line.
    """
    levels: dict[float, list[tuple[int, int]]] = {}
    for i, o in enumerate(ocr_products):
        for j, w in enumerate(written_products):
            score = pair_score(o, w)
            if score >= threshold:
                levels.setdefault(round(score, SCORE_DIGITS), []).append((i, j))
    used_ocr: set[int] = set()
    used_written: set[int] = set()
    matches: list[Match] = []
    for level in sorted(levels, reverse=True):
        edges = [(i, j) for i, j in levels[level] if i not in used_ocr and j not in used_written]
        for group in _connected_groups(edges):
            for i, j in _assign_group(group, ocr_products, written_products, tie_cost):
                used_ocr.add(i)
                used_written.add(j)
                matches.append(Match(ocr_index=i, written_index=j, score=level))
    matches.sort(key=lambda m: (-m.score, m.ocr_index, m.written_index))
    return matches


def _connected_groups(edges: Sequence[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """Split bipartite edges into groups that share no OCR or written product."""
    parent: dict[tuple[str, int], tuple[str, int]] = {}

    def find(node: tuple[str, int]) -> tuple[str, int]:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for i, j in edges:
        a, b = find(("o", i)), find(("w", j))
        if a != b:
            parent[b] = a
    groups: dict[tuple[str, int], list[tuple[int, int]]] = {}
    for i, j in edges:
        groups.setdefault(find(("o", i)), []).append((i, j))
    return list(groups.values())


def _assign_group(
    edges: Sequence[tuple[int, int]],
    ocr_products: Sequence[dict],
    written_products: Sequence[dict],
    tie_cost: TieCost | None,
) -> list[tuple[int, int]]:
    if len(edges) == 1:
        return list(edges)
    rows = sorted({i for i, _ in edges})
    cols = sorted({j for _, j in edges})
    allowed = set(edges)

    def cost(i: int, j: int) -> int:
        if (i, j) not in allowed:
            return _FORBIDDEN
        o, w = ocr_products[i], written_products[j]
        name_gap = round((1 - similarity(_full_text(o), _full_text(w))) * 10**SCORE_DIGITS)
        extra = 0 if tie_cost is None else max(0, min(int(tie_cost(o, w)), _TIE_COST_LIMIT - 1))
        return name_gap * _NAME_STEP + extra

    transpose = len(rows) > len(cols)
    if transpose:
        matrix = [[cost(i, j) for i in rows] for j in cols]
    else:
        matrix = [[cost(i, j) for j in cols] for i in rows]
    chosen = min_cost_assignment(matrix)
    pairs = []
    for r, c in enumerate(chosen):
        i, j = (rows[c], cols[r]) if transpose else (rows[r], cols[c])
        if (i, j) in allowed:
            pairs.append((i, j))
    return pairs


def min_cost_assignment(cost: Sequence[Sequence[int]]) -> list[int]:
    """Column chosen for each row, minimising the total (Hungarian method, O(n²m)).

    Needs at least as many columns as rows. Written out here because the measurement must
    not pull in scipy for a handful of tied products per brochure.
    """
    n = len(cost)
    if n == 0:
        return []
    m = len(cost[0])
    if m < n:
        raise ValueError("min_cost_assignment needs at least as many columns as rows")
    inf = float("inf")
    u = [0] * (n + 1)
    v = [0] * (m + 1)
    owner = [0] * (m + 1)  # owner[j]: 1-based row holding column j, 0 when free
    way = [0] * (m + 1)
    for row in range(1, n + 1):
        owner[0] = row
        j0 = 0
        minv: list[float] = [inf] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = owner[j0]
            delta: float = inf
            j1 = 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[owner[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if owner[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            owner[j0] = owner[j1]
            j0 = j1
    result = [-1] * n
    for j in range(1, m + 1):
        if owner[j]:
            result[owner[j] - 1] = j - 1
    return result
