import type {
  ABTestResults,
  BacktestRun,
  Candle,
  DecisionLog,
  HealthStatus,
  OptimisedParams,
  PnLPoint,
  RiskState,
  Signal,
  SignalStatus,
  StrategyPerformance,
  Timeframe,
} from "./types";

// Server Components need the full backend URL; client-side uses the rewrite proxy
const isServer = typeof window === "undefined";
const BASE = isServer ? "http://localhost:8000" : "";

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function getCandles(
  symbol: string,
  timeframe: Timeframe,
  limit = 500,
): Promise<Candle[]> {
  return fetchJSON<Candle[]>(
    `${BASE}/api/candles/${symbol}/${timeframe}?limit=${limit}`,
  );
}

export async function getSignals(opts?: {
  strategy?: string;
  status?: SignalStatus;
  limit?: number;
}): Promise<Signal[]> {
  const params = new URLSearchParams();
  if (opts?.strategy) params.set("strategy", opts.strategy);
  if (opts?.status) params.set("status", opts.status);
  if (opts?.limit) params.set("limit", String(opts.limit));
  return fetchJSON<Signal[]>(`${BASE}/api/signals?${params}`);
}

export async function getStrategyPerformance(): Promise<StrategyPerformance[]> {
  return fetchJSON<StrategyPerformance[]>(`${BASE}/api/performance/strategies`);
}

export async function getPnLHistory(): Promise<PnLPoint[]> {
  return fetchJSON<PnLPoint[]>(`${BASE}/api/performance/pnl`);
}

export async function getRiskState(): Promise<RiskState> {
  return fetchJSON<RiskState>(`${BASE}/api/risk/state`);
}

export async function getDecisions(limit = 50): Promise<DecisionLog[]> {
  return fetchJSON<DecisionLog[]>(`${BASE}/api/decisions?limit=${limit}`);
}

export async function getBacktests(limit = 50): Promise<BacktestRun[]> {
  return fetchJSON<BacktestRun[]>(`${BASE}/api/backtests?limit=${limit}`);
}

export async function getActiveParams(): Promise<OptimisedParams[]> {
  return fetchJSON<OptimisedParams[]>(`${BASE}/api/params`);
}

export async function getABTestResults(): Promise<ABTestResults> {
  return fetchJSON<ABTestResults>(`${BASE}/api/ab-tests`);
}

export async function getHealth(): Promise<HealthStatus> {
  return fetchJSON<HealthStatus>(`${BASE}/api/health`);
}
