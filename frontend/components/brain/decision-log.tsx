"use client";

import { useCallback, useState } from "react";
import type { DecisionLog, WSMessage } from "@/lib/types";
import { useWebSocket } from "@/lib/websocket";
import { ScrollArea } from "@/components/ui/scroll-area";
import { relativeTime } from "@/lib/utils";

interface DecisionLogViewProps {
  initialDecisions: DecisionLog[];
}

export function DecisionLogView({ initialDecisions }: DecisionLogViewProps) {
  const [decisions, setDecisions] = useState<DecisionLog[]>(initialDecisions);

  const handleMessage = useCallback((msg: WSMessage) => {
    // Decisions arrive as part of signal events context; we refresh on any signal
    if (msg.type === "signal") {
      // Fetch fresh decisions could be done here, but for now we rely on initial load + page refreshes
    }
  }, []);

  useWebSocket({ onMessage: handleMessage });

  return (
    <div className="rounded-lg border border-border bg-surface">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold">Decision Log</h3>
      </div>
      <ScrollArea className="h-[400px]">
        <div className="flex flex-col gap-2 p-3">
          {decisions.length === 0 ? (
            <p className="py-8 text-center text-xs text-muted-foreground">
              No decisions recorded yet
            </p>
          ) : (
            decisions.map((d) => (
              <div
                key={d.id}
                className="rounded-md border border-border bg-surface-raised p-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-muted">
                    {relativeTime(d.created_at)}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    Risk: {d.risk_status}
                  </span>
                </div>
                <div className="mt-1.5 text-xs">
                  <span className="text-muted-foreground">Strategies: </span>
                  {Object.keys(d.ranked_strategies).join(", ") || "None"}
                </div>
                <div className="mt-1 text-xs">
                  <span className="text-muted-foreground">Size mult: </span>
                  <span className="font-mono">{d.position_size_multiplier.toFixed(2)}x</span>
                </div>
                {d.notes && (
                  <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                    {d.notes}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
