"""money.com.tr catalogue pages, shared by the Migros (Migroskop, 5M) and Macrocenter sources.

Each page opens with a block for the current issue: a heading ("Güncel Migroskop Dijital"),
the validity printed as "5 - 18 Kasım 2026" (also in an ``mcdate`` attribute), the issue
("Sayı: 910" or "Sayı: Kasım 2026"), a cover image and a link to the viewer or the PDF.
Past issues follow as ``_df_button`` links; they are not used (our archive is our own
previous runs, and their PDFs are 24-56 MB each).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from posixpath import basename
from urllib.parse import quote, unquote, urlsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from scraper.core.source import SourceError
from scraper.core.text import fold_turkish

# Migros' image server writes the pixel size into the file name: "..._743x1024.jpg".
_SIZE_IN_NAME = re.compile(r"_(\d{2,5})x(\d{2,5})\.(?:jpe?g|png|webp)$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class CurrentIssue:
    heading: str
    date_text: str | None
    # "910" for Migroskop, "Kasım 2026" for MacroStyle; None when the page omits it.
    issue: str | None
    cover_url: str | None
    viewer_url: str | None
    pdf_url: str | None


def parse_current_issue(html: str) -> CurrentIssue:
    """The current-issue block at the top of a money.com.tr catalogue page."""
    tree = LexborHTMLParser(html)
    head = tree.css_first("#insertListContainer .head")
    if head is None:
        raise SourceError("money.com.tr page has no current issue block (page layout may have changed)")

    heading_node = head.css_first(".detail h4 span")
    heading = text_of(heading_node) if heading_node else ""
    dated = head.css_first("[mcdate]")
    date_text = clean(dated.attributes.get("mcdate")) if dated else ""
    if not date_text:
        # The heading repeats the dates after a <br>: "Güncel Migroskop Dijital 5 - 18 Kasım 2026".
        h4 = head.css_first(".detail h4")
        full = text_of(h4) if h4 else ""
        date_text = full[len(heading) :].strip() if full.startswith(heading) else ""

    issue_node = head.css_first(".detail h5 b")
    cover = head.css_first(".image img")
    viewer = head.css_first("a[mcdate][href]")
    pdf = head.css_first("._df_button[source]")
    if not heading:
        raise SourceError("money.com.tr current issue block has no heading (page layout may have changed)")
    return CurrentIssue(
        heading=heading,
        date_text=date_text or None,
        issue=(text_of(issue_node) if issue_node else "") or None,
        cover_url=https_url(first_attr(cover, "data-src", "src")) if cover else None,
        viewer_url=https_url(viewer.attributes.get("href")) if viewer else None,
        pdf_url=https_url(pdf.attributes.get("source")) if pdf else None,
    )


def heading_names(heading: str, name: str) -> bool:
    """True when ``heading`` ("Güncel 5M Migroskop Dijital") is about the publication ``name``."""
    words = fold_turkish(heading).split()
    core = [w for w in words if w not in ("guncel", "dijital")]
    return core == fold_turkish(name).split()


def size_from_name(url: str) -> tuple[int, int] | None:
    """Pixel size encoded in a Migros image file name, e.g. ``..._743x1024.jpg`` -> (743, 1024)."""
    m = _SIZE_IN_NAME.search(basename(urlsplit(url).path))
    return (int(m.group(1)), int(m.group(2))) if m else None


def https_url(value: str | None) -> str | None:
    """An absolute https URL safe for the catalog (spaces in folder names are percent-encoded)."""
    if not value:
        return None
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.netloc:
        return None
    path = quote(unquote(parts.path), safe="/%:@!$&'()*+,;=-._~")
    query = f"?{parts.query}" if parts.query else ""
    url = f"https://{parts.netloc}{path}{query}"
    return None if any(c.isspace() for c in url) else url


def first_attr(node: LexborNode, *names: str) -> str | None:
    for name in names:
        value = (node.attributes.get(name) or "").strip()
        if value:
            return value
    return None


def text_of(node: LexborNode) -> str:
    return clean(node.text(deep=True, separator=" "))


def clean(value: str | None) -> str:
    return " ".join((value or "").split())
