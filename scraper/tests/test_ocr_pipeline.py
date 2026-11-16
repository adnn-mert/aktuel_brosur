"""The scrape job's OCR step (scraper/ocr/pipeline.py), without network.

Each test scrapes fake sources with the real pipeline into ``out/``, then runs the OCR step
against a real ``GeminiClient`` whose transport answers from hand-made responses.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from scraper.chains import CHAINS
from scraper.core.models import Brochure, BrochureKind, Catalog, Page, Product, ProductFile
from scraper.core.pdf import RenderedPage
from scraper.core.pipeline import OutputError, run, verify_output
from scraper.core.source import SourceContext, SourceResult, products_path
from scraper.core.validate import ContractError, validate_catalog, validate_ocr_state, validate_products
from scraper.ocr import pipeline as ocr
from scraper.ocr.gemini import BROCHURE_STORES, GeminiClient, parse_brochure_response
from scraper.ocr.state import STATE_FILE, quota_day, us_pacific_offset
from scraper.tests.conftest import FIXTURES, mock_http

FAKE_KEY = "test-key-not-real-ocr-456"
TODAY = date(2026, 11, 17)
# 09:00 UTC is 01:00 PST: quota day 2026-11-17.
NOW = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
HAKMAR_IMG = "https://hakmar.com.tr/wp-content/uploads/2026/11/{key}-{i}.jpg"
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-bytes" * 10


# --- scrape side: fake sources run through the real pipeline ---------------------------------


@dataclass(frozen=True)
class Spec:
    key: str
    pages: int = 1
    start: date | None = TODAY
    end: date | None = TODAY + timedelta(days=6)
    tag: str = "v1"


def webp(text: str) -> bytes:
    payload = text.encode("utf-8").ljust(40, b".")
    return b"RIFF" + len(payload).to_bytes(4, "little") + b"WEBP" + payload


def _brochure(chain: str, spec: Spec) -> Brochure:
    return Brochure(
        id=f"{chain}-{spec.key}",
        chain_id=chain,
        title=f"Broşür {spec.key}",
        date_label=None,
        valid_from=spec.start,
        valid_to=spec.end,
        kind=BrochureKind.PAGES,
        cover=None,
        pages=(),
        products_url=None,
        product_count=0,
        source_url=f"https://example.com/{chain}/{spec.key}.pdf",
        first_seen=NOW,
        updated_at=NOW,
    )


class Source:
    def __init__(self, chain_id: str, fn: Callable[[SourceContext], SourceResult]) -> None:
        self.chain_id = chain_id
        self.fn = fn

    def collect(self, ctx: SourceContext) -> SourceResult:
        return self.fn(ctx)


def sok(*specs: Spec) -> Source:
    """Pages we render ourselves (local WebP files), like Şok."""

    def collect(ctx: SourceContext) -> SourceResult:
        out = []
        for spec in specs:
            b = _brochure("sok", spec)
            rendered = [RenderedPage(webp(f"{spec.key}-{spec.tag}-{i}"), 100, 140) for i in range(spec.pages)]
            pages = ctx.media.write_pages("sok", b.id, rendered)
            out.append(replace(b, pages=tuple(pages), cover=pages[0]))
        return SourceResult(out)

    return Source("sok", collect)


def hakmar(*specs: Spec) -> Source:
    """Pages hosted by the chain (remote JPEG URLs, no sizes), like Hakmar."""

    def collect(_ctx: SourceContext) -> SourceResult:
        out = []
        for spec in specs:
            pages = tuple(Page(HAKMAR_IMG.format(key=f"{spec.key}{spec.tag}", i=i)) for i in range(spec.pages))
            out.append(replace(_brochure("hakmar", spec), pages=pages, cover=pages[0]))
        return SourceResult(out)

    return Source("hakmar", collect)


def bim() -> Source:
    """A chain with a written list (kind both): never read by OCR."""

    def collect(_ctx: SourceContext) -> SourceResult:
        b = _brochure("bim", Spec("aktuel"))
        b = replace(
            b,
            kind=BrochureKind.BOTH,
            pages=(Page("https://cdn1.bim.com.tr/uploads/afisler/a.jpg"),),
            products_url=products_path(b.id),
            product_count=1,
        )
        return SourceResult([b], {b.id: ProductFile(b.id, (Product(name="Süt", price_minor=3990),))})

    return Source("bim", collect)


CHAIN_INFOS = [c for c in CHAINS if c.id in {"bim", "sok", "hakmar", "a101"}]


def scrape(root: Path, name: str, *sources: Source, state: Path | None = None) -> Path:
    out = root / name
    report = run(list(sources), CHAIN_INFOS, state, out, TODAY, NOW, http=mock_http({}))
    assert report.output_ok, report.output_error
    return out


# --- Gemini side -----------------------------------------------------------------------------


def answer(products: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps({"products": products}, ensure_ascii=False)}]}, "finishReason": "STOP"}
        ],
        "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 100},
    }


def priced(pages: int, per_page: int = 5, base: int = 10) -> dict[str, Any]:
    """An answer with ``per_page`` valid products on each of ``pages`` request-relative pages."""
    items = [
        {"page_index": p, "name": f"Ürün {p}-{n}", "brand": None, "quantity_text": f"{n + 1} kg",
         "price": f"{base + p},{n:02d}", "old_price": None}
        for p in range(pages)
        for n in range(per_page)
    ]
    return answer(items)


def fixture_answer() -> dict[str, Any]:
    return json.loads((FIXTURES / "ocr" / "gemini_pages_response.json").read_text(encoding="utf-8"))


class FakeGemini:
    """Answers each request with the next item: a body dict, an HTTP status, or a callable."""

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.requests: list[dict[str, Any]] = []
        self.headers: list[httpx.Headers] = []
        self.urls: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        self.headers.append(request.headers)
        self.urls.append(str(request.url))
        if not self.answers:
            return httpx.Response(500, json={"error": {"message": "unexpected request in test"}})
        item = self.answers.pop(0)
        if callable(item):
            item = item(body)
        if isinstance(item, int):
            message = f"status {item}"
            if item == 400:
                message = f"bad request for key {FAKE_KEY}"
            return httpx.Response(item, json={"error": {"message": message}})
        return httpx.Response(200, json=item)

    def client(self) -> GeminiClient:
        return GeminiClient(
            FAKE_KEY,
            model=ocr.MODEL,
            thinking_level=ocr.THINKING_LEVEL,
            max_retries=0,
            min_interval=0,
            transport=httpx.MockTransport(self.handler),
            sleep=lambda _s: None,
        )

    def images_per_request(self) -> list[int]:
        return [sum(1 for p in r["contents"][0]["parts"] if "inlineData" in p) for r in self.requests]


def hakmar_routes(*specs: Spec, body: bytes = JPEG) -> dict[str, Any]:
    return {
        HAKMAR_IMG.format(key=f"{s.key}{s.tag}", i=i): body + f"{s.key}{i}".encode()
        for s in specs
        for i in range(s.pages)
    }


def step(
    out: Path,
    fake: FakeGemini | None,
    *,
    state: Path | None = None,
    now: datetime = NOW,
    today: date = TODAY,
    http_routes: dict[str, Any] | None = None,
    http_calls: list[str] | None = None,
    clock: Callable[[], float] = lambda: 0.0,
    dry_run: bool = False,
    run_limit: int = ocr.RUN_REQUEST_LIMIT,
) -> ocr.OcrReport:
    return ocr.OcrStep(
        out,
        state or out,
        now=now,
        today=today,
        reader=fake.client() if fake else None,
        http=mock_http(http_routes or {}, http_calls),
        dry_run=dry_run,
        run_limit=run_limit,
        clock=clock,
        sleep=lambda _s: None,
    ).execute()


def catalog_of(out: Path) -> dict[str, Any]:
    return json.loads((out / "catalog.json").read_text(encoding="utf-8"))


def brochure_of(out: Path, bid: str) -> dict[str, Any]:
    return next(b for b in catalog_of(out)["brochures"] if b["id"] == bid)


def state_of(out: Path) -> dict[str, Any]:
    data = json.loads((out / STATE_FILE).read_text(encoding="utf-8"))
    validate_ocr_state(data)
    return data


def results(report: ocr.OcrReport) -> dict[str, str]:
    return {o.brochure_id: o.result for o in report.outcomes}


# --- settings ----------------------------------------------------------------------------------


def test_allow_list_and_limits() -> None:
    assert ocr.OCR_CHAINS == ("sok", "hakmar")
    # Every allowed chain has a store name for the page prompt.
    assert all(chain in BROCHURE_STORES for chain in ocr.OCR_CHAINS)
    # Chains with written prices or no pages never belong on the list.
    assert not {"bim", "migros", "a101", "gratis", "carrefoursa"} & set(ocr.OCR_CHAINS)
    assert (ocr.DAILY_REQUEST_LIMIT, ocr.RUN_REQUEST_LIMIT, ocr.MAX_FAILED_ATTEMPTS) == (15, 5, 3)
    assert ocr.MODEL == "gemini-3.8-flash" and ocr.THINKING_LEVEL == "LOW"
    assert ocr.MAX_PAGES_PER_REQUEST == 10


# --- quota day ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("moment", "day"),
    [
        (datetime(2026, 11, 17, 7, 59, tzinfo=UTC), date(2026, 11, 16)),  # 23:59 PST
        (datetime(2026, 11, 17, 8, 0, tzinfo=UTC), date(2026, 11, 17)),  # 00:00 PST, 11:00 in Turkey
        (datetime(2026, 7, 1, 6, 59, tzinfo=UTC), date(2026, 6, 30)),  # 23:59 PDT
        (datetime(2026, 7, 1, 7, 0, tzinfo=UTC), date(2026, 7, 1)),  # 00:00 PDT
    ],
)
def test_quota_day_is_the_pacific_calendar_day(moment: datetime, day: date) -> None:
    assert quota_day(moment) == day


def test_us_pacific_rule_switches_on_the_federal_dates() -> None:
    # 2026: DST from Sunday 8 March 10:00 UTC to Sunday 1 November 09:00 UTC.
    assert us_pacific_offset(datetime(2026, 3, 8, 9, 59, tzinfo=UTC)) == timedelta(hours=-8)
    assert us_pacific_offset(datetime(2026, 3, 8, 10, 0, tzinfo=UTC)) == timedelta(hours=-7)
    assert us_pacific_offset(datetime(2026, 11, 1, 8, 59, tzinfo=UTC)) == timedelta(hours=-7)
    assert us_pacific_offset(datetime(2026, 11, 1, 9, 0, tzinfo=UTC)) == timedelta(hours=-8)


def test_us_pacific_rule_matches_the_time_zone_database() -> None:
    zoneinfo = pytest.importorskip("zoneinfo")
    try:
        zone = zoneinfo.ZoneInfo("America/Los_Angeles")
    except zoneinfo.ZoneInfoNotFoundError:
        pytest.skip("no time zone database on this machine")
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    while moment.year == 2026:
        assert us_pacific_offset(moment) == moment.astimezone(zone).utcoffset(), moment
        moment += timedelta(hours=1)


# --- pure helpers ------------------------------------------------------------------------------


def test_convert_products_from_the_fixture_drops_unusable_ones() -> None:
    raw = parse_brochure_response(fixture_answer(), 3).products
    products, dropped = ocr.convert_products(raw, offset=0, page_count=3)
    assert dropped == 3  # percentage-only price, empty name, page_index past the last page
    assert [(p.name, p.quantity_text, p.price_minor, p.page_index) for p in products] == [
        ("Ayçiçek Yağı", "5 L", 34990, 0),
        ("Toz Şeker", "3 kg", 11950, 0),
        ("Lastik", "2 cm", 13900, 1),
        ("Lastik", "3 cm", 17900, 1),
        ("Siyah Çay", "1 kg", 18900, 1),
        ("Toz Deterjan", "6 kg", 129900, 2),
    ]
    assert products[0].old_price_minor == 39990 and products[0].brand == "Yudum"
    # An "old" price below the price is a misread, not a discount.
    assert products[4].old_price_minor is None
    assert all(p.source == "ocr" for p in products)


def test_convert_products_moves_page_index_by_the_chunk_offset() -> None:
    raw = parse_brochure_response(priced(2, per_page=1), 2).products
    products, dropped = ocr.convert_products(raw, offset=6, page_count=8)
    assert dropped == 0 and [p.page_index for p in products] == [6, 7]
    products, dropped = ocr.convert_products(raw, offset=7, page_count=8)
    assert [p.page_index for p in products] == [7] and dropped == 1


def test_convert_products_rejects_odd_types() -> None:
    raw = [
        {"page_index": 0, "name": ["x"], "price": "10"},
        {"page_index": 0, "name": "A", "price": {"v": 1}},
        {"page_index": True, "name": "B", "price": "10"},
        {"page_index": 0, "name": "C", "price": "0"},
        {"page_index": 0, "name": "D", "price": 12, "old_price": [1], "brand": 5, "quantity_text": "  "},
    ]
    products, dropped = ocr.convert_products(raw, offset=0, page_count=1)
    assert dropped == 4
    assert products == [Product(name="D", price_minor=1200, page_index=0, source="ocr")]


@pytest.mark.parametrize(
    ("kept", "dropped", "pages", "ok"),
    [(5, 0, 1, True), (4, 0, 1, False), (7, 0, 8, False), (8, 0, 8, True), (6, 6, 1, True), (6, 7, 1, False)],
)
def test_rejection(kept: int, dropped: int, pages: int, ok: bool) -> None:
    assert (ocr.rejection(kept, dropped, pages) is None) is ok


def test_plan_requests_splits_by_pages_and_bytes() -> None:
    assert ocr.plan_requests([1] * 8) == [list(range(8))]
    assert [len(c) for c in ocr.plan_requests([1] * 23)] == [8, 8, 7]
    assert [len(c) for c in ocr.plan_requests([1] * 12)] == [6, 6]
    # Four 4 MB pages do not fit one ~14.5 MB request: two requests of two pages.
    mb = 1024 * 1024
    assert ocr.plan_requests([4 * mb] * 4) == [[0, 1], [2, 3]]
    assert ocr.plan_requests([]) == []
    with pytest.raises(ValueError, match="page 2"):
        ocr.plan_requests([1, 20 * mb])


def test_fingerprint_covers_order_size_and_content() -> None:
    pages = [{"url": "a", "w": 1, "h": 2}, {"url": "b", "w": 1, "h": 2}]
    base = ocr.page_fingerprint(pages, ["x", "y"])
    assert ocr.page_fingerprint(pages, ["x", "y"]) == base
    assert ocr.page_fingerprint(pages[::-1], ["y", "x"]) != base
    assert ocr.page_fingerprint(pages, ["x", "z"]) != base
    assert ocr.page_fingerprint([{**pages[0], "w": 3}, pages[1]], ["x", "y"]) != base


# --- reading and caching -----------------------------------------------------------------------


def test_reads_a_new_brochure_and_publishes_it_beside_the_scrape_output(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a", pages=3)), bim())
    before = catalog_of(out)
    fake = FakeGemini(fixture_answer())
    report = step(out, fake)

    assert results(report) == {"sok-a": "read"}
    assert len(fake.requests) == 1 and fake.images_per_request() == [3]
    request = fake.requests[0]
    assert request["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "LOW"}
    assert "Şok" in request["contents"][0]["parts"][0]["text"]
    assert fake.urls == ["https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"]
    assert fake.headers[0]["x-goog-api-key"] == FAKE_KEY and FAKE_KEY not in fake.urls[0]
    assert all(p["inlineData"]["mimeType"] == "image/webp" for p in request["contents"][0]["parts"] if "inlineData" in p)

    verify_output(out)
    sok_b = brochure_of(out, "sok-a")
    assert sok_b["ocr_products_url"] == "products_ocr/sok-a.json"
    data = json.loads((out / "products_ocr" / "sok-a.json").read_text(encoding="utf-8"))
    validate_products(data)
    assert data["brochure_id"] == "sok-a" and len(data["products"]) == 6
    assert {p["source"] for p in data["products"]} == {"ocr"}
    assert [p["page_index"] for p in data["products"]] == [0, 0, 1, 1, 1, 2]
    lastik = [(p["quantity_text"], p["price_minor"]) for p in data["products"] if p["name"] == "Lastik"]
    assert lastik == [("2 cm", 13900), ("3 cm", 17900)]

    # Nothing else changed: the scrape step's catalog plus one key.
    after = catalog_of(out)
    for old, new in zip(before["brochures"], after["brochures"], strict=True):
        new = dict(new)
        new.pop("ocr_products_url", None)
        assert new == old

    state = state_of(out)
    assert state["usage"] == {"quota_day": "2026-11-17", "attempts": 1}
    record = state["brochures"]["sok-a"]
    assert record["failed_attempts"] == 0
    assert record["reading"] == {
        "products_url": "products_ocr/sok-a.json",
        "product_count": 6,
        "read_at": "2026-11-17T09:00:00Z",
        "model": "gemini-3.8-flash",
        "thinking_level": "LOW",
        "prompt_version": "pages-b1",
        "requests": 1,
    }
    assert "bim-aktuel" not in state["brochures"]


def test_old_apps_see_the_ocr_brochure_unchanged(tmp_path) -> None:
    """kind, products_url and product_count stay as the scrape step wrote them."""
    out = scrape(tmp_path, "out", sok(Spec("a", pages=3)))
    step(out, FakeGemini(fixture_answer()))
    b = brochure_of(out, "sok-a")
    assert (b["kind"], b["products_url"], b["product_count"]) == ("pages", None, 0)
    assert not (out / "products").exists()
    # Readers that do not know the field ignore it (the Python model here, the Dart one in the app).
    catalog = catalog_of(out)
    validate_catalog(catalog)
    parsed = Catalog.from_dict(catalog)
    assert parsed.brochures[0].kind is BrochureKind.PAGES and parsed.brochures[0].products_url is None


def test_unchanged_brochure_is_carried_over_without_a_request(tmp_path) -> None:
    first = scrape(tmp_path, "run1", sok(Spec("a", pages=3)))
    step(first, FakeGemini(fixture_answer()))
    # Next scheduled run: state/ is the published first output, out/ a fresh scrape.
    second = scrape(tmp_path, "run2", sok(Spec("a", pages=3)), state=first)
    assert not (second / "products_ocr").exists() and not (second / STATE_FILE).exists()
    fake = FakeGemini()
    report = step(second, fake, state=first, now=NOW + timedelta(hours=6))

    assert fake.requests == []
    assert results(report) == {"sok-a": "cached"}
    assert (second / "products_ocr" / "sok-a.json").read_bytes() == (first / "products_ocr" / "sok-a.json").read_bytes()
    assert brochure_of(second, "sok-a")["ocr_products_url"] == "products_ocr/sok-a.json"
    record = state_of(second)["brochures"]["sok-a"]
    assert record["reading"]["read_at"] == "2026-11-17T09:00:00Z"
    verify_output(second)


def test_changed_pages_are_read_again(tmp_path) -> None:
    first = scrape(tmp_path, "run1", sok(Spec("a", pages=3)))
    step(first, FakeGemini(fixture_answer()))
    fingerprint = state_of(first)["brochures"]["sok-a"]["fingerprint"]
    # Same brochure id and page paths, new page content.
    second = scrape(tmp_path, "run2", sok(Spec("a", pages=3, tag="v2")), state=first)
    fake = FakeGemini(fixture_answer())
    report = step(second, fake, state=first)
    assert len(fake.requests) == 1 and results(report) == {"sok-a": "read"}
    assert state_of(second)["brochures"]["sok-a"]["fingerprint"] != fingerprint


def test_rerun_on_the_same_folder_reuses_its_own_reading(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a", pages=3)))
    step(out, FakeGemini(fixture_answer()))
    fake = FakeGemini()
    report = step(out, fake)
    assert fake.requests == [] and results(report) == {"sok-a": "cached"}
    verify_output(out)


def test_corrupt_cached_file_is_read_again(tmp_path) -> None:
    first = scrape(tmp_path, "run1", sok(Spec("a", pages=3)))
    step(first, FakeGemini(fixture_answer()))
    (first / "products_ocr" / "sok-a.json").write_text("{ not json", encoding="utf-8")
    second = scrape(tmp_path, "run2", sok(Spec("a", pages=3)), state=first)
    fake = FakeGemini(fixture_answer())
    report = step(second, fake, state=first)
    assert len(fake.requests) == 1 and results(report) == {"sok-a": "read"}
    assert any("not reused" in n for n in report.notes)


def test_pruned_brochures_lose_their_record_and_file(tmp_path) -> None:
    first = scrape(tmp_path, "run1", sok(Spec("a", pages=3), Spec("b", pages=3)))
    step(first, FakeGemini(fixture_answer(), fixture_answer()))
    assert set(state_of(first)["brochures"]) == {"sok-a", "sok-b"}
    # sok-b expired out of the archive; the scrape step dropped it.
    old = Spec("b", pages=3, start=TODAY - timedelta(days=60), end=TODAY - timedelta(days=40))
    second = scrape(tmp_path, "run2", sok(Spec("a", pages=3), old), state=first)
    assert "sok-b" not in {b["id"] for b in catalog_of(second)["brochures"]}
    report = step(second, FakeGemini(), state=first)
    assert set(state_of(second)["brochures"]) == {"sok-a"}
    assert sorted(p.name for p in (second / "products_ocr").iterdir()) == ["sok-a.json"]
    assert results(report) == {"sok-a": "cached"}


def test_hakmar_pages_are_downloaded_politely(tmp_path) -> None:
    spec = Spec("k", pages=2)
    out = scrape(tmp_path, "out", hakmar(spec))
    calls: list[str] = []
    fake = FakeGemini(priced(2, per_page=3))
    report = step(out, fake, http_routes=hakmar_routes(spec), http_calls=calls)
    assert results(report) == {"hakmar-k": "read"}
    assert calls == [HAKMAR_IMG.format(key="kv1", i=0), HAKMAR_IMG.format(key="kv1", i=1)]
    assert fake.images_per_request() == [2]
    assert all(p["inlineData"]["mimeType"] == "image/jpeg" for p in fake.requests[0]["contents"][0]["parts"] if "inlineData" in p)
    assert "Hakmar" in fake.requests[0]["contents"][0]["parts"][0]["text"]
    verify_output(out)


def test_failed_page_download_does_not_count_against_the_brochure(tmp_path) -> None:
    out = scrape(tmp_path, "out", hakmar(Spec("k", pages=2)))
    fake = FakeGemini()
    report = step(out, fake, http_routes={})
    assert fake.requests == [] and results(report) == {"hakmar-k": "not read"}
    assert "HTTP 404" in report.outcomes[0].detail
    assert "hakmar-k" not in state_of(out)["brochures"]
    assert state_of(out)["usage"]["attempts"] == 0


def test_long_brochure_is_split_and_page_index_translated(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("long", pages=12)))
    # Two requests of six pages; each answers with request-relative page_index 0..5.
    fake = FakeGemini(priced(6, per_page=1, base=10), priced(6, per_page=1, base=50))
    report = step(out, fake)
    assert results(report) == {"sok-long": "read"} and fake.images_per_request() == [6, 6]
    labels = [[p["text"] for p in r["contents"][0]["parts"] if p.get("text", "").startswith("page_index")] for r in fake.requests]
    assert labels[1][0] == "page_index: 0"  # each request numbers its own pages
    data = json.loads((out / "products_ocr" / "sok-long.json").read_text(encoding="utf-8"))
    assert [p["page_index"] for p in data["products"]] == list(range(12))
    assert data["products"][6]["price_minor"] == 5000
    assert state_of(out)["brochures"]["sok-long"]["reading"]["requests"] == 2


def test_order_current_before_upcoming_newest_first_and_expired_never(tmp_path) -> None:
    specs = [
        Spec("old-current", start=TODAY - timedelta(days=5), end=TODAY + timedelta(days=1)),
        Spec("upcoming-near", start=TODAY + timedelta(days=1), end=TODAY + timedelta(days=7)),
        Spec("new-current", start=TODAY - timedelta(days=1), end=TODAY + timedelta(days=5)),
        Spec("upcoming-far", start=TODAY + timedelta(days=4), end=TODAY + timedelta(days=10)),
        Spec("expired", start=TODAY - timedelta(days=10), end=TODAY - timedelta(days=2)),
        Spec("undated", start=None, end=None),
    ]
    out = scrape(tmp_path, "out", sok(*specs))
    fake = FakeGemini(*[priced(1)] * 5)
    report = step(out, fake)
    read = [o.brochure_id for o in report.outcomes if o.result == "read"]
    assert read == ["sok-new-current", "sok-old-current", "sok-undated", "sok-upcoming-far", "sok-upcoming-near"]
    assert results(report)["sok-expired"] == "not read" and len(fake.requests) == 5


# --- budget --------------------------------------------------------------------------------------


def test_run_limit_is_five_requests(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(*[Spec(f"b{i}") for i in range(7)]))
    fake = FakeGemini(*[priced(1)] * 7)
    report = step(out, fake)
    assert len(fake.requests) == 5
    assert list(results(report).values()).count("read") == 5
    skipped = [o for o in report.outcomes if o.result == "not read"]
    assert len(skipped) == 2 and "this run 5/5" in skipped[0].detail
    assert state_of(out)["usage"] == {"quota_day": "2026-11-17", "attempts": 5}


def test_daily_limit_counts_earlier_runs_of_the_same_quota_day(tmp_path) -> None:
    first = scrape(tmp_path, "run1", sok(*[Spec(f"a{i}") for i in range(5)]))
    step(first, FakeGemini(*[priced(1)] * 5))
    second = scrape(tmp_path, "run2", sok(*[Spec(f"a{i}") for i in range(5)], *[Spec(f"b{i}") for i in range(5)]), state=first)
    step(second, FakeGemini(*[priced(1)] * 5), state=first, now=NOW + timedelta(hours=6))
    assert state_of(second)["usage"]["attempts"] == 10
    third = scrape(tmp_path, "run3", sok(*[Spec(f"c{i}") for i in range(8)]), state=second)
    fake = FakeGemini(*[priced(1)] * 8)
    report = step(third, fake, state=second, now=NOW + timedelta(hours=12))
    # 10 spent today: only 5 left, which is also the run limit.
    assert len(fake.requests) == 5 and state_of(third)["usage"]["attempts"] == 15
    fourth = scrape(tmp_path, "run4", sok(*[Spec(f"c{i}") for i in range(8)]), state=third)
    fake = FakeGemini(*[priced(1)] * 3)
    report = step(fourth, fake, state=third, now=NOW + timedelta(hours=14))  # 23:00 UTC, still 17 Nov in California
    assert fake.requests == []
    assert "today 15/15" in next(o.detail for o in report.outcomes if o.result == "not read")


def test_daily_limit_resets_on_the_pacific_day_not_the_turkish_one(tmp_path) -> None:
    first = scrape(tmp_path, "run1", sok(Spec("x")))
    step(first, FakeGemini(priced(1)))
    state = state_of(first)
    state["usage"] = {"quota_day": "2026-11-17", "attempts": 15}
    (first / STATE_FILE).write_text(json.dumps(state), encoding="utf-8")

    # 07:30 UTC on 18 Nov is 10:30 in Turkey (already the 18th) but 23:30 on the 17th in California.
    second = scrape(tmp_path, "run2", sok(Spec("x"), Spec("y")), state=first)
    fake = FakeGemini(priced(1))
    step(second, fake, state=first, now=datetime(2026, 11, 18, 7, 30, tzinfo=UTC), today=date(2026, 11, 18))
    assert fake.requests == []
    assert state_of(second)["usage"] == {"quota_day": "2026-11-17", "attempts": 15}

    # 08:00 UTC: midnight in California, a fresh quota day.
    third = scrape(tmp_path, "run3", sok(Spec("x"), Spec("y")), state=second)
    fake = FakeGemini(priced(1))
    report = step(third, fake, state=second, now=datetime(2026, 11, 18, 8, 0, tzinfo=UTC), today=date(2026, 11, 18))
    assert len(fake.requests) == 1 and results(report)["sok-y"] == "read"
    assert state_of(third)["usage"] == {"quota_day": "2026-11-18", "attempts": 1}


def test_unreadable_state_spends_no_quota_that_day(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a")))
    (out / STATE_FILE).write_text('{"schema_version": 1}', encoding="utf-8")
    fake = FakeGemini(priced(1))
    report = step(out, fake)
    assert fake.requests == []
    assert any("no requests until the next quota day" in n for n in report.notes)
    assert state_of(out)["usage"] == {"quota_day": "2026-11-17", "attempts": 15}


def test_request_is_counted_on_disk_before_it_is_sent(tmp_path) -> None:
    """A step killed by its timeout mid-request must still have paid for that request."""
    out = scrape(tmp_path, "out", sok(Spec("a")))
    seen: list[int] = []

    def peek(_body):
        seen.append(state_of(out)["usage"]["attempts"])
        return priced(1)

    step(out, FakeGemini(peek))
    assert seen == [1]


def test_max_requests_option_lowers_the_run_limit(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a"), Spec("b")))
    fake = FakeGemini(priced(1), priced(1))
    step(out, fake, run_limit=1)
    assert len(fake.requests) == 1
    out2 = scrape(tmp_path, "out2", sok(Spec("a"), Spec("b")))
    fake = FakeGemini(*[priced(1)] * 2)
    step(out2, fake, run_limit=99)  # never above the fixed limit
    assert len(fake.requests) == 2


def test_brochure_needing_more_requests_than_left_waits(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("big", pages=12, start=TODAY), Spec("small", start=TODAY - timedelta(days=1))))
    fake = FakeGemini(priced(1))
    report = step(out, fake, run_limit=1)
    assert results(report) == {"sok-big": "not read", "sok-small": "read"}
    assert fake.images_per_request() == [1]


# --- errors ----------------------------------------------------------------------------------------


def test_http_429_stops_ocr_for_the_run(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a"), Spec("b", start=TODAY - timedelta(days=1))))
    fake = FakeGemini(429, priced(1))
    report = step(out, fake)
    assert len(fake.requests) == 1
    assert results(report) == {"sok-a": "stopped", "sok-b": "not read"}
    state = state_of(out)
    # The request counts against the quota but not against the brochure.
    assert state["usage"]["attempts"] == 1
    assert "sok-a" not in state["brochures"]
    assert "ocr_products_url" not in brochure_of(out, "sok-a")
    verify_output(out)


def test_server_error_is_retried_once(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a")))
    fake = FakeGemini(503, priced(1))
    report = step(out, fake)
    assert len(fake.requests) == 2 and results(report) == {"sok-a": "read"}
    state = state_of(out)
    assert state["usage"]["attempts"] == 2
    assert state["brochures"]["sok-a"]["reading"]["requests"] == 2


def test_second_server_error_fails_the_brochure(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a")))
    fake = FakeGemini(500, 503, priced(1))
    report = step(out, fake)
    assert len(fake.requests) == 2 and results(report) == {"sok-a": "failed"}
    record = state_of(out)["brochures"]["sok-a"]
    assert record["failed_attempts"] == 1 and "HTTP 503" in record["last_error"]
    assert state_of(out)["usage"]["attempts"] == 2


def test_brochure_is_given_up_after_three_failed_attempts(tmp_path) -> None:
    state_dir = scrape(tmp_path, "run0", sok(Spec("bad")))
    for n in range(1, 4):
        out = scrape(tmp_path, f"run{n}", sok(Spec("bad")), state=state_dir)
        fake = FakeGemini(answer([]))  # an answer with no products
        report = step(out, fake, state=state_dir, now=NOW + timedelta(days=n))
        assert len(fake.requests) == 1 and results(report) == {"sok-bad": "failed"}
        assert state_of(out)["brochures"]["sok-bad"]["failed_attempts"] == n
        state_dir = out
    out = scrape(tmp_path, "run4", sok(Spec("bad")), state=state_dir)
    fake = FakeGemini(priced(1))
    report = step(out, fake, state=state_dir, now=NOW + timedelta(days=4))
    assert fake.requests == [] and results(report) == {"sok-bad": "given up"}
    assert state_of(out)["brochures"]["sok-bad"]["failed_attempts"] == 3

    # New pages are a new brochure as far as OCR is concerned: the count starts again.
    out = scrape(tmp_path, "run5", sok(Spec("bad", tag="v2")), state=state_dir)
    fake = FakeGemini(priced(1))
    report = step(out, fake, state=state_dir, now=NOW + timedelta(days=4))
    assert len(fake.requests) == 1 and results(report) == {"sok-bad": "read"}


def test_too_few_products_are_not_published(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a", pages=2)))
    fake = FakeGemini(priced(2, per_page=1))  # 2 products, need 5
    report = step(out, fake)
    assert results(report) == {"sok-a": "failed"}
    assert "only 2 usable products" in report.outcomes[0].detail
    assert not (out / "products_ocr").exists()
    assert "ocr_products_url" not in brochure_of(out, "sok-a")


def test_unparsable_answer_counts_as_a_failed_attempt(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a")))
    broken = {"candidates": [{"content": {"parts": [{"text": "{not json"}]}, "finishReason": "MAX_TOKENS"}]}
    report = step(out, FakeGemini(broken))
    assert results(report) == {"sok-a": "failed"}
    assert state_of(out)["brochures"]["sok-a"]["failed_attempts"] == 1
    assert state_of(out)["usage"]["attempts"] == 1


def test_internal_error_costs_one_brochure_not_the_step(tmp_path, monkeypatch) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a"), Spec("b", start=TODAY - timedelta(days=1))))
    real = ocr.convert_products
    calls = {"n": 0}

    def flaky(raw, offset, page_count):
        calls["n"] += 1
        if calls["n"] == 1:
            raise KeyError("boom")
        return real(raw, offset, page_count)

    monkeypatch.setattr(ocr, "convert_products", flaky)
    report = step(out, FakeGemini(priced(1), priced(1)))
    assert results(report) == {"sok-a": "failed", "sok-b": "read"}
    assert "internal error" in state_of(out)["brochures"]["sok-a"]["last_error"]


def test_failed_output_check_rolls_back_only_that_brochure(tmp_path, monkeypatch) -> None:
    out = scrape(tmp_path, "out", sok(Spec("good"), Spec("bad", start=TODAY - timedelta(days=1))))
    real = ocr.verify_output

    def picky(root: Path) -> None:
        if "sok-bad" in {b["id"] for b in catalog_of(root)["brochures"] if b.get("ocr_products_url")}:
            raise OutputError(["products_ocr/sok-bad.json: pretend schema failure"])
        real(root)

    monkeypatch.setattr(ocr, "verify_output", picky)
    report = step(out, FakeGemini(priced(1), priced(1)))
    assert results(report) == {"sok-good": "read", "sok-bad": "failed"}
    assert brochure_of(out, "sok-good")["ocr_products_url"] == "products_ocr/sok-good.json"
    assert "ocr_products_url" not in brochure_of(out, "sok-bad")
    assert sorted(p.name for p in (out / "products_ocr").iterdir()) == ["sok-good.json"]
    assert state_of(out)["brochures"]["sok-bad"]["failed_attempts"] == 1
    real(out)


def test_broken_scrape_output_is_left_without_ocr(tmp_path, monkeypatch) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a")))
    (out / "products").mkdir()
    (out / "products" / "orphan.json").write_text("{}", encoding="utf-8")
    fake = FakeGemini(priced(1))
    report = step(out, fake)
    assert fake.requests == []
    assert any("scrape output itself fails" in n for n in report.notes)
    assert "ocr_products_url" not in brochure_of(out, "sok-a")


def test_time_budget_stops_starting_new_brochures(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a"), Spec("b", start=TODAY - timedelta(days=1))))
    now = {"t": 0.0}

    def slow(_body):
        now["t"] = ocr.TIME_BUDGET - 60  # the first request took almost the whole budget
        return priced(1)

    report = step(out, FakeGemini(slow, priced(1)), clock=lambda: now["t"])
    assert results(report) == {"sok-a": "read", "sok-b": "not read"}
    assert "time budget" in report.outcomes[1].detail


def test_written_list_chains_are_never_read(tmp_path) -> None:
    out = scrape(tmp_path, "out", bim(), sok(Spec("a")))
    fake = FakeGemini(priced(1), priced(1))
    report = step(out, fake)
    assert set(results(report)) == {"sok-a"} and len(fake.requests) == 1
    assert "ocr_products_url" not in brochure_of(out, "bim-aktuel")


# --- command line --------------------------------------------------------------------------------


def args(out: Path, *extra: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    ocr.add_arguments(parser)
    return parser.parse_args(["--out", str(out), *extra])


def test_without_the_secret_ocr_is_disabled_but_readings_are_kept(tmp_path, monkeypatch, capsys) -> None:
    first = scrape(tmp_path, "run1", sok(Spec("a", pages=3)))
    step(first, FakeGemini(fixture_answer()))
    second = scrape(tmp_path, "run2", sok(Spec("a", pages=3), Spec("b")), state=first)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    code = ocr.main(args(second, "--state-dir", str(first)), environ={}, http=mock_http({}), now=NOW)
    assert code == 0
    printed = capsys.readouterr().out
    assert "OCR disabled" in printed and "GEMINI_API_KEY" in printed
    assert brochure_of(second, "sok-a")["ocr_products_url"] == "products_ocr/sok-a.json"
    assert "ocr_products_url" not in brochure_of(second, "sok-b")
    assert state_of(second)["usage"]["attempts"] == 1
    assert "## OCR" in summary.read_text(encoding="utf-8")
    verify_output(second)


def test_cli_creates_the_client_from_the_environment_only(tmp_path, monkeypatch) -> None:
    created: list[dict[str, Any]] = []

    class Spy:
        requests_sent = 0

        def __init__(self, key: str, **kwargs: Any) -> None:
            created.append({"key": key, **kwargs})

        def read_brochure(self, images, mime_type="image/jpeg", chain="bim"):
            self.requests_sent += 1
            return parse_brochure_response(priced(len(images)), len(images)), {}

        def close(self) -> None:
            pass

    monkeypatch.setattr(ocr, "GeminiClient", Spy)
    out = scrape(tmp_path, "out", sok(Spec("a")))
    assert ocr.main(args(out), environ={"GEMINI_API_KEY": " k-123 "}, http=mock_http({}), now=NOW) == 0
    assert created and created[0]["key"] == "k-123"
    assert created[0]["thinking_level"] == "LOW" and created[0]["model"] == "gemini-3.8-flash"
    # The step does its own retry accounting; the client must not retry behind its back.
    assert created[0]["max_retries"] == 0
    assert brochure_of(out, "sok-a")["ocr_products_url"] == "products_ocr/sok-a.json"


def test_cli_never_prints_the_key(tmp_path, capsys) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a")))
    fake = FakeGemini(400)  # the error message echoes the key
    code = ocr.main(args(out), reader=fake.client(), environ={"GEMINI_API_KEY": FAKE_KEY}, http=mock_http({}), now=NOW)
    assert code == 0
    captured = capsys.readouterr()
    assert FAKE_KEY not in captured.out + captured.err
    assert FAKE_KEY not in (out / STATE_FILE).read_text(encoding="utf-8")
    assert "[redacted]" in state_of(out)["brochures"]["sok-a"]["last_error"]


def test_cli_without_scrape_output_does_nothing(tmp_path, capsys) -> None:
    assert ocr.main(args(tmp_path / "missing"), environ={}, now=NOW) == 0
    assert "nothing to do" in capsys.readouterr().out
    assert not (tmp_path / "missing").exists()


def test_cli_survives_an_unexpected_error_and_leaves_valid_output(tmp_path, monkeypatch, capsys) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a")))

    def explode(self, t):  # noqa: ANN001
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(ocr.OcrStep, "_try", explode)
    assert ocr.main(args(out), reader=FakeGemini().client(), environ={}, now=NOW, http=mock_http({})) == 0
    assert "OCR step aborted" in capsys.readouterr().err
    verify_output(out)


def test_dry_run_plans_without_requests_downloads_or_writes(tmp_path, capsys) -> None:
    first = scrape(tmp_path, "run1", sok(Spec("a", pages=3)))
    step(first, FakeGemini(fixture_answer()))
    second = scrape(tmp_path, "run2", sok(Spec("a", pages=3), Spec("long", pages=12)), hakmar(Spec("k", pages=2)), state=first)
    before = {p: p.read_bytes() for p in second.rglob("*") if p.is_file()}
    calls: list[str] = []
    fake = FakeGemini()
    code = ocr.main(
        args(second, "--state-dir", str(first), "--dry-run"),
        reader=fake.client(),
        environ={"GEMINI_API_KEY": FAKE_KEY},
        http=mock_http({}, calls),
        now=NOW,
    )
    assert code == 0 and fake.requests == [] and calls == []
    assert {p: p.read_bytes() for p in second.rglob("*") if p.is_file()} == before
    printed = capsys.readouterr().out
    assert "sok-a: cached" in printed
    assert "sok-long: would read - 12 pages in 2 request(s)" in printed
    assert "hakmar-k: would read - 2 pages in 1 request(s) (remote pages" in printed
    assert "GEMINI_API_KEY is set" in printed


def test_subcommand_is_registered() -> None:
    from scraper.__main__ import build_parser

    parsed = build_parser().parse_args(["ocr", "--state-dir", "state", "--out", "out"])
    assert parsed.func is ocr.main and parsed.state_dir == Path("state") and parsed.out == Path("out")


# --- contract --------------------------------------------------------------------------------------


def _ocr_product(**overrides: Any) -> dict[str, Any]:
    return {
        "name": "Lastik", "brand": None, "quantity_text": "2 cm", "price_minor": 13900, "old_price_minor": None,
        "image": None, "page_index": 1, "source_url": None, "source": "ocr", **overrides,
    }


def test_products_schema_requires_a_page_for_ocr_products() -> None:
    validate_products({"schema_version": 1, "brochure_id": "x", "currency": "TRY", "products": [_ocr_product()]})
    with pytest.raises(ContractError, match="page_index"):
        validate_products({"schema_version": 1, "brochure_id": "x", "currency": "TRY", "products": [_ocr_product(page_index=None)]})
    with pytest.raises(ContractError, match="source"):
        validate_products({"schema_version": 1, "brochure_id": "x", "currency": "TRY", "products": [_ocr_product(source="ai")]})


def test_catalog_ocr_url_needs_pages(catalog) -> None:
    b = next(x for x in catalog["brochures"] if x["kind"] == "products")
    b["ocr_products_url"] = f"products_ocr/{b['id']}.json"
    with pytest.raises(ContractError, match="ocr_products_url"):
        validate_catalog(catalog)


def test_verify_output_checks_ocr_files(tmp_path) -> None:
    out = scrape(tmp_path, "out", sok(Spec("a", pages=3)))
    step(out, FakeGemini(fixture_answer()))
    verify_output(out)
    path = out / "products_ocr" / "sok-a.json"
    good = path.read_text(encoding="utf-8")

    data = json.loads(good)
    data["products"][0]["page_index"] = 3
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(OutputError, match="past the last page"):
        verify_output(out)

    data = json.loads(good)
    del data["products"][0]["source"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(OutputError, match="source must be 'ocr'"):
        verify_output(out)

    path.write_text(good, encoding="utf-8")
    (out / "products_ocr" / "stray.json").write_text("{}", encoding="utf-8")
    with pytest.raises(OutputError, match="orphan product file products_ocr/stray.json"):
        verify_output(out)


def test_scrape_run_ignores_ocr_files_of_the_previous_output(tmp_path) -> None:
    """The next scrape merges with a state/ holding OCR results and still publishes cleanly."""
    first = scrape(tmp_path, "run1", sok(Spec("a", pages=3)))
    step(first, FakeGemini(fixture_answer()))
    second = scrape(tmp_path, "run2", sok(Spec("a", pages=3)), state=first)
    b = brochure_of(second, "sok-a")
    assert "ocr_products_url" not in b
    # Same brochure, same updated_at: the OCR field never counts as a content change.
    assert b["updated_at"] == brochure_of(first, "sok-a")["updated_at"]
