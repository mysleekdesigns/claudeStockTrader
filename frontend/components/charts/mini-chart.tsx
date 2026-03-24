"use client";

import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries, type CandlestickData, type Time, ColorType } from "lightweight-charts";
import type { Candle, Timeframe } from "@/lib/types";
import { formatPrice } from "@/lib/utils";

interface MiniChartProps {
  candles: Candle[];
  timeframe: Timeframe;
  signalCount?: number;
}

export function MiniChart({ candles, timeframe, signalCount = 0 }: MiniChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const last = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const trendUp = last && prev ? last.close >= prev.close : true;

  useEffect(() => {
    const container = containerRef.current;
    if (!container || candles.length === 0) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: "#111118" },
        textColor: "#a1a1aa",
        fontSize: 10,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: "#1a1a24" },
      },
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      crosshair: {
        vertLine: { visible: false },
        horzLine: { visible: false },
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

    const data: CandlestickData<Time>[] = candles
      .map((c) => ({
        time: (new Date(c.timestamp).getTime() / 1000) as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
      .sort((a, b) => (a.time as number) - (b.time as number));
    series.setData(data);
    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [candles]);

  return (
    <div className="flex flex-col rounded-lg border border-border bg-surface overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border">
        <span className="text-xs font-medium text-muted-foreground">{timeframe}</span>
        <div className="flex items-center gap-2">
          {last && (
            <span className={`font-mono text-xs ${trendUp ? "text-bull" : "text-bear"}`}>
              {formatPrice(last.close)}
            </span>
          )}
          {signalCount > 0 && (
            <span className="rounded bg-gold-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-gold-400">
              {signalCount}
            </span>
          )}
        </div>
      </div>
      <div ref={containerRef} className="h-[140px]" />
    </div>
  );
}
