import { getCandles, getSignals } from "@/lib/api";
import type { Candle, Timeframe } from "@/lib/types";
import { LiveChart } from "@/components/charts/live-chart";
import { TimeframePanel } from "@/components/charts/timeframe-panel";
import { SignalFeed } from "@/components/signals/signal-feed";

const TIMEFRAMES: Timeframe[] = ["15m", "1h", "4h", "1d"];

export default async function HomePage() {
  let candlesByTf: Record<Timeframe, Candle[]> = {
    "15m": [],
    "1h": [],
    "4h": [],
    "1d": [],
  };
  let signals = [];

  try {
    const candleResults = await Promise.all(
      TIMEFRAMES.map((tf) => getCandles("XAU/USD", tf, 500)),
    );
    for (let i = 0; i < TIMEFRAMES.length; i++) {
      candlesByTf[TIMEFRAMES[i]] = candleResults[i];
    }
  } catch {
    // Backend may not be running; render with empty data
  }

  try {
    signals = await getSignals({ limit: 100 });
  } catch {
    // Backend may not be running
  }

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_380px]">
      <div className="space-y-4">
        <div className="rounded-lg border border-border bg-surface">
          <LiveChart initialCandles={candlesByTf["1h"]} initialSignals={signals} />
        </div>
        <TimeframePanel candlesByTf={candlesByTf} signals={signals} />
      </div>
      <div className="h-[calc(100vh-8rem)]">
        <SignalFeed initialSignals={signals} />
      </div>
    </div>
  );
}
