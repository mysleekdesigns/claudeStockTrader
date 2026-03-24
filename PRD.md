# claudeStockTrader — Product Requirements Document

Build a production-grade, AI-assisted gold (XAU/USD) trading system. The system generates trade signals via 4 strategies, uses Claude AI for decision-making, self-optimises via Monte Carlo simulation, and presents everything through a real-time dashboard.

---

## Tech Stack

### Backend
| Package | Version | Notes |
|---|---|---|
| Python | 3.14.3 | Free-threaded mode where applicable |
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
| lightweight-charts | 5.1.0 | TradingView charts, multi-pane |

---

## Phase 1: Infrastructure & Database

### 1.1 Docker + Project Bootstrap
- [ ] `docker-compose.yml` — PostgreSQL 17 + Redis 8.6.1-alpine with healthchecks
- [ ] `backend/pyproject.toml` — all pinned Python dependencies
- [ ] `backend/Dockerfile` — Python 3.14.3 image
- [ ] `.gitignore` — standard Python/Node/env exclusions
- [ ] `backend/.env.example` — template without secrets

### 1.2 Configuration
- [ ] `backend/__init__.py`
- [ ] `backend/config.py` — pydantic-settings BaseSettings loading from `.env`
  - database_url, redis_url, twelve_data_api_key, anthropic_api_key
  - max_risk_per_trade (0.01), max_daily_loss (0.02), min_signal_confidence (0.60), consecutive_sl_limit (8)

### 1.3 Database Models (SQLAlchemy 2.0 async, Mapped annotations)
- [ ] `backend/database/__init__.py`
- [ ] `backend/database/connection.py` — create_async_engine + async_sessionmaker, expire_on_commit=False, pool_size=20
- [ ] `backend/database/models.py` — 7 tables:
  - [ ] **candles** — id, symbol, timeframe (15m/1h/4h/1d), timestamp, open, high, low, close, volume. Unique constraint on (symbol, timeframe, timestamp). Composite index on (symbol, timeframe, timestamp DESC)
  - [ ] **signals** — id, strategy_name, direction (long/short), entry_price, stop_loss, take_profit, confidence_score, reasoning (text), status enum (pending/active/won/lost/expired), pips_result, created_at, resolved_at. Index on (status, created_at)
  - [ ] **strategy_performance** — id, strategy_name, window_days, win_rate, avg_rr, total_signals, sharpe_ratio, max_drawdown, updated_at
  - [ ] **backtest_runs** — id, run_type (monte_carlo/walk_forward/reoptimise), window_days, train_start, test_start, test_end, result (pass/fail/overfit), params_used (JSONB), metrics (JSONB), created_at
  - [ ] **optimised_params** — id, strategy_name, params (JSONB), is_active, validated_at
  - [ ] **risk_state** — id, date, daily_loss_pct, consecutive_stops, is_shutdown, shutdown_until
  - [ ] **decision_log** — id, ranked_strategies (JSONB), risk_status, position_size_multiplier, notes, created_at. Index on created_at

### 1.4 Alembic Migrations
- [ ] `backend/alembic.ini`
- [ ] `backend/migrations/env.py` — async migration runner
- [ ] `backend/migrations/versions/001_initial.py` — auto-generated from models

### 1.5 Repository Layer
- [ ] `backend/database/repositories/__init__.py`
- [ ] `backend/database/repositories/candles.py` — upsert via INSERT ... ON CONFLICT DO UPDATE, range queries
- [ ] `backend/database/repositories/signals.py` — create, list with filters, resolve
- [ ] `backend/database/repositories/performance.py` — read/update strategy metrics
- [ ] `backend/database/repositories/risk.py` — get/set risk state, shutdown/reset
- [ ] `backend/database/repositories/decisions.py` — log and list decisions

### 1.6 Pydantic v2 Schemas
- [ ] `backend/schemas/__init__.py`
- [ ] `backend/schemas/signal.py` — SignalCreate, SignalResponse, SignalResolution
- [ ] `backend/schemas/performance.py` — StrategyPerformanceResponse, PnLPoint
- [ ] `backend/schemas/risk.py` — RiskStateResponse

### 1.7 FastAPI Skeleton with Lifespan
- [ ] `backend/main.py` — lifespan context manager initialising:
  - [ ] Async engine + connection check
  - [ ] Redis connection pool
  - [ ] Shared httpx.AsyncClient (connection pooled)
  - [ ] Data feed provider
  - [ ] Claude client
  - [ ] APScheduler (AsyncIOScheduler)
  - [ ] Include all routers

### 1.8 Verification
- [ ] `docker compose up -d` starts Postgres + Redis
- [ ] Alembic migrations run successfully
- [ ] Uvicorn starts, `GET /docs` returns Swagger UI

---

## Phase 2: Data Ingestion & Candle Feed

### 2.1 Data Feed Provider
- [ ] `backend/data/__init__.py`
- [ ] `backend/data/feed.py` — DataFeedProvider Protocol with two implementations:
  - [ ] **TwelveDataFeed** (primary) — `GET /time_series?symbol=XAU/USD&interval={tf}` via httpx. Free tier: 800 calls/day, 8/min
  - [ ] **OandaFeed** (fallback) — v20 REST API for candles. Free practice account
  - [ ] Automatic failover: try primary, fall back to OANDA on error
  - [ ] Add to `.env`: TWELVE_DATA_API_KEY, OANDA_ACCOUNT_ID, OANDA_ACCESS_TOKEN

### 2.2 Candle Ingestion Job
- [ ] `backend/data/candle_ingestion.py` — staggered ingestion to respect rate limits:
  - [ ] 15m candles: check every 1 min
  - [ ] 1h candles: check every 5 min
  - [ ] 4h candles: check every 15 min
  - [ ] 1d candles: check every 60 min
  - [ ] Average ~1.5 calls/min (within free tier)
  - [ ] Publish latest candle to Redis pub/sub channel `candles:XAU/USD`

### 2.3 Verification
- [ ] Docker services running
- [ ] Run ingestion manually, verify candles in DB via psql
- [ ] Redis pub/sub receives candle messages

---

## Phase 3: Trading Strategies

### 3.1 Strategy Base
- [ ] `backend/strategies/__init__.py`
- [ ] `backend/strategies/base.py`:
  - [ ] `TradingStrategy` Protocol with `name` attribute and `evaluate()` method
  - [ ] `SignalCandidate` frozen dataclass: strategy_name, direction, entry/SL/TP, confidence, reasoning, timeframe_bias, timeframe_entry, atr_value
- [ ] `backend/strategies/indicators.py` — pure numpy/pandas implementations:
  - [ ] EMA (any period)
  - [ ] ATR (any period)
  - [ ] RSI (any period)
  - [ ] Bollinger Bands
  - [ ] Equal-level detection (highs/lows within tolerance)

### 3.2 Strategy 1 — Liquidity Sweep
- [ ] `backend/strategies/liquidity_sweep.py`:
  - [ ] Detect equal highs/lows (liquidity pools) on 1h chart
  - [ ] Identify sweep: wick beyond pool + reversal candle closing back inside range
  - [ ] 15m confirmation entry (engulfing or pin bar)
  - [ ] Params: eq_tolerance, sl_atr_mult, tp_atr_mult, atr_period

### 3.3 Strategy 2 — Trend Continuation
- [ ] `backend/strategies/trend_continuation.py`:
  - [ ] 50/200 EMA on 4h to define trend direction
  - [ ] Wait for pullback to 50 EMA or prior structure on 1h
  - [ ] Entry on bullish/bearish engulfing candle at the level
  - [ ] Params: ema_fast, ema_slow, pullback_tolerance

### 3.4 Strategy 3 — Breakout Expansion
- [ ] `backend/strategies/breakout_expansion.py`:
  - [ ] Identify consolidation range on daily (compressed ATR)
  - [ ] Breakout confirmed: price closes beyond range with expanding volume on 4h/1h
  - [ ] Entry on retest of broken level
  - [ ] Params: squeeze_period, breakout_atr_mult, volume_threshold

### 3.5 Strategy 4 — EMA Momentum
- [ ] `backend/strategies/ema_momentum.py`:
  - [ ] 8/21/50 EMA fan-out on same chart (15m and 1h)
  - [ ] Signal when all three fan out, price rides 8 EMA
  - [ ] Momentum confirmed by RSI > 55 (long) or < 45 (short)
  - [ ] Params: ema_fast, ema_mid, ema_slow, rsi_period, rsi_threshold

### 3.6 Signal Resolution
- [ ] `backend/scheduler/signal_resolver.py`:
  - [ ] Every 5 min: check pending/active signals against current price
  - [ ] Won: price hit take_profit before stop_loss
  - [ ] Lost: price hit stop_loss first
  - [ ] Expired: neither hit within TTL (default 48h)
  - [ ] Update strategy_performance metrics after each resolution
  - [ ] Publish status changes to Redis

### 3.7 Win/Loss Definitions
- [ ] A strategy is validated once it has 100+ resolved signals with win rate > 50% and RR >= 1.5

### 3.8 Verification
- [ ] Load historical candles, run each strategy, verify signal quality
- [ ] Unit tests with fixture candle data for each strategy

---

## Phase 4: Brain Pipeline & Risk Management

### 4.1 Claude Client
- [ ] `backend/brain/__init__.py`
- [ ] `backend/brain/claude_client.py`:
  - [ ] Wrap `anthropic.AsyncAnthropic`
  - [ ] Semaphore: max 3 concurrent API calls
  - [ ] Redis prompt cache: 25-min TTL, keyed by SHA-256 of prompt
  - [ ] Sliding window rate limiter: 60 calls/hour via Redis counter
  - [ ] `decide()` method — uses claude-sonnet-4-6 for brain decisions
  - [ ] `analyze()` method — uses claude-haiku-4-5 for Monte Carlo reasoning

### 4.2 Risk Manager
- [ ] `backend/brain/risk_manager.py`:
  - [ ] `check_risk_state()` — load risk_state from DB, enforce limits:
    - [ ] 2% daily loss cap → set is_shutdown=true if exceeded
    - [ ] 8 consecutive stop losses → set is_shutdown=true, shutdown_until=now()+24h
  - [ ] `calculate_position_size()`:
    - [ ] ATR-based: `(account_risk × max_risk_per_trade) / pip_risk × volatility_scale`
    - [ ] Volatility scaling: reduce when ATR > 2x 20-period average
    - [ ] Never exceed 1% risk per trade
  - [ ] `reset_circuit_breaker()` — hourly check:
    - [ ] Reset after 24h for consecutive SL shutdowns
    - [ ] Reset on new UTC day for daily loss shutdowns
  - [ ] `record_signal_result()` — update consecutive_stops counter, daily_loss_pct

### 4.3 Decision Pipeline (every 30 min)
- [ ] `backend/brain/decision_pipeline.py`:
  - [ ] Step 1: Check risk state — abort if is_shutdown=true
  - [ ] Step 2: Load candles for all 4 timeframes (200 bars each)
  - [ ] Step 3: Load strategy_performance metrics
  - [ ] Step 4: Rank strategies by composite score: `win_rate × avg_rr × (1 - max_drawdown)`
  - [ ] Step 5: Send rankings + risk state + market summary to claude-sonnet-4-6
  - [ ] Step 6: Parse Claude response — which strategies to activate/suppress
  - [ ] Step 7: Run activated strategies with their optimised_params
  - [ ] Step 8: Filter candidates by minimum confidence (0.60)
  - [ ] Step 9: Persist qualified signals to DB
  - [ ] Step 10: Publish new signals to Redis pub/sub `signals:XAU/USD`
  - [ ] Step 11: Log full decision to decision_log table

### 4.4 Cold Start Handling
- [ ] When strategy_performance is empty (first deployment):
  - [ ] Use default params from each strategy
  - [ ] Equal strategy weights
  - [ ] Skip Claude ranking until >= 50 resolved signals per strategy

### 4.5 Verification
- [ ] Mock Claude responses, run pipeline end-to-end
- [ ] Verify signals created in DB and decisions logged
- [ ] Verify circuit breaker triggers correctly at thresholds

---

## Phase 5: Self-Optimisation Engine

### 5.1 Monte Carlo Simulation (every 4h)
- [ ] `backend/optimisation/__init__.py`
- [ ] `backend/optimisation/monte_carlo.py`:
  - [ ] For each strategy × each window (7, 14, 30, 60 days):
    - [ ] Load resolved signals for the window
    - [ ] Extract PnL array
    - [ ] Reshuffle 1,000 times (minimum)
    - [ ] Compute distribution: mean drawdown, P95 drawdown, win rate
    - [ ] Store results to backtest_runs table
  - [ ] Claude Haiku summarises findings across all strategies

### 5.2 Walk-Forward Validation
- [ ] `backend/optimisation/walk_forward.py`:
  - [ ] 80/20 train/test split on 60-day signal history (non-overlapping)
  - [ ] Compute metrics on both sets (win_rate, Sharpe, max_drawdown)
  - [ ] Flag overfitting if test win_rate drops > 20 percentage points vs train
  - [ ] If overfit detected: deactivate current params for that strategy

### 5.3 Parameter Reoptimisation (every 6h)
- [ ] `backend/optimisation/reoptimiser.py`:
  - [ ] Per strategy: define parameter search space (ranges/choices)
  - [ ] Random search (not grid): 200 candidate param sets
  - [ ] Mini-backtest each on 30-day window, score by Sharpe ratio
  - [ ] Best candidate must pass walk-forward validation before promotion
  - [ ] If no candidate passes: retain existing params, log attempt
  - [ ] Save winning params to optimised_params with is_active=true

### 5.4 Verification
- [ ] Seed DB with synthetic signal history
- [ ] Run Monte Carlo, verify results in backtest_runs table
- [ ] Run reoptimiser, verify params updated in optimised_params
- [ ] Verify overfitting detection flags correctly

---

## Phase 6: API Routes & WebSocket

### 6.1 REST Routers (FastAPI, Pydantic v2 response models)
- [ ] `backend/routers/__init__.py`
- [ ] `backend/routers/candles.py` — `GET /api/candles/{symbol}/{timeframe}` (paginated, optional start/end, limit<=1000)
- [ ] `backend/routers/signals.py`:
  - [ ] `GET /api/signals` — filter by strategy, status, timeframe
  - [ ] `POST /api/signals/{id}/resolve` — manually resolve a signal
- [ ] `backend/routers/performance.py`:
  - [ ] `GET /api/performance/strategies` — strategy leaderboard
  - [ ] `GET /api/performance/pnl` — P&L history
- [ ] `backend/routers/risk.py` — `GET /api/risk/state`
- [ ] `backend/routers/decisions.py`:
  - [ ] `GET /api/decisions` — decision log
  - [ ] `GET /api/backtests` — backtest run history
  - [ ] `GET /api/params` — active optimised params per strategy
- [ ] `backend/routers/health.py` — `GET /api/health` (DB, Redis, feed, scheduler status)

### 6.2 WebSocket
- [ ] `backend/routers/websocket.py`:
  - [ ] `ConnectionManager` class managing active WebSocket connections
  - [ ] `WS /ws/live` endpoint:
    - [ ] On connect: subscribe to Redis pub/sub channels (candles:XAU/USD, signals:XAU/USD, risk:alerts)
    - [ ] Async task 1: Redis listener → forward messages to client
    - [ ] Async task 2: Client listener → handle ping/pong keepalive
    - [ ] On disconnect: cleanup Redis subscription
  - [ ] Message format: `{"type": "candle"|"signal"|"risk_update", "data": {...}}`

### 6.3 Scheduler Wiring
- [ ] `backend/scheduler/__init__.py`
- [ ] `backend/scheduler/jobs.py` — register all jobs with AsyncIOScheduler:
  - [ ] `ingest_candles` — every 1 min → data/candle_ingestion
  - [ ] `run_signals` — every 15 min → strategies quick scan
  - [ ] `decision_pipeline` — every 30 min → brain/decision_pipeline
  - [ ] `resolve_signals` — every 5 min → scheduler/signal_resolver
  - [ ] `monte_carlo_engine` — every 4 hours → optimisation/monte_carlo
  - [ ] `reoptimise_params` — every 6 hours → optimisation/reoptimiser
  - [ ] `circuit_breaker_reset` — every 1 hour → brain/risk_manager
- [ ] Each job creates its own AsyncSession (no shared sessions across ticks)
- [ ] Staggered next_run_time offsets to prevent simultaneous startup

**Note:** Single uvicorn worker required — APScheduler runs in-process. Extract to separate process for horizontal scaling later.

### 6.4 Verification
- [ ] Start full backend, all endpoints respond via Swagger
- [ ] Connect WebSocket client, observe live candle streaming
- [ ] Verify all scheduler jobs fire on schedule

---

## Phase 7: Frontend — Next.js 16.2 Dashboard

### 7.1 Project Setup
- [ ] Create Next.js app: `npx create-next-app@16.2 frontend --typescript --tailwind --eslint --app --turbopack`
- [ ] Pin versions in `frontend/package.json`: next 16.2.0, react 19, lightweight-charts 5.1.0, tailwindcss 4.2.2
- [ ] `frontend/next.config.ts` — API rewrites to proxy `/api/*` to `localhost:8000`
- [ ] `frontend/postcss.config.mjs` — @tailwindcss/postcss plugin
- [ ] `frontend/app/globals.css` — Tailwind v4 @theme directive (NO tailwind.config.js):
  - [ ] Gold trading color palette (gold-50 through gold-900)
  - [ ] Bull green (#22c55e), bear red (#ef4444)
  - [ ] Dark-only theme: bg #0a0a0f, surface #111118, surface-raised #1a1a24
  - [ ] Inter font family, JetBrains Mono for monospace data
- [ ] Run `npx shadcn@4.1.0 init` + add components: badge, button, card, dialog, scroll-area, table, tabs, tooltip, skeleton

### 7.2 Core Infrastructure
- [ ] `frontend/lib/types.ts` — TypeScript interfaces:
  - [ ] Candle, Timeframe, Signal, SignalDirection, SignalStatus
  - [ ] StrategyPerformance, PnLPoint, RiskState
  - [ ] Decision, BacktestResult, StrategyParams
  - [ ] HealthStatus, JobStatus
  - [ ] WSMessage, WSPriceUpdate (WebSocket message types)
- [ ] `frontend/lib/api.ts` — thin fetch wrapper with methods for all endpoints
- [ ] `frontend/lib/websocket.ts` — `useWebSocket` hook: auto-reconnect (3s interval, 20 max retries), typed messages
- [ ] `frontend/lib/utils.ts` — cn() helper (shadcn), formatters
- [ ] `frontend/.env.local` — NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/live

### 7.3 Layout
- [ ] `frontend/app/layout.tsx` — Server Component: root layout, font imports, metadata
- [ ] `frontend/components/layout/nav.tsx` — Server Component: nav bar with links (/, /brain, /health)
- [ ] `frontend/components/layout/ws-status.tsx` — Client Component: green/red connection indicator

### 7.4 Home Page (`/`)
- [ ] `frontend/app/page.tsx` — Server Component: fetch initial candles + active signals, pass as props
- [ ] `frontend/components/charts/chart-container.tsx` — Client: shared wrapper with ResizeObserver
- [ ] `frontend/components/charts/live-chart.tsx` — Client: Lightweight Charts v5.1.0:
  - [ ] Candlestick series for XAU/USD
  - [ ] Signal overlay price lines: entry (gold), SL (red), TP (green)
  - [ ] Timeframe switcher: 15m | 1h | 4h | D
  - [ ] WebSocket live updates via series.update()
- [ ] `frontend/components/charts/mini-chart.tsx` — Client: reusable smaller chart
- [ ] `frontend/components/charts/timeframe-panel.tsx` — Client: 2x2 CSS Grid of mini charts (15m, 1h, 4h, D)
  - [ ] Each panel: current price, trend direction indicator, active signal count
- [ ] `frontend/components/signals/signal-card.tsx` — Client:
  - [ ] Strategy name, direction badge (LONG green / SHORT red)
  - [ ] Entry / SL / TP prices formatted
  - [ ] Confidence score bar (0-100%)
  - [ ] Expandable Claude reasoning text
  - [ ] Status badge, relative timestamp
- [ ] `frontend/components/signals/signal-feed.tsx` — Client:
  - [ ] Real-time scrollable list via shadcn ScrollArea
  - [ ] Prepends new signals from WebSocket
  - [ ] Filter controls (strategy, status)
- [ ] Layout: `grid grid-cols-1 xl:grid-cols-[1fr_380px]` — charts left, signal feed right sidebar

### 7.5 Brain Dashboard (`/brain`)
- [ ] `frontend/app/brain/page.tsx` — Server Component: fetch all brain data in parallel
- [ ] `frontend/components/brain/strategy-table.tsx` — Server Component:
  - [ ] shadcn Table ranked by Sharpe ratio
  - [ ] Columns: rank, name, win rate, total signals, avg RR, Sharpe, max drawdown
  - [ ] Color coding: win rate > 55% green, < 45% red
- [ ] `frontend/components/charts/pnl-chart.tsx` — Client: Lightweight Charts AreaSeries for cumulative P&L
- [ ] `frontend/components/brain/risk-panel.tsx` — Client:
  - [ ] Daily loss percentage gauge
  - [ ] Consecutive stops counter with warning colors
  - [ ] Circuit breaker status: prominent SYSTEM PAUSED banner with countdown
  - [ ] Position size multiplier indicator
  - [ ] Live updates via WebSocket risk_update messages
- [ ] `frontend/components/brain/decision-log.tsx` — Client:
  - [ ] Scrollable timeline of 30-min pipeline decisions
  - [ ] Each entry: timestamp, active strategies, Claude commentary, signals generated
  - [ ] Auto-scroll to latest
- [ ] `frontend/components/brain/backtest-table.tsx` — Server Component:
  - [ ] Table of Monte Carlo + walk-forward runs
  - [ ] Columns: strategy, window, result (pass/fail/overfit badge), key metrics
- [ ] `frontend/components/brain/params-viewer.tsx` — Server Component:
  - [ ] Active parameters per strategy
  - [ ] Last validated timestamp
  - [ ] Version/history indicator

### 7.6 Health Page (`/health`)
- [ ] `frontend/components/health/health-card.tsx` — Server Component: service status card
- [ ] `frontend/app/health/page.tsx` — Server Component: grid of health cards
  - [ ] APScheduler job status (last run, next run, status)
  - [ ] Database connection status
  - [ ] Redis connection status
  - [ ] Data feed connectivity + last price age

### 7.7 Server/Client Boundary Rules
- [ ] **Server Components** (default): layout, nav, static tables (strategy, backtest, params), health page
- [ ] **Client Components** (`'use client'`): charts (DOM required), WebSocket consumers (signal feed, risk panel, decision log), interactive controls (timeframe switcher)

### 7.8 Verification
- [ ] `npm run dev` starts with Turbopack
- [ ] All pages render with seeded/mock data
- [ ] WebSocket connects and receives live updates
- [ ] Charts render correctly with candle data
- [ ] Signal feed updates in real-time
- [ ] Responsive layout works across breakpoints

---

## Phase 8: Polish & Hardening

### 8.1 Loading States
- [ ] `frontend/app/loading.tsx` — skeleton loading for home page
- [ ] `frontend/app/brain/loading.tsx` — skeleton loading for brain dashboard

### 8.2 Error Handling
- [ ] Error boundaries for chart components (prevent full-page crash)
- [ ] Global exception handler middleware in FastAPI main.py
- [ ] Retry decorator for external API calls (Twelve Data, OANDA, Anthropic) — exponential backoff

### 8.3 Observability
- [ ] Structured logging via structlog (add to backend dependencies)
- [ ] Log all scheduler job runs with timing and outcomes

### 8.4 End-to-End Testing
- [ ] Docker Compose up → seed candles → run pipeline → verify signal on dashboard
- [ ] Backend tests: pytest-asyncio with real DB (testcontainers or Docker)
  - [ ] `tests/test_strategies/` — unit tests per strategy with fixture data
  - [ ] `tests/test_brain/` — decision pipeline + risk manager tests
  - [ ] `tests/test_optimisation/` — Monte Carlo statistical properties
  - [ ] `tests/test_routers/` — integration tests via httpx.AsyncClient

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
4. **Twelve Data primary + OANDA fallback** — free tier adequate with staggered ingestion (~1.5 calls/min)
5. **Cold start graceful degradation** — default params + equal strategy weights until >= 50 resolved signals per strategy
6. **Tailwind v4 CSS-first** — no tailwind.config.js, all theming via @theme directive in globals.css

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
| Next.js 16.2 not yet stable | Fall back to latest canary release, pin in package.json |
| Cold start with no data | Graceful degradation: default params, equal weights, skip Claude ranking |
| APScheduler in single worker | Extract to separate process if horizontal scaling needed later |

---

## Complete File Tree (~65 files)

```
claudeStocks/
├── docker-compose.yml
├── .gitignore
├── .env
├── PRD.md
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── .env.example
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── alembic.ini
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── models.py
│   │   └── repositories/
│   │       ├── __init__.py
│   │       ├── candles.py
│   │       ├── signals.py
│   │       ├── performance.py
│   │       ├── risk.py
│   │       └── decisions.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── signal.py
│   │   ├── performance.py
│   │   └── risk.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── feed.py
│   │   └── candle_ingestion.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── indicators.py
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
│   │   ├── env.py
│   │   └── versions/
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_strategies/
│       ├── test_brain/
│       ├── test_optimisation/
│       └── test_routers/
└── frontend/
    ├── package.json
    ├── next.config.ts
    ├── tsconfig.json
    ├── postcss.config.mjs
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
    │   │   ├── live-chart.tsx
    │   │   ├── mini-chart.tsx
    │   │   ├── timeframe-panel.tsx
    │   │   └── pnl-chart.tsx
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
    │   └── ui/ (shadcn generated)
    └── lib/
        ├── types.ts
        ├── api.ts
        ├── websocket.ts
        └── utils.ts
```
