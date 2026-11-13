"""One module per chain; each turns a site's pages into catalog models.

Adding a chain: see README.md in this folder.
"""

from __future__ import annotations

from scraper.core.source import Source
from scraper.sources.bim import BimSource
from scraper.sources.sok import SokSource

# Every scraped chain in scraper.chains.CHAINS has exactly one entry here.
SOURCES: tuple[Source, ...] = (
    BimSource(),
    SokSource(),
)
