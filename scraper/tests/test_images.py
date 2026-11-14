from __future__ import annotations

import io

import httpx
from PIL import Image

from scraper.core.http import HttpClient
from scraper.core.images import HEADER_BYTES, fetch_image_size, image_size

URL = "https://cdn1.bim.com.tr/uploads/afisler/k_test.jpg"


def jpeg(w: int = 258, h: int = 387) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(out, format="JPEG", quality=90)
    return out.getvalue()


def client(handler) -> HttpClient:
    return HttpClient(transport=httpx.MockTransport(handler), min_interval=0, sleep=lambda _s: None)


def test_image_size_reads_only_the_header() -> None:
    data = jpeg()
    assert image_size(data) == (258, 387)
    # The header up to the start of the pixel data (SOS marker) is enough.
    header_only = data[: data.index(b"\xff\xda") + 16]
    assert len(header_only) < len(data) // 2
    assert image_size(header_only) == (258, 387)
    assert image_size(b"<html>not an image</html>") is None
    assert image_size(b"") is None


def test_range_request_is_used_when_supported() -> None:
    data = jpeg(940, 1409)
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Range"))
        start, end = (int(x) for x in request.headers["Range"].removeprefix("bytes=").split("-"))
        return httpx.Response(206, content=data[start : end + 1])

    assert fetch_image_size(client(handler), URL) == (940, 1409)
    assert seen == [f"bytes=0-{HEADER_BYTES - 1}"]


def test_server_without_range_support_sends_the_whole_file() -> None:
    # cdn1.bim.com.tr ignores Range and answers 200 with the ~40 KB thumbnail.
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=jpeg())

    assert fetch_image_size(client(handler), URL) == (258, 387)
    assert calls == [URL]


def test_header_beyond_the_first_bytes_falls_back_to_a_full_download() -> None:
    data = jpeg()
    headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        headers.append(request.headers.get("Range"))
        if "Range" in request.headers:
            return httpx.Response(206, content=b"\xff\xd8\xff")  # a header cut too short to read
        return httpx.Response(200, content=data)

    assert fetch_image_size(client(handler), URL) == (258, 387)
    assert headers == [f"bytes=0-{HEADER_BYTES - 1}", None]


def test_errors_give_none() -> None:
    assert fetch_image_size(client(lambda _r: httpx.Response(404, text="not found")), URL) is None
    assert fetch_image_size(client(lambda _r: httpx.Response(200, text="<html></html>")), URL) is None

    def broken(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    no_retry = HttpClient(transport=httpx.MockTransport(broken), min_interval=0, max_retries=0, sleep=lambda _s: None)
    assert fetch_image_size(no_retry, URL) is None
