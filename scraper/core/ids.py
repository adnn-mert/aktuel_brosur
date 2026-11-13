"""Stable, human-readable brochure identifiers."""

from __future__ import annotations

import hashlib
import re
from datetime import date

from scraper.core.text import fold_turkish

CHAIN_ID_RE = re.compile(r"^[a-z0-9_]+$")
BROCHURE_ID_RE = re.compile(r"^[a-z0-9_-]+$")

# Ids end up in file and folder names (products/<id>.json, media/<chain>/<id>/), so they
# are kept short; anything longer is truncated and made unique with a digest suffix.
MAX_ID_LENGTH = 80
_DIGEST_LENGTH = 8


def slugify(text: str) -> str:
    """Lower-case ASCII slug with single hyphens, e.g. "Haftanın Fırsatları" -> "haftanin-firsatlari"."""
    return re.sub(r"[^a-z0-9]+", "-", fold_turkish(text)).strip("-")


def brochure_id(chain_id: str, *parts: str | int | date) -> str:
    """Build a deterministic brochure id such as ``sok-2026-11-18-haftanin-firsatlari``.

    The same input always yields the same id, so a brochure keeps its id (and its
    ``first_seen`` timestamp) across scraper runs.
    """
    if not CHAIN_ID_RE.fullmatch(chain_id):
        raise ValueError(f"invalid chain id: {chain_id!r}")
    if not parts:
        raise ValueError("brochure_id needs at least one part besides the chain id")

    raw = [p.isoformat() if isinstance(p, date) else str(p) for p in parts]
    slugs = [s for s in (slugify(p) for p in raw) if s]
    readable = "-".join([chain_id, *slugs])

    # Parts that slugify to nothing (or ids that would be too long) still need to stay
    # distinct, so a digest of the exact input is appended.
    needs_digest = len(slugs) < len(raw) or len(readable) > MAX_ID_LENGTH
    if not needs_digest:
        return readable
    digest = hashlib.sha256("\x1f".join([chain_id, *raw]).encode("utf-8")).hexdigest()[:_DIGEST_LENGTH]
    head = readable[: MAX_ID_LENGTH - _DIGEST_LENGTH - 1].rstrip("-")
    return f"{head}-{digest}"
