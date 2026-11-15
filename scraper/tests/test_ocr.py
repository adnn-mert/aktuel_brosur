from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scraper.ocr import evaluate
from scraper.ocr.gemini import (
    API_KEY_ENV,
    BROCHURE_PROMPT_VERSION,
    MAX_INLINE_REQUEST_BYTES,
    GeminiClient,
    GeminiError,
    MissingApiKey,
    brochure_prompt,
    brochure_timeout,
    build_brochure_request,
    build_request,
    load_api_key,
    parse_brochure_response,
    parse_response,
    retry_delay,
)
from scraper.ocr.matching import match_products, normalize_name, pair_score, similarity, tokens
from scraper.ocr.metrics import Poster, classify_error, evaluate_brochure, poster_group, summarize
from scraper.ocr.prices import parse_ocr_price
from scraper.tests.conftest import FIXTURES, mock_http

FAKE_KEY = "test-key-not-real-123"
CARD = "https://cdn1.bim.com.tr/uploads/aktuel-urunler/1705_kucuk_543X467_{id}_{group}_0001_vector-smart-object.jpg"


def gemini_fixture() -> dict:
    return json.loads((FIXTURES / "ocr" / "gemini_response.json").read_text(encoding="utf-8"))


def written(name: str, price: int, *, brand: str | None = None, qty: str | None = None, group: int = 1,
            old: int | None = None) -> dict:
    return {
        "name": name,
        "brand": brand,
        "quantity_text": qty,
        "price_minor": price,
        "old_price_minor": old,
        "image": CARD.format(id=price, group=group),
    }


# --- prices ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("49,90", 4990),
        ("1.299,00", 129900),
        ("149₺", 14900),
        ("149 ₺", 14900),
        ("149 TL", 14900),
        ("149TL", 14900),
        ("219", 21900),
        ("49 90", 4990),
        ("49 ,90", 4990),
        ("49⁹⁰", 4990),
        ("49.90", 4990),
        ("1.299", 129900),
        ("1,299.00", 129900),
        ("25,", 2500),
        ("7,5", 750),
        (219, 21900),
        (49.9, 4990),
    ],
)
def test_parse_ocr_price_reads_poster_spellings(text, expected) -> None:
    assert parse_ocr_price(text) == expected


@pytest.mark.parametrize("text", [None, "", "fiyat", "6 taksit", "₺", True, -5])
def test_parse_ocr_price_rejects_non_prices(text) -> None:
    assert parse_ocr_price(text) is None


# --- normalisation and matching ---------------------------------------------------------------


def test_normalize_name_folds_turkish_and_punctuation() -> None:
    assert normalize_name("ÇAY BARDAĞI ~170 CC") == "cay bardagi 170 cc"
    assert normalize_name("İNCE Işık") == "ince isik"
    assert normalize_name("6'LI Kupa") == normalize_name("6LI kupa") == "6 li kupa"
    assert normalize_name("26,5X16 CM") == "26 5 x 16 cm"


def test_tokens_drop_filler_words_and_unify_units() -> None:
    assert tokens("TEK FİYAT 6'lı Kupa ~190 cc") == ["6", "kupa", "190", "ml"]


def test_similarity_prefers_the_same_size() -> None:
    small = similarity("LAV Tasty Cam Kavanoz ~575 cc", "LAV TASTY KAVANOZ ~575 CC")
    other = similarity("LAV Tasty Cam Kavanoz ~575 cc", "LAV TASTY KAVANOZ ~1050 CC")
    assert small > other


def test_pair_score_uses_brand_and_quantity_from_either_side() -> None:
    ocr = {"name": "Cam Kupa", "brand": "Glass in Love", "quantity_text": "~190 ml"}
    truth = written("CAM 6LI KUPA ~190 CC", 22900, brand="GLASS IN LOVE")
    assert pair_score(ocr, truth) > 0.6


def test_match_products_is_one_to_one_and_ignores_price() -> None:
    ocr = [
        {"name": "Tasty Cam Kavanoz", "quantity_text": "~1050 cc", "price": "35"},
        {"name": "Tasty Cam Kavanoz", "quantity_text": "~575 cc", "price": "45"},
        {"name": "Tasty Cam Kavanoz", "quantity_text": "~575 cc", "price": "35"},
        {"name": "Elektrikli Süpürge", "price": "1.999"},
    ]
    truth = [written("TASTY KAVANOZ ~575 CC", 3500), written("TASTY KAVANOZ ~1050 CC", 4500)]
    matches = match_products(ocr, truth)
    pairs = {(m.ocr_index, m.written_index) for m in matches}
    # Sizes decide the pairing even though the first OCR item carries the other jar's price.
    assert (0, 1) in pairs
    assert len({m.written_index for m in matches}) == len(matches) == 2
    assert all(m.ocr_index != 3 for m in matches)


def test_match_products_respects_threshold() -> None:
    assert match_products([{"name": "Kahve Makinesi"}], [written("ÇAYDANLIK", 99900)]) == []


# --- Gemini request and response ------------------------------------------------------------


def test_parse_response_skips_thought_parts_and_reads_usage() -> None:
    result = parse_response(gemini_fixture())
    assert len(result.products) == 6
    assert result.products[0]["name"] == "Bouquet Çay Bardağı"
    assert result.usage.prompt_tokens == 1290
    assert result.usage.thought_tokens == 800
    assert result.finish_reason == "STOP"
    assert result.usage.cost_usd == pytest.approx((1290 * 0.75 + 1210 * 3.75) / 1e6)


def test_parse_response_rejects_bad_bodies() -> None:
    with pytest.raises(GeminiError):
        parse_response({"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(GeminiError):
        parse_response({"candidates": [{"content": {"parts": [{"text": "not json"}]}}]})
    with pytest.raises(GeminiError):
        parse_response({"candidates": [{"content": {"parts": [{"text": "{\"items\": []}"}]}}]})


def test_build_request_asks_for_json_with_inline_image() -> None:
    body = build_request(b"\xff\xd8jpeg", media_resolution="MEDIA_RESOLUTION_HIGH", thinking_level="LOW")
    parts = body["contents"][0]["parts"]
    assert parts[0]["inlineData"] == {"mimeType": "image/jpeg", "data": "/9hqcGVn"}
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseJsonSchema"]["required"] == ["products"]
    assert config["mediaResolution"] == "MEDIA_RESOLUTION_HIGH"
    assert config["thinkingConfig"] == {"thinkingLevel": "LOW"}
    assert "mediaResolution" not in build_request(b"x")["generationConfig"]


def test_load_api_key_prefers_environment_then_file(tmp_path: Path) -> None:
    key_file = tmp_path / "key.txt"
    key_file.write_text("  from-file \n", encoding="utf-8")
    assert load_api_key({API_KEY_ENV: "from-env"}, key_file) == "from-env"
    assert load_api_key({}, key_file) == "from-file"
    with pytest.raises(MissingApiKey):
        load_api_key({}, tmp_path / "missing.txt")
    (tmp_path / "blank.txt").write_text("\n", encoding="utf-8")
    with pytest.raises(MissingApiKey):
        load_api_key({API_KEY_ENV: "  "}, tmp_path / "blank.txt")


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def gemini_client(handler, fake: FakeTime, **kwargs) -> GeminiClient:
    return GeminiClient(
        FAKE_KEY, transport=httpx.MockTransport(handler), clock=fake.clock, sleep=fake.sleep, **kwargs
    )


def test_client_sends_key_in_header_not_url_and_paces_requests() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=gemini_fixture())

    fake = FakeTime()
    with gemini_client(handler, fake, min_interval=12.0) as client:
        client.read_poster(b"img")
        client.read_poster(b"img")
    assert seen[0].headers["x-goog-api-key"] == FAKE_KEY
    assert FAKE_KEY not in str(seen[0].url)
    assert str(seen[0].url).endswith("/models/gemini-3.8-flash:generateContent")
    assert "Mozilla" not in seen[0].headers["user-agent"]
    assert fake.sleeps == [12.0]
    assert client.requests_sent == 2


def test_client_backs_off_on_429_using_retry_info() -> None:
    responses = [
        httpx.Response(429, json={"error": {"message": "quota", "details": [{"retryDelay": "7s"}]}}),
        httpx.Response(200, json=gemini_fixture()),
    ]
    fake = FakeTime()
    with gemini_client(lambda _r: responses.pop(0), fake, min_interval=0) as client:
        result, _raw = client.read_poster(b"img")
    assert len(result.products) == 6
    assert fake.sleeps == [7.0]


def test_client_gives_up_on_long_waits_and_never_leaks_the_key() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, json={"error": {"message": f"bad key {FAKE_KEY}", "details": [{"retryDelay": "3600s"}]}}
        )

    fake = FakeTime()
    with gemini_client(handler, fake, min_interval=0) as client, pytest.raises(GeminiError) as info:
        client.read_poster(b"img")
    assert FAKE_KEY not in str(info.value)
    assert "[redacted]" in str(info.value)


def test_client_does_not_retry_client_errors() -> None:
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    with gemini_client(handler, FakeTime(), min_interval=0) as client, pytest.raises(GeminiError, match="400"):
        client.read_poster(b"img")
    assert len(calls) == 1


def test_retry_delay_falls_back_to_header() -> None:
    assert retry_delay(httpx.Response(429, headers={"retry-after": "20"}, text="x")) == 20.0
    assert retry_delay(httpx.Response(503, text="x")) is None


# --- metrics --------------------------------------------------------------------------------


def test_poster_group_reads_the_card_image_name() -> None:
    assert poster_group(CARD.format(id=5247, group=3)) == "3"
    assert poster_group("https://example.com/x.jpg") is None
    assert poster_group(None) is None


@pytest.mark.parametrize(
    ("ocr", "true", "old", "score", "kind"),
    [
        (4990, 4990, None, 0.9, None),
        (None, 4990, None, 0.9, "price_unreadable"),
        (5990, 4990, 5990, 0.9, "read_old_price"),
        (4900, 4990, None, 0.9, "kurus_wrong"),
        (2990, 4990, None, 0.55, "possible_wrong_match"),
        (2990, 4990, None, 0.9, "one_digit_wrong"),
        (299000, 29900, None, 0.9, "other_price"),
    ],
)
def test_classify_error(ocr, true, old, score, kind) -> None:
    assert classify_error(ocr, true, old, score) == kind


def test_evaluate_brochure_against_fixture_response() -> None:
    products = parse_response(gemini_fixture()).products
    truth = [
        written("6'LI BOUQUET ÇAY BARDAĞI ~170 CC", 21900, brand="PAŞABAHÇE", group=2),
        written("CAM 6LI KUPA ~190 CC", 22900, brand="GLASS IN LOVE", group=2),
        written("TASTY KAVANOZ ~550 CC", 3500, brand="LAV", group=2),
        written("TASTY KAVANOZ ~1050 CC", 4500, brand="LAV", group=2),
        written("GRAVÜR KENARLI BORCAM", 29900, brand="BORCAM", qty="~37 cm ~2850 cc", group=2),
        written("ERKEK TREKKING AYAKKABI", 79900, group=3),
    ]
    result = evaluate_brochure("bim-x", truth, [Poster(url="https://cdn/p1.jpg", products=products)])
    by_written = {p.written_name: p for p in result.pairs}
    assert len(result.pairs) == 5
    assert by_written["CAM 6LI KUPA ~190 CC"].correct
    assert by_written["TASTY KAVANOZ ~550 CC"].ocr_price_minor == 3500
    assert by_written["GRAVÜR KENARLI BORCAM"].error_kind == "other_price"
    assert [i["name"] for i in result.unmatched_ocr] == ["Kahve Makinesi"]
    assert [w["name"] for w in result.unmatched_written] == ["ERKEK TREKKING AYAKKABI"]
    assert result.poster_recall == [("https://cdn/p1.jpg", "2", 5, 5)]

    summary = summarize([result])
    assert summary.written_expected == 6
    assert summary.matched == 5
    assert summary.price_correct == 4
    assert summary.match_rate == pytest.approx(5 / 6)
    assert summary.price_accuracy == pytest.approx(0.8)
    assert summary.ocr_extra == 1
    assert summary.poster_match_rate == 1.0
    assert summary.error_kinds == {"other_price": 1}


def test_summarize_handles_empty_input() -> None:
    summary = summarize([])
    assert summary.match_rate == 0.0
    assert summary.price_accuracy == 0.0


# --- evaluate CLI plumbing ------------------------------------------------------------------


def test_select_brochures_takes_whole_bim_brochures_within_budget() -> None:
    def b(id_: str, pages: int, chain: str = "bim", products: bool = True) -> dict:
        return {
            "id": id_,
            "chain_id": chain,
            "pages": [{"url": f"{id_}/{i}"} for i in range(pages)],
            "products_url": f"products/{id_}.json" if products else None,
        }

    catalog = {"brochures": [b("a", 3), b("m", 2, chain="migros"), b("p", 1, products=False), b("big", 4), b("c", 1)]}
    assert [x["id"] for x in evaluate.select_brochures(catalog, 4)] == ["a", "c"]


def test_evaluate_runs_offline_from_cache(tmp_path: Path, capsys) -> None:
    base = "https://data.example/"
    image = "https://cdn1.bim.com.tr/uploads/afisler/p1.jpg"
    catalog = {"brochures": [{"id": "bim-1", "chain_id": "bim", "pages": [{"url": image}],
                              "products_url": "products/bim-1.json"}]}
    products = {"products": [written("CAM 6LI KUPA ~190 CC", 22900, brand="GLASS IN LOVE")]}
    data = tmp_path / "data"
    for sub, url, body in (("catalog", base + "catalog.json", catalog),
                           ("products", base + "products/bim-1.json", products)):
        (data / sub).mkdir(parents=True, exist_ok=True)
        (data / sub / f"{evaluate.digest(url)}.json").write_text(json.dumps(body), encoding="utf-8")
    cache = evaluate.gemini_cache_path(tmp_path, image, "gemini-3.8-flash", None, None)
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"image_url": image, "response": gemini_fixture()}), encoding="utf-8")

    code = evaluate.main(["--offline", "--out", str(tmp_path), "--base-url", base, "--max-images", "5"])
    assert code == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["matched"] == 1
    assert report["summary"]["price_correct"] == 1
    assert report["live_requests"] == 0
    assert report["downloads"] == 0
    assert "price accuracy on matches: 1/1" in capsys.readouterr().out


def test_real_gemini_response_parses_to_kurus() -> None:
    """A trimmed response recorded from gemini-3.8-flash on a BİM poster (2026-11-15)."""
    recorded = json.loads((FIXTURES / "ocr" / "gemini_bim_real.json").read_text(encoding="utf-8"))
    result = parse_response(recorded["response"])
    prices = [parse_ocr_price(p["price"]) for p in result.products]
    assert len(result.products) == 12
    assert prices[0] == 1590000
    assert None not in prices
    assert result.usage.prompt_tokens == 1311


def test_client_backs_off_exponentially_without_server_hint() -> None:
    responses = [httpx.Response(503, text="busy"), httpx.Response(503, text="busy"),
                 httpx.Response(200, json=gemini_fixture())]
    fake = FakeTime()
    with gemini_client(lambda _r: responses.pop(0), fake, min_interval=0) as client:
        client.read_poster(b"img")
    assert fake.sleeps == [30.0, 60.0]
    assert client.requests_sent == 3


def test_thinking_level_is_sent_upper_case_and_keys_the_cache(tmp_path: Path) -> None:
    assert build_request(b"x", thinking_level="low")["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "LOW"}
    url = "https://cdn1.bim.com.tr/uploads/afisler/p1.jpg"
    default = evaluate.gemini_cache_path(tmp_path, url, "gemini-3.8-flash", None, None)
    low = evaluate.gemini_cache_path(tmp_path, url, "gemini-3.8-flash", None, "LOW")
    assert default != low
    assert low == evaluate.gemini_cache_path(tmp_path, url, "gemini-3.8-flash", None, "low")
    assert evaluate.build_parser().parse_args(["--thinking-level", "low"]).thinking_level == "LOW"


def test_client_records_latency_of_the_successful_request() -> None:
    fake = FakeTime()

    def handler(_request: httpx.Request) -> httpx.Response:
        fake.now += 42.0
        return httpx.Response(200, json=gemini_fixture())

    with gemini_client(handler, fake, min_interval=0) as client:
        client.read_poster(b"img")
    assert client.last_elapsed == 42.0


def test_live_read_caches_response_with_latency(tmp_path: Path) -> None:
    fake = FakeTime()

    def handler(_request: httpx.Request) -> httpx.Response:
        fake.now += 5.0
        return httpx.Response(200, json=gemini_fixture())

    image = "https://cdn1.bim.com.tr/uploads/afisler/p1.jpg"
    store = evaluate.Store(tmp_path / "data", mock_http({image: b"\xff\xd8jpeg"}))
    cache = evaluate.gemini_cache_path(tmp_path, image, "gemini-3.8-flash", None, "LOW")
    with gemini_client(handler, fake, min_interval=0, thinking_level="LOW") as client:
        result, live, elapsed = evaluate.read_poster(image, store, client, cache)
        again = evaluate.read_poster(image, store, client, cache)
    assert (live, elapsed, len(result.products)) == (True, 5.0, 6)
    assert again[1:] == (False, 5.0)
    assert client.requests_sent == 1
    assert store.downloads == 1
    saved = json.loads(cache.read_text(encoding="utf-8"))
    assert saved["thinking_level"] == "LOW"
    assert FAKE_KEY not in cache.read_text(encoding="utf-8")


# --- brochure batch mode --------------------------------------------------------------------

MODEL = "gemini-3.8-flash"
BASE = "https://data.example/"


def brochure_fixture() -> dict:
    return json.loads((FIXTURES / "ocr" / "gemini_brochure_response.json").read_text(encoding="utf-8"))


def page_urls(brochure_id: str, count: int) -> list[str]:
    return [f"https://cdn1.bim.com.tr/uploads/afisler/{brochure_id}-p{i}.jpg" for i in range(count)]


def catalog_entry(brochure_id: str, pages: int, chain: str = "bim") -> dict:
    return {
        "id": brochure_id,
        "chain_id": chain,
        "pages": [{"url": u} for u in page_urls(brochure_id, pages)],
        "products_url": f"products/{brochure_id}.json",
    }


TRUTH = [
    written("6'LI BOUQUET ÇAY BARDAĞI ~170 CC", 21900, brand="PAŞABAHÇE", group=2),
    written("CAM 6LI KUPA ~190 CC", 22900, brand="GLASS IN LOVE", group=2),
    written("TASTY KAVANOZ ~575 CC", 3500, brand="LAV", group=2),
    written("TASTY KAVANOZ ~1050 CC", 4500, brand="LAV", group=2),
    written("ERKEK TREKKING AYAKKABI", 79900, group=3),
]


def write_data(root: Path, brochures: list[dict]) -> None:
    """Cache the catalog and product lists exactly where ``Store`` looks for them."""
    data = root / "data"
    entries = [("catalog", BASE + "catalog.json", {"brochures": brochures})]
    entries += [("products", BASE + b["products_url"], {"products": TRUTH}) for b in brochures]
    for sub, url, body in entries:
        (data / sub).mkdir(parents=True, exist_ok=True)
        (data / sub / f"{evaluate.digest(url)}.json").write_text(json.dumps(body), encoding="utf-8")


def write_brochure_cache(root: Path, urls: list[str], index: int = 0, count: int = 1, thinking=None,
                         body: dict | None = None, elapsed: float | None = 30.0) -> Path:
    path = evaluate.gemini_brochure_cache_path(root, urls, index, count, MODEL, None, thinking)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"image_urls": urls, "elapsed_s": elapsed, "response": body or brochure_fixture()}),
        encoding="utf-8",
    )
    return path


def write_poster_cache(root: Path, url: str, thinking=None) -> None:
    path = evaluate.gemini_cache_path(root, url, MODEL, None, thinking)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"image_url": url, "elapsed_s": 10.0, "response": gemini_fixture()}), encoding="utf-8")


def run_offline(entries: list[dict], root: Path, max_pages: int = 10):
    return evaluate.run_brochures(
        entries, mode="brochure", base=BASE, out=root, store=evaluate.Store(root / "data", None), gemini=None,
        model=MODEL, media_resolution=None, thinking_level=None, threshold=0.6, max_pages=max_pages,
        log=lambda *_a, **_k: None,
    )


def test_build_brochure_request_sends_all_images_in_one_request() -> None:
    body = build_brochure_request([b"one", b"two", b"three"], media_resolution="MEDIA_RESOLUTION_HIGH",
                                  thinking_level="low")
    assert len(body["contents"]) == 1
    parts = body["contents"][0]["parts"]
    assert parts[0] == {"text": brochure_prompt(3)}
    assert "page_index 2" in parts[0]["text"]
    # Each image is preceded by its label so the model needn't count.
    assert [p["text"] for p in parts[1::2]] == ["page_index: 0", "page_index: 1", "page_index: 2"]
    images = [p["inlineData"] for p in parts[2::2]]
    assert [i["data"] for i in images] == ["b25l", "dHdv", "dGhyZWU="]
    assert {i["mimeType"] for i in images} == {"image/jpeg"}
    config = body["generationConfig"]
    assert config["thinkingConfig"] == {"thinkingLevel": "LOW"}
    assert config["mediaResolution"] == "MEDIA_RESOLUTION_HIGH"
    item = config["responseJsonSchema"]["properties"]["products"]["items"]
    assert "page_index" in item["required"]
    assert "page_index" in item["properties"]
    assert "thinkingConfig" not in build_brochure_request([b"x"])["generationConfig"]


def test_build_brochure_request_needs_an_image() -> None:
    with pytest.raises(ValueError):
        build_brochure_request([])


def test_chunk_pages_splits_in_order_into_even_chunks() -> None:
    pages = list(range(23))
    chunks = evaluate.chunk_pages(pages, 10)
    assert [len(c) for c in chunks] == [8, 8, 7]
    assert [x for c in chunks for x in c] == pages
    assert [len(c) for c in evaluate.chunk_pages(list(range(11)), 10)] == [6, 5]
    assert evaluate.chunk_pages(list(range(10)), 10) == [list(range(10))]
    assert evaluate.chunk_pages([], 10) == []
    with pytest.raises(ValueError):
        evaluate.chunk_pages([1], 0)


def test_parse_brochure_response_assigns_page_indexes_from_fixture() -> None:
    result = parse_brochure_response(brochure_fixture(), 3)
    # The string "2" is coerced; 7 is out of range for three images.
    assert [p["page_index"] for p in result.products] == [0, 0, 1, 1, 2, None]
    assert result.products[0]["name"] == "Bouquet Çay Bardağı"
    assert result.usage.prompt_tokens == 3900
    assert result.usage.output_tokens == 640
    assert result.usage.thought_tokens == 1500
    assert result.finish_reason == "STOP"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, None), (1.0, 1), (1.5, None), (-1, None), ("x", None), (None, None), (3, None), (" 2 ", 2)],
)
def test_brochure_page_index_coercion(value, expected) -> None:
    text = json.dumps({"products": [{"page_index": value, "name": "a", "price": "1"}]})
    body = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    assert parse_brochure_response(body, 3).products[0]["page_index"] == expected


def test_brochure_cache_key_never_collides_with_poster_or_other_settings(tmp_path: Path) -> None:
    urls = page_urls("bim-x", 4)
    base = evaluate.gemini_brochure_cache_path(tmp_path, urls, 0, 1, MODEL, None, None)
    assert base == evaluate.gemini_brochure_cache_path(tmp_path, urls, 0, 1, MODEL, None, None)
    variants = {
        "thinking": evaluate.gemini_brochure_cache_path(tmp_path, urls, 0, 1, MODEL, None, "LOW"),
        "resolution": evaluate.gemini_brochure_cache_path(tmp_path, urls, 0, 1, MODEL, "MEDIA_RESOLUTION_HIGH", None),
        "model": evaluate.gemini_brochure_cache_path(tmp_path, urls, 0, 1, "other-model", None, None),
        "chunk size": evaluate.gemini_brochure_cache_path(tmp_path, urls, 0, 2, MODEL, None, None),
        "chunk position": evaluate.gemini_brochure_cache_path(tmp_path, urls, 1, 2, MODEL, None, None),
        "images": evaluate.gemini_brochure_cache_path(tmp_path, urls[:3], 0, 1, MODEL, None, None),
    }
    assert len({base, *variants.values()}) == len(variants) + 1
    assert evaluate.gemini_brochure_cache_path(tmp_path, urls, 0, 1, MODEL, None, "low") == variants["thinking"]
    # Poster answers for the same URL or the same settings live in another folder.
    poster = evaluate.gemini_cache_path(tmp_path, urls[0], MODEL, None, None)
    assert poster.parent != base.parent
    assert poster != base


def test_poster_cache_key_is_unchanged(tmp_path: Path) -> None:
    """Brochure mode must not orphan the poster answers cached before it existed."""
    path = evaluate.gemini_cache_path(tmp_path, "https://x/y.jpg", MODEL, None, None)
    assert path.parent.name == evaluate.digest(f"{MODEL}|v1|-|-", 8)


def test_select_brochures_for_batch_prefers_discount_brochures() -> None:
    catalog = {"brochures": [
        catalog_entry("bim-aktuel-1", 2),
        catalog_entry("migros-1", 2, chain="migros"),
        catalog_entry("bim-aktuel-2", 2),
        catalog_entry("bim-indirim-1", 3),
        catalog_entry("bim-indirim-2", 3),
    ]}

    def ids(limit: int, max_images: int | None = None) -> list[str]:
        return [b["id"] for b in evaluate.select_brochures_for_batch(catalog, limit, max_images)]

    assert ids(3) == ["bim-indirim-1", "bim-indirim-2", "bim-aktuel-1"]
    assert ids(1) == ["bim-indirim-1"]
    assert ids(8) == ["bim-indirim-1", "bim-indirim-2", "bim-aktuel-1", "bim-aktuel-2"]
    # --max-images still keeps whole brochures only and skips ones that do not fit.
    assert ids(8, 5) == ["bim-indirim-1", "bim-aktuel-1"]
    args = evaluate.build_parser().parse_args([])
    assert (args.max_brochures, args.max_pages_per_request) == (8, 10)


def test_brochure_timeout_grows_with_images_and_is_capped() -> None:
    assert brochure_timeout(1) < brochure_timeout(10)
    assert brochure_timeout(5, 420.0) == 420.0 + 120.0 * 5
    assert brochure_timeout(500) == 1500.0


def timeout_handler(seen: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    return handler


def test_brochure_request_times_out_once_then_retries_exactly_once() -> None:
    seen: list[httpx.Request] = []
    fake = FakeTime()
    with gemini_client(timeout_handler(seen), fake, min_interval=0) as client:
        with pytest.raises(GeminiError, match="network error"):
            client.read_brochure([b"a", b"b"])
    assert client.requests_sent == len(seen) == 2
    # The per-request timeout scales with the image count instead of using the client default.
    assert seen[0].extensions["timeout"]["read"] == brochure_timeout(2)
    assert fake.sleeps == [30.0]


def test_brochure_request_recovers_when_the_retry_succeeds() -> None:
    responses: list = [httpx.ReadTimeout("slow"), httpx.Response(200, json=brochure_fixture())]

    def handler(_request: httpx.Request) -> httpx.Response:
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    with gemini_client(handler, FakeTime(), min_interval=0) as client:
        result, _raw = client.read_brochure([b"a", b"b", b"c"])
    assert client.requests_sent == 2
    assert len(result.products) == 6


def test_poster_request_keeps_the_generic_retry_budget_on_timeouts() -> None:
    seen: list[httpx.Request] = []
    with gemini_client(timeout_handler(seen), FakeTime(), min_interval=0) as client:
        with pytest.raises(GeminiError):
            client.read_poster(b"img")
    assert len(seen) == 5  # first try plus MAX_RETRIES (4)


def test_brochure_request_over_20_mb_is_refused_before_any_request() -> None:
    seen: list[httpx.Request] = []
    half = MAX_INLINE_REQUEST_BYTES * 3 // 8 + 1000  # base64 inflates by 4/3: two of these are just over the limit
    images = [b"\0" * half, b"\0" * half]
    with gemini_client(timeout_handler(seen), FakeTime(), min_interval=0) as client:
        with pytest.raises(GeminiError, match="20 MB"):
            client.read_brochure(images)
    assert seen == []
    assert client.requests_sent == 0


def test_brochure_request_under_20_mb_is_sent() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=brochure_fixture())

    images = [b"\0" * (MAX_INLINE_REQUEST_BYTES // 2)]  # 10 MiB raw -> 13.3 MiB encoded
    with gemini_client(handler, FakeTime(), min_interval=0) as client:
        client.read_brochure(images)
    assert len(seen) == 1


def test_live_brochure_read_sends_one_request_and_caches_the_chunk(tmp_path: Path) -> None:
    urls = page_urls("bim-x", 3)
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=brochure_fixture())

    http = mock_http({u: b"\xff\xd8" + str(i).encode() for i, u in enumerate(urls)})
    store = evaluate.Store(tmp_path / "data", http)
    cache = evaluate.gemini_brochure_cache_path(tmp_path, urls, 0, 1, MODEL, None, "LOW")
    with gemini_client(handler, FakeTime(), min_interval=0, thinking_level="LOW") as client:
        result, live, _elapsed = evaluate.read_brochure_chunk(urls, store, client, cache)
        again, live_again, _ = evaluate.read_brochure_chunk(urls, store, client, cache)
    assert live and not live_again
    assert len(seen) == 1
    assert len(seen[0]["contents"][0]["parts"]) == 1 + 2 * 3
    assert seen[0]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "LOW"}
    assert [p["page_index"] for p in again.products] == [p["page_index"] for p in result.products]
    saved = json.loads(cache.read_text(encoding="utf-8"))
    assert saved["image_urls"] == urls
    assert saved["thinking_level"] == "LOW"
    assert FAKE_KEY not in cache.read_text(encoding="utf-8")


def test_read_brochure_chunk_offline_without_cache_fails_cleanly(tmp_path: Path) -> None:
    store = evaluate.Store(tmp_path / "data", None)
    with pytest.raises(GeminiError, match="not cached"):
        evaluate.read_brochure_chunk(["a", "b"], store, None, tmp_path / "missing.json")


def test_posters_from_chunk_groups_by_page_and_keeps_strays() -> None:
    urls = ["u0", "u1"]
    products = [{"name": "a", "page_index": 1}, {"name": "b", "page_index": 0}, {"name": "c", "page_index": None},
                {"name": "d", "page_index": 5}]
    posters = evaluate.posters_from_chunk(urls, products)
    assert [p.url for p in posters] == ["u0", "u1", "u0" + evaluate.UNASSIGNED]
    assert [[x["name"] for x in p.products] for p in posters] == [["b"], ["a"], ["c", "d"]]
    assert len(evaluate.posters_from_chunk(urls, [])) == 2


def test_brochure_run_counts_tokens_only_for_fully_read_brochures(tmp_path: Path) -> None:
    full = catalog_entry("bim-indirim-1", 4)
    partial = catalog_entry("bim-indirim-2", 4)
    write_data(tmp_path, [full, partial])
    full_chunks = evaluate.chunk_pages([p["url"] for p in full["pages"]], 2)
    partial_chunks = evaluate.chunk_pages([p["url"] for p in partial["pages"]], 2)
    for i, chunk in enumerate(full_chunks):
        write_brochure_cache(tmp_path, chunk, i, 2)
    write_brochure_cache(tmp_path, partial_chunks[0], 0, 2)  # the second chunk is missing
    run = run_offline([full, partial], tmp_path, max_pages=2)
    assert [r.brochure_id for r in run.results] == ["bim-indirim-1"]
    assert run.reads == 2
    assert run.usage.prompt_tokens == 2 * 3900  # the half-read brochure adds nothing
    assert run.latencies == [30.0, 30.0]
    assert len(run.failures) == 1 and run.failures[0].startswith("bim-indirim-2")
    # In a two-image chunk both "2" and 7 are out of range: 2 strays per chunk, 2 chunks.
    assert run.unassigned_products == 4


def test_brochure_run_unassigned_and_cache_split_by_chunk_size(tmp_path: Path) -> None:
    entry = catalog_entry("bim-indirim-1", 3)
    write_data(tmp_path, [entry])
    write_brochure_cache(tmp_path, [p["url"] for p in entry["pages"]])  # cached for one request of 3 pages
    run = run_offline([entry], tmp_path, max_pages=10)
    assert run.reads == 1
    assert run.unassigned_products == 1  # page_index 7 is out of range for 3 pages
    # Asking for 2 pages per request is a different split, so the old answer is not reused.
    again = run_offline([entry], tmp_path, max_pages=2)
    assert again.results == [] and again.reads == 0
    assert "not cached" in again.failures[0]


def test_brochure_mode_end_to_end_offline(tmp_path: Path, capsys) -> None:
    entry = catalog_entry("bim-indirim-1", 3)
    other = catalog_entry("bim-aktuel-1", 3)
    write_data(tmp_path, [other, entry])
    write_brochure_cache(tmp_path, [p["url"] for p in entry["pages"]], thinking="LOW")

    code = evaluate.main(["--batch", "brochure", "--offline", "--out", str(tmp_path), "--base-url", BASE,
                          "--max-brochures", "1", "--thinking-level", "low"])
    assert code == 0
    out = capsys.readouterr().out
    report = json.loads((tmp_path / "report_brochure_low.json").read_text(encoding="utf-8"))
    # Only the discount brochure was picked (the other has no cached answer) and nothing hit the network.
    assert report["mode"] == "brochure"
    assert report["prompt_version"] == BROCHURE_PROMPT_VERSION
    assert report["options"]["max_pages_per_request"] == 10
    assert report["options"]["thinking_level"] == "LOW"
    assert report["live_requests"] == 0
    assert report["downloads"] == 0
    assert report["requests_evaluated"] == 1
    assert report["failures"] == []
    assert report["unassigned_products"] == 1
    assert report["summary"]["brochures"] == 1
    assert report["summary"]["written_expected"] == 5
    assert report["summary"]["matched"] == 5
    assert report["usage"]["prompt_tokens"] == 3900
    assert {p["brochure_id"] for p in report["pairs"]} == {"bim-indirim-1"}
    assert all(evaluate.UNASSIGNED not in p["image_url"] for p in report["pairs"])
    assert "mode: brochure (up to 10 pages per request)" in out
    assert "OCR products without a valid page_index: 1" in out
    assert (tmp_path / "report_brochure_low.txt").exists()
    assert not (tmp_path / "report.json").exists()


def test_brochure_mode_offline_without_cache_reports_nothing_evaluated(tmp_path: Path, capsys) -> None:
    write_data(tmp_path, [catalog_entry("bim-indirim-1", 2)])
    code = evaluate.main(["--batch", "brochure", "--offline", "--out", str(tmp_path), "--base-url", BASE])
    assert code == 1
    captured = capsys.readouterr()
    assert "nothing evaluated" in captured.err
    assert "not cached" in captured.err


def test_compare_prints_runs_side_by_side_without_network(tmp_path: Path, capsys, monkeypatch) -> None:
    def no_network(*_a, **_k):
        raise AssertionError("--compare must not create an HTTP or Gemini client")

    monkeypatch.setattr(evaluate, "HttpClient", no_network)
    monkeypatch.setattr(evaluate, "GeminiClient", no_network)
    entry = catalog_entry("bim-indirim-1", 2)
    write_data(tmp_path, [entry])
    urls = [p["url"] for p in entry["pages"]]
    for url in urls:
        write_poster_cache(tmp_path, url)  # poster / default
    write_brochure_cache(tmp_path, urls)  # brochure / default
    write_brochure_cache(tmp_path, urls, thinking="LOW")  # brochure / LOW; poster / LOW stays missing

    code = evaluate.main(["--compare", "--out", str(tmp_path), "--base-url", BASE])
    assert code == 0
    out = capsys.readouterr().out
    lines = {line.split()[0]: line for line in out.splitlines() if line.strip()}
    assert lines["brochure"].split()[1:] == ["poster/default", "brochure/default", "poster/LOW", "brochure/LOW"]
    cells = lines["bim-indirim-1"].split()[1:]
    # Cells are "matched/written correct/matched" (two tokens) or a lone "-".
    assert cells.count("-") == 1
    assert len(cells) == 3 * 2 + 1
    assert "poster/LOW: no brochures" in out
    assert "brochure/default: brochures 1" in out
    # Poster mode behind these numbers is two requests (two pages), brochure mode one.
    assert "poster/default: requests 2" in out
    assert "brochure/default: requests 1" in out
    assert "tokens in 3900 out 640 thinking 1500" in out
    assert (tmp_path / "compare.txt").read_text(encoding="utf-8").startswith("comparison from cached answers")


def test_compare_fails_when_nothing_is_cached(tmp_path: Path, capsys) -> None:
    write_data(tmp_path, [catalog_entry("bim-indirim-1", 2)])
    assert evaluate.main(["--compare", "--out", str(tmp_path), "--base-url", BASE]) == 1
    assert "no cached results" in capsys.readouterr().err


def test_parse_levels_and_compare_defaults() -> None:
    assert evaluate.parse_levels("-,low") == [None, "LOW"]
    assert evaluate.build_parser().parse_args([]).compare_levels == [None, "LOW"]
