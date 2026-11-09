"""Shared polite HTTP client: identifying User-Agent, rate limit, retries with backoff."""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

# Wikimedia rejects httpx requests unless the UA has an https:// contact URL and a library token.
USER_AGENT = (
    "mp-polling-postmortem/0.1 (https://github.com/johnpospisil/midterm-polling-2026) "
    f"httpx/{httpx.__version__}"
)


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 500, 502, 503, 504)


class PoliteClient:
    """httpx client that waits `min_interval` seconds between requests and retries transient errors."""

    def __init__(self, min_interval: float = 1.0, timeout: float = 60.0):
        self.min_interval = min_interval
        self._last = 0.0
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True
        )

    @retry(
        retry=retry_if_exception(_retryable),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def get(self, url: str, **kwargs) -> httpx.Response:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        r = self._client.get(url, **kwargs)
        r.raise_for_status()
        return r


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()
