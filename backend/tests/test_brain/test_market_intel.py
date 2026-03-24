"""Tests for market intelligence — sentiment scoring and caching."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.brain.market_intel import (
    CACHE_KEY,
    CACHE_TTL,
    SentimentResult,
    fetch_headlines,
    get_market_sentiment,
    score_sentiment,
)


class TestScoreSentiment:
    def test_empty_headlines_returns_neutral(self):
        result = score_sentiment([])
        assert result.sentiment_label == "neutral"
        assert result.score == 0.0
        assert result.headlines == []

    def test_bullish_headlines(self):
        headlines = [
            "Gold prices rally on safe haven demand",
            "XAU surges past $2400 as inflation fears rise",
            "Dovish Fed signals rate cut, gold climbs",
        ]
        result = score_sentiment(headlines)
        assert result.sentiment_label == "bullish"
        assert result.score > 0.0
        assert len(result.headlines) == 3

    def test_bearish_headlines(self):
        headlines = [
            "Gold prices drop as dollar strengthens",
            "Hawkish Fed rate hike sends gold plunging",
            "Strong dollar correction hits gold market",
        ]
        result = score_sentiment(headlines)
        assert result.sentiment_label == "bearish"
        assert result.score < 0.0

    def test_neutral_headlines(self):
        headlines = [
            "Gold trading near yesterday's levels",
            "Markets await economic data release",
        ]
        result = score_sentiment(headlines)
        assert result.sentiment_label == "neutral"
        assert -0.15 <= result.score <= 0.15

    def test_score_bounded(self):
        headlines = ["rally " * 100]  # extreme bullish
        result = score_sentiment(headlines)
        assert -1.0 <= result.score <= 1.0

    def test_mixed_headlines(self):
        headlines = [
            "Gold rally meets strong dollar resistance",
            "Rate hike fears offset safe haven demand",
        ]
        result = score_sentiment(headlines)
        assert -1.0 <= result.score <= 1.0


class TestFetchHeadlines:
    @pytest.mark.asyncio
    async def test_returns_empty_on_failure(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("network error"))
        result = await fetch_headlines(mock_client)
        assert result == []

    @pytest.mark.asyncio
    async def test_parses_rss_titles(self):
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = (
            "<rss><channel>"
            "<title>Google News</title>"
            "<item><title>Gold surges to record</title></item>"
            "<item><title>XAU hits $2500</title></item>"
            "</channel></rss>"
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        result = await fetch_headlines(mock_client)
        assert len(result) == 2
        assert "Gold surges to record" in result[0]

    @pytest.mark.asyncio
    async def test_limits_to_5_headlines(self):
        items = "".join(f"<title>Headline {i}</title>" for i in range(10))
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = f"<rss><channel><title>Google News</title>{items}</channel></rss>"
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        result = await fetch_headlines(mock_client)
        assert len(result) <= 5


class TestGetMarketSentiment:
    @pytest.mark.asyncio
    async def test_returns_cached_result(self):
        cached_data = json.dumps({
            "sentiment_label": "bullish",
            "score": 0.5,
            "headlines": ["Cached headline"],
        })
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=cached_data)
        mock_http = AsyncMock()

        result = await get_market_sentiment(mock_redis, mock_http)
        assert result.sentiment_label == "bullish"
        assert result.score == 0.5
        # Should not have called http since cache hit
        mock_http.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetches_and_caches_on_miss(self):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = (
            "<rss><channel><title>Google News</title>"
            "<title>Gold rally on safe haven demand</title>"
            "</channel></rss>"
        )
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)

        result = await get_market_sentiment(mock_redis, mock_http)
        assert isinstance(result, SentimentResult)
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == CACHE_KEY
        assert call_args[1]["ex"] == CACHE_TTL
