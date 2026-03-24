export type Timeframe = "15m" | "1h" | "4h" | "1d";

export type SignalDirection = "long" | "short";

export type SignalStatus = "pending" | "active" | "won" | "lost" | "expired";

export type BacktestRunType = "monte_carlo" | "walk_forward" | "reoptimise";

export type BacktestResultType = "pass" | "fail" | "overfit";

export interface Candle {
  id: number;
  symbol: string;
  timeframe: Timeframe;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Signal {
  id: number;
  strategy_name: string;
  direction: SignalDirection;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  confidence_score: number;
  reasoning: string | null;
  status: SignalStatus;
  pips_result: number | null;
  created_at: string;
  resolved_at: string | null;
}

export interface StrategyPerformance {
  id: number;
  strategy_name: string;
  window_days: number;
  win_rate: number;
  avg_rr: number;
  total_signals: number;
  sharpe_ratio: number;
  max_drawdown: number;
  updated_at: string;
}

export interface PnLPoint {
  timestamp: string;
  cumulative_pnl: number;
  strategy_name: string | null;
}

export interface RiskState {
  id: number;
  date: string;
  daily_loss_pct: number;
  consecutive_stops: number;
  is_shutdown: boolean;
  shutdown_until: string | null;
}

export interface DecisionLog {
  id: number;
  ranked_strategies: Record<string, unknown>;
  risk_status: string;
  position_size_multiplier: number;
  notes: string | null;
  created_at: string;
}

export interface BacktestRun {
  id: number;
  run_type: BacktestRunType;
  window_days: number;
  train_start: string | null;
  test_start: string | null;
  test_end: string | null;
  result: BacktestResultType;
  params_used: Record<string, unknown> | null;
  metrics: Record<string, unknown> | null;
  created_at: string;
}

export interface OptimisedParams {
  id: number;
  strategy_name: string;
  params: Record<string, unknown>;
  is_active: boolean;
  validated_at: string | null;
}

export interface ABVariantSummary {
  variant_name: string;
  total_cycles: number;
  total_signals: number;
  total_won: number;
  total_lost: number;
  win_rate: number;
  is_significant: boolean;
  p_value: number | null;
}

export interface ABTestResults {
  variants: ABVariantSummary[];
  significant: boolean;
  p_value: number | null;
  recommendation: string;
}

export interface HealthStatus {
  status: string;
  database: string;
  redis: string;
  feed: string;
  scheduler: string;
}

export interface WSMessage {
  type: "candle" | "signal" | "risk_update";
  data: Candle | Signal | RiskState;
}
