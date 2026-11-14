"""Pixel size of a remote image, so the app can reserve the right space before it loads.

Only the first bytes are requested (an HTTP ``Range``); image headers sit at the start of
the file. A server that ignores ``Range`` answers 200 with the whole file, which is fine
for the small cover thumbnails this is used for.
"""

from __future__ import annotations

import io

import httpx
from PIL import Image, UnidentifiedImageError

from scraper.core.http import HttpClient

HEADER_BYTES = 64 * 1024


def image_size(data: bytes) -> tuple[int, int] | None:
    """(width, height) read from the image header in ``data``; ``data`` may be truncated."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            w, h = image.size
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        return None
    return (w, h) if w > 0 and h > 0 else None


def fetch_image_size(http: HttpClient, url: str) -> tuple[int, int] | None:
    """Size of the image at ``url``, or None when it cannot be read (never raises for HTTP errors)."""
    try:
        response = http.get(url, headers={"Range": f"bytes=0-{HEADER_BYTES - 1}"})
        if response.status_code == 206:
            size = image_size(response.content)
            if size is not None:
                return size
            # The header did not fit in the first bytes (e.g. a large embedded thumbnail).
            response = http.get(url)
        if response.status_code != 200:
            return None
        return image_size(response.content)
    except httpx.HTTPError:
        return None
