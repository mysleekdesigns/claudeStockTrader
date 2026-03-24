# YouTube Research: AI-Built Trading Strategies

## Video Details

| Field | Value |
|-------|-------|
| **Title** | I Gave Claude AI Full Access to TradingView… The Scalping Strategy It Built Was Insane |
| **Creator** | DaviddTech (Trading with DaviddTech) |
| **URL** | https://www.youtube.com/watch?v=zJf5B5haBjc |
| **Published** | 2026-03-16 |
| **Duration** | 13:32 |
| **Views** | ~32,700 |
| **Likes** | ~900 |
| **Genre** | Education / Algorithmic Trading |

---

## Video Summary

DaviddTech connected Claude AI directly to his TradingView environment using an **MCP server** (via **Cursor IDE**) and asked the AI to autonomously:

1. **Choose the indicators** — Claude selected the indicators itself, removing human bias
2. **Build the Pine Script strategy** — fully automated strategy code generation
3. **Backtest and optimize it** — run backtests and iterate on parameters
4. **Find the best settings** — optimize for the highest performance

The results were then verified directly on TradingView.

---

## Video Chapters & Key Content

| Timestamp | Chapter | Key Takeaways |
|-----------|---------|---------------|
| 0:00 | Giving Claude AI Access to TradingView | Claude Code connected to TradingView via MCP server |
| 0:42 | Setting Up the AI Agent (Cursor + MCP Server) | Used Cursor IDE with an MCP server to bridge Claude AI and TradingView's indicator/backtesting environment |
| 1:39 | Indicators Selected by AI | Claude autonomously chose **Bollinger Bands** and **ATR (Average True Range)** as core indicators |
| 3:11 | Building the Strategy Automatically | AI wrote full Pine Script strategy code combining the selected indicators |
| 6:38 | Backtesting Results | Initial backtest results evaluated across profit, drawdown, win rate, and profit factor |
| 9:16 | Why Lower Timeframes Failed | Strategy failed on lower timeframes (e.g. 5m, 15m) — noise overwhelmed signals |
| 10:39 | Strategy Optimization | AI optimized parameters to improve performance |
| 11:45 | Final TradingView Results (4,242%) | Optimized strategy on **30-minute Ethereum (ETH)** charts achieved **4,242% returns** in backtesting |
| 12:44 | Why AI Strategy Building Changes Everything | AI removes human bias in indicator selection and parameter tuning |

---

## Strategy Architecture (as described)

### Indicators Selected by Claude AI

- **Bollinger Bands** — used for mean-reversion / breakout detection (price relative to upper/lower bands)
- **ATR (Average True Range)** — used for dynamic stop-loss placement based on volatility

### Strategy Characteristics

- **Asset**: Ethereum (ETH/USD)
- **Optimal Timeframe**: 30-minute charts
- **Style**: Scalping / short-term trend following
- **Failed on**: Lower timeframes (5m, 15m) — too much noise
- **Backtested Return**: 4,242% (on TradingView)
- **Key Metrics Evaluated**: Profit, max drawdown, win rate, profit factor

### Technical Setup

- **AI Tool**: Claude Code (via Cursor IDE)
- **Bridge**: MCP (Model Context Protocol) server connecting Claude to TradingView
- **Language**: Pine Script (TradingView's native scripting language)
- **Workflow**: AI selects indicators → writes strategy → backtests → optimizes → repeats

---

## Relevance to claudeStockTrader Project

### Direct Parallels

| Video Concept | Our Implementation | Opportunity |
|--------------|-------------------|-------------|
| Bollinger Bands indicator | Not currently in our 4 strategies | **Add as 5th strategy** — Bollinger Band mean-reversion/breakout for XAU/USD |
| ATR-based stop loss | Risk manager uses fixed % stops | **Enhance risk_manager.py** with ATR-based dynamic stop-loss sizing |
| 30m optimal timeframe | We use M15, H1, H4, D1 | **Consider adding 30m timeframe** or note that mid-range timeframes filter noise better |
| AI selects indicators autonomously | Brain makes decisions on pre-built signals | **Explore letting Claude brain evaluate/weight indicator combinations** |
| Strategy optimization loop | Monte Carlo + walk-forward optimization | Already aligned — our optimization pipeline mirrors this approach |
| MCP server for tool access | CrawlForge MCP for web scraping | **Consider TradingView MCP** for direct chart/indicator access |

### Key Takeaways for Our Project

1. **Bollinger Bands + ATR is a proven AI-selected combination** — Claude independently chose these indicators when given free rein. Adding a Bollinger Bands strategy to our `strategies/` module would complement our existing EMA momentum and breakout strategies.

2. **ATR-based dynamic stops outperform fixed percentage stops** — Our `risk_manager.py` currently uses fixed 1% per-trade risk. Implementing ATR-based stop-loss placement would adapt to XAU/USD's volatility regime (gold can have very different ATR across sessions).

3. **Lower timeframes add noise, not signal** — The video confirms that scalping strategies fail on very low timeframes. Our M15 is the lowest — worth validating that our strategies perform better on H1+ and potentially down-weighting M15 signals in the decision pipeline.

4. **Automated backtesting + optimization loop** — The video's workflow (build → backtest → optimize → repeat) is exactly what our Monte Carlo (`optimisation/monte_carlo.py`) and walk-forward (`optimisation/walk_forward.py`) modules do. This validates our architecture.

5. **AI removes human bias in strategy design** — The video's core thesis is that letting AI choose indicators removes confirmation bias. Our brain/decision pipeline could be enhanced to periodically re-evaluate which strategy signals to weight more heavily, rather than using fixed weights.

6. **MCP as the bridge layer** — Using MCP servers to give AI access to trading tools is a pattern we could adopt. A TradingView MCP server could let our Claude brain directly analyze charts and indicators rather than relying solely on computed signals.

---

## Suggested Action Items

- [ ] Implement a **Bollinger Bands strategy** in `backend/strategies/` following the `TradingStrategy` protocol
- [ ] Add **ATR-based dynamic stop-loss** option to `backend/brain/risk_manager.py`
- [ ] Evaluate adding **30-minute timeframe** support to candle ingestion
- [ ] Benchmark existing strategies on M15 vs H1 to validate the lower-timeframe-noise finding
- [ ] Research TradingView MCP servers for potential integration

---

## Source Metadata

**Video Tags**: Algorithmic Trading, Hedge Fund Trading Strategy, TradingView Indicator, Automated Trading Bots, Algo Trading Strategies, Bollinger Bands Trading, ATR Stop Loss Strategy, Profitable Trading Indicators, Trading Automation Tools, Trend Following Strategies, High Win Rate Trading, Trading Indicator Setup, Trading Strategy Backtesting, Forex Trading Indicators, Day Trading Bots, Automated Trading Systems, Stock Trading Automation

**Creator Website**: https://daviddtech.com (AI Crypto Trading Bot platform with automated strategy bots)

**Note**: This analysis is based on the video's metadata, full description, chapter timestamps, and keyword tags extracted via CrawlForge MCP. The video transcript was not directly accessible due to YouTube's IP-restricted caption API. The specific Pine Script code and exact backtest parameters shown in the video are not captured here — watching the video directly is recommended for those details.
