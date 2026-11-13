"""Typed, immutable mirror of the published JSON contract (see ``schema/``).

``to_dict`` output must validate against the schemas; ``from_dict`` accepts schema-valid
input and ignores unknown keys so newer files can still be read.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Any, Self

SCHEMA_VERSION = 1


class ChainKind(StrEnum):
    SCRAPED = "scraped"
    WEBVIEW = "webview"


class ChainStatus(StrEnum):
    OK = "ok"
    STALE = "stale"


class BrochureKind(StrEnum):
    PAGES = "pages"
    PRODUCTS = "products"
    BOTH = "both"


def format_datetime(value: datetime) -> str:
    _require_utc(value)
    text = value.astimezone(UTC).isoformat()
    return text.removesuffix("+00:00") + "Z"


def parse_datetime(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    if value.tzinfo is None:
        raise ValueError(f"date-time without time zone: {text!r}")
    return value.astimezone(UTC)


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"datetime must be timezone-aware UTC, got {value!r}")


def _opt_datetime(text: str | None) -> datetime | None:
    return parse_datetime(text) if text is not None else None


def _opt_date(text: str | None) -> date | None:
    return date.fromisoformat(text) if text is not None else None


@dataclass(frozen=True, slots=True)
class Page:
    """An image reference: a brochure page or a cover. Sizes are unknown for some sources."""

    url: str
    w: int | None = None
    h: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"url": self.url, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(url=data["url"], w=data["w"], h=data["h"])


@dataclass(frozen=True, slots=True)
class Chain:
    id: str
    name: str
    country: str
    kind: ChainKind
    web_url: str
    status: ChainStatus
    last_ok_at: datetime | None
    sort_order: int
    brand_color: str | None = None
    logo_url: str | None = None

    def __post_init__(self) -> None:
        if self.last_ok_at is not None:
            _require_utc(self.last_ok_at)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "country": self.country,
            "kind": self.kind.value,
            "web_url": self.web_url,
            "status": self.status.value,
            "last_ok_at": format_datetime(self.last_ok_at) if self.last_ok_at else None,
            "sort_order": self.sort_order,
        }
        # Optional in the schema: omitted rather than null.
        if self.brand_color is not None:
            out["brand_color"] = self.brand_color
        if self.logo_url is not None:
            out["logo_url"] = self.logo_url
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=data["id"],
            name=data["name"],
            country=data["country"],
            kind=ChainKind(data["kind"]),
            web_url=data["web_url"],
            status=ChainStatus(data["status"]),
            last_ok_at=_opt_datetime(data["last_ok_at"]),
            sort_order=data["sort_order"],
            brand_color=data.get("brand_color"),
            logo_url=data.get("logo_url"),
        )


@dataclass(frozen=True, slots=True)
class Brochure:
    id: str
    chain_id: str
    title: str
    date_label: str | None
    valid_from: date | None
    valid_to: date | None
    kind: BrochureKind
    cover: Page | None
    pages: tuple[Page, ...]
    products_url: str | None
    product_count: int
    source_url: str
    first_seen: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _require_utc(self.first_seen)
        _require_utc(self.updated_at)
        # Callers may pass a list; a tuple keeps the dataclass hashable and immutable.
        if not isinstance(self.pages, tuple):
            object.__setattr__(self, "pages", tuple(self.pages))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "chain_id": self.chain_id,
            "title": self.title,
            "date_label": self.date_label,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "kind": self.kind.value,
            "cover": self.cover.to_dict() if self.cover else None,
            "pages": [p.to_dict() for p in self.pages],
            "products_url": self.products_url,
            "product_count": self.product_count,
            "source_url": self.source_url,
            "first_seen": format_datetime(self.first_seen),
            "updated_at": format_datetime(self.updated_at),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        cover = data["cover"]
        return cls(
            id=data["id"],
            chain_id=data["chain_id"],
            title=data["title"],
            date_label=data["date_label"],
            valid_from=_opt_date(data["valid_from"]),
            valid_to=_opt_date(data["valid_to"]),
            kind=BrochureKind(data["kind"]),
            cover=Page.from_dict(cover) if cover is not None else None,
            pages=tuple(Page.from_dict(p) for p in data["pages"]),
            products_url=data["products_url"],
            product_count=data["product_count"],
            source_url=data["source_url"],
            first_seen=parse_datetime(data["first_seen"]),
            updated_at=parse_datetime(data["updated_at"]),
        )


@dataclass(frozen=True, slots=True)
class Catalog:
    generated_at: datetime
    min_app_version: int
    chains: tuple[Chain, ...]
    brochures: tuple[Brochure, ...]
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_utc(self.generated_at)
        object.__setattr__(self, "chains", tuple(self.chains))
        object.__setattr__(self, "brochures", tuple(self.brochures))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": format_datetime(self.generated_at),
            "min_app_version": self.min_app_version,
            "chains": [c.to_dict() for c in self.chains],
            "brochures": [b.to_dict() for b in self.brochures],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            schema_version=data["schema_version"],
            generated_at=parse_datetime(data["generated_at"]),
            min_app_version=data["min_app_version"],
            chains=tuple(Chain.from_dict(c) for c in data["chains"]),
            brochures=tuple(Brochure.from_dict(b) for b in data["brochures"]),
        )


@dataclass(frozen=True, slots=True)
class Product:
    name: str
    price_minor: int
    brand: str | None = None
    quantity_text: str | None = None
    old_price_minor: int | None = None
    image: str | None = None
    page_index: int | None = None
    source_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "brand": self.brand,
            "quantity_text": self.quantity_text,
            "price_minor": self.price_minor,
            "old_price_minor": self.old_price_minor,
            "image": self.image,
            "page_index": self.page_index,
            "source_url": self.source_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            name=data["name"],
            brand=data["brand"],
            quantity_text=data["quantity_text"],
            price_minor=data["price_minor"],
            old_price_minor=data["old_price_minor"],
            image=data["image"],
            page_index=data["page_index"],
            source_url=data["source_url"],
        )


@dataclass(frozen=True, slots=True)
class ProductFile:
    brochure_id: str
    products: tuple[Product, ...]
    currency: str = "TRY"
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "products", tuple(self.products))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "brochure_id": self.brochure_id,
            "currency": self.currency,
            "products": [p.to_dict() for p in self.products],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            schema_version=data["schema_version"],
            brochure_id=data["brochure_id"],
            currency=data["currency"],
            products=tuple(Product.from_dict(p) for p in data["products"]),
        )


@dataclass(frozen=True, slots=True)
class SourceHealth:
    chain_id: str
    ok: bool
    last_ok_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    brochure_count: int
    duration_ms: int

    def __post_init__(self) -> None:
        if self.last_ok_at is not None:
            _require_utc(self.last_ok_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "ok": self.ok,
            "last_ok_at": format_datetime(self.last_ok_at) if self.last_ok_at else None,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
            "brochure_count": self.brochure_count,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            chain_id=data["chain_id"],
            ok=data["ok"],
            last_ok_at=_opt_datetime(data["last_ok_at"]),
            last_error=data["last_error"],
            consecutive_failures=data["consecutive_failures"],
            brochure_count=data["brochure_count"],
            duration_ms=data["duration_ms"],
        )


@dataclass(frozen=True, slots=True)
class HealthReport:
    generated_at: datetime
    sources: tuple[SourceHealth, ...]

    def __post_init__(self) -> None:
        _require_utc(self.generated_at)
        object.__setattr__(self, "sources", tuple(self.sources))

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": format_datetime(self.generated_at),
            "sources": [s.to_dict() for s in self.sources],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            generated_at=parse_datetime(data["generated_at"]),
            sources=tuple(SourceHealth.from_dict(s) for s in data["sources"]),
        )
