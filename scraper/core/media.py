"""Files the scraper hosts itself (PDF pages rendered to WebP), laid out next to catalog.json.

Every run writes a complete new output folder. Media that already exists in the previous
output is copied over instead of being downloaded and rendered again, which is why
brochure ids for PDF sources are derived from the PDF address.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable, Sequence
from pathlib import Path

from scraper.core.models import Brochure, Page
from scraper.core.pdf import RenderedPage

MEDIA_DIR = "media"


def page_path(chain_id: str, brochure_id: str, index: int) -> str:
    """Relative path of page ``index`` (1-based), e.g. ``media/sok/sok-x/p01.webp``."""
    return f"{MEDIA_DIR}/{chain_id}/{brochure_id}/p{index:02d}.webp"


def is_local(url: str) -> bool:
    """True for paths relative to catalog.json, i.e. files this scraper publishes."""
    return "://" not in url


def local_paths(brochure: Brochure) -> list[str]:
    """Relative image paths a brochure points to (cover and pages), without duplicates."""
    images: Iterable[Page] = (*((brochure.cover,) if brochure.cover else ()), *brochure.pages)
    seen: dict[str, None] = {}
    for image in images:
        if is_local(image.url):
            seen.setdefault(image.url, None)
    return list(seen)


class MediaWriter:
    """Writes media into ``root`` and copies reusable media from ``previous_root``."""

    def __init__(self, root: Path, previous_root: Path | None) -> None:
        self.root = root
        self.previous_root = previous_root

    def write_pages(self, chain_id: str, brochure_id: str, pages: Sequence[RenderedPage]) -> list[Page]:
        folder = self.root / MEDIA_DIR / chain_id / brochure_id
        # A brochure that shrank must not keep its old trailing pages.
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        out: list[Page] = []
        for i, page in enumerate(pages, start=1):
            rel = page_path(chain_id, brochure_id, i)
            (self.root / rel).write_bytes(page.webp)
            out.append(Page(url=rel, w=page.w, h=page.h))
        return out

    def has_previous(self, brochure: Brochure) -> bool:
        """True when every local file of ``brochure`` exists in the previous output."""
        if self.previous_root is None:
            return False
        return all((self.previous_root / rel).is_file() for rel in local_paths(brochure))

    def reuse(self, brochure: Brochure) -> bool:
        """Copy the brochure's local files from the previous output; False if any is missing."""
        if not self.has_previous(brochure):
            return False
        assert self.previous_root is not None
        for rel in local_paths(brochure):
            target = self.root / rel
            if target.is_file():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.previous_root / rel, target)
        return True

    def exists(self, rel: str) -> bool:
        return (self.root / rel).is_file()

    def discard_chain(self, chain_id: str) -> None:
        """Remove whatever a failed source wrote, so only kept data is published."""
        folder = self.root / MEDIA_DIR / chain_id
        if folder.exists():
            shutil.rmtree(folder)
