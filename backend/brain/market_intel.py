"""Market intelligence — headline fetching and sentiment scoring."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

CACHE_KEY = "market_intel:sentiment"
CACHE_TTL = 25 * 60  # 25 minutes — matches Claude cache TTL

BULLISH_WORDS = [
    "rally", "surge", "soar", "jump", "gain", "rise", "climb", "bullish",
    "upside", "breakout", "highs", "demand", "safe haven", "inflation",
    "dovish", "rate cut", "stimulus", "buy", "accumulate", "golden cross",
]

BEARISH_WORDS = [
    "drop", "fall", "decline", "plunge", "sell", "crash", "bearish",
    "downside", "breakdown", "lows", "hawkish", "rate hike", "taper",
    "strong dollar", "risk-on", "dump", "death cross", "correction",
]


@dataclass(frozen=True)
class SentimentResult:
    sentiment_label: str  # "bullish", "bearish", "neutral"
    score: float  # -1.0 to +1.0
    headlines: list[str]


async def fetch_headlines(http_client: httpx.AsyncClient) -> list[str]:
    """Fetch top gold news headlines.

    Uses a simple Google News RSS-style query. In production, CrawlForge MCP
    tools (mcp__crawlforge__search_web) would be used for richer results.
    Falls back to empty list on failure.
    """
    try:
        resp = await http_client.get(
            "https://news.google.com/rss/search",
            params={"q": "gold XAU price news today", "hl": "en-US", "gl": "US"},
            timeout=10.0,
        )
        resp.raise_for_status()
        # Parse RSS XML for titles (lightweight — no lxml dependency)
        text = resp.text
        titles: list[str] = []
        for chunk in text.split("<title>")[1:]:
            title = chunk.split("</title>")[0].strip()
            if title and title != "Google News":
                titles.append(title)
            if len(titles) >= 5:
                break
        return titles
    except Exception:
        logger.warning("Failed to fetch headlines, returning empty list")
        return []


def score_sentiment(headlines: list[str]) -> SentimentResult:
    """Score sentiment from headlines using keyword matching.

    Returns a normalized score from -1.0 (bearish) to +1.0 (bullish).
    """
    if not headlines:
        return SentimentResult(sentiment_label="neutral", score=0.0, headlines=[])

    bullish_count = 0
    bearish_count = 0
    combined_text = " ".join(h.lower() for h in headlines)

    for word in BULLISH_WORDS:
        bullish_count += combined_text.count(word.lower())
    for word in BEARISH_WORDS:
        bearish_count += combined_text.count(word.lower())

    total = bullish_count + bearish_count
    if total == 0:
        return SentimentResult(sentiment_label="neutral", score=0.0, headlines=headlines)

    raw_score = (bullish_count - bearish_count) / total  # -1.0 to +1.0

    if raw_score > 0.15:
        label = "bullish"
    elif raw_score < -0.15:
        label = "bearish"
    else:
        label = "neutral"

    return SentimentResult(
        sentiment_label=label,
        score=round(raw_score, 3),
        headlines=headlines,
    )


async def get_market_sentiment(
    redis: aioredis.Redis,
    http_client: httpx.AsyncClient,
) -> SentimentResult:
    """Get market sentiment, using Redis cache with 25-min TTL."""
    cached = await redis.get(CACHE_KEY)
    if cached:
        try:
            data = json.loads(cached)
            return SentimentResult(**data)
        except (json.JSONDecodeError, TypeError):
            pass

    headlines = await fetch_headlines(http_client)
    result = score_sentiment(headlines)

    await redis.set(
        CACHE_KEY,
        json.dumps({
            "sentiment_label": result.sentiment_label,
            "score": result.score,
            "headlines": result.headlines,
        }),
        ex=CACHE_TTL,
    )

    return result
