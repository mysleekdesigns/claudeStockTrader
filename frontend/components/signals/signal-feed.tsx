"use client";

import { useCallback, useState } from "react";
import type { Signal, WSMessage } from "@/lib/types";
import { useWebSocket } from "@/lib/websocket";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { SignalCard } from "./signal-card";

interface SignalFeedProps {
  initialSignals: Signal[];
}

const STRATEGIES = [
  "all",
  "liquidity_sweep",
  "trend_continuation",
  "breakout_expansion",
  "ema_momentum",
];

const STATUSES = ["all", "pending", "active", "won", "lost", "expired"] as const;

export function SignalFeed({ initialSignals }: SignalFeedProps) {
  const [signals, setSignals] = useState<Signal[]>(initialSignals);
  const [strategyFilter, setStrategyFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const handleMessage = useCallback((msg: WSMessage) => {
    if (msg.type === "signal") {
      setSignals((prev) => [msg.data as Signal, ...prev]);
    }
  }, []);

  useWebSocket({ onMessage: handleMessage });

  const filtered = signals.filter((s) => {
    if (strategyFilter !== "all" && s.strategy_name !== strategyFilter) return false;
    if (statusFilter !== "all" && s.status !== statusFilter) return false;
    return true;
  });

  return (
    <div className="flex h-full flex-col rounded-lg border border-border bg-surface">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">Signal Feed</h2>
        <div className="mt-2 flex flex-wrap gap-1">
          {STRATEGIES.map((s) => (
            <Button
              key={s}
              variant={strategyFilter === s ? "default" : "ghost"}
              size="sm"
              onClick={() => setStrategyFilter(s)}
              className="text-[10px]"
            >
              {s === "all" ? "All" : s.replace("_", " ")}
            </Button>
          ))}
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          {STATUSES.map((s) => (
            <Button
              key={s}
              variant={statusFilter === s ? "default" : "ghost"}
              size="sm"
              onClick={() => setStatusFilter(s)}
              className="text-[10px]"
            >
              {s}
            </Button>
          ))}
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="flex flex-col gap-2 p-3">
          {filtered.length === 0 ? (
            <p className="py-8 text-center text-xs text-muted-foreground">No signals</p>
          ) : (
            filtered.map((signal) => <SignalCard key={signal.id} signal={signal} />)
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
