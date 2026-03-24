"use client";

import { useWebSocket } from "@/lib/websocket";
import { cn } from "@/lib/utils";

export function WsStatus() {
  const { isConnected, retryCount } = useWebSocket();

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span
        className={cn("h-2 w-2 rounded-full", isConnected ? "bg-bull" : "bg-bear")}
      />
      <span>{isConnected ? "Live" : retryCount >= 20 ? "Disconnected" : "Reconnecting..."}</span>
    </div>
  );
}
