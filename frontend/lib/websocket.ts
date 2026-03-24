"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { WSMessage } from "./types";

interface UseWebSocketOptions {
  url?: string;
  onMessage?: (msg: WSMessage) => void;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  retryCount: number;
}

const MAX_RETRIES = 20;
const RECONNECT_INTERVAL = 3000;

export function useWebSocket(opts: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    url = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/live",
    onMessage,
  } = opts;

  const [isConnected, setIsConnected] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (retryRef.current >= MAX_RETRIES) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      retryRef.current = 0;
      setRetryCount(0);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage;
        onMessageRef.current?.(msg);
      } catch {
        // ignore non-JSON messages like pong
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      wsRef.current = null;
      retryRef.current += 1;
      setRetryCount(retryRef.current);
      if (retryRef.current < MAX_RETRIES) {
        setTimeout(connect, RECONNECT_INTERVAL);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return { isConnected, retryCount };
}
