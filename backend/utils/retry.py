"""Retry decorator with exponential backoff for external API calls."""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRIABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.ConnectTimeout,
    httpx.RemoteProtocolError,
    ConnectionError,
    TimeoutError,
)


def retry_async(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = RETRIABLE_EXCEPTIONS,
) -> Callable:
    """Decorator: retry an async function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds (doubles each retry).
        max_delay: Maximum delay cap in seconds.
        exceptions: Tuple of exception types to retry on.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_retries:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func.__qualname__,
                            max_retries + 1,
                            exc,
                        )
                        raise
                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.warning(
                        "%s attempt %d/%d failed (%s), retrying in %.1fs",
                        func.__qualname__,
                        attempt + 1,
                        max_retries + 1,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
            raise last_exc  # Should never reach here

        return wrapper

    return decorator
