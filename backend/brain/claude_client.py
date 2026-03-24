"""Claude AI client with rate limiting, prompt caching, and concurrency control."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time

import anthropic
import redis.asyncio as aioredis

from backend.config import settings

logger = logging.getLogger(__name__)

RATE_LIMIT_KEY = "rate:claude:window"
RATE_LIMIT_MAX = 60
RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
CACHE_PREFIX = "claude:cache:"
CACHE_TTL = 25 * 60  # 25 minutes in seconds

DECIDE_MODEL = "claude-sonnet-4-6"
ANALYZE_MODEL = "claude-haiku-4-5"


class RateLimitExceeded(Exception):
    pass


class ClaudeClient:
    """Async Claude client with semaphore, Redis prompt cache, and sliding window rate limiter."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._redis = redis
        self._semaphore = asyncio.Semaphore(3)

    async def _check_rate_limit(self) -> None:
        """Enforce sliding window rate limit: 60 calls per hour via Redis."""
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(RATE_LIMIT_KEY, 0, window_start)
        pipe.zcard(RATE_LIMIT_KEY)
        pipe.zadd(RATE_LIMIT_KEY, {str(now): now})
        pipe.expire(RATE_LIMIT_KEY, RATE_LIMIT_WINDOW)
        results = await pipe.execute()

        current_count = results[1]
        if current_count >= RATE_LIMIT_MAX:
            # Remove the entry we just added
            await self._redis.zrem(RATE_LIMIT_KEY, str(now))
            raise RateLimitExceeded(
                f"Claude API rate limit exceeded: {current_count}/{RATE_LIMIT_MAX} calls in the last hour"
            )

    def _cache_key(self, prompt: str) -> str:
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        return f"{CACHE_PREFIX}{prompt_hash}"

    async def _get_cached(self, prompt: str) -> str | None:
        cached = await self._redis.get(self._cache_key(prompt))
        if cached:
            logger.debug("Claude prompt cache hit")
        return cached

    async def _set_cached(self, prompt: str, response: str) -> None:
        await self._redis.set(self._cache_key(prompt), response, ex=CACHE_TTL)

    async def _call(
        self,
        model: str,
        system: str,
        user_prompt: str,
        max_tokens: int = 2048,
        thinking: dict | None = None,
    ) -> tuple[str, str | None]:
        """Core method: rate-limit, cache check, semaphore-guarded API call.

        Returns:
            (response_text, thinking_text) — thinking_text is None when thinking is disabled.
        """
        full_prompt = f"{system}\n---\n{user_prompt}"

        cached = await self._get_cached(full_prompt)
        if cached:
            return cached, None

        await self._check_rate_limit()

        async with self._semaphore:
            logger.info("Calling Claude %s (prompt length: %d chars)", model, len(full_prompt))
            kwargs: dict = {
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            if thinking:
                kwargs["thinking"] = thinking
            response = await self._client.messages.create(**kwargs)

            # Extract thinking and text blocks
            thinking_text = None
            text = ""
            for block in response.content:
                if block.type == "thinking":
                    thinking_text = block.thinking
                elif block.type == "text":
                    text = block.text

        await self._set_cached(full_prompt, text)
        return text, thinking_text

    async def decide(self, system: str, user_prompt: str) -> str:
        """Use claude-sonnet-4-6 for brain trading decisions with extended thinking."""
        text, thinking = await self._call(
            DECIDE_MODEL, system, user_prompt, max_tokens=16000,
            thinking={"type": "enabled", "budget_tokens": 8000},
        )
        self._last_thinking = thinking
        return text

    async def get_last_thinking(self) -> str | None:
        """Return the thinking text from the most recent decide() call."""
        return getattr(self, "_last_thinking", None)

    async def analyze(self, system: str, user_prompt: str) -> str:
        """Use claude-haiku-4-5 for Monte Carlo reasoning and analysis."""
        text, _ = await self._call(ANALYZE_MODEL, system, user_prompt, max_tokens=2048)
        return text
