"""Shared async HTTP client for mcp-brasil.

Provides a configured httpx.AsyncClient factory and a fetch helper
with retry + exponential backoff for transient errors (5xx, 429, timeouts).

Usage:
    from mcp_realmak.compras._shared.http_client import create_client, http_get

    # Option 1: client factory (for multiple requests in a feature client)
    async with create_client(base_url="https://api.example.com") as client:
        response = await client.get("/endpoint")

    # Option 2: one-shot fetch with automatic retry
    data = await http_get("https://api.example.com/endpoint")
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from mcp_realmak.compras.exceptions import HttpClientError
from mcp_realmak.compras.settings import HTTP_BACKOFF_BASE, HTTP_MAX_RETRIES, HTTP_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

# Status codes that trigger a retry
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def _parse_json(response: httpx.Response) -> Any:
    """Parse JSON tolerating raw control characters inside strings.

    Some government APIs (e.g. PNCP search) return unescaped line breaks
    inside string values, which the strict parser rejects.
    """
    try:
        return response.json()
    except json.JSONDecodeError:
        return json.loads(response.text, strict=False)


def create_client(
    base_url: str = "",
    timeout: float | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    """Create a configured httpx.AsyncClient.

    Args:
        base_url: Base URL for all requests.
        timeout: Request timeout in seconds. Default: settings.HTTP_TIMEOUT.
        headers: Extra headers to merge with defaults.

    Returns:
        Configured httpx.AsyncClient (use as async context manager).
    """
    default_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if headers:
        default_headers.update(headers)

    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout or HTTP_TIMEOUT),
        headers=default_headers,
        follow_redirects=True,
    )


async def http_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    backoff_base: float | None = None,
    max_wait: float | None = None,
) -> Any:
    """Make a GET request with retry + exponential backoff.

    Retries on: HTTP 429/5xx, timeouts, and transport errors (refused or reset
    connections). Does NOT retry on 4xx (except 429) — those are client errors.

    Args:
        url: Full URL to request.
        params: Query parameters.
        headers: Extra headers (merged with defaults).
        timeout: Request timeout in seconds.
        max_retries: Max retry attempts. Default: settings.HTTP_MAX_RETRIES.
        backoff_base: First wait in seconds, doubled each retry.
            Default: settings.HTTP_BACKOFF_BASE.
        max_wait: Cap for a single wait in seconds. Default: no cap. Useful for
            APIs that fail fast and at random, where many short retries beat
            few long ones.

    Returns:
        Parsed JSON response.

    Raises:
        HttpClientError: On non-retryable errors or exhausted retries.
    """
    retries = max_retries if max_retries is not None else HTTP_MAX_RETRIES
    base = backoff_base if backoff_base is not None else HTTP_BACKOFF_BASE
    last_error: Exception | None = None

    def _wait(attempt: int) -> float:
        wait = base * (2**attempt)
        return min(wait, max_wait) if max_wait is not None else wait

    async with create_client(timeout=timeout, headers=headers) as client:
        for attempt in range(retries + 1):
            try:
                response = await client.get(url, params=params)

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    if attempt < retries:
                        wait = _wait(attempt)
                        logger.warning(
                            "Retry %d/%d for %s (HTTP %d), waiting %.1fs",
                            attempt + 1,
                            retries,
                            url,
                            response.status_code,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    # Last attempt still failed with retryable status
                    raise HttpClientError(
                        f"Request to {url} failed after {retries + 1} attempts "
                        f"(last: HTTP {response.status_code})"
                    )

                response.raise_for_status()
                return _parse_json(response)

            except httpx.HTTPStatusError as exc:
                raise HttpClientError(
                    f"HTTP {exc.response.status_code} from {url}: {exc.response.text[:200]}"
                ) from exc

            except httpx.TransportError as exc:
                last_error = exc
                if attempt < retries:
                    wait = _wait(attempt)
                    logger.warning(
                        "Request to %s failed (attempt %d/%d): %s, waiting %.1fs",
                        url,
                        attempt + 1,
                        retries,
                        type(exc).__name__,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

    raise HttpClientError(f"Request to {url} failed after {retries + 1} attempts") from last_error


async def http_post(
    url: str,
    *,
    json_body: Any | None = None,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
) -> Any:
    """Make a POST request with retry + exponential backoff.

    Retries on: HTTP 429/5xx, timeouts, and connection errors.

    Args:
        url: Full URL to request.
        json_body: JSON body to send.
        params: Query parameters.
        headers: Extra headers (merged with defaults).
        timeout: Request timeout in seconds.
        max_retries: Max retry attempts. Default: settings.HTTP_MAX_RETRIES.

    Returns:
        Parsed JSON response.

    Raises:
        HttpClientError: On non-retryable errors or exhausted retries.
    """
    retries = max_retries if max_retries is not None else HTTP_MAX_RETRIES
    last_error: Exception | None = None

    async with create_client(timeout=timeout, headers=headers) as client:
        for attempt in range(retries + 1):
            try:
                response = await client.post(url, json=json_body, params=params)

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    if attempt < retries:
                        wait = HTTP_BACKOFF_BASE * (2**attempt)
                        logger.warning(
                            "Retry %d/%d for %s (HTTP %d), waiting %.1fs",
                            attempt + 1,
                            retries,
                            url,
                            response.status_code,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise HttpClientError(
                        f"Request to {url} failed after {retries + 1} attempts "
                        f"(last: HTTP {response.status_code})"
                    )

                response.raise_for_status()
                return _parse_json(response)

            except httpx.HTTPStatusError as exc:
                raise HttpClientError(
                    f"HTTP {exc.response.status_code} from {url}: {exc.response.text[:200]}"
                ) from exc

            except httpx.TransportError as exc:
                last_error = exc
                if attempt < retries:
                    wait = HTTP_BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        "Request to %s failed (attempt %d/%d): %s, waiting %.1fs",
                        url,
                        attempt + 1,
                        retries,
                        type(exc).__name__,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

    raise HttpClientError(f"Request to {url} failed after {retries + 1} attempts") from last_error
