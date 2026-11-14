from __future__ import annotations

import json
from datetime import UTC, datetime

from scraper.__main__ import build_parser
from scraper.chains import CHAINS
from scraper.core.models import ChainKind
from scraper.runner import main
from scraper.sources import SOURCES
from scraper.tests.conftest import ROOT, mock_http
from scraper.tests.test_pipeline import FakeSource, boom, brochure, static

NOW = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)


def _run(argv: list[str], sources, **kw) -> int:
    args = build_parser().parse_args(["run", *argv])
    return main(args, sources=sources, http=mock_http({}), now=NOW, **kw)


def test_registry_has_one_source_per_scraped_chain() -> None:
    scraped = [c.id for c in CHAINS if c.kind is ChainKind.SCRAPED]
    assert sorted(s.chain_id for s in SOURCES) == sorted(scraped) == ["bim", "macrocenter", "migros", "sok"]
    assert len({c.id for c in CHAINS}) == len(CHAINS)
    assert {c.id for c in CHAINS if c.kind is ChainKind.WEBVIEW} == {"a101", "carrefoursa", "gratis"}


def test_brand_colours_match_the_designers_sample() -> None:
    # The designer picked and contrast-checked these; the registry copies them verbatim.
    sample = json.loads((ROOT / "app" / "assets" / "sample" / "catalog.json").read_text(encoding="utf-8"))
    colours = {c["id"]: c.get("brand_color") for c in sample["chains"]}
    assert {c.id: c.brand_color for c in CHAINS} == {c.id: colours.get(c.id) for c in CHAINS}
    assert next(c for c in CHAINS if c.id == "macrocenter").brand_color is None


def test_chain_order() -> None:
    ordered = [c.id for c in sorted(CHAINS, key=lambda c: c.sort_order)]
    assert ordered[:5] == ["bim", "a101", "sok", "migros", "macrocenter"]
    assert len({c.sort_order for c in CHAINS}) == len(CHAINS)


def test_run_writes_output_and_summary(tmp_path, monkeypatch, capsys) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    out = tmp_path / "out"
    code = _run(["--out", str(out), "--today", "2026-11-13"], [FakeSource("bim", static(brochure("bim", "a")))])
    assert code == 0
    assert (out / "catalog.json").is_file()
    printed = capsys.readouterr().out
    assert "chain" in printed and "bim" in printed and "published 1 brochures" in printed
    text = summary.read_text(encoding="utf-8")
    # "new" is 0: a chain's first run is not announced as new brochures.
    assert text.startswith("## Scraper run") and "| bim | ok | 1 | 0 |" in text


def test_only_selects_sources(tmp_path) -> None:
    bim = FakeSource("bim", static(brochure("bim", "a")))
    sok = FakeSource("sok", static(brochure("sok", "x")))
    assert _run(["--out", str(tmp_path / "out"), "--only", "sok"], [bim, sok]) == 0
    assert (bim.calls, sok.calls) == (0, 1)


def test_unknown_source_is_rejected(tmp_path, capsys) -> None:
    assert _run(["--out", str(tmp_path / "out"), "--only", "migros"], [FakeSource("bim", boom)]) == 1
    assert "unknown source" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_dry_run_leaves_out_untouched(tmp_path, capsys) -> None:
    out = tmp_path / "out"
    assert _run(["--out", str(out), "--dry-run"], [FakeSource("bim", static(brochure("bim", "a")))]) == 0
    assert not out.exists()
    assert "dry run" in capsys.readouterr().out


def test_exit_code_2_after_three_failures_in_a_row(tmp_path, capsys) -> None:
    out = tmp_path / "out"
    good = FakeSource("bim", static(brochure("bim", "a")))
    assert _run(["--out", str(out)], [good, FakeSource("sok", static(brochure("sok", "x")))]) == 0
    codes = [_run(["--out", str(out)], [good, FakeSource("sok", boom)]) for _ in range(3)]
    assert codes == [0, 0, 2]
    assert "FAILED (3x)" in capsys.readouterr().out


def test_exit_code_1_when_output_is_invalid(tmp_path, capsys) -> None:
    from scraper.chains import ChainInfo

    bad = [*CHAINS, ChainInfo("bad", "Bad", ChainKind.WEBVIEW, "http://insecure.example.com", 99)]
    code = _run(["--out", str(tmp_path / "out")], [FakeSource("bim", static(brochure("bim", "a")))], chains=bad)
    assert code == 1
    assert "NOT PUBLISHED" in capsys.readouterr().out
    assert not (tmp_path / "out").exists()


def test_state_dir_is_separate_from_out(tmp_path) -> None:
    state, out = tmp_path / "state", tmp_path / "out"
    assert _run(["--out", str(state)], [FakeSource("bim", static(brochure("bim", "a")))]) == 0
    assert _run(["--out", str(out), "--state-dir", str(state)], [FakeSource("bim", static(brochure("bim", "b")))]) == 0
    # The archived brochure comes from the state folder.
    assert "bim-a" in (out / "catalog.json").read_text(encoding="utf-8")
