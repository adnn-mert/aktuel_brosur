"""PDF pages -> WebP images, for chains that only publish their brochure as a PDF.

Pages are rasterised at a fixed width so the app gets predictable sizes, and the
published repository stays small (a 22 MB vector PDF becomes a few MB of WebP).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pymupdf
from PIL import Image

DEFAULT_WIDTH = 1600
DEFAULT_QUALITY = 82
MAX_PDF_BYTES = 80 * 1024 * 1024
MAX_PAGES = 60
# A page this much wider than tall is a two-page spread printed on one sheet.
SPREAD_RATIO = 1.2
# WebP cannot encode images larger than this in either direction.
_WEBP_MAX_SIDE = 16383


class PdfError(ValueError):
    """The PDF is unusable (too big, too many pages, not a PDF at all)."""


@dataclass(frozen=True, slots=True)
class RenderedPage:
    webp: bytes
    w: int
    h: int


def render_pdf_pages(
    pdf_bytes: bytes,
    target_width: int = DEFAULT_WIDTH,
    *,
    quality: int = DEFAULT_QUALITY,
    max_bytes: int = MAX_PDF_BYTES,
    max_pages: int = MAX_PAGES,
) -> list[RenderedPage]:
    """Render every page of ``pdf_bytes`` as a WebP ``target_width`` pixels wide.

    A spread is kept as one image but rendered twice as wide, so each half keeps the
    same resolution as a single page.
    """
    if len(pdf_bytes) > max_bytes:
        raise PdfError(f"PDF is {len(pdf_bytes) / 1_048_576:.1f} MB, limit is {max_bytes / 1_048_576:.0f} MB")
    if not pdf_bytes.lstrip()[:5].startswith(b"%PDF"):
        raise PdfError("downloaded file is not a PDF")
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several unrelated types for broken files.
        raise PdfError(f"PDF cannot be opened: {exc}") from exc
    with doc:
        if doc.needs_pass:
            raise PdfError("PDF is password protected")
        if doc.page_count == 0:
            raise PdfError("PDF has no pages")
        if doc.page_count > max_pages:
            raise PdfError(f"PDF has {doc.page_count} pages, limit is {max_pages}")
        return [_render(page, target_width, quality) for page in doc]


def _render(page: pymupdf.Page, target_width: int, quality: int) -> RenderedPage:
    rect = page.rect
    if rect.width <= 0 or rect.height <= 0:
        raise PdfError(f"page {page.number + 1} has no area")
    width = target_width * 2 if rect.width > rect.height * SPREAD_RATIO else target_width
    height = round(rect.height * width / rect.width)
    if height > _WEBP_MAX_SIDE or width > _WEBP_MAX_SIDE:
        raise PdfError(f"page {page.number + 1} would be {width}x{height} px, too large")

    zoom = width / rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    # MuPDF rounds the pixmap size; resizing by a pixel keeps every page exactly as wide.
    if image.size != (width, height):
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, format="WEBP", quality=quality, method=4)
    return RenderedPage(webp=out.getvalue(), w=width, h=height)
