"""Both real sources against recorded pages, through the full pipeline (no network)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

from scraper.__main__ import main as cli
from scraper.chains import CHAINS
from scraper.core.pipeline import run, verify_output
from scraper.sources.bim import POSTERS_URL, BimSource, parse_product_tabs
from scraper.sources.sok import PAGE_URL, SokSource
from scraper.tests.conftest import fixture_text, make_pdf, mock_http

TODAY = date(2026, 11, 13)
NOW = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)


def _routes() -> dict[str, object]:
    posters = fixture_text("bim", "afisler.html")
    routes: dict[str, object] = {POSTERS_URL: posters, PAGE_URL: fixture_text("sok", "firsatlar.html")}
    for tab in parse_product_tabs(posters):
        key = tab.url.rsplit("=", 1)[1]
        routes[tab.url] = (
            fixture_text("bim", f"aktuel-urunler-{key}.html")
            if key in ("1705", "1711", "1709")
            else '<div class="productArea"></div>'
        )
    routes["https://kurumsal.sokmarket.com.tr/uploads/pdf/mwajrdpq-18-24kasim.pdf"] = make_pdf(2)
    routes["https://kurumsal.sokmarket.com.tr/uploads/pdf/mwajlev6-21-24kasim.pdf"] = make_pdf(1)
    return routes


def test_broken_bim_page_keeps_bim_and_publishes_sok(tmp_path) -> None:
    out = tmp_path / "out"
    routes = _routes()
    first = run([BimSource(), SokSource()], CHAINS, out, out, TODAY, NOW, http=mock_http(routes))
    assert first.exit_code == 0
    verify_output(out)
    assert cli(["validate", str(out / "catalog.json")]) == 0
    catalog = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    bim_before = [b for b in catalog["brochures"] if b["chain_id"] == "bim"]
    assert len(bim_before) == 19
    assert sum(b["chain_id"] == "sok" for b in catalog["brochures"]) == 2

    # BİM redesigns its page: the poster groups are gone.
    routes[POSTERS_URL] = "<html><body><h1>Yeni tasarım</h1></body></html>"
    second = run([BimSource(), SokSource()], CHAINS, out, out, TODAY, NOW + timedelta(hours=6), http=mock_http(routes))
    assert second.exit_code == 0
    by_chain = {s.chain_id: s for s in second.sources}
    assert not by_chain["bim"].ok and "layout" in (by_chain["bim"].error or "")
    assert by_chain["sok"].ok

    catalog = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    chains = {c["id"]: c for c in catalog["chains"]}
    assert chains["bim"]["status"] == "stale" and chains["sok"]["status"] == "ok"
    assert [b for b in catalog["brochures"] if b["chain_id"] == "bim"] == bim_before
    assert (out / "products/bim-aktuel-2026-11-13.json").is_file()
    verify_output(out)
