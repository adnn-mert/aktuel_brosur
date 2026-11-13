from __future__ import annotations

import copy
import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schema" / "examples"


@cache
def _load(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


@pytest.fixture
def catalog() -> dict[str, Any]:
    return copy.deepcopy(_load("catalog.example.json"))


@pytest.fixture
def products() -> dict[str, Any]:
    return copy.deepcopy(_load("products.example.json"))


@pytest.fixture
def health() -> dict[str, Any]:
    return copy.deepcopy(_load("health.example.json"))


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture_text(*parts: str) -> str:
    return FIXTURES.joinpath(*parts).read_text(encoding="utf-8")


def make_pdf(pages: int = 2, width: float = 595, height: float = 842) -> bytes:
    """A tiny vector PDF built on the fly, so no real brochure PDF lives in the repository."""
    import pymupdf

    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page(width=width, height=height)
        page.insert_text((72, 100), f"Sayfa {i + 1} - 49,90 TL", fontsize=24)
        page.draw_rect(pymupdf.Rect(72, 150, width - 72, 300), color=(1, 0, 0), fill=(1, 0.9, 0))
    data = doc.tobytes()
    doc.close()
    return data


def mock_http(routes: dict[str, Any], calls: list[str] | None = None):
    """An HttpClient whose transport answers from ``routes`` (url -> body or (status, body)).

    Unknown URLs return 404; every requested URL is appended to ``calls``.
    """
    import httpx

    from scraper.core.http import HttpClient

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if calls is not None:
            calls.append(url)
        if url not in routes:
            return httpx.Response(404, text="not found")
        value = routes[url]
        status, body = value if isinstance(value, tuple) else (200, value)
        if isinstance(body, Exception):
            raise body
        content = body.encode("utf-8") if isinstance(body, str) else body
        return httpx.Response(status, content=content)

    return HttpClient(transport=httpx.MockTransport(handler), min_interval=0, sleep=lambda _s: None)
