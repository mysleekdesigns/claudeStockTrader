# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

claudeStockTrader — an AI-assisted gold (XAU/USD) trading system. Generates trade signals via 4 strategies, uses Claude AI for decision-making, self-optimises via Monte Carlo simulation, and presents everything through a real-time dashboard. The full spec is in `PRD.md`.

## Architecture

```
Phase 1 (infra/DB) ──┬──> Phase 2 (data feed)
                     ├──> Phase 3 (strategies) ──> Phase 4 (brain/AI) ──> Phase 5 (optimisation)
                     └──> Phase 6 (API/WS) ──────────────────────────────> Phase 7 (frontend)
                                                                           └──> Phase 8 (polish)
```

### Backend (`backend/`)

FastAPI app with async-everywhere architecture. Single uvicorn worker; APScheduler runs in-process.

- **Entrypoint**: `main.py` — lifespan context manager initialises engine, Redis, httpx client, data feeds, scheduler, and Claude client
- **Config**: `config.py` — pydantic-settings `BaseSettings` loading from `.env`
- **DB**: `database/connection.py` — async engine + session factory (asyncpg, pool_size=20, `expire_on_commit=False`)
- **Models**: `database/models.py` — 7 tables: candles, signals, strategy_performance, backtest_runs, optimised_params, risk_state, decision_log
- **Repositories**: `database/repositories/` — async CRUD per entity (candles, signals, performance, risk, decisions, backtests)
- **Strategies**: `strategies/` — 4 strategies implementing `TradingStrategy` protocol (`strategies/base.py`): `liquidity_sweep`, `trend_continuation`, `breakout_expansion`, `ema_momentum`. `runner.py` executes all strategies and persists signals.
- **Brain**: `brain/` — `claude_client.py` (rate-limited Anthropic calls via Redis), `risk_manager.py` (circuit breaker + position sizing), `decision_pipeline.py` (30-min AI decision loop)
- **Optimisation**: `optimisation/` — `monte_carlo.py`, `walk_forward.py`, `reoptimiser.py`
- **Scheduler**: `scheduler/jobs.py` — APScheduler jobs: signals (15m), decisions (30m), resolve (5m), Monte Carlo (4h), reoptimise (6h), circuit breaker reset (1h)
- **Routers**: `routers/` — REST endpoints for health, candles, signals, performance, risk, decisions + WebSocket at `/ws/live`
- **Data feeds**: `data/feed.py` — `FailoverFeed` wrapping `TwelveDataFeed` (primary) and `OandaFeed` (fallback); `data/candle_ingestion.py` handles persistence

### Frontend (`frontend/`)

Next.js 16.2 App Router + React 19 + TradingView Lightweight Charts.

- **Pages**: `app/page.tsx` (dashboard with charts + signal feed), `app/brain/page.tsx` (strategy/risk/decision views), `app/health/page.tsx`
- **Components**: `components/charts/` (TradingView chart wrappers), `components/signals/` (signal feed), `components/brain/` (strategy table, risk panel, decision log, backtest table, params viewer)
- **WebSocket**: `lib/websocket.ts` — `useWebSocket` hook with auto-reconnect to `ws://localhost:8000/ws/live`
- **Styling**: Tailwind CSS v4.2.2 with CSS-first `@theme` in `globals.css` — do NOT create `tailwind.config.js`

### Message Bus

Redis pub/sub channels (`candles:XAU/USD`, `signals:XAU/USD`, `risk:alerts`) decouple scheduler jobs from WebSocket consumers.

## Tech Stack Constraints

These are hard rules — do not deviate:

- **All DB ops async**: asyncpg + SQLAlchemy 2.0 async session, `expire_on_commit=False`
- **All HTTP calls async**: httpx with retry logic and timeouts
- **Anthropic SDK**: rate-limited (60/hr via Redis sliding window) and prompt-cached (25-min TTL). claude-sonnet-4-6 for trading decisions, claude-haiku-4-5 for Monte Carlo analysis.
- **Tailwind CSS v4.2.2**: CSS-first `@theme` directive — no `tailwind.config.js`
- **Next.js 16.2**: Server Components by default, `'use client'` only where DOM/WS access is needed
- **Risk limits**: max 1% per trade, 2% daily loss cap, 8 consecutive SLs → 24h shutdown
- **Monte Carlo**: minimum 1,000 reshuffles per backtest run
- **Signal confidence**: minimum 0.60 to display or persist
- **Walk-forward overfitting**: flag if test win_rate drops >20pp vs training

## Commands

```bash
# Infrastructure
docker compose up -d                    # Start PostgreSQL 17 (port 5433) + Redis 8.6.1 (port 6379)
cd backend && alembic upgrade head      # Run migrations

# Backend
cd backend && uvicorn main:app --reload # Dev server on :8000

# Frontend
cd frontend && npm run dev              # Dev server on :3000 (Turbopack)
cd frontend && npm run lint             # ESLint

# Tests (backend uses pytest-asyncio with asyncio_mode="auto", in-memory SQLite)
cd backend && pytest                    # Full test suite
cd backend && pytest tests/test_strategies/test_liquidity_sweep.py -v  # Single test file
cd backend && pytest -k "test_circuit_breaker"                         # By test name

# Dependencies
cd backend && pip install -e ".[dev]"   # Install backend with dev deps (pyproject.toml)
cd frontend && npm install              # Install frontend deps
```

## Key Patterns

- **Strategy protocol**: All strategies implement `TradingStrategy` from `strategies/base.py` — `evaluate(candles: dict[Timeframe, pd.DataFrame]) -> list[SignalCandidate]`. Register new strategies in `strategies/__init__.py`.
- **Repository pattern**: All DB access goes through `database/repositories/`. Repositories take an `AsyncSession`. Use `database/deps.py` for FastAPI dependency injection.
- **Test fixtures**: `tests/conftest.py` provides `session` (in-memory SQLite), candle generators (`candles_m15`, `candles_h1`, `candles_h4`, `candles_d1`, `all_candles`), `mock_redis`, `mock_claude_client`, and risk state fixtures.
- **Docker ports**: PostgreSQL is mapped to host port **5433** (not 5432). The default `database_url` in `config.py` uses port 5432 — `.env` must override this if using Docker.

## Agent Team

9 specialized agents in `.claude/agents/` for team-based builds. Spawn the `project-coordinator` to orchestrate a full build with `TeamCreate`.

| Agent | Phase | Domain |
|---|---|---|
| `project-coordinator` | All | Orchestration, integration review (Opus) |
| `infra-database-architect` | 1 | Docker, DB models, migrations, repos, schemas |
| `data-feed-engineer` | 2 | Twelve Data + OANDA feeds, candle ingestion |
| `trading-strategy-developer` | 3 | Indicators, 4 strategies, signal resolution |
| `brain-risk-engineer` | 4 | Claude client, risk manager, decision pipeline |
| `optimisation-engineer` | 5 | Monte Carlo, walk-forward, reoptimiser |
| `api-websocket-developer` | 6 | REST routes, WebSocket, scheduler wiring |
| `frontend-dashboard-developer` | 7 | Next.js dashboard, charts, components |
| `test-quality-engineer` | 8 | Tests, error handling, logging |

## Environment

- `.env` contains API keys (ANTHROPIC_API_KEY, TWELVE_DATA_API_KEY, OANDA_ACCESS_TOKEN, etc.) — never commit
- Backend venv: `backend/.venv/` (Python 3.11)
- MCP: CrawlForge configured in `.mcp.json` — use `mcp__crawlforge__*` tools for web scraping/search
