"use client";

import { useCallback, useState } from "react";
import type { RiskState, WSMessage } from "@/lib/types";
import { useWebSocket } from "@/lib/websocket";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPct } from "@/lib/utils";

interface RiskPanelProps {
  initialRisk: RiskState | null;
}

export function RiskPanel({ initialRisk }: RiskPanelProps) {
  const [risk, setRisk] = useState<RiskState | null>(initialRisk);

  const handleMessage = useCallback((msg: WSMessage) => {
    if (msg.type === "risk_update") {
      setRisk(msg.data as RiskState);
    }
  }, []);

  useWebSocket({ onMessage: handleMessage });

  if (!risk) {
    return (
      <Card>
        <CardHeader><CardTitle>Risk Status</CardTitle></CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">No risk data available</p>
        </CardContent>
      </Card>
    );
  }

  const dailyLossPct = risk.daily_loss_pct * 100;
  const dailyLossMax = 2;
  const gaugeWidth = Math.min((dailyLossPct / dailyLossMax) * 100, 100);
  const gaugeColor = dailyLossPct > 1.5 ? "bg-bear" : dailyLossPct > 1 ? "bg-gold-500" : "bg-bull";

  const stopsColor =
    risk.consecutive_stops >= 6 ? "text-bear" : risk.consecutive_stops >= 4 ? "text-gold-400" : "text-foreground";

  return (
    <div className="space-y-3">
      {risk.is_shutdown && (
        <div className="rounded-lg border border-bear bg-bear/10 p-4 text-center">
          <p className="text-sm font-bold text-bear">SYSTEM PAUSED</p>
          {risk.shutdown_until && (
            <p className="mt-1 text-xs text-muted-foreground">
              Until {new Date(risk.shutdown_until).toLocaleString()}
            </p>
          )}
        </div>
      )}

      <Card>
        <CardHeader><CardTitle>Daily Loss</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center justify-between text-xs">
            <span className="font-mono">{formatPct(risk.daily_loss_pct)}</span>
            <span className="text-muted-foreground">/ {dailyLossMax}%</span>
          </div>
          <div className="mt-2 h-2 w-full rounded-full bg-surface-raised">
            <div
              className={`h-full rounded-full transition-all ${gaugeColor}`}
              style={{ width: `${gaugeWidth}%` }}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Consecutive Stops</CardTitle></CardHeader>
        <CardContent>
          <p className={`font-mono text-2xl font-bold ${stopsColor}`}>
            {risk.consecutive_stops}
            <span className="text-sm text-muted-foreground"> / 8</span>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
