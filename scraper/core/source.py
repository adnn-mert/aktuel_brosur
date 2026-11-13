"""The contract between the pipeline and a chain's source module.

A source downloads pages and hands them to pure ``parse_*`` functions; it never writes
catalog files itself. Whatever it raises is caught by the pipeline and turns that chain
``stale`` without touching the others.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

import httpx

from scraper.core.http import HttpClient
from scraper.core.media import MediaWriter
from scraper.core.models import Brochure, ProductFile


class SourceError(Exception):
    """A source-level failure with a short message meant for health.json."""


@dataclass(frozen=True, slots=True)
class SourceContext:
    http: HttpClient
    today: date
    now: datetime
    media: MediaWriter
    # This chain's brochures from the previous run, so unchanged ones are not fetched again.
    previous: tuple[Brochure, ...] = ()
    previous_products: Callable[[str], ProductFile | None] = lambda _id: None

    def previous_by_id(self) -> dict[str, Brochure]:
        return {b.id: b for b in self.previous}


@dataclass(slots=True)
class SourceResult:
    brochures: list[Brochure]
    product_files: dict[str, ProductFile] = field(default_factory=dict)
    # Non-fatal remarks shown in the run summary, e.g. "3 products skipped".
    warnings: list[str] = field(default_factory=list)


class Source(Protocol):
    chain_id: str

    def collect(self, ctx: SourceContext) -> SourceResult: ...


def products_path(brochure_id: str) -> str:
    """Where a brochure's product file is published, relative to catalog.json."""
    return f"products/{brochure_id}.json"


def fetch(http: HttpClient, url: str, *, timeout: float | None = None) -> httpx.Response:
    """GET ``url`` and insist on 200; anything else is a source failure with a clear reason."""
    response = http.get(url, timeout=timeout)
    if response.status_code != 200:
        snippet = " ".join(response.text[:120].split()) if response.content else ""
        detail = f": {snippet}" if snippet else ""
        raise SourceError(f"HTTP {response.status_code} from {url}{detail}")
    return response
