"use client";

import { useEffect, useRef } from "react";
import { createChart, AreaSeries, type Time, ColorType } from "lightweight-charts";
import type { PnLPoint } from "@/lib/types";

interface PnLChartProps {
  data: PnLPoint[];
}

export function PnLChart({ data }: PnLChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || data.length === 0) return;

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
      rightPriceScale: { borderColor: "#2a2a3a" },
      timeScale: { borderColor: "#2a2a3a", timeVisible: true },
    });

    const lastPnl = data[data.length - 1]?.cumulative_pnl ?? 0;
    const lineColor = lastPnl >= 0 ? "#22c55e" : "#ef4444";
    const topColor = lastPnl >= 0 ? "rgba(34, 197, 94, 0.3)" : "rgba(239, 68, 68, 0.3)";
    const bottomColor = lastPnl >= 0 ? "rgba(34, 197, 94, 0.0)" : "rgba(239, 68, 68, 0.0)";

    const series = chart.addSeries(AreaSeries, {
      lineColor,
      topColor,
      bottomColor,
      lineWidth: 2,
    });

    series.setData(
      data.map((p) => ({
        time: (new Date(p.timestamp).getTime() / 1000) as Time,
        value: p.cumulative_pnl,
      })),
    );

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
  }, [data]);

  return <div ref={containerRef} className="h-[300px] w-full" />;
}
