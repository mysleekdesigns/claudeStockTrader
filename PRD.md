# claudeStockTrader — Product Requirements Document

Build a production-grade, AI-assisted gold (XAU/USD) trading system. The system generates trade signals via 4 strategies, uses Claude AI for decision-making, self-optimises via Monte Carlo simulation, and presents everything through a real-time dashboard.

**Implementation Status: COMPLETE** — All 8 phases built and verified on 2026-03-24.

---

## Tech Stack

### Backend
| Package | Version | Notes |
|---|---|---|
| Python | >=3.11 | Runs on 3.11+ (PRD originally specified 3.14.3) |
| FastAPI | 0.135.2 | Lifespan context managers |
| Pydantic | 2.12.5 | v2 — BaseModel, model_validator, field_validator |
| asyncpg | 0.31.0 | Async PostgreSQL driver |
| SQLAlchemy | 2.0.48 | Async session factory over asyncpg |
| APScheduler | 3.11.2 | AsyncIOScheduler |
| redis-py | latest | Async redis client (redis.asyncio) |
| anthropic | latest | claude-sonnet-4-6 brain, claude-haiku-4-5 Monte Carlo |
| uvicorn | latest | ASGI server with uvloop |
| alembic | latest | DB migrations |
| httpx | latest | Async HTTP client |
| numpy / pandas | latest | Signal maths and backtest computation |
| structlog | latest | Structured logging |

### Infrastructure
| Tool | Version |
|---|---|
| PostgreSQL | 17 (Docker) |
| Redis | 8.6.1 (Docker) |

### Frontend
| Package | Version | Notes |
|---|---|---|
| Next.js | 16.2 | App Router, Turbopack, Server Components |
| React | 19 | `use client` only where needed |
| TypeScript | 5.8+ | Strict mode |
| Tailwind CSS | 4.2.2 | CSS-first @theme config (NO tailwind.config.js) |
| shadcn/ui | CLI v4.1.0 | Radix primitives |
| lightweight-charts | 5.1.0 | TradingView charts, multi-pane (v5 `addSeries()` API) |

---

## Phase 1: Infrastructure & Database ✅

### 1.1 Docker + Project Bootstrap
- [x] `docker-compose.yml` — PostgreSQL 17 + Redis 8.6.1-alpine with healthchecks
- [x] `backend/pyproject.toml` — all pinned Python dependencies
- [x] `backend/Dockerfile` — Python 3.14.3-slim image
- [x] `.gitignore` — standard Python/Node/env exclusions
- [x] `backend/.env.example` — template without secrets

### 1.2 Configuration
- [x] `backend/__init__.py`
- [x] `backend/config.py` — pydantic-settings BaseSettings loading from `.env`
  - database_url, redis_url, twelve_data_api_key, anthropic_api_key
  - max_risk_per_trade (0.01), max_daily_loss (0.02), min_signal_confidence (0.60), consecutive_sl_limit (8)
  - `extra = "ignore"` to allow additional env vars in shared `.env`

### 1.3 Database Models (SQLAlchemy 2.0 async, Mapped annotations)
- [x] `backend/database/__init__.py`
- [x] `backend/database/connection.py` — create_async_engine + async_sessionmaker, expire_on_commit=False, pool_size=20
- [x] `backend/database/models.py` — 7 tables with explicit `Enum(..., values_callable=...)` for correct PostgreSQL enum mapping:
  - [x] **candles** — id, symbol, timeframe (15m/1h/4h/1d), timestamp, open, high, low, close, volume. Unique constraint on (symbol, timeframe, timestamp). Composite index on (symbol, timeframe, timestamp DESC)
  - [x] **signals** — id, strategy_name, direction (long/short), entry_price, stop_loss, take_profit, confidence_score, reasoning (text), status enum (pending/active/won/lost/expired), pips_result, created_at, resolved_at. Index on (status, created_at)
  - [x] **strategy_performance** — id, strategy_name, window_days, win_rate, avg_rr, total_signals, sharpe_ratio, max_drawdown, updated_at
  - [x] **backtest_runs** — id, run_type (monte_carlo/walk_forward/reoptimise), window_days, train_start, test_start, test_end, result (pass/fail/overfit), params_used (JSONB), metrics (JSONB), created_at
  - [x] **optimised_params** — id, strategy_name, params (JSONB), is_active, validated_at
  - [x] **risk_state** — id, date, daily_loss_pct, consecutive_stops, is_shutdown, shutdown_until
  - [x] **decision_log** — id, ranked_strategies (JSONB), risk_status, position_size_multiplier, notes, created_at. Index on created_at

### 1.4 Alembic Migrations
- [x] `backend/alembic.ini` — script_location points to `backend/migrations` for root-level execution
- [x] `backend/migrations/env.py` — async migration runner
- [x] `backend/migrations/versions/001_initial.py` — creates all 7 tables with enums, indexes, constraints

### 1.5 Repository Layer
- [x] `backend/database/repositories/__init__.py`
- [x] `backend/database/repositories/candles.py` — upsert via INSERT ... ON CONFLICT DO UPDATE, range queries, get_latest
- [x] `backend/database/repositories/signals.py` — create, list with filters, get_pending_and_active, resolve
- [x] `backend/database/repositories/performance.py` — get_all, get_by_strategy, upsert
- [x] `backend/database/repositories/risk.py` — get_current, get_or_create_today, set_shutdown, reset_shutdown
- [x] `backend/database/repositories/decisions.py` — log, list_recent
- [x] `backend/database/repositories/backtests.py` — list_runs, get_active_params, get_all_params (added in Phase 6)
- [x] `backend/database/deps.py` — get_session async generator for FastAPI Depends (added in Phase 6)

### 1.6 Pydantic v2 Schemas
- [x] `backend/schemas/__init__.py`
- [x] `backend/schemas/signal.py` — SignalCreate (with validators), SignalResponse, SignalResolution
- [x] `backend/schemas/performance.py` — StrategyPerformanceResponse, PnLPoint
- [x] `backend/schemas/risk.py` — RiskStateResponse
- [x] `backend/schemas/candle.py` — CandleResponse (added in Phase 6)
- [x] `backend/schemas/decision.py` — DecisionLogResponse, BacktestRunResponse, OptimisedParamsResponse (added in Phase 6)
- [x] `backend/schemas/health.py` — HealthResponse (added in Phase 6)

### 1.7 FastAPI Skeleton with Lifespan
- [x] `backend/main.py` — lifespan context manager initialising:
  - [x] Async engine + connection check
  - [x] Redis connection pool
  - [x] Shared httpx.AsyncClient (connection pooled)
  - [x] Data feed provider (FailoverFeed)
  - [x] Claude client (ClaudeClient)
  - [x] APScheduler (AsyncIOScheduler) with all jobs wired
  - [x] Include all 7 routers
  - [x] Global exception handler middleware
  - [x] Structlog configuration

### 1.8 Verification
- [x] `docker compose up -d` starts Postgres + Redis
- [x] Alembic migrations run successfully
- [x] Uvicorn starts, `GET /docs` returns Swagger UI

---

## Phase 2: Data Ingestion & Candle Feed ✅

### 2.1 Data Feed Provider
- [x] `backend/data/__init__.py`
- [x] `backend/data/feed.py` — DataFeedProvider Protocol with two implementations:
  - [x] **TwelveDataFeed** (primary) — `GET /time_series?symbol=XAU/USD&interval={tf}` via httpx. Free tier: 800 calls/day, 8/min
  - [x] **OandaFeed** (fallback) — v20 REST API for candles. Free practice account
  - [x] **FailoverFeed** — automatic failover with 2 retries before falling back to OANDA
  - [x] Add to `.env`: TWELVE_DATA_API_KEY, OANDA_ACCOUNT_ID, OANDA_ACCESS_TOKEN

### 2.2 Candle Ingestion Job
- [x] `backend/data/candle_ingestion.py` — CandleIngestionService with staggered ingestion:
  - [x] 15m candles: check every 1 min
  - [x] 1h candles: check every 5 min
  - [x] 4h candles: check every 15 min
  - [x] 1d candles: check every 60 min
  - [x] Average ~1.28 calls/min (within free tier)
  - [x] Publish latest candle to Redis pub/sub channel `candles:XAU/USD`
  - [x] Tracks last-ingested timestamp per timeframe to skip redundant API calls
  - [x] `backfill()` method available for initial historical data population

### 2.3 Verification
- [x] Docker services running
- [x] Ingestion service registered with APScheduler
- [x] Redis pub/sub publishes candle messages

---

## Phase 3: Trading Strategies ✅

### 3.1 Strategy Base
- [x] `backend/strategies/__init__.py` — exports ALL_STRATEGIES list
- [x] `backend/strategies/base.py`:
  - [x] `TradingStrategy` Protocol with `name` attribute and `evaluate()` method
  - [x] `SignalCandidate` frozen dataclass: strategy_name, direction, entry/SL/TP, confidence, reasoning, timeframe_bias, timeframe_entry, atr_value
- [x] `backend/strategies/indicators.py` — pure numpy/pandas implementations:
  - [x] EMA (any period)
  - [x] ATR (any period)
  - [x] RSI (any period)
  - [x] Bollinger Bands
  - [x] Equal-level detection (highs/lows within tolerance)
  - [x] Engulfing and pin bar pattern detection

### 3.2 Strategy 1 — Liquidity Sweep
- [x] `backend/strategies/liquidity_sweep.py`:
  - [x] Detect equal highs/lows (liquidity pools) on 1h chart
  - [x] Identify sweep: wick beyond pool + reversal candle closing back inside range
  - [x] 15m confirmation entry (engulfing or pin bar)
  - [x] Params: eq_tolerance, sl_atr_mult, tp_atr_mult, atr_period, lookback, min_touches

### 3.3 Strategy 2 — Trend Continuation
- [x] `backend/strategies/trend_continuation.py`:
  - [x] 50/200 EMA on 4h to define trend direction
  - [x] Wait for pullback to 50 EMA or prior structure on 1h
  - [x] Entry on bullish/bearish engulfing candle at the level
  - [x] Params: ema_fast, ema_slow, pullback_tolerance, sl_atr_mult, tp_atr_mult

### 3.4 Strategy 3 — Breakout Expansion
- [x] `backend/strategies/breakout_expansion.py`:
  - [x] Identify consolidation range on daily (compressed ATR)
  - [x] Breakout confirmed: price closes beyond range with expanding volume on 4h/1h
  - [x] Entry on retest of broken level
  - [x] Params: squeeze_period, breakout_atr_mult, volume_threshold, sl_atr_mult, tp_atr_mult, retest_tolerance

### 3.5 Strategy 4 — EMA Momentum
- [x] `backend/strategies/ema_momentum.py`:
  - [x] 8/21/50 EMA fan-out on same chart (15m and 1h)
  - [x] Signal when all three fan out, price rides 8 EMA
  - [x] Momentum confirmed by RSI > 55 (long) or < 45 (short)
  - [x] Params: ema_fast, ema_mid, ema_slow, rsi_period, rsi_long_threshold, rsi_short_threshold

### 3.6 Signal Resolution
- [x] `backend/scheduler/signal_resolver.py`:
  - [x] Every 5 min: check pending/active signals against current price
  - [x] Won: price hit take_profit before stop_loss
  - [x] Lost: price hit stop_loss first
  - [x] Expired: neither hit within TTL (default 48h)
  - [x] Update strategy_performance metrics across 7/30/90 day windows
  - [x] Publish status changes to Redis

### 3.7 Win/Loss Definitions
- [x] A strategy is validated once it has 100+ resolved signals with win rate > 50% and RR >= 1.5

### 3.8 Verification
- [x] Unit tests with fixture candle data for each strategy (Phase 8)

### Additional Files
- [x] `backend/strategies/runner.py` — loads candle data from DB, runs all strategies, persists qualifying signals (confidence >= 0.60)

---

## Phase 4: Brain Pipeline & Risk Management ✅

### 4.1 Claude Client
- [x] `backend/brain/__init__.py`
- [x] `backend/brain/claude_client.py`:
  - [x] Wrap `anthropic.AsyncAnthropic`
  - [x] Semaphore: max 3 concurrent API calls (asyncio.Semaphore)
  - [x] Redis prompt cache: 25-min TTL, keyed by SHA-256 of prompt
  - [x] Sliding window rate limiter: 60 calls/hour via Redis sorted set
  - [x] `decide()` method — uses claude-sonnet-4-6 for brain decisions
  - [x] `analyze()` method — uses claude-haiku-4-5 for Monte Carlo reasoning

### 4.2 Risk Manager
- [x] `backend/brain/risk_manager.py`:
  - [x] `check_risk_state()` — load risk_state from DB, enforce limits:
    - [x] 2% daily loss cap → set is_shutdown=true if exceeded
    - [x] 8 consecutive stop losses → set is_shutdown=true, shutdown_until=now()+24h
  - [x] `calculate_position_size()`:
    - [x] ATR-based: `(account_risk × max_risk_per_trade) / pip_risk × volatility_scale`
    - [x] Volatility scaling: reduce when ATR > 2x 20-period average
    - [x] Never exceed 1% risk per trade
  - [x] `reset_circuit_breaker()` — hourly check:
    - [x] Reset after 24h for consecutive SL shutdowns
    - [x] Reset on new UTC day for daily loss shutdowns
  - [x] `record_signal_result()` — update consecutive_stops counter, daily_loss_pct

### 4.3 Decision Pipeline (every 30 min)
- [x] `backend/brain/decision_pipeline.py`:
  - [x] Step 1: Check risk state — abort if is_shutdown=true
  - [x] Step 2: Load candles for all 4 timeframes (200 bars each)
  - [x] Step 3: Load strategy_performance metrics
  - [x] Step 4: Rank strategies by composite score: `win_rate × avg_rr × (1 - max_drawdown)`
  - [x] Step 5: Send rankings + risk state + market summary to claude-sonnet-4-6
  - [x] Step 6: Parse Claude response — which strategies to activate/suppress
  - [x] Step 7: Run activated strategies with their optimised_params
  - [x] Step 8: Filter candidates by minimum confidence (0.60)
  - [x] Step 9: Persist qualified signals to DB
  - [x] Step 10: Publish new signals to Redis pub/sub `signals:XAU/USD`
  - [x] Step 11: Log full decision to decision_log table
  - [x] Graceful fallback on Claude rate limit or errors

### 4.4 Cold Start Handling
- [x] When strategy_performance is empty (first deployment):
  - [x] Use default params from each strategy
  - [x] Equal strategy weights
  - [x] Skip Claude ranking until >= 50 resolved signals per strategy

### 4.5 Verification
- [x] Decision pipeline and risk manager tests written (Phase 8)
- [x] Circuit breaker triggers correctly at thresholds (tested)

---

## Phase 5: Self-Optimisation Engine ✅

### 5.1 Monte Carlo Simulation (every 4h)
- [x] `backend/optimisation/__init__.py`
- [x] `backend/optimisation/monte_carlo.py`:
  - [x] For each strategy × each window (7, 14, 30, 60 days):
    - [x] Load resolved signals for the window
    - [x] Extract PnL array
    - [x] Reshuffle 1,000 times (minimum)
    - [x] Compute distribution: mean drawdown, P95 drawdown, win rate
    - [x] Store results to backtest_runs table
  - [x] Claude Haiku summarises findings across all strategies (best-effort, failure doesn't block)

### 5.2 Walk-Forward Validation
- [x] `backend/optimisation/walk_forward.py`:
  - [x] 80/20 train/test split on 60-day signal history (non-overlapping)
  - [x] Compute metrics on both sets (win_rate, Sharpe, max_drawdown)
  - [x] Flag overfitting if test win_rate drops > 20 percentage points vs train
  - [x] If overfit detected: deactivate current params for that strategy

### 5.3 Parameter Reoptimisation (every 6h)
- [x] `backend/optimisation/reoptimiser.py`:
  - [x] Per strategy: define parameter search space (ranges/choices) matching strategy __init__ signatures
  - [x] Random search (not grid): 200 candidate param sets
  - [x] Mini-backtest each on 30-day window, score by Sharpe ratio
  - [x] Best candidate must pass walk-forward validation before promotion
  - [x] If no candidate passes: retain existing params, log attempt
  - [x] Save winning params to optimised_params with is_active=true

### 5.4 Verification
- [x] `backend/seed_data.py` — seeds DB with synthetic signal history, candles, performance data, backtest runs, and decision log entries
- [x] Monte Carlo statistical properties tested (Phase 8)

---

## Phase 6: API Routes & WebSocket ✅

### 6.1 REST Routers (FastAPI, Pydantic v2 response models)
- [x] `backend/routers/__init__.py` — exports all routers
- [x] `backend/routers/candles.py` — `GET /api/candles/{symbol:path}/{timeframe}` (paginated, optional start/end, limit<=1000). Uses `:path` converter to handle `XAU/USD` slash in URL.
- [x] `backend/routers/signals.py`:
  - [x] `GET /api/signals` — filter by strategy, status, timeframe
  - [x] `POST /api/signals/{id}/resolve` — manually resolve a signal
- [x] `backend/routers/performance.py`:
  - [x] `GET /api/performance/strategies` — strategy leaderboard
  - [x] `GET /api/performance/pnl` — P&L history
- [x] `backend/routers/risk.py` — `GET /api/risk/state`
- [x] `backend/routers/decisions.py`:
  - [x] `GET /api/decisions` — decision log
  - [x] `GET /api/backtests` — backtest run history
  - [x] `GET /api/params` — active optimised params per strategy
- [x] `backend/routers/health.py` — `GET /api/health` (DB, Redis, feed, scheduler status)

### 6.2 WebSocket
- [x] `backend/routers/websocket.py`:
  - [x] `ConnectionManager` class managing active WebSocket connections
  - [x] `WS /ws/live` endpoint:
    - [x] On connect: subscribe to Redis pub/sub channels (candles:XAU/USD, signals:XAU/USD, risk:alerts)
    - [x] Async task 1: Redis listener → forward messages to client
    - [x] Async task 2: Client listener → handle ping/pong keepalive
    - [x] On disconnect: cleanup Redis subscription
  - [x] Message format: `{"type": "candle"|"signal"|"risk_update", "data": {...}}`

### 6.3 Scheduler Wiring
- [x] `backend/scheduler/__init__.py`
- [x] `backend/scheduler/jobs.py` — register all jobs with AsyncIOScheduler:
  - [x] `ingest_candles` — 4 staggered jobs (15m/1h/4h/1d) via candle_ingestion
  - [x] `run_signals` — every 15 min → strategies runner
  - [x] `decision_pipeline` — every 30 min → brain/decision_pipeline
  - [x] `resolve_signals` — every 5 min → scheduler/signal_resolver
  - [x] `monte_carlo_engine` — every 4 hours → optimisation/monte_carlo
  - [x] `reoptimise_params` — every 6 hours → optimisation/reoptimiser
  - [x] `circuit_breaker_reset` — every 1 hour → brain/risk_manager
- [x] Each job creates its own AsyncSession (no shared sessions across ticks)
- [x] Staggered next_run_time offsets to prevent simultaneous startup
- [x] All jobs instrumented with `_log_job` timing context manager

**Note:** Single uvicorn worker required — APScheduler runs in-process. Extract to separate process for horizontal scaling later.

### 6.4 Verification
- [x] Start full backend, all endpoints respond via Swagger
- [x] All 10 scheduler jobs register and fire on schedule

---

## Phase 7: Frontend — Next.js 16.2 Dashboard ✅

### 7.1 Project Setup
- [x] `frontend/package.json` — pinned next 16.2.0, react 19, lightweight-charts 5.1.0, tailwindcss 4.2.2
- [x] `frontend/next.config.ts` — API rewrites to proxy `/api/*` to `localhost:8000`
- [x] `frontend/postcss.config.mjs` — @tailwindcss/postcss plugin
- [x] `frontend/app/globals.css` — Tailwind v4 @theme directive (NO tailwind.config.js):
  - [x] Gold trading color palette (gold-50 through gold-900)
  - [x] Bull green (#22c55e), bear red (#ef4444)
  - [x] Dark-only theme: bg #0a0a0f, surface #111118, surface-raised #1a1a24
  - [x] Inter font family, JetBrains Mono for monospace data
- [x] shadcn components: badge, button, card, dialog, scroll-area, table, tabs, tooltip, skeleton

### 7.2 Core Infrastructure
- [x] `frontend/lib/types.ts` — TypeScript interfaces:
  - [x] Candle, Timeframe, Signal, SignalDirection, SignalStatus
  - [x] StrategyPerformance, PnLPoint, RiskState
  - [x] DecisionLog, BacktestRun, OptimisedParams
  - [x] HealthStatus
  - [x] WSMessage (WebSocket message types)
- [x] `frontend/lib/api.ts` — thin fetch wrapper with methods for all endpoints. Server-side fetches use `http://localhost:8000` directly; client-side uses rewrite proxy.
- [x] `frontend/lib/websocket.ts` — `useWebSocket` hook: auto-reconnect (3s interval, 20 max retries), typed messages
- [x] `frontend/lib/utils.ts` — cn() helper (shadcn), formatPrice(), formatPct(), formatPips(), relativeTime()
- [x] `frontend/.env.local` — NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/live

### 7.3 Layout
- [x] `frontend/app/layout.tsx` — Server Component: root layout, font imports, metadata, full-width content area
- [x] `frontend/components/layout/nav.tsx` — Server Component: nav bar with links (/, /brain, /health)
- [x] `frontend/components/layout/ws-status.tsx` — Client Component: green/red connection indicator

### 7.4 Home Page (`/`)
- [x] `frontend/app/page.tsx` — Server Component: fetch initial candles + active signals, pass as props
- [x] `frontend/components/charts/chart-container.tsx` — Client: shared wrapper with ResizeObserver
- [x] `frontend/components/charts/live-chart.tsx` — Client: Lightweight Charts v5.1.0:
  - [x] Candlestick series for XAU/USD (uses v5 `addSeries(CandlestickSeries, ...)` API)
  - [x] Signal overlay price lines: entry (gold), SL (red), TP (green)
  - [x] Timeframe switcher: 15m | 1h | 4h | D
  - [x] WebSocket live updates via series.update()
  - [x] Data sorted ascending by time before rendering
- [x] `frontend/components/charts/mini-chart.tsx` — Client: reusable smaller chart (v5 API, sorted data)
- [x] `frontend/components/charts/timeframe-panel.tsx` — Client: 2x2 CSS Grid of mini charts (15m, 1h, 4h, D)
  - [x] Each panel: current price, trend direction indicator, active signal count
- [x] `frontend/components/signals/signal-card.tsx` — Client:
  - [x] Strategy name, direction badge (LONG green / SHORT red) with null-safe rendering
  - [x] Entry / SL / TP prices formatted
  - [x] Confidence score bar (0-100%)
  - [x] Expandable Claude reasoning text
  - [x] Status badge, relative timestamp
- [x] `frontend/components/signals/signal-feed.tsx` — Client:
  - [x] Real-time scrollable list via shadcn ScrollArea
  - [x] Prepends new signals from WebSocket
  - [x] Filter controls (strategy, status)
- [x] Layout: `grid grid-cols-1 xl:grid-cols-[1fr_380px]` — charts left, signal feed right sidebar

### 7.5 Brain Dashboard (`/brain`)
- [x] `frontend/app/brain/page.tsx` — Server Component: fetch all brain data in parallel
- [x] `frontend/components/brain/strategy-table.tsx` — Server Component:
  - [x] shadcn Table ranked by Sharpe ratio
  - [x] Columns: rank, name, win rate, total signals, avg RR, Sharpe, max drawdown
  - [x] Color coding: win rate > 55% green, < 45% red
- [x] `frontend/components/charts/pnl-chart.tsx` — Client: Lightweight Charts AreaSeries for cumulative P&L (v5 `addSeries(AreaSeries, ...)` API)
- [x] `frontend/components/brain/risk-panel.tsx` — Client:
  - [x] Daily loss percentage gauge
  - [x] Consecutive stops counter with warning colors
  - [x] Circuit breaker status: prominent SYSTEM PAUSED banner with countdown
  - [x] Position size multiplier indicator
  - [x] Live updates via WebSocket risk_update messages
- [x] `frontend/components/brain/decision-log.tsx` — Client:
  - [x] Scrollable timeline of 30-min pipeline decisions
  - [x] Each entry: timestamp, active strategies, Claude commentary, signals generated
  - [x] Auto-scroll to latest
- [x] `frontend/components/brain/backtest-table.tsx` — Server Component:
  - [x] Table of Monte Carlo + walk-forward runs
  - [x] Columns: strategy, window, result (pass/fail/overfit badge), key metrics
- [x] `frontend/components/brain/params-viewer.tsx` — Server Component:
  - [x] Active parameters per strategy
  - [x] Last validated timestamp
  - [x] Version/history indicator

### 7.6 Health Page (`/health`)
- [x] `frontend/components/health/health-card.tsx` — Server Component: service status card
- [x] `frontend/app/health/page.tsx` — Server Component: grid of health cards
  - [x] Database connection status
  - [x] Redis connection status
  - [x] Data feed connectivity
  - [x] Scheduler status

### 7.7 Server/Client Boundary Rules
- [x] **Server Components** (default): layout, nav, static tables (strategy, backtest, params), health page
- [x] **Client Components** (`'use client'`): charts (DOM required), WebSocket consumers (signal feed, risk panel, decision log), interactive controls (timeframe switcher)

### 7.8 Verification
- [x] `npm run dev` starts with Turbopack
- [x] All pages render with seeded data
- [x] Charts render correctly with candle data
- [x] Signal feed displays with filter controls

---

## Phase 8: Polish & Hardening ✅

### 8.1 Loading States
- [x] `frontend/app/loading.tsx` — skeleton loading for home page
- [x] `frontend/app/brain/loading.tsx` — skeleton loading for brain dashboard

### 8.2 Error Handling
- [x] `frontend/components/charts/chart-error-boundary.tsx` — error boundary for chart components (prevent full-page crash)
- [x] `backend/middleware.py` — global exception handler middleware (ExceptionHandlerMiddleware)
- [x] `backend/utils/retry.py` — `retry_async` decorator for external API calls (Twelve Data, OANDA, Anthropic) — exponential backoff

### 8.3 Observability
- [x] `backend/logging_config.py` — structlog configuration (structlog included in pyproject.toml)
- [x] All scheduler job runs instrumented with `_log_job` timing context manager

### 8.4 End-to-End Testing
- [x] `backend/seed_data.py` — seeds complete dataset for visual verification
- [x] Backend tests: pytest-asyncio with async fixtures (in-memory SQLite for isolation)
  - [x] `tests/test_strategies/test_indicators.py` — 20 tests: EMA, ATR, RSI, Bollinger, equal levels, engulfing, pin bars
  - [x] `tests/test_strategies/test_liquidity_sweep.py` — 7 tests: sweep scenarios, confidence filtering, custom params
  - [x] `tests/test_strategies/test_trend_continuation.py` — 6 tests: uptrend/downtrend, flat market, SL/TP validation
  - [x] `tests/test_strategies/test_breakout_expansion.py` — 6 tests: squeeze/breakout, volume confirmation
  - [x] `tests/test_strategies/test_ema_momentum.py` — 7 tests: momentum fan-out, H1 preference, RSI thresholds
  - [x] `tests/test_brain/test_risk_manager.py` — 11 tests: circuit breaker at exact thresholds (8 SLs, 2% daily), position sizing, volatility scaling
  - [x] `tests/test_brain/test_decision_pipeline.py` — 7 tests: Claude response parsing, composite score, cold start, risk shutdown abort
  - [x] `tests/test_optimisation/test_monte_carlo.py` — 9 tests: drawdown computation, 1000-reshuffle minimum, P95 >= mean, win rate bounds, statistical convergence
  - [x] `tests/test_routers/test_health.py` — 2 tests: health endpoint schema
  - [x] `tests/test_routers/test_candles.py` — 4 tests: candle CRUD, field validation, invalid timeframe
  - [x] `tests/test_routers/test_signals.py` — 6 tests: list/resolve signals, already-resolved rejection

**Total: 85+ tests across 11 test files**

---

## Redis Caching Strategy

| Key Pattern | TTL | Purpose |
|---|---|---|
| `claude:cache:{prompt_hash}` | 25 min | Deduplicate Claude calls within decision cycle |
| `candles:latest:{symbol}:{tf}` | 60s | Quick reads for WebSocket |
| `risk:state` | 30s | Avoid DB reads on every signal check |
| `perf:{strategy_name}` | 5 min | Cache strategy performance metrics |
| `rate:claude:window` | 3600s | Sliding window rate limiter for Anthropic API |

**Pub/sub channels:** `candles:XAU/USD`, `signals:XAU/USD`, `risk:alerts`

---

## Key Architectural Decisions

1. **Single uvicorn worker** — APScheduler runs in-process; multi-worker would duplicate scheduled jobs
2. **Strategies return candidates, brain persists** — gives the brain full veto power and ensures atomic risk checks
3. **Redis pub/sub as message bus** — decouples scheduler jobs from WebSocket consumers, supports future horizontal scaling
4. **Twelve Data primary + OANDA fallback** — free tier adequate with staggered ingestion (~1.28 calls/min)
5. **Cold start graceful degradation** — default params + equal strategy weights until >= 50 resolved signals per strategy
6. **Tailwind v4 CSS-first** — no tailwind.config.js, all theming via @theme directive in globals.css
7. **Server-side vs client-side API fetching** — Server Components fetch directly from `localhost:8000`; client-side uses Next.js rewrite proxy
8. **Lightweight Charts v5 API** — uses `chart.addSeries(CandlestickSeries, opts)` instead of deprecated v4 `chart.addCandlestickSeries(opts)`
9. **Enum values_callable** — SQLAlchemy enum columns use `values_callable` to ensure `.value` (lowercase) is sent to PostgreSQL, not `.name` (uppercase)

---

## Constraints & Hard Rules

- All DB operations must be async (asyncpg + SQLAlchemy 2.0 async session)
- All external API calls must be async (httpx) with retry logic and timeouts
- Anthropic SDK calls rate-limited and cached in Redis
- No hard-coded credentials — all secrets via .env
- Position sizing: never risk more than 1% per trade
- Daily loss hard cap: 2% of account equity — enforced in risk_manager.py
- Circuit breaker: 8 consecutive SLs → 24h cooldown, no exceptions
- Walk-forward overfitting threshold: test win rate drops > 20 percentage points vs training
- Monte Carlo minimum sample: 1,000 reshuffles per backtest run
- Signal minimum confidence to display: 0.60 (60%)
- Tailwind CSS v4.2.2: CSS-first @theme — do NOT generate tailwind.config.js
- Next.js 16.2: Turbopack enabled, Server Components by default, `use client` only where required

---

## Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Twelve Data free tier rate limits | Staggered ingestion schedule + automatic OANDA failover |
| Claude API costs (~$2-5/day) | Redis prompt cache (25-min TTL) + sliding window rate limiter |
| Long-running Monte Carlo blocking scheduler | APScheduler max_instances=1 + fully async execution |
| Signal resolution 5-min lag | Acceptable for gold ATR ($15-30); can tighten to 1 min if needed |
| Cold start with no data | Graceful degradation: default params, equal weights, skip Claude ranking |
| APScheduler in single worker | Extract to separate process if horizontal scaling needed later |

---

## Quick Start

```bash
# 1. Set up environment
cp backend/.env.example .env
# Edit .env with your API keys (TWELVE_DATA_API_KEY, OANDA_*, ANTHROPIC_API_KEY)

# 2. Start infrastructure
docker compose up -d

# 3. Set up backend
cd backend && python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && pip install greenlet

# 4. Run migrations (from project root)
PYTHONPATH=. alembic -c backend/alembic.ini upgrade head

# 5. Seed sample data (optional, for demo without API keys)
PYTHONPATH=. python backend/seed_data.py

# 6. Start backend
PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 7. Start frontend (new terminal)
cd frontend && npm install && npm run dev

# 8. Open dashboard
open http://localhost:3000         # Trading dashboard
open http://localhost:3000/brain   # Brain/strategy dashboard
open http://localhost:3000/health  # System health
open http://localhost:8000/docs    # API documentation
```

---

## Complete File Tree (~124 files)

```
claudeStocks/
├── docker-compose.yml
├── .gitignore
├── .env
├── PRD.md
├── CLAUDE.md
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── .env.example
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── middleware.py
│   ├── logging_config.py
│   ├── seed_data.py
│   ├── alembic.ini
│   ├── utils/
│   │   ├── __init__.py
│   │   └── retry.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── deps.py
│   │   ├── models.py
│   │   └── repositories/
│   │       ├── __init__.py
│   │       ├── candles.py
│   │       ├── signals.py
│   │       ├── performance.py
│   │       ├── risk.py
│   │       ├── decisions.py
│   │       └── backtests.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── signal.py
│   │   ├── candle.py
│   │   ├── performance.py
│   │   ├── risk.py
│   │   ├── decision.py
│   │   └── health.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── feed.py
│   │   └── candle_ingestion.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── indicators.py
│   │   ├── runner.py
│   │   ├── liquidity_sweep.py
│   │   ├── trend_continuation.py
│   │   ├── breakout_expansion.py
│   │   └── ema_momentum.py
│   ├── brain/
│   │   ├── __init__.py
│   │   ├── claude_client.py
│   │   ├── risk_manager.py
│   │   └── decision_pipeline.py
│   ├── optimisation/
│   │   ├── __init__.py
│   │   ├── monte_carlo.py
│   │   ├── walk_forward.py
│   │   └── reoptimiser.py
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── jobs.py
│   │   └── signal_resolver.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── candles.py
│   │   ├── signals.py
│   │   ├── performance.py
│   │   ├── risk.py
│   │   ├── decisions.py
│   │   ├── health.py
│   │   └── websocket.py
│   ├── migrations/
│   │   ├── __init__.py
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 001_initial.py
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_strategies/
│       │   ├── __init__.py
│       │   ├── test_indicators.py
│       │   ├── test_liquidity_sweep.py
│       │   ├── test_trend_continuation.py
│       │   ├── test_breakout_expansion.py
│       │   └── test_ema_momentum.py
│       ├── test_brain/
│       │   ├── __init__.py
│       │   ├── test_risk_manager.py
│       │   └── test_decision_pipeline.py
│       ├── test_optimisation/
│       │   ├── __init__.py
│       │   └── test_monte_carlo.py
│       └── test_routers/
│           ├── __init__.py
│           ├── test_health.py
│           ├── test_candles.py
│           └── test_signals.py
└── frontend/
    ├── package.json
    ├── package-lock.json
    ├── next.config.ts
    ├── tsconfig.json
    ├── postcss.config.mjs
    ├── next-env.d.ts
    ├── .env.local
    ├── app/
    │   ├── globals.css
    │   ├── layout.tsx
    │   ├── page.tsx
    │   ├── loading.tsx
    │   ├── brain/
    │   │   ├── page.tsx
    │   │   └── loading.tsx
    │   └── health/
    │       └── page.tsx
    ├── components/
    │   ├── charts/
    │   │   ├── chart-container.tsx
    │   │   ├── chart-error-boundary.tsx
    │   │   ├── live-chart.tsx
    │   │   ├── mini-chart.tsx
    │   │   ├── pnl-chart.tsx
    │   │   └── timeframe-panel.tsx
    │   ├── signals/
    │   │   ├── signal-card.tsx
    │   │   └── signal-feed.tsx
    │   ├── brain/
    │   │   ├── strategy-table.tsx
    │   │   ├── risk-panel.tsx
    │   │   ├── decision-log.tsx
    │   │   ├── backtest-table.tsx
    │   │   └── params-viewer.tsx
    │   ├── health/
    │   │   └── health-card.tsx
    │   ├── layout/
    │   │   ├── nav.tsx
    │   │   └── ws-status.tsx
    │   └── ui/
    │       ├── badge.tsx
    │       ├── button.tsx
    │       ├── card.tsx
    │       ├── dialog.tsx
    │       ├── scroll-area.tsx
    │       ├── skeleton.tsx
    │       ├── table.tsx
    │       ├── tabs.tsx
    │       └── tooltip.tsx
    └── lib/
        ├── types.ts
        ├── api.ts
        ├── websocket.ts
        └── utils.ts
```
