from __future__ import annotations

import io
from datetime import UTC, date, datetime

import pytest
from PIL import Image

from scraper.core.media import MediaWriter, local_paths, page_path
from scraper.core.models import Brochure, BrochureKind, Page
from scraper.core.pdf import PdfError, RenderedPage, render_pdf_pages
from scraper.core.prices import parse_price_minor
from scraper.tests.conftest import make_pdf

NOW = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("25,00", 2500),
        ("345," + "00", 34500),
        ("36.900," + "00", 3690000),
        ("429,00", 42900),
        ("7,5", 750),
        ("1.299,90 ₺", 129990),
        ("99 TL", 9900),
        ("12,", 1200),
        ("0,99", 99),
    ],
)
def test_parse_price_minor(text: str, expected: int) -> None:
    assert parse_price_minor(text) == expected


@pytest.mark.parametrize("text", [None, "", "abc", "% 19", "12,345", "1.29,00", "-5,00", "12.5"])
def test_parse_price_minor_rejects_non_prices(text: str | None) -> None:
    assert parse_price_minor(text) is None


# --- pdf -------------------------------------------------------------------------------


def test_render_two_pages_at_target_width() -> None:
    pages = render_pdf_pages(make_pdf(2), target_width=400)
    assert len(pages) == 2
    for page in pages:
        image = Image.open(io.BytesIO(page.webp))
        assert image.format == "WEBP"
        assert image.size == (page.w, page.h) == (400, round(842 * 400 / 595))


def test_render_is_deterministic() -> None:
    pdf = make_pdf(1)
    assert render_pdf_pages(pdf, target_width=300) == render_pdf_pages(pdf, target_width=300)


def test_spread_is_kept_whole_and_twice_as_wide() -> None:
    (page,) = render_pdf_pages(make_pdf(1, width=1190, height=842), target_width=300)
    assert (page.w, page.h) == (600, round(842 * 600 / 1190))


def test_size_limit() -> None:
    with pytest.raises(PdfError, match="MB"):
        render_pdf_pages(make_pdf(1), max_bytes=100)


def test_page_limit() -> None:
    with pytest.raises(PdfError, match="3 pages, limit is 2"):
        render_pdf_pages(make_pdf(3), target_width=100, max_pages=2)


def test_not_a_pdf() -> None:
    with pytest.raises(PdfError, match="not a PDF"):
        render_pdf_pages(b"<html>blocked</html>")


def test_broken_pdf() -> None:
    with pytest.raises(PdfError):
        render_pdf_pages(b"%PDF-1.7\n garbage without objects")


# --- media -----------------------------------------------------------------------------


def _brochure(pages: list[Page]) -> Brochure:
    return Brochure(
        id="sok-x",
        chain_id="sok",
        title="t",
        date_label=None,
        valid_from=date(2026, 11, 18),
        valid_to=date(2026, 11, 24),
        kind=BrochureKind.PAGES,
        cover=pages[0],
        pages=tuple(pages),
        products_url=None,
        product_count=0,
        source_url="https://example.com/x.pdf",
        first_seen=NOW,
        updated_at=NOW,
    )


def test_media_writer_paths_and_reuse(tmp_path) -> None:
    previous, current = tmp_path / "prev", tmp_path / "cur"
    writer = MediaWriter(previous, None)
    pages = writer.write_pages("sok", "sok-x", [RenderedPage(b"a", 10, 20), RenderedPage(b"b", 10, 20)])
    assert [p.url for p in pages] == [page_path("sok", "sok-x", 1), "media/sok/sok-x/p02.webp"]
    assert (previous / "media/sok/sok-x/p02.webp").read_bytes() == b"b"

    brochure = _brochure(pages)
    assert local_paths(brochure) == ["media/sok/sok-x/p01.webp", "media/sok/sok-x/p02.webp"]
    reuser = MediaWriter(current, previous)
    assert reuser.reuse(brochure)
    assert (current / "media/sok/sok-x/p01.webp").read_bytes() == b"a"

    (previous / "media/sok/sok-x/p02.webp").unlink()
    assert not MediaWriter(tmp_path / "other", previous).reuse(brochure)
    assert not MediaWriter(tmp_path / "other", None).reuse(brochure)


def test_rewriting_a_brochure_drops_old_trailing_pages(tmp_path) -> None:
    writer = MediaWriter(tmp_path, None)
    writer.write_pages("sok", "sok-x", [RenderedPage(b"a", 1, 1)] * 3)
    writer.write_pages("sok", "sok-x", [RenderedPage(b"a", 1, 1)])
    assert sorted(p.name for p in (tmp_path / "media/sok/sok-x").iterdir()) == ["p01.webp"]


def test_remote_images_are_not_local() -> None:
    assert local_paths(_brochure([Page("https://cdn.example.com/a.jpg")])) == []
