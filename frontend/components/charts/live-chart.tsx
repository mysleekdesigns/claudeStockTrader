"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createChart, CandlestickSeries, type IChartApi, type ISeriesApi, type CandlestickData, type Time, ColorType } from "lightweight-charts";
import type { Candle, Signal, Timeframe, WSMessage } from "@/lib/types";
import { useWebSocket } from "@/lib/websocket";
import { Button } from "@/components/ui/button";
import { WsStatus } from "@/components/layout/ws-status";

const TIMEFRAMES: Timeframe[] = ["15m", "1h", "4h", "1d"];

function toChartData(candle: Candle): CandlestickData<Time> {
  return {
    time: (new Date(candle.timestamp).getTime() / 1000) as Time,
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
  };
}

interface LiveChartProps {
  initialCandles: Candle[];
  initialSignals: Signal[];
}

export function LiveChart({ initialCandles, initialSignals }: LiveChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [activeTimeframe, setActiveTimeframe] = useState<Timeframe>("1h");
  const [candles, setCandles] = useState<Candle[]>(initialCandles);
  const [signals, setSignals] = useState<Signal[]>(initialSignals);

  const handleMessage = useCallback((msg: WSMessage) => {
    if (msg.type === "candle") {
      const candle = msg.data as Candle;
      if (candle.timeframe === activeTimeframe) {
        setCandles((prev) => [...prev, candle]);
        if (seriesRef.current) {
          seriesRef.current.update(toChartData(candle));
        }
      }
    } else if (msg.type === "signal") {
      setSignals((prev) => [msg.data as Signal, ...prev]);
    }
  }, [activeTimeframe]);

  useWebSocket({ onMessage: handleMessage });

  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: "#111118" },
        textColor: "#a1a1aa",
        fontFamily: "Inter, sans-serif",
        fontSize: 12,
      },
      grid: {
        vertLines: { color: "#1a1a24" },
        horzLines: { color: "#1a1a24" },
      },
      crosshair: {
        vertLine: { color: "#facc15", width: 1, style: 2 },
        horzLine: { color: "#facc15", width: 1, style: 2 },
      },
      timeScale: {
        borderColor: "#2a2a3a",
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: "#2a2a3a",
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const filteredCandles = candles.filter((c) => c.timeframe === activeTimeframe);
    const chartData = filteredCandles
      .map(toChartData)
      .sort((a, b) => (a.time as number) - (b.time as number));
    series.setData(chartData);

    // Add signal price lines
    const activeSignals = signals.filter(
      (s) => s.status === "pending" || s.status === "active",
    );
    for (const signal of activeSignals) {
      series.createPriceLine({
        price: signal.entry_price,
        color: "#facc15",
        lineWidth: 1,
        lineStyle: 2,
        title: `Entry (${signal.strategy_name})`,
      });
      series.createPriceLine({
        price: signal.stop_loss,
        color: "#ef4444",
        lineWidth: 1,
        lineStyle: 2,
        title: "SL",
      });
      series.createPriceLine({
        price: signal.take_profit,
        color: "#22c55e",
        lineWidth: 1,
        lineStyle: 2,
        title: "TP",
      });
    }

    chart.timeScale().fitContent();
    chartRef.current = chart;
    seriesRef.current = series;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [activeTimeframe, candles, signals]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gold-400">XAU/USD</span>
          <div className="flex gap-1">
            {TIMEFRAMES.map((tf) => (
              <Button
                key={tf}
                variant={tf === activeTimeframe ? "default" : "ghost"}
                size="sm"
                onClick={() => setActiveTimeframe(tf)}
              >
                {tf}
              </Button>
            ))}
          </div>
        </div>
        <WsStatus />
      </div>
      <div ref={chartContainerRef} className="flex-1 min-h-[400px]" />
    </div>
  );
}
