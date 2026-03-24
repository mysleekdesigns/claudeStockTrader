"use client";

import { useState } from "react";
import type { Signal } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { formatPrice, relativeTime } from "@/lib/utils";

interface SignalCardProps {
  signal: Signal;
}

export function SignalCard({ signal }: SignalCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isLong = signal.direction === "long";
  const confidencePct = Math.round(signal.confidence_score * 100);

  const statusVariant = {
    pending: "secondary" as const,
    active: "default" as const,
    won: "success" as const,
    lost: "destructive" as const,
    expired: "outline" as const,
  }[signal.status];

  return (
    <div className="rounded-lg border border-border bg-surface p-3 transition-colors hover:bg-surface-raised">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Badge variant={isLong ? "success" : "destructive"}>
            {signal.direction?.toUpperCase() ?? "—"}
          </Badge>
          <span className="text-xs font-medium text-muted-foreground">
            {signal.strategy_name}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={statusVariant}>{signal.status}</Badge>
          <span className="text-[10px] text-muted">{relativeTime(signal.created_at)}</span>
        </div>
      </div>

      <div className="mt-2 grid grid-cols-3 gap-2 font-mono text-xs">
        <div>
          <span className="text-muted-foreground">Entry</span>
          <p className="text-gold-400">{formatPrice(signal.entry_price)}</p>
        </div>
        <div>
          <span className="text-muted-foreground">SL</span>
          <p className="text-bear">{formatPrice(signal.stop_loss)}</p>
        </div>
        <div>
          <span className="text-muted-foreground">TP</span>
          <p className="text-bull">{formatPrice(signal.take_profit)}</p>
        </div>
      </div>

      <div className="mt-2">
        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <span>Confidence</span>
          <span>{confidencePct}%</span>
        </div>
        <div className="mt-1 h-1.5 w-full rounded-full bg-surface-raised">
          <div
            className="h-full rounded-full bg-gold-500 transition-all"
            style={{ width: `${confidencePct}%` }}
          />
        </div>
      </div>

      {signal.reasoning && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 text-[10px] text-gold-400 hover:underline"
        >
          {expanded ? "Hide reasoning" : "Show reasoning"}
        </button>
      )}
      {expanded && signal.reasoning && (
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          {signal.reasoning}
        </p>
      )}
    </div>
  );
}
