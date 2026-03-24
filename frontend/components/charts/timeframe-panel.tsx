"use client";

import { MiniChart } from "./mini-chart";
import type { Candle, Signal, Timeframe } from "@/lib/types";

const TIMEFRAMES: Timeframe[] = ["15m", "1h", "4h", "1d"];

interface TimeframePanelProps {
  candlesByTf: Record<Timeframe, Candle[]>;
  signals: Signal[];
}

export function TimeframePanel({ candlesByTf, signals }: TimeframePanelProps) {
  const activeSignals = signals.filter(
    (s) => s.status === "pending" || s.status === "active",
  );

  return (
    <div className="grid grid-cols-2 gap-3">
      {TIMEFRAMES.map((tf) => (
        <MiniChart
          key={tf}
          timeframe={tf}
          candles={candlesByTf[tf] ?? []}
          signalCount={activeSignals.length}
        />
      ))}
    </div>
  );
}
