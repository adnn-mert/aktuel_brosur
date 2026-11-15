"""Score OCR output against the written product list of the same brochure."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from scraper.ocr.matching import DEFAULT_THRESHOLD, match_products
from scraper.ocr.prices import parse_ocr_price

# BİM card images are named "<n>_kucuk_543X467_<id>_<poster>_<slot>_...": the middle number
# groups the cards by poster, though not in the order the posters are listed.
_POSTER_GROUP = re.compile(r"_\d+X\d+_\d+_(\d+)_\d+_", re.IGNORECASE)

# Below this the pair is plausible but not certain, so a price miss may be the matcher's fault.
WEAK_MATCH = 0.6


def poster_group(image_url: str | None) -> str | None:
    if not image_url:
        return None
    m = _POSTER_GROUP.search(image_url)
    return m.group(1) if m else None


@dataclass(frozen=True)
class Poster:
    url: str
    products: list[dict[str, Any]]


@dataclass(frozen=True)
class PairResult:
    brochure_id: str
    image_url: str
    ocr_name: str
    written_name: str
    ocr_price_text: str | None
    ocr_price_minor: int | None
    true_price_minor: int
    true_old_price_minor: int | None
    score: float
    error_kind: str | None

    @property
    def correct(self) -> bool:
        return self.error_kind is None


@dataclass
class BrochureResult:
    brochure_id: str
    written_count: int
    ocr_count: int
    pairs: list[PairResult] = field(default_factory=list)
    unmatched_ocr: list[dict[str, Any]] = field(default_factory=list)
    unmatched_written: list[dict[str, Any]] = field(default_factory=list)
    # Heuristic per-poster recall: (expected in the inferred group, matched from that poster).
    poster_recall: list[tuple[str, str | None, int, int]] = field(default_factory=list)


def _one_digit_off(a: int, b: int) -> bool:
    sa, sb = str(a), str(b)
    return len(sa) == len(sb) and sum(x != y for x, y in zip(sa, sb, strict=True)) == 1


def classify_error(ocr_minor: int | None, true_minor: int, old_minor: int | None, score: float) -> str | None:
    """Name the most likely reason an OCR price differs; None when it is exactly right."""
    if ocr_minor == true_minor:
        return None
    if ocr_minor is None:
        return "price_unreadable"
    if old_minor is not None and ocr_minor == old_minor:
        return "read_old_price"
    if ocr_minor // 100 == true_minor // 100:
        return "kurus_wrong"
    if score < WEAK_MATCH:
        return "possible_wrong_match"
    if _one_digit_off(ocr_minor, true_minor):
        return "one_digit_wrong"
    return "other_price"


def evaluate_brochure(
    brochure_id: str,
    written: Sequence[dict[str, Any]],
    posters: Sequence[Poster],
    threshold: float = DEFAULT_THRESHOLD,
) -> BrochureResult:
    ocr_items: list[tuple[str, dict[str, Any]]] = [(p.url, item) for p in posters for item in p.products]
    matches = match_products([item for _, item in ocr_items], written, threshold)
    result = BrochureResult(brochure_id=brochure_id, written_count=len(written), ocr_count=len(ocr_items))
    matched_ocr = {m.ocr_index for m in matches}
    matched_written = {m.written_index for m in matches}
    by_poster: dict[str, list[int]] = {p.url: [] for p in posters}
    for m in matches:
        url, item = ocr_items[m.ocr_index]
        truth = written[m.written_index]
        price_text = item.get("price")
        ocr_minor = parse_ocr_price(price_text)
        true_minor = int(truth["price_minor"])
        old_minor = truth.get("old_price_minor")
        result.pairs.append(
            PairResult(
                brochure_id=brochure_id,
                image_url=url,
                ocr_name=str(item.get("name") or ""),
                written_name=str(truth.get("name") or ""),
                ocr_price_text=None if price_text is None else str(price_text),
                ocr_price_minor=ocr_minor,
                true_price_minor=true_minor,
                true_old_price_minor=old_minor,
                score=m.score,
                error_kind=classify_error(ocr_minor, true_minor, old_minor, m.score),
            )
        )
        by_poster[url].append(m.written_index)
    result.unmatched_ocr = [item for i, (_, item) in enumerate(ocr_items) if i not in matched_ocr]
    result.unmatched_written = [w for j, w in enumerate(written) if j not in matched_written]

    groups = [poster_group(w.get("image")) for w in written]
    group_sizes = Counter(g for g in groups if g is not None)
    for url, written_indices in by_poster.items():
        votes = Counter(groups[j] for j in written_indices if groups[j] is not None)
        if not votes:
            result.poster_recall.append((url, None, 0, 0))
            continue
        group, hits = votes.most_common(1)[0]
        result.poster_recall.append((url, group, group_sizes[group], hits))
    return result


@dataclass(frozen=True)
class Summary:
    brochures: int
    posters: int
    written_expected: int
    ocr_products: int
    matched: int
    price_correct: int
    ocr_extra: int
    ocr_without_price: int
    poster_expected: int
    poster_matched: int
    error_kinds: dict[str, int]

    @property
    def match_rate(self) -> float:
        return self.matched / self.written_expected if self.written_expected else 0.0

    @property
    def price_accuracy(self) -> float:
        return self.price_correct / self.matched if self.matched else 0.0

    @property
    def poster_match_rate(self) -> float:
        return self.poster_matched / self.poster_expected if self.poster_expected else 0.0


def summarize(results: Sequence[BrochureResult]) -> Summary:
    pairs = [p for r in results for p in r.pairs]
    kinds = Counter(p.error_kind for p in pairs if p.error_kind is not None)
    all_ocr = sum(r.ocr_count for r in results)
    without_price = sum(
        1 for r in results for item in r.unmatched_ocr if parse_ocr_price(item.get("price")) is None
    ) + sum(1 for p in pairs if p.ocr_price_minor is None)
    recall = [pr for r in results for pr in r.poster_recall if pr[1] is not None]
    return Summary(
        brochures=len(results),
        posters=sum(len(r.poster_recall) for r in results),
        written_expected=sum(r.written_count for r in results),
        ocr_products=all_ocr,
        matched=len(pairs),
        price_correct=sum(1 for p in pairs if p.correct),
        ocr_extra=sum(len(r.unmatched_ocr) for r in results),
        ocr_without_price=without_price,
        poster_expected=sum(pr[2] for pr in recall),
        poster_matched=sum(pr[3] for pr in recall),
        error_kinds=dict(sorted(kinds.items())),
    )
