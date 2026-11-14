"""One module per chain; each turns a site's pages into catalog models.

Adding a chain: see README.md in this folder. ``money.py`` is not a source: it parses the
money.com.tr pages shared by the Migros and Macrocenter sources.
"""

from __future__ import annotations

from scraper.core.source import Source
from scraper.sources.bim import BimSource
from scraper.sources.macrocenter import MacrocenterSource
from scraper.sources.migros import MigrosSource
from scraper.sources.sok import SokSource

# Every scraped chain in scraper.chains.CHAINS has exactly one entry here.
SOURCES: tuple[Source, ...] = (
    BimSource(),
    SokSource(),
    MigrosSource(),
    MacrocenterSource(),
)
