from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scraper.ocr import evaluate
from scraper.ocr.gemini import (
    API_KEY_ENV,
    GeminiClient,
    GeminiError,
    MissingApiKey,
    build_request,
    load_api_key,
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
