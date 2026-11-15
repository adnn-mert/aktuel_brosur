"""Minimal Gemini ``generateContent`` client for poster OCR.

Uses plain ``httpx`` so no SDK dependency is added for a measurement script. The API key
travels only in the ``x-goog-api-key`` header and is scrubbed from every error message.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import httpx

from scraper.core.http import user_agent

# Verified on 2026-11-15 at https://aistudio.google.com/docs/models (ai.google.dev redirects there):
# "Gemini 3.8 Flash", code `gemini-3.8-flash`, stable.
DEFAULT_MODEL = "gemini-3.8-flash"
API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
API_KEY_ENV = "GEMINI_API_KEY"
API_KEY_FILE = Path(__file__).resolve().parents[2] / "secrets" / "gemini_api_key.txt"

# Paid tier, https://aistudio.google.com/docs/pricing (2026-11-15), USD per 1M tokens, valid
# through 2026-12-31. Output includes thinking tokens. The free tier is "Free of charge".
PRICE_INPUT_PER_M = 0.75
PRICE_OUTPUT_PER_M = 3.75

# The docs publish no free-tier RPM for this model (they point to the AI Studio console),
# so the default spacing assumes the strictest free Flash limit seen historically: 5 RPM.
DEFAULT_MIN_INTERVAL = 12.0
# Measured 2026-11-15: one poster took ~160-170 s with the default thinking level, so a
# shorter timeout only buys a duplicate (and quota-counted) request.
DEFAULT_TIMEOUT = 420.0
MAX_RETRIES = 4
FALLBACK_BACKOFF = 30.0
MAX_WAIT = 300.0

PROMPT_VERSION = "v1"
PROMPT = """\
This image is one Turkish supermarket (BİM) promotional poster.
List every product on it that has its own price.
For each product return:
- name: the product name exactly as printed (keep Turkish letters; do not translate).
- brand: the brand printed with it, or null.
- quantity_text: size/amount/count as printed (e.g. "~190 ml", "6'lı", "1 kg"), or null.
- price: the selling price exactly as printed, including kuruş if printed (e.g. "219", "49,90", "1.299,00"). \
Kuruş are often printed small and raised next to the lira digits; include them after a comma. \
Ignore installment text such as "PEŞİN FİYATINA 6 TAKSİT".
- old_price: a crossed-out or "yerine" earlier price if printed, else null.
Do not invent products or prices that are not visible. If one price covers several variants, list it once.
"""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "brand": {"type": ["string", "null"]},
                    "quantity_text": {"type": ["string", "null"]},
                    "price": {"type": "string"},
                    "old_price": {"type": ["string", "null"]},
                },
                "required": ["name", "price"],
            },
        }
    },
    "required": ["products"],
}


class GeminiError(RuntimeError):
    """A request failed; the message never contains the API key."""


class MissingApiKey(GeminiError):
    pass


def load_api_key(env: dict[str, str] | None = None, key_file: Path = API_KEY_FILE) -> str:
    """Environment first (CI secret), then the git-ignored local file."""
    environ = os.environ if env is None else env
    value = (environ.get(API_KEY_ENV) or "").strip()
    if value:
        return value
    try:
        value = key_file.read_text(encoding="utf-8").strip()
    except OSError:
        value = ""
    if not value:
        raise MissingApiKey(f"no API key: set {API_KEY_ENV} or create {key_file.name} under secrets/")
    return value


def build_request(
    image: bytes,
    mime_type: str = "image/jpeg",
    *,
    media_resolution: str | None = None,
    thinking_level: str | None = None,
) -> dict[str, Any]:
    generation_config: dict[str, Any] = {
        "responseMimeType": "application/json",
        "responseJsonSchema": RESPONSE_SCHEMA,
    }
    if media_resolution:
        generation_config["mediaResolution"] = media_resolution
    if thinking_level:
        # The REST enum is upper case; accept "low" from the command line too.
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level.upper()}
    return {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inlineData": {"mimeType": mime_type, "data": base64.b64encode(image).decode("ascii")}},
                    {"text": PROMPT},
                ],
            }
        ],
        "generationConfig": generation_config,
    }


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        return (
            self.prompt_tokens * PRICE_INPUT_PER_M + (self.output_tokens + self.thought_tokens) * PRICE_OUTPUT_PER_M
        ) / 1_000_000


@dataclass(frozen=True)
class OcrResult:
    products: list[dict[str, Any]] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    finish_reason: str | None = None


def parse_response(body: dict[str, Any]) -> OcrResult:
    """Pull the JSON product list out of a ``generateContent`` response body."""
    candidates = body.get("candidates") or []
    if not candidates:
        reason = (body.get("promptFeedback") or {}).get("blockReason")
        raise GeminiError(f"no candidates in response (blockReason={reason})")
    first = candidates[0]
    parts = (first.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiError(f"response is not JSON (finishReason={first.get('finishReason')}): {exc}") from None
    products = data.get("products") if isinstance(data, dict) else None
    if not isinstance(products, list):
        raise GeminiError("response JSON has no 'products' list")
    meta = body.get("usageMetadata") or {}
    usage = Usage(
        prompt_tokens=int(meta.get("promptTokenCount") or 0),
        output_tokens=int(meta.get("candidatesTokenCount") or 0),
        thought_tokens=int(meta.get("thoughtsTokenCount") or 0),
    )
    return OcrResult(
        products=[p for p in products if isinstance(p, dict)],
        usage=usage,
        finish_reason=first.get("finishReason"),
    )


_DELAY = re.compile(r"^(\d+(?:\.\d+)?)s$")


def retry_delay(response: httpx.Response) -> float | None:
    """Server-suggested wait: ``RetryInfo.retryDelay`` in the error body, else ``Retry-After``."""
    try:
        details = response.json().get("error", {}).get("details", [])
    except (ValueError, AttributeError):
        details = []
    for detail in details if isinstance(details, list) else []:
        delay = detail.get("retryDelay") if isinstance(detail, dict) else None
        if isinstance(delay, str) and (m := _DELAY.match(delay)):
            return float(m.group(1))
    header = response.headers.get("retry-after")
    if header and header.replace(".", "", 1).isdigit():
        return float(header)
    return None


def _error_message(response: httpx.Response) -> str:
    try:
        message = response.json().get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        message = response.text
    # Long enough to keep the quota metric and limit that Google appends to 429 messages.
    return str(message)[:800]


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_MODEL,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        max_retries: int = MAX_RETRIES,
        timeout: float = DEFAULT_TIMEOUT,
        media_resolution: str | None = None,
        thinking_level: str | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        log: Callable[[str], None] = lambda _msg: None,
    ) -> None:
        self.model = model
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.media_resolution = media_resolution
        self.thinking_level = thinking_level
        self.requests_sent = 0
        # Seconds the last successful request took on the wire (pacing and retries excluded).
        self.last_elapsed: float | None = None
        self._key = api_key
        self._clock = clock
        self._sleep = sleep
        self._log = log
        self._last: float | None = None
        self._client = httpx.Client(
            transport=transport,
            timeout=timeout,
            headers={"User-Agent": user_agent(), "x-goog-api-key": api_key},
        )

    @property
    def url(self) -> str:
        return f"{API_ROOT}/models/{self.model}:generateContent"

    def _scrub(self, text: str) -> str:
        return text.replace(self._key, "[redacted]") if self._key else text

    def _wait_for_slot(self) -> None:
        if self._last is not None:
            remaining = self.min_interval - (self._clock() - self._last)
            if remaining > 0:
                self._sleep(remaining)
        self._last = self._clock()

    def read_poster(self, image: bytes, mime_type: str = "image/jpeg") -> tuple[OcrResult, dict[str, Any]]:
        """Return the parsed result and the raw response body (for the on-disk cache)."""
        payload = build_request(
            image, mime_type, media_resolution=self.media_resolution, thinking_level=self.thinking_level
        )
        attempt = 0
        while True:
            self._wait_for_slot()
            self.requests_sent += 1
            started = self._clock()
            try:
                response = self._client.post(self.url, json=payload)
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise GeminiError(self._scrub(f"network error: {type(exc).__name__}")) from None
                attempt += 1
                self._log(f"gemini: {type(exc).__name__}, retry {attempt} in {FALLBACK_BACKOFF * attempt:.0f}s")
                self._sleep(FALLBACK_BACKOFF * attempt)
                continue
            if response.status_code == 200:
                try:
                    body = response.json()
                except ValueError:
                    raise GeminiError("HTTP 200 with a non-JSON body") from None
                self.last_elapsed = self._clock() - started
                return parse_response(body), body
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable or attempt >= self.max_retries:
                raise GeminiError(self._scrub(f"HTTP {response.status_code}: {_error_message(response)}"))
            delay = retry_delay(response) or FALLBACK_BACKOFF * 2**attempt
            # A long suggested wait means the daily quota is gone; waiting it out is pointless here.
            if delay > MAX_WAIT:
                raise GeminiError(
                    self._scrub(f"HTTP {response.status_code}, retry in {delay:.0f}s: {_error_message(response)}")
                )
            attempt += 1
            self._log(f"gemini: HTTP {response.status_code}, retry {attempt} in {delay:.0f}s")
            self._sleep(delay)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
