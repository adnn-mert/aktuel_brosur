"""The fixed list of chains shown in the catalog.

Scraped chains are listed only once their source module exists; webview chains have no
source and are always published with ``status: ok`` so the app can open their own page.
Order: the big discount markets first (BİM, A101, Şok), then Migros and the other
supermarkets, then the cosmetics chains.
"""

from __future__ import annotations

from dataclasses import dataclass

from scraper.core.models import ChainKind


@dataclass(frozen=True, slots=True)
class ChainInfo:
    id: str
    name: str
    kind: ChainKind
    web_url: str
    sort_order: int
    country: str = "TR"
    # The designer's contrast-checked colours (app/assets/sample/catalog.json). A chain
    # without one is left empty; the app falls back to a neutral colour.
    brand_color: str | None = None
    logo_url: str | None = None


CHAINS: tuple[ChainInfo, ...] = (
    ChainInfo(
        id="bim",
        name="BİM",
        kind=ChainKind.SCRAPED,
        web_url="https://www.bim.com.tr/Categories/680/afisler.aspx",
        sort_order=10,
        brand_color="#E30613",
    ),
    ChainInfo(
        id="a101",
        name="A101",
        kind=ChainKind.WEBVIEW,
        web_url="https://www.a101.com.tr/afisler",
        sort_order=20,
        brand_color="#00A0E3",
    ),
    ChainInfo(
        id="sok",
        name="Şok",
        kind=ChainKind.SCRAPED,
        web_url="https://kurumsal.sokmarket.com.tr/tr/firsatlar",
        sort_order=30,
        brand_color="#FFD100",
    ),
    ChainInfo(
        id="migros",
        name="Migros",
        kind=ChainKind.SCRAPED,
        web_url="https://www.money.com.tr/migroskop-dijital",
        sort_order=40,
        brand_color="#FF8300",
    ),
    ChainInfo(
        id="macrocenter",
        name="Macrocenter",
        kind=ChainKind.SCRAPED,
        web_url="https://www.money.com.tr/macrostyle-dijital",
        sort_order=50,
    ),
    ChainInfo(
        id="carrefoursa",
        name="CarrefourSA",
        kind=ChainKind.WEBVIEW,
        web_url="https://www.carrefoursa.com/kataloglar",
        sort_order=60,
        brand_color="#1E5BC6",
    ),
    ChainInfo(
        id="gratis",
        name="Gratis",
        kind=ChainKind.WEBVIEW,
        web_url="https://www.gratis.com/gratis-katalog",
        sort_order=70,
        brand_color="#E5007D",
    ),
)
