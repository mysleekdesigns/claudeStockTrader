# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

claudeStockTrader — an AI-assisted gold (XAU/USD) trading system. Generates trade signals via 4 strategies, uses Claude AI for decision-making, self-optimises via Monte Carlo simulation, and presents everything through a real-time dashboard. The project is pre-implementation; the full spec is in `PRD.md`.

## Architecture

The system has 8 build phases with this dependency graph:

```
Phase 1 (infra/DB) ──┬──> Phase 2 (data feed)
                     ├──> Phase 3 (strategies) ──> Phase 4 (brain/AI) ──> Phase 5 (optimisation)
                     └──> Phase 6 (API/WS) ──────────────────────────────> Phase 7 (frontend)
                                                                           └──> Phase 8 (polish)
```

**Backend** (`backend/`): FastAPI + SQLAlchemy 2.0 async + asyncpg + Redis + APScheduler. Single uvicorn worker (APScheduler runs in-process).

**Frontend** (`frontend/`): Next.js 16.2 App Router + React 19 + TradingView Lightweight Charts 5.1.0.

**Message bus**: Redis pub/sub channels (`candles:XAU/USD`, `signals:XAU/USD`, `risk:alerts`) decouple scheduler jobs from WebSocket consumers.

**AI layer**: claude-sonnet-4-6 for trading decisions (30-min pipeline), claude-haiku-4-5 for Monte Carlo analysis.

## Tech Stack Constraints

These are hard rules from the PRD — do not deviate:

- **All DB ops async**: asyncpg + SQLAlchemy 2.0 async session, `expire_on_commit=False`
- **All HTTP calls async**: httpx with retry logic and timeouts
- **Anthropic SDK**: rate-limited (60/hr via Redis) and prompt-cached (25-min TTL)
- **Tailwind CSS v4.2.2**: CSS-first `@theme` directive in `globals.css` — do NOT create `tailwind.config.js`
- **Next.js 16.2**: Server Components by default, `'use client'` only where DOM/WS access is needed
- **Risk limits**: max 1% per trade, 2% daily loss cap, 8 consecutive SLs → 24h shutdown
- **Monte Carlo**: minimum 1,000 reshuffles per backtest run
- **Signal confidence**: minimum 0.60 to display or persist
- **Walk-forward overfitting**: flag if test win_rate drops >20pp vs training

## Commands (once built)

```bash
# Infrastructure
docker compose up -d                    # Start PostgreSQL 17 + Redis 8.6.1
cd backend && alembic upgrade head      # Run migrations

# Backend
cd backend && uvicorn main:app --reload # Dev server on :8000

# Frontend
cd frontend && npm run dev              # Dev server on :3000 (Turbopack)

# Tests
cd backend && pytest                    # Full test suite
cd backend && pytest tests/test_strategies/test_liquidity_sweep.py -v  # Single test file
cd backend && pytest -k "test_circuit_breaker"                         # By test name
```

## Agent Team

9 specialized agents in `.claude/agents/` for team-based builds:

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

Spawn the `project-coordinator` to orchestrate a full build with `TeamCreate`.

## Custom Commands

- `/enhanced-plan` — read-only codebase exploration and implementation planning
- `/agent-creation` — design and create AI agent configurations from requirements

## MCP Servers

- **CrawlForge** (`.mcp.json`): web scraping, search, content extraction. Use `mcp__crawlforge__*` tools for fetching market data.

## Environment

- `.env` contains API keys (ANTHROPIC_API_KEY, TWELVE_DATA_API_KEY, OANDA_ACCESS_TOKEN, etc.) — never commit
- `backend/.env.example` will template all required vars once Phase 1 is built
