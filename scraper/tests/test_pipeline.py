from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from scraper.chains import CHAINS, ChainInfo
from scraper.core.models import Brochure, BrochureKind, Page, Product, ProductFile
from scraper.core.pdf import RenderedPage
from scraper.core.pipeline import ARCHIVE_DAYS, run
from scraper.core.source import SourceContext, SourceResult, products_path
from scraper.core.validate import validate_catalog, validate_health, validate_products
from scraper.tests.conftest import mock_http

TODAY = date(2026, 11, 13)
T0 = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)


class FakeSource:
    """A source whose behaviour each test swaps in via ``fn``."""

    def __init__(self, chain_id: str, fn: Callable[[SourceContext], SourceResult]) -> None:
        self.chain_id = chain_id
        self.fn = fn
        self.calls = 0

    def collect(self, ctx: SourceContext) -> SourceResult:
        self.calls += 1
        return self.fn(ctx)


def brochure(chain_id: str, key: str, **overrides) -> Brochure:
    fields = dict(
        id=f"{chain_id}-{key}",
        chain_id=chain_id,
        title=f"Broşür {key}",
        date_label=None,
        valid_from=TODAY,
        valid_to=TODAY + timedelta(days=6),
        kind=BrochureKind.PAGES,
        cover=None,
        pages=(Page(f"https://cdn.example.com/{chain_id}/{key}.jpg"),),
        products_url=None,
        product_count=0,
        source_url=f"https://example.com/{chain_id}",
        first_seen=T0,
        updated_at=T0,
    )
    fields.update(overrides)
    return Brochure(**fields)


def with_products(b: Brochure, *names: str) -> tuple[Brochure, ProductFile]:
    products = ProductFile(b.id, tuple(Product(name=n, price_minor=100 * (i + 1)) for i, n in enumerate(names)))
    return replace(b, kind=BrochureKind.BOTH, products_url=products_path(b.id), product_count=len(names)), products


def static(*brochures: Brochure, products: dict[str, ProductFile] | None = None):
    return lambda _ctx: SourceResult(list(brochures), dict(products or {}))


def boom(_ctx: SourceContext) -> SourceResult:
    raise RuntimeError("layout changed\nTraceback (most recent call last): ...")


def media_source(*keys: str, pages: int = 2):
    """A PDF-like source that writes its own page images, the way Şok does."""

    def collect(ctx: SourceContext) -> SourceResult:
        out = []
        for key in keys:
            b = brochure("sok", key)
            written = ctx.media.write_pages("sok", b.id, [RenderedPage(f"{key}-{i}".encode(), 10, 14) for i in range(pages)])
            out.append(replace(b, pages=tuple(written), cover=written[0]))
        return SourceResult(out)

    return collect


def do_run(tmp_path: Path, sources, now: datetime = T0, today: date = TODAY, chains=CHAINS, **kw):
    out = tmp_path / "out"
    kw.setdefault("http", mock_http({}))
    kw.setdefault("clock", lambda: 0.0)
    return run(sources, chains, out, out, today, now, **kw)


def load(tmp_path: Path, name: str = "catalog.json") -> dict:
    return json.loads((tmp_path / "out" / name).read_text(encoding="utf-8"))


def ids(catalog: dict, chain_id: str | None = None) -> list[str]:
    return [b["id"] for b in catalog["brochures"] if chain_id is None or b["chain_id"] == chain_id]


def chain(catalog: dict, chain_id: str) -> dict:
    return next(c for c in catalog["chains"] if c["id"] == chain_id)


def health(tmp_path: Path, chain_id: str) -> dict:
    return next(s for s in load(tmp_path, "health.json")["sources"] if s["chain_id"] == chain_id)


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# --- basics ----------------------------------------------------------------------------


def test_first_run_publishes_valid_output(tmp_path) -> None:
    b, products = with_products(brochure("bim", "a"), "Su", "Çay")
    report = do_run(tmp_path, [FakeSource("bim", static(b, products={b.id: products})), FakeSource("sok", media_source("x"))])
    assert report.exit_code == 0 and report.written and report.first_run
    # Every chain's first run only fills in what is already out: nothing to announce.
    assert report.new_brochure_ids == []

    catalog = load(tmp_path)
    validate_catalog(catalog)
    validate_health(load(tmp_path, "health.json"))
    product_file = load(tmp_path, f"products/{b.id}.json")
    validate_products(product_file)
    assert [p["name"] for p in product_file["products"]] == ["Su", "Çay"]
    assert (tmp_path / "out/media/sok/sok-x/p02.webp").read_bytes() == b"x-1"
    assert chain(catalog, "bim")["status"] == "ok"
    assert chain(catalog, "bim")["last_ok_at"] == "2026-11-13T09:00:00Z"


def test_webview_chains_are_listed_without_brochures(tmp_path) -> None:
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a")))])
    catalog = load(tmp_path)
    webviews = {c["id"]: c for c in catalog["chains"] if c["kind"] == "webview"}
    assert set(webviews) == {"a101", "carrefoursa", "gratis"}
    assert webviews["a101"]["web_url"] == "https://www.a101.com.tr/afisler"
    assert all(c["status"] == "ok" and c["last_ok_at"] is None for c in webviews.values())
    assert not any(b["chain_id"] in webviews for b in catalog["brochures"])
    assert [c["id"] for c in catalog["chains"]] == ["bim", "a101", "sok", "migros", "macrocenter", "carrefoursa", "gratis"]


# --- isolation and failure tracking ----------------------------------------------------


def test_failing_source_keeps_previous_data_and_others_publish(tmp_path) -> None:
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a"))), FakeSource("sok", static(brochure("sok", "x")))])
    before = load(tmp_path)

    later = T0 + timedelta(hours=6)
    report = do_run(
        tmp_path,
        [FakeSource("bim", boom), FakeSource("sok", static(brochure("sok", "y")))],
        now=later,
    )
    assert report.exit_code == 0
    catalog = load(tmp_path)
    bim = chain(catalog, "bim")
    assert bim["status"] == "stale"
    assert bim["last_ok_at"] == "2026-11-13T09:00:00Z"
    assert [b for b in catalog["brochures"] if b["chain_id"] == "bim"] == [
        b for b in before["brochures"] if b["chain_id"] == "bim"
    ]
    # The healthy source was published normally (the old Şok brochure is archived).
    assert chain(catalog, "sok")["status"] == "ok"
    assert set(ids(catalog, "sok")) == {"sok-x", "sok-y"}

    h = health(tmp_path, "bim")
    assert (h["ok"], h["consecutive_failures"], h["brochure_count"]) == (False, 1, 0)
    assert h["last_error"] == "RuntimeError: layout changed"
    run_bim = next(s for s in report.sources if s.chain_id == "bim")
    assert not run_bim.ok and run_bim.error == "RuntimeError: layout changed"


def test_consecutive_failures_count_up_turn_red_and_reset(tmp_path) -> None:
    good = FakeSource("bim", static(brochure("bim", "a")))
    assert do_run(tmp_path, [good]).exit_code == 0
    codes = []
    for i in range(1, 4):
        report = do_run(tmp_path, [FakeSource("bim", boom)], now=T0 + timedelta(hours=i))
        codes.append(report.exit_code)
        assert health(tmp_path, "bim")["consecutive_failures"] == i
    # Third failure in a row: still published, but the job must turn red.
    assert codes == [0, 0, 2]
    assert report.written
    assert ids(load(tmp_path), "bim") == ["bim-a"]

    assert do_run(tmp_path, [good], now=T0 + timedelta(hours=5)).exit_code == 0
    h = health(tmp_path, "bim")
    assert (h["ok"], h["consecutive_failures"], h["last_error"]) == (True, 0, None)
    assert chain(load(tmp_path), "bim")["status"] == "ok"


def test_empty_result_is_a_failure(tmp_path) -> None:
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a")))])
    report = do_run(tmp_path, [FakeSource("bim", static())])
    assert not report.sources[0].ok
    assert "no brochures" in (report.sources[0].error or "")
    assert ids(load(tmp_path)) == ["bim-a"]
    assert chain(load(tmp_path), "bim")["status"] == "stale"


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (brochure("bim", "a", pages=()), "pages"),
        (brochure("sok", "a"), "belongs to chain"),
        (brochure("bim", "a", valid_from=TODAY, valid_to=TODAY - timedelta(days=1)), "valid_from"),
        (brochure("bim", "a", pages=(Page("media/bim/bim-a/p01.webp"),)), "was not written"),
        (brochure("bim", "a", kind=BrochureKind.BOTH, products_url="products/bim-a.json", product_count=1), "no product file"),
    ],
)
def test_invalid_source_output_fails_only_that_source(tmp_path, bad: Brochure, message: str) -> None:
    report = do_run(tmp_path, [FakeSource("bim", static(bad)), FakeSource("sok", static(brochure("sok", "x")))])
    by_chain = {s.chain_id: s for s in report.sources}
    assert not by_chain["bim"].ok and message in (by_chain["bim"].error or "")
    assert by_chain["sok"].ok
    assert report.written and ids(load(tmp_path)) == ["sok-x"]


def test_failed_source_media_is_not_published(tmp_path) -> None:
    do_run(tmp_path, [FakeSource("sok", media_source("x"))])

    def half_done(ctx: SourceContext) -> SourceResult:
        ctx.media.write_pages("sok", "sok-new", [RenderedPage(b"partial", 1, 1)])
        raise TimeoutError("PDF download timed out")

    report = do_run(tmp_path, [FakeSource("sok", half_done)], now=T0 + timedelta(hours=1))
    assert report.sources[0].error == "TimeoutError: PDF download timed out"
    assert not (tmp_path / "out/media/sok/sok-new").exists()
    assert (tmp_path / "out/media/sok/sok-x/p01.webp").read_bytes() == b"x-0"


def test_chain_not_in_this_run_is_republished_unchanged(tmp_path) -> None:
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a"))), FakeSource("sok", media_source("x"))])
    before = load(tmp_path)
    sok_health = health(tmp_path, "sok")
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a")))], now=T0 + timedelta(hours=1))
    after = load(tmp_path)
    assert chain(after, "sok") == chain(before, "sok")
    assert [b for b in after["brochures"] if b["chain_id"] == "sok"] == [
        b for b in before["brochures"] if b["chain_id"] == "sok"
    ]
    assert health(tmp_path, "sok") == sok_health
    assert (tmp_path / "out/media/sok/sok-x/p01.webp").is_file()


# --- merging ---------------------------------------------------------------------------


def test_first_seen_is_kept_and_updated_at_moves_only_on_change(tmp_path) -> None:
    b, products = with_products(brochure("bim", "a"), "Su")
    source = FakeSource("bim", static(b, products={b.id: products}))
    do_run(tmp_path, [source])
    do_run(tmp_path, [source], now=T0 + timedelta(hours=6))
    record = load(tmp_path)["brochures"][0]
    # First run of the chain: first_seen is the start day (see test_first_seen_on_a_chains_first_run).
    assert (record["first_seen"], record["updated_at"]) == ("2026-11-13T00:00:00Z", "2026-11-13T09:00:00Z")

    _, changed = with_products(b, "Su", "Ekmek")
    source.fn = static(replace(b, product_count=2), products={b.id: changed})
    do_run(tmp_path, [source], now=T0 + timedelta(hours=12))
    record = load(tmp_path)["brochures"][0]
    assert (record["first_seen"], record["updated_at"]) == ("2026-11-13T00:00:00Z", "2026-11-13T21:00:00Z")

    source.fn = static(replace(b, product_count=2, title="Yeni başlık"), products={b.id: changed})
    do_run(tmp_path, [source], now=T0 + timedelta(hours=18))
    assert load(tmp_path)["brochures"][0]["updated_at"] == "2026-11-14T03:00:00Z"


def test_brochure_gone_from_source_stays_as_archive(tmp_path) -> None:
    old, products = with_products(brochure("bim", "old", valid_from=TODAY - timedelta(days=7), valid_to=TODAY - timedelta(days=1)), "Su")
    do_run(tmp_path, [FakeSource("bim", static(old, brochure("bim", "new"), products={old.id: products}))])
    report = do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "new")))], now=T0 + timedelta(hours=1))
    assert report.sources[0].brochure_count == 1
    assert ids(load(tmp_path)) == ["bim-new", "bim-old"]
    assert len(load(tmp_path, "products/bim-old.json")["products"]) == 1


def test_retired_brochures_are_not_kept_as_archive(tmp_path) -> None:
    do_run(tmp_path, [FakeSource("sok", media_source("x", "y", "z"))])
    assert (tmp_path / "out/media/sok/sok-y/p01.webp").is_file()

    def retire(ctx: SourceContext) -> SourceResult:
        result = media_source("x", "z")(ctx)
        # "sok-z" is returned as well, so it stays; an unknown id is simply ignored.
        result.retired_ids = frozenset({"sok-y", "sok-z", "sok-unknown"})
        return result

    report = do_run(tmp_path, [FakeSource("sok", retire)], now=T0 + timedelta(hours=1))
    assert report.written
    assert ids(load(tmp_path)) == ["sok-x", "sok-z"]
    assert not (tmp_path / "out/media/sok/sok-y").exists()


def test_new_brochure_ids(tmp_path) -> None:
    source = FakeSource("bim", static(brochure("bim", "a")))
    # The chain's first run is not news (see test_first_seen_on_a_chains_first_run).
    assert do_run(tmp_path, [source]).new_brochure_ids == []
    source.fn = static(brochure("bim", "a"), brochure("bim", "b"))
    report = do_run(tmp_path, [source], now=T0 + timedelta(hours=1))
    assert report.new_brochure_ids == ["bim-b"]
    assert not report.first_run
    assert report.sources[0].new_count == 1
    assert do_run(tmp_path, [source], now=T0 + timedelta(hours=2)).new_brochure_ids == []


def by_id(catalog: dict) -> dict[str, dict]:
    return {b["id"]: b for b in catalog["brochures"]}


def test_first_seen_on_a_chains_first_run(tmp_path) -> None:
    # BİM already has brochures in the previous output; Migros is added in the second run.
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a")))])
    started = brochure("migros", "started", valid_from=TODAY - timedelta(days=3))
    upcoming = brochure("migros", "upcoming", valid_from=TODAY + timedelta(days=2), valid_to=TODAY + timedelta(days=9))
    undated = brochure("migros", "undated", valid_from=None, valid_to=None)
    migros = FakeSource("migros", static(started, upcoming, undated))
    t1 = T0 + timedelta(hours=1)
    report = do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a"), brochure("bim", "b"))), migros], now=t1)

    records = by_id(load(tmp_path))
    assert records["migros-started"]["first_seen"] == "2026-11-10T00:00:00Z"
    assert records["migros-upcoming"]["first_seen"] == "2026-11-13T10:00:00Z"
    assert records["migros-undated"]["first_seen"] == "2026-11-13T10:00:00Z"
    assert records["migros-started"]["updated_at"] == "2026-11-13T10:00:00Z"
    # The existing chain is unaffected: its new brochure is seen now and announced.
    assert records["bim-a"]["first_seen"] == "2026-11-13T00:00:00Z"
    assert records["bim-b"]["first_seen"] == "2026-11-13T10:00:00Z"
    assert report.new_brochure_ids == ["bim-b"]
    assert {s.chain_id: s.new_count for s in report.sources} == {"bim": 1, "migros": 0}

    # On the chain's next run a new brochure is news again, even one that started earlier.
    t2 = T0 + timedelta(hours=2)
    later = brochure("migros", "later", valid_from=TODAY - timedelta(days=1))
    migros.fn = static(started, upcoming, undated, later)
    report = do_run(tmp_path, [migros], now=t2)
    records = by_id(load(tmp_path))
    assert records["migros-later"]["first_seen"] == "2026-11-13T11:00:00Z"
    assert records["migros-started"]["first_seen"] == "2026-11-10T00:00:00Z"
    assert report.new_brochure_ids == ["migros-later"]


def test_first_run_brochures_never_get_a_future_first_seen() -> None:
    from scraper.core.pipeline import backfill_first_seen

    # 22:00 UTC on the 12th is already the 13th in Turkey.
    now = datetime(2026, 11, 12, 22, 0, tzinfo=UTC)
    assert backfill_first_seen(brochure("migros", "x", valid_from=TODAY), TODAY, now) == now
    assert backfill_first_seen(brochure("migros", "x", valid_from=TODAY - timedelta(days=1)), TODAY, now) == datetime(
        2026, 11, 12, 0, 0, tzinfo=UTC
    )


def test_failed_first_run_does_not_count_as_the_chains_first_run(tmp_path) -> None:
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a"))), FakeSource("migros", boom)])
    report = do_run(tmp_path, [FakeSource("migros", static(brochure("migros", "a")))], now=T0 + timedelta(hours=1))
    assert by_id(load(tmp_path))["migros-a"]["first_seen"] == "2026-11-13T00:00:00Z"
    assert report.new_brochure_ids == []


def test_brand_colours_are_published(tmp_path) -> None:
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a")))])
    chains = {c["id"]: c for c in load(tmp_path)["chains"]}
    assert chains["bim"]["brand_color"] == "#E30613"
    assert chains["a101"]["brand_color"] == "#00A0E3"
    assert "brand_color" not in chains["macrocenter"]


# --- pruning ---------------------------------------------------------------------------


def test_expired_brochures_are_pruned_with_their_files(tmp_path) -> None:
    def expired_at(days: int) -> Brochure:
        end = TODAY - timedelta(days=days)
        return brochure("bim", f"d{days}", valid_from=end - timedelta(days=6), valid_to=end)

    old, products = with_products(expired_at(20), "Su")
    do_run(tmp_path, [FakeSource("bim", static(old, products={old.id: products})), FakeSource("sok", media_source("x"))])
    assert (tmp_path / "out/products/bim-d20.json").is_file()

    # Nine days later the bim brochure ended 29 days ago; the Şok one (valid_to = TODAY + 6) ended 3 days ago.
    later = TODAY + timedelta(days=9)
    report = do_run(
        tmp_path,
        [FakeSource("bim", static(brochure("bim", "now", valid_from=later, valid_to=later)))],
        now=T0 + timedelta(days=9),
        today=later,
    )
    assert report.written
    assert ids(load(tmp_path)) == ["bim-now", "sok-x"]
    assert not (tmp_path / "out/products/bim-d20.json").exists()

    # Exactly ARCHIVE_DAYS after its end a brochure is still kept; one day more and it goes.
    edge = TODAY + timedelta(days=6 + ARCHIVE_DAYS)
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "now", valid_from=edge, valid_to=edge)))], now=T0 + timedelta(days=40), today=edge)
    assert "sok-x" in ids(load(tmp_path))
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "now", valid_from=edge, valid_to=edge)))], now=T0 + timedelta(days=41), today=edge + timedelta(days=1))
    assert "sok-x" not in ids(load(tmp_path))
    assert not (tmp_path / "out/media").exists()


def test_source_returning_an_old_brochure_does_not_publish_it(tmp_path) -> None:
    ancient = brochure("bim", "ancient", valid_from=TODAY - timedelta(days=60), valid_to=TODAY - timedelta(days=50))
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a")))])
    report = do_run(tmp_path, [FakeSource("bim", static(ancient, brochure("bim", "a"), brochure("bim", "b")))], now=T0 + timedelta(hours=1))
    assert ids(load(tmp_path)) == ["bim-a", "bim-b"]
    assert report.new_brochure_ids == ["bim-b"]


def test_undated_brochures_expire_once_unlisted_and_old(tmp_path) -> None:
    undated = brochure("bim", "campaign", valid_from=None, valid_to=None)
    source = FakeSource("bim", static(undated, brochure("bim", "a")))
    do_run(tmp_path, [source])
    # Still listed after 40 days: kept.
    day40 = TODAY + timedelta(days=40)
    current = brochure("bim", "b", valid_from=day40, valid_to=day40)
    source.fn = static(undated, current)
    do_run(tmp_path, [source], now=T0 + timedelta(days=40), today=day40)
    assert "bim-campaign" in ids(load(tmp_path))
    # Unlisted and first seen more than 35 days ago: removed.
    source.fn = static(current)
    do_run(tmp_path, [source], now=T0 + timedelta(days=41), today=day40)
    assert "bim-campaign" not in ids(load(tmp_path))


def test_recent_unlisted_undated_brochure_is_kept(tmp_path) -> None:
    undated = brochure("bim", "campaign", valid_from=None, valid_to=None)
    do_run(tmp_path, [FakeSource("bim", static(undated, brochure("bim", "a")))])
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a")))], now=T0 + timedelta(days=10))
    assert "bim-campaign" in ids(load(tmp_path))


# --- publishing ------------------------------------------------------------------------


def test_invalid_output_leaves_out_dir_untouched(tmp_path) -> None:
    do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a")))])
    before = snapshot(tmp_path / "out")
    broken_chains = [*CHAINS, ChainInfo("bad", "Bad", CHAINS[1].kind, "http://insecure.example.com", 99)]
    report = do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "b")))], chains=broken_chains, now=T0 + timedelta(hours=1))
    assert report.exit_code == 1 and not report.written
    assert "web_url" in (report.output_error or "")
    assert snapshot(tmp_path / "out") == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out"]


def test_corrupt_previous_state_is_ignored(tmp_path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "catalog.json").write_text('{"schema_version": 1, "chains": "nope"}', encoding="utf-8")
    (out / "health.json").write_text("not json", encoding="utf-8")
    report = do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a")))])
    assert report.exit_code == 0
    assert report.first_run
    assert any("previous catalog.json ignored" in w for w in report.warnings)
    assert any("previous health.json ignored" in w for w in report.warnings)
    assert ids(load(tmp_path)) == ["bim-a"]


def test_missing_previous_files_drop_only_that_brochure(tmp_path) -> None:
    do_run(tmp_path, [FakeSource("sok", media_source("x", "y"))])
    (tmp_path / "out/media/sok/sok-y/p02.webp").unlink()
    report = do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a")))], now=T0 + timedelta(hours=1))
    assert report.written
    assert ids(load(tmp_path)) == ["bim-a", "sok-x"]
    assert any("sok-y" in w for w in report.warnings)


def test_same_input_gives_byte_identical_output(tmp_path) -> None:
    def sources():
        b, products = with_products(brochure("bim", "a"), "Su", "Çay")
        return [FakeSource("bim", static(b, brochure("bim", "u", valid_from=None, valid_to=None), products={b.id: products})), FakeSource("sok", media_source("x"))]

    do_run(tmp_path / "one", sources())
    do_run(tmp_path / "two", sources())
    first = snapshot(tmp_path / "one/out")
    assert first == snapshot(tmp_path / "two/out")
    # Running again on its own output with the same clock changes nothing either.
    do_run(tmp_path / "one", sources())
    assert snapshot(tmp_path / "one/out") == first
    assert (tmp_path / "one/out/catalog.json").read_bytes().count(b"\r") == 0


def test_dry_run_writes_nothing(tmp_path) -> None:
    report = do_run(tmp_path, [FakeSource("bim", static(brochure("bim", "a")))], dry_run=True)
    assert report.output_ok and not report.written and report.exit_code == 0
    assert list(tmp_path.iterdir()) == []
