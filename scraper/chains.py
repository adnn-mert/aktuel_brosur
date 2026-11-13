"""The fixed list of chains shown in the catalog.

Scraped chains are listed only once their source module exists; webview chains have no
source and are always published with ``status: ok`` so the app can open their own page.
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
    # Left empty until confirmed from the chain's own brand guide; the app has a fallback.
    brand_color: str | None = None
    logo_url: str | None = None


CHAINS: tuple[ChainInfo, ...] = (
    ChainInfo(
        id="bim",
        name="BİM",
        kind=ChainKind.SCRAPED,
        web_url="https://www.bim.com.tr/Categories/680/afisler.aspx",
        sort_order=10,
    ),
    ChainInfo(
        id="a101",
        name="A101",
        kind=ChainKind.WEBVIEW,
        web_url="https://www.a101.com.tr/afisler",
        sort_order=20,
    ),
    ChainInfo(
        id="sok",
        name="Şok",
        kind=ChainKind.SCRAPED,
        web_url="https://kurumsal.sokmarket.com.tr/tr/firsatlar",
        sort_order=30,
    ),
    ChainInfo(
        id="carrefoursa",
        name="CarrefourSA",
        kind=ChainKind.WEBVIEW,
        web_url="https://www.carrefoursa.com/kataloglar",
        sort_order=60,
    ),
    ChainInfo(
        id="gratis",
        name="Gratis",
        kind=ChainKind.WEBVIEW,
        web_url="https://www.gratis.com/gratis-katalog",
        sort_order=70,
    ),
)
