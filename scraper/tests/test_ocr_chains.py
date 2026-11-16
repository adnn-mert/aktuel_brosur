"""OCR measurement: same-name tie-breaking and the Tarım Kredi (second chain) path. No network."""

from __future__ import annotations

import hashlib
import itertools
import json
import random
from pathlib import Path

import httpx
import pytest

from scraper.ocr import evaluate
from scraper.ocr.gemini import BROCHURE_PROMPT_VERSION, brochure_prompt, build_brochure_request
from scraper.ocr.matching import match_products, min_cost_assignment
from scraper.ocr.metrics import Poster, evaluate_brochure, price_tie_cost
from scraper.ocr.written import (
    WrittenListError,
    campaign_for_pdf,
    check_card_dates,
    parse_card_page,
    tkkoop_card_url,
)
from scraper.sources.tkkoop import PAGE_URL as TKKOOP_HOME
from scraper.tests.conftest import FIXTURES, fixture_text, mock_http
from scraper.tests.test_ocr import FAKE_KEY, FakeTime, gemini_client, written

MODEL = "gemini-3.8-flash"
BASE = "https://data.example/"
HOME_HTML = fixture_text("tkkoop", "anasayfa.html")
CARDS_HTML = fixture_text("ocr", "tkkoop_firsat-dolu-haftasonu.html")
PDF = "https://www.tkkoop.com.tr/assets/images/kampanya/14-16-firsat-dolu-haftasonu_1794402490.pdf"
CARDS_URL = "https://www.tkkoop.com.tr/haftalik-kampanyalar/firsat-dolu-haftasonu"
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 fake"


def tk_answer() -> dict:
    return json.loads((FIXTURES / "ocr" / "gemini_tkkoop_brochure_response.json").read_text(encoding="utf-8"))


def ocr(name: str, price: str, *, brand: str | None = None, qty: str | None = None) -> dict:
    return {"name": name, "brand": brand, "quantity_text": qty, "price": price}


def evaluate_one(ocr_items: list[dict], truth: list[dict]):
    return evaluate_brochure("x", truth, [Poster(url="https://cdn/p1.jpg", products=ocr_items)])


# --- same-name tie-breaking ----------------------------------------------------------------


def test_same_named_products_are_paired_by_price_not_input_order() -> None:
    """BİM 13 Kasım: two "LASTİK" cards (2 cm 139, 3 cm 179) with nothing else written."""
    truth = [written("LASTİK", 13900, brand="ÖREN BAYAN"), written("LASTİK", 17900, brand="ÖREN BAYAN")]
    items = [
        ocr("Lastik", "179", brand="Ören Bayan", qty="3 cm ~10 mt"),
        ocr("Lastik", "139", brand="Ören Bayan", qty="2 cm ~10 mt"),
    ]
    result = evaluate_one(items, truth)
    assert len(result.pairs) == 2
    assert all(p.correct for p in result.pairs)


def test_energy_drinks_with_equal_bare_names_pair_correctly() -> None:
    """BİM 14-20 Kasım indirim: five "Enerji İçeceği" cards; the old greedy pairing swapped two."""
    truth = [
        written("Enerji İçeceği", 9950, brand="Redbull", qty="473 ml", old=12000),
        written("Enerji İçeceği", 5950, brand="Redbull", qty="250 ml", old=7000),
        written("Enerji İçeceği", 3600, brand="Black Eagle", qty="500 ml", old=4350),
        written("Enerji İçeceği", 3600, brand="Hotline", qty="500 ml", old=4350),
        written("Enerji İçeceği", 4050, brand="Black Bruin", qty="500 ml", old=4900),
    ]
    items = [
        ocr("Enerji İçeceği", "99,50", brand="Redbull", qty="473 ml"),
        ocr("Enerji İçeceği", "59,50", brand="Redbull", qty="250 ml"),
        ocr("Enerji İçeceği", "40,50", brand="Black Bruin", qty="500 ml"),
        ocr("Enerji İçeceği", "36,00", brand="Hotline", qty="500 ml"),
        ocr("Enerji İçeceği", "36,00", brand="Black Eagle", qty="500 ml"),
    ]
    result = evaluate_one(items, truth)
    assert len(result.pairs) == 5
    assert [p.error_kind for p in result.pairs] == [None] * 5


def test_a_single_misread_price_is_still_an_error() -> None:
    result = evaluate_one([ocr("Enerji İçeceği", "40,05")], [written("Enerji İçeceği", 4050)])
    assert [p.error_kind for p in result.pairs] == ["kurus_wrong"]


def test_tie_break_does_not_hide_a_misread_among_same_named_products() -> None:
    truth = [written("LASTİK", 13900), written("LASTİK", 17900)]
    result = evaluate_one([ocr("Lastik", "189"), ocr("Lastik", "139")], truth)
    by_truth = {p.true_price_minor: p for p in result.pairs}
    assert by_truth[13900].correct
    assert not by_truth[17900].correct
    assert by_truth[17900].ocr_price_minor == 18900


def test_price_never_overrides_a_better_name_match() -> None:
    """The OCR price fits the weaker-named card exactly, yet the exact name wins and the miss is counted."""
    truth = [written("KAHVE MAKİNESİ", 20000), written("KAHVE MAKİNESİ FİLTRELİ", 10000)]
    result = evaluate_one([ocr("Kahve Makinesi", "100")], truth)
    assert [(p.written_name, p.correct) for p in result.pairs] == [("KAHVE MAKİNESİ", False)]


def test_brand_separates_same_named_products_before_price_does() -> None:
    """Both prices are swapped by the OCR itself: the brands say so, and both stay errors."""
    truth = [
        written("Enerji İçeceği", 4050, brand="Black Bruin", qty="500 ml"),
        written("Enerji İçeceği", 3600, brand="Hotline", qty="500 ml"),
    ]
    items = [
        ocr("Enerji İçeceği", "36,00", brand="Black Bruin", qty="500 ml"),
        ocr("Enerji İçeceği", "40,50", brand="Hotline", qty="500 ml"),
    ]
    result = evaluate_one(items, truth)
    assert [p.correct for p in result.pairs] == [False, False]


def test_tie_group_keeps_the_most_pairs_when_counts_differ() -> None:
    truth = [written("LASTİK", 13900), written("LASTİK", 17900)]
    items = [ocr("Lastik", "179"), ocr("Lastik", "139"), ocr("Lastik", "179")]
    matches = match_products(items, truth, tie_cost=price_tie_cost)
    assert len(matches) == 2
    pairs = {(m.ocr_index, m.written_index) for m in matches}
    assert (1, 0) in pairs
    assert {m.written_index for m in matches} == {0, 1}


def test_price_tie_cost_orders_exact_then_close_then_unreadable() -> None:
    truth = {"price_minor": 4050}
    assert price_tie_cost({"price": "40,50"}, truth) == 0
    near, far = price_tie_cost({"price": "40,00"}, truth), price_tie_cost({"price": "99,00"}, truth)
    assert 0 < near < far < price_tie_cost({"price": "?"}, truth)


def test_min_cost_assignment_matches_brute_force() -> None:
    rng = random.Random(7)
    for _ in range(200):
        n = rng.randint(1, 4)
        m = rng.randint(n, 5)
        cost = [[rng.randint(0, 9) for _ in range(m)] for _ in range(n)]
        chosen = min_cost_assignment(cost)
        assert len(set(chosen)) == n
        best = min(sum(cost[r][c] for r, c in enumerate(perm)) for perm in itertools.permutations(range(m), n))
        assert sum(cost[r][c] for r, c in enumerate(chosen)) == best
    assert min_cost_assignment([]) == []
    with pytest.raises(ValueError):
        min_cost_assignment([[1], [2]])


# --- Tarım Kredi written list ------------------------------------------------------------------


def test_parse_card_page_reads_full_names_and_split_prices() -> None:
    page = parse_card_page(CARDS_HTML)
    assert page.title == "14 - 16 Fırsat Dolu Haftasonu - KOOP MARKET"
    assert len(page.products) == 15
    assert page.unreadable == 0
    first = page.products[0]
    # The visible title is cut ("...") but the link title carries the whole name.
    assert first["name"] == "PAŞABAHÇE USKUDAR ÇAY BARDAĞI 6'LI"
    assert first["price_minor"] == 7990
    assert first["image"].startswith("https://www.tkkoop.com.tr/assets/images/urun/")
    assert {p["name"]: p["price_minor"] for p in page.products}["TKS AYRAN"] == 1250


def test_parse_card_page_without_cards_fails() -> None:
    with pytest.raises(WrittenListError):
        parse_card_page("<html><head><title>x</title></head><body></body></html>")


def test_campaign_for_pdf_links_the_brochure_to_its_card_page() -> None:
    campaign = campaign_for_pdf(HOME_HTML, PDF)
    assert campaign.slug == "firsat-dolu-haftasonu"
    assert tkkoop_card_url(campaign.slug) == CARDS_URL
    with pytest.raises(WrittenListError, match="no longer links"):
        campaign_for_pdf(HOME_HTML, "https://www.tkkoop.com.tr/assets/images/kampanya/old.pdf")
    with pytest.raises(WrittenListError):
        campaign_for_pdf("<html></html>", PDF)


def test_card_page_from_another_week_is_refused() -> None:
    week = {"valid_from": "2026-11-10", "valid_to": "2026-11-16"}
    check_card_dates("10 - 16 Kasım Kat Kat Fırsat - KOOP MARKET", week)
    with pytest.raises(WrittenListError, match="2026-11-24"):
        check_card_dates("24 - 30 Kasım Kat Kat Fırsat - KOOP MARKET", week)
    # No month in the title: the home page block is the only link, and that is accepted.
    check_card_dates("14 - 16 Fırsat Dolu Haftasonu", {"valid_from": "2026-11-14", "valid_to": "2026-11-16"})
    check_card_dates("10 - 16 Kasım", {"valid_from": None})


# --- chain plumbing ----------------------------------------------------------------------------


def tk_entry(brochure_id: str = "tkkoop-2026-11-14-firsat", pages: int = 1, source: str = PDF) -> dict:
    return {
        "id": brochure_id,
        "chain_id": "tkkoop",
        "valid_from": "2026-11-14",
        "valid_to": "2026-11-16",
        "pages": [{"url": f"media/tkkoop/{brochure_id}/p{i + 1:02d}.webp"} for i in range(pages)],
        "products_url": None,
        "source_url": source,
    }


def bim_entry(brochure_id: str) -> dict:
    return {
        "id": brochure_id,
        "chain_id": "bim",
        "pages": [{"url": f"https://cdn1.bim.com.tr/uploads/afisler/{brochure_id}.jpg"}],
        "products_url": f"products/{brochure_id}.json",
    }


def write_tk_inputs(root: Path, brochures: list[dict], *, catalog: bool = True, written_pages: bool = True) -> None:
    store = evaluate.Store(root / "data", None)
    files: list[tuple[Path, str]] = []
    if catalog:
        files.append((store.path(BASE + "catalog.json", "catalog/tkkoop", ".json"), json.dumps({"brochures": brochures})))
    if written_pages:
        files.append((store.path(TKKOOP_HOME, "tkkoop", ".html"), HOME_HTML))
        files.append((store.path(CARDS_URL, "tkkoop", ".html"), CARDS_HTML))
    for path, text in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def write_tk_answer(root: Path, entry: dict, thinking: str | None = "LOW", index: int = 0, count: int = 1,
                    urls: list[str] | None = None) -> Path:
    urls = urls or evaluate.page_urls(entry, BASE)
    path = evaluate.gemini_brochure_cache_path(root, urls, index, count, MODEL, None, thinking, "tkkoop")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"image_urls": urls, "elapsed_s": 40.0, "response": tk_answer()}), encoding="utf-8")
    return path


def test_selection_by_chain_keeps_bim_unchanged() -> None:
    catalog = {"brochures": [
        bim_entry("bim-aktuel-1"),
        tk_entry("tkkoop-a"),
        tk_entry("tkkoop-no-pdf", source="https://www.tkkoop.com.tr/"),
        bim_entry("bim-indirim-1"),
    ]}
    assert [b["id"] for b in evaluate.select_brochures_for_batch(catalog, 8)] == ["bim-indirim-1", "bim-aktuel-1"]
    assert [b["id"] for b in evaluate.select_brochures_for_batch(catalog, 8, chain="tkkoop")] == ["tkkoop-a"]
    assert [b["id"] for b in evaluate.select_brochures(catalog, 5, chain="tkkoop")] == ["tkkoop-a"]
    assert evaluate.build_parser().parse_args([]).chain == "bim"


def test_page_urls_resolve_our_rendered_pages_and_keep_absolute_ones() -> None:
    assert evaluate.page_urls(tk_entry(), BASE) == [f"{BASE}media/tkkoop/tkkoop-2026-11-14-firsat/p01.webp"]
    bim = bim_entry("bim-x")
    assert evaluate.page_urls(bim, BASE) == [bim["pages"][0]["url"]]


def test_image_suffix_and_mime_follow_the_file() -> None:
    assert evaluate.image_suffix("https://cdn1.bim.com.tr/uploads/afisler/x.jpg") == ".jpg"
    assert evaluate.image_suffix("https://x/media/p01.webp") == ".webp"
    assert evaluate.image_suffix("https://x/Image.ashx?PageNumber=1") == ".jpg"
    assert evaluate.image_mime(WEBP) == "image/webp"
    assert evaluate.image_mime(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert evaluate.image_mime(b"\xff\xd8\xff") == "image/jpeg"


def test_bim_prompt_and_cache_keys_are_unchanged(tmp_path: Path) -> None:
    """Changing either would orphan the BİM answers measured on 16 November."""
    assert hashlib.sha256(brochure_prompt(3).encode()).hexdigest() == (
        "ac09ef949254fbb3f589ff1eb0c66f3f9f7b7043a22947181906bf5ccab9aca7"
    )
    urls = ["https://cdn1.bim.com.tr/uploads/afisler/a.jpg"]
    bim = evaluate.gemini_brochure_cache_path(tmp_path, urls, 0, 1, MODEL, None, "LOW")
    assert bim.parent.name == evaluate.digest(f"brochure|{MODEL}|{BROCHURE_PROMPT_VERSION}|-|LOW", 8)
    assert bim == evaluate.gemini_brochure_cache_path(tmp_path, urls, 0, 1, MODEL, None, "LOW", "bim")
    tk = evaluate.gemini_brochure_cache_path(tmp_path, urls, 0, 1, MODEL, None, "LOW", "tkkoop")
    assert tk.parent != bim.parent
    assert evaluate.catalog_sub("bim") == "catalog"
    assert evaluate.catalog_sub("tkkoop") == "catalog/tkkoop"


def test_tkkoop_prompt_speaks_of_pages_and_skips_badge_only_offers() -> None:
    text = brochure_prompt(2, "tkkoop")
    assert "Tarım Kredi" in text and "BİM" not in text
    assert "pages of ONE" in text and "page_index 1" in text
    assert "%20 İNDİRİM" in text
    body = build_brochure_request([WEBP], "image/webp", chain="tkkoop")
    parts = body["contents"][0]["parts"]
    assert parts[0]["text"] == brochure_prompt(1, "tkkoop")
    assert parts[2]["inlineData"]["mimeType"] == "image/webp"


def test_report_and_compare_names_carry_the_chain() -> None:
    assert evaluate.report_stem("bim", "poster", None) == "report"
    assert evaluate.report_stem("bim", "brochure", "LOW") == "report_brochure_low"
    assert evaluate.report_stem("bim", "brochure", None) == "report_brochure_default"
    assert evaluate.report_stem("tkkoop", "brochure", "LOW") == "report_tkkoop_brochure_low"
    assert evaluate.report_stem("tkkoop", "brochure", None) == "report_tkkoop_brochure_default"
    assert evaluate.compare_name("bim") == "compare.txt"
    assert evaluate.compare_name("tkkoop") == "compare_tkkoop.txt"


def test_tkkoop_rejects_poster_mode(capsys) -> None:
    with pytest.raises(SystemExit) as info:
        evaluate.main(["--chain", "tkkoop", "--dry-run"])
    assert info.value.code == 2
    assert "supports --batch brochure only" in capsys.readouterr().err


def test_store_refreshes_each_url_once_per_run(tmp_path: Path) -> None:
    calls: list[str] = []
    store = evaluate.Store(tmp_path, mock_http({TKKOOP_HOME: HOME_HTML}, calls))
    for _ in range(3):
        store.text(TKKOOP_HOME, "tkkoop", ".html", refresh=True)
    assert calls == [TKKOOP_HOME]


def test_tkkoop_end_to_end_offline_scores_against_the_cards(tmp_path: Path, capsys) -> None:
    entry = tk_entry()
    write_tk_inputs(tmp_path, [bim_entry("bim-indirim-1"), entry])
    write_tk_answer(tmp_path, entry)

    code = evaluate.main(["--chain", "tkkoop", "--batch", "brochure", "--offline", "--out", str(tmp_path),
                          "--base-url", BASE, "--thinking-level", "low"])
    assert code == 0
    out = capsys.readouterr().out
    report = json.loads((tmp_path / "report_tkkoop_brochure_low.json").read_text(encoding="utf-8"))
    assert not (tmp_path / "report_brochure_low.json").exists()
    assert report["chain"] == "tkkoop"
    assert report["prompt_version"] == f"{BROCHURE_PROMPT_VERSION}:tkkoop"
    assert (report["live_requests"], report["downloads"], report["requests_evaluated"]) == (0, 0, 1)
    summary = report["summary"]
    assert (summary["written_expected"], summary["ocr_products"]) == (15, 16)
    assert (summary["matched"], summary["price_correct"]) == (13, 12)
    # The cards say 108,00 for the eggs, the printed page 105,00: the truth itself disagrees here.
    errors = [p for p in report["pairs"] if p["error_kind"]]
    assert [(p["written_name"], p["ocr_price_minor"], p["true_price_minor"]) for p in errors] == [
        ("TK ORGANİK YUMURTA 10 LU", 10500, 10800)
    ]
    assert sorted(report["unmatched_ocr"][entry["id"]], key=lambda i: i["name"])[0]["name"] == "Piliç Pirzola"
    assert "chain: tkkoop" in out
    assert "price accuracy on matches: 12/13" in out


def test_tkkoop_live_read_sends_webp_with_the_tkkoop_prompt(tmp_path: Path) -> None:
    entry = tk_entry()
    image_url = evaluate.page_urls(entry, BASE)[0]
    calls: list[str] = []
    http = mock_http({TKKOOP_HOME: HOME_HTML, CARDS_URL: CARDS_HTML, image_url: WEBP}, calls)
    store = evaluate.Store(tmp_path / "data", http)
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=tk_answer())

    with gemini_client(handler, FakeTime(), min_interval=0, thinking_level="LOW") as client:
        run = evaluate.run_brochures(
            [entry], mode="brochure", base=BASE, out=tmp_path, store=store, gemini=client, model=MODEL,
            media_resolution=None, thinking_level="LOW", threshold=0.5, max_pages=10,
            log=lambda *_a, **_k: None, chain="tkkoop",
        )
    assert run.failures == []
    assert len(sent) == 1
    parts = sent[0]["contents"][0]["parts"]
    assert parts[0]["text"] == brochure_prompt(1, "tkkoop")
    assert parts[2]["inlineData"]["mimeType"] == "image/webp"
    assert sorted(calls) == sorted([TKKOOP_HOME, CARDS_URL, image_url])
    assert store.path(image_url, "images", ".webp").exists()
    cache = evaluate.gemini_brochure_cache_path(tmp_path, [image_url], 0, 1, MODEL, None, "LOW", "tkkoop")
    saved = cache.read_text(encoding="utf-8")
    assert json.loads(saved)["chain"] == "tkkoop"
    assert FAKE_KEY not in saved
    assert run.results[0].written_count == 15


def test_tkkoop_brochure_whose_campaign_left_the_home_page_is_skipped(tmp_path: Path) -> None:
    entry = tk_entry(source="https://www.tkkoop.com.tr/assets/images/kampanya/gone.pdf")
    write_tk_inputs(tmp_path, [entry])
    write_tk_answer(tmp_path, entry)
    run = evaluate.run_brochures(
        [entry], mode="brochure", base=BASE, out=tmp_path, store=evaluate.Store(tmp_path / "data", None),
        gemini=None, model=MODEL, media_resolution=None, thinking_level="LOW", threshold=0.5, max_pages=10,
        log=lambda *_a, **_k: None, chain="tkkoop",
    )
    assert run.results == []
    assert "no longer links" in run.failures[0]


def no_network(monkeypatch) -> None:
    def refuse(*_a, **_k):
        raise AssertionError("this mode must not open a connection or read the API key")

    monkeypatch.setattr(evaluate, "HttpClient", refuse)
    monkeypatch.setattr(evaluate, "GeminiClient", refuse)
    monkeypatch.setattr(evaluate, "load_api_key", refuse)


def test_dry_run_counts_requests_from_the_cache_alone(tmp_path: Path, capsys, monkeypatch) -> None:
    no_network(monkeypatch)
    big = tk_entry("tkkoop-big", pages=3)
    small = tk_entry("tkkoop-small", pages=1, source="https://www.tkkoop.com.tr/assets/images/kampanya/x.pdf")
    write_tk_inputs(tmp_path, [big, small])
    chunks = evaluate.chunk_pages(evaluate.page_urls(big, BASE), 2)
    write_tk_answer(tmp_path, big, index=0, count=2, urls=chunks[0])

    code = evaluate.main(["--chain", "tkkoop", "--batch", "brochure", "--thinking-level", "LOW", "--dry-run",
                          "--max-pages-per-request", "2", "--max-retries", "1", "--out", str(tmp_path),
                          "--base-url", BASE])
    assert code == 0
    out = capsys.readouterr().out
    assert "plan (nothing sent): chain tkkoop, mode brochure, up to 2 pages per request" in out
    assert "tkkoop-big: 3 pages -> 2 request(s), 1 cached; images cached 0/3; written list cached (15 products)" in out
    assert "tkkoop-small: 1 pages -> 1 request(s), 0 cached" in out
    assert "written list not ready" in out  # its PDF is not on the cached home page
    assert "total: 2 brochures, 4 pages, 2 Gemini request(s) to send (1 already cached)" in out
    assert "retried up to 1 times" in out
    assert not list(tmp_path.glob("report*"))


def test_dry_run_without_a_cached_catalog_points_to_prefetch(tmp_path: Path, capsys, monkeypatch) -> None:
    no_network(monkeypatch)
    code = evaluate.main(["--chain", "tkkoop", "--batch", "brochure", "--dry-run", "--out", str(tmp_path),
                          "--base-url", BASE])
    assert code == 1
    assert "--prefetch" in capsys.readouterr().err


def test_prefetch_downloads_inputs_but_never_calls_gemini(tmp_path: Path, capsys, monkeypatch) -> None:
    entry = tk_entry(pages=2)
    urls = evaluate.page_urls(entry, BASE)
    calls: list[str] = []
    routes = {BASE + "catalog.json": json.dumps({"brochures": [entry]}), TKKOOP_HOME: HOME_HTML,
              CARDS_URL: CARDS_HTML} | {u: WEBP for u in urls}
    monkeypatch.setattr(evaluate, "HttpClient", lambda: mock_http(routes, calls))

    def refuse(*_a, **_k):
        raise AssertionError("prefetch must not touch Gemini")

    monkeypatch.setattr(evaluate, "GeminiClient", refuse)
    monkeypatch.setattr(evaluate, "load_api_key", refuse)
    code = evaluate.main(["--chain", "tkkoop", "--batch", "brochure", "--thinking-level", "LOW", "--prefetch",
                          "--out", str(tmp_path), "--base-url", BASE])
    assert code == 0
    assert sorted(calls) == sorted(routes)
    out = capsys.readouterr().out
    assert "15 written products, 2 images" in out
    assert "total: 1 brochures, 2 pages, 1 Gemini request(s) to send (0 already cached)" in out
    # The catalog snapshot lives apart from BİM's, so a refresh here never moves BİM's brochures.
    assert (tmp_path / "data" / "catalog" / "tkkoop").is_dir()
    assert not list((tmp_path / "data" / "catalog").glob("*.json"))


def test_prefetch_and_offline_cannot_be_combined(capsys) -> None:
    with pytest.raises(SystemExit):
        evaluate.main(["--chain", "tkkoop", "--batch", "brochure", "--prefetch", "--offline"])
    assert "cannot be combined" in capsys.readouterr().err


def test_compare_for_tkkoop_has_only_brochure_columns(tmp_path: Path, capsys, monkeypatch) -> None:
    no_network(monkeypatch)
    entry = tk_entry()
    write_tk_inputs(tmp_path, [entry])
    write_tk_answer(tmp_path, entry, thinking=None)
    code = evaluate.main(["--chain", "tkkoop", "--compare", "--out", str(tmp_path), "--base-url", BASE])
    assert code == 0
    out = capsys.readouterr().out
    header = next(line for line in out.splitlines() if line.startswith("brochure "))
    assert header.split()[1:] == ["brochure/default", "brochure/LOW"]
    assert (tmp_path / "compare_tkkoop.txt").exists()
    assert not (tmp_path / "compare.txt").exists()
