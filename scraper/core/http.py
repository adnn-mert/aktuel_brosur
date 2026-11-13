"""Polite HTTP client: honest User-Agent, per-host rate limit, narrow retries.

The scraper identifies itself and never pretends to be a browser. A 403 or 429 means
the site does not want us; it is reported, not retried.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from types import TracebackType
from typing import Self
from urllib.parse import urlsplit

import httpx

BOT_NAME = "AktuelBrosurBot"
BOT_VERSION = "0.1"
CONTACT_ENV = "SCRAPER_CONTACT_URL"
# Neutral placeholder; deployments set SCRAPER_CONTACT_URL to the public repository URL.
DEFAULT_CONTACT_URL = "https://example.com/aktuel-brosur-bot"

DEFAULT_TIMEOUT = 30.0
MIN_INTERVAL = 1.0
MAX_RETRIES = 2
RETRY_BACKOFF = 2.0


def user_agent(contact_url: str | None = None) -> str:
    contact = contact_url or os.environ.get(CONTACT_ENV) or DEFAULT_CONTACT_URL
    return f"{BOT_NAME}/{BOT_VERSION} (+{contact})"


def _should_retry_status(status_code: int) -> bool:
    return 500 <= status_code <= 599


class HttpClient:
    """Thin wrapper around ``httpx.Client``.

    ``clock`` and ``sleep`` are injectable so tests can check the rate limit and
    retry timing without waiting for real time to pass.
    """

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        min_interval: float = MIN_INTERVAL,
        max_retries: int = MAX_RETRIES,
        retry_backoff: float = RETRY_BACKOFF,
        contact_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.timeout = timeout
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._clock = clock
        self._sleep = sleep
        self._last_request: dict[str, float] = {}
        self._client = httpx.Client(
            transport=transport,
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": user_agent(contact_url),
                "Accept-Language": "tr-TR,tr;q=0.9",
            },
        )

    @property
    def headers(self) -> httpx.Headers:
        return self._client.headers

    def get(
        self,
        url: str,
        *,
        timeout: float | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """GET ``url``; retries network errors and 5xx only.

        Returns the last response even when it is an error status, so callers can
        report it. Re-raises the last ``httpx.TransportError`` if every attempt failed
        at the network level.
        """
        host = urlsplit(url).hostname or ""
        attempt = 0
        while True:
            self._wait_for_slot(host)
            try:
                response = self._client.get(
                    url,
                    headers=headers,
                    timeout=timeout if timeout is not None else self.timeout,
                )
            except httpx.TransportError:
                if attempt >= self.max_retries:
                    raise
            else:
                if not _should_retry_status(response.status_code) or attempt >= self.max_retries:
                    return response
                response.close()
            attempt += 1
            self._sleep(self.retry_backoff * attempt)

    def _wait_for_slot(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            remaining = self.min_interval - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request[host] = self._clock()

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
