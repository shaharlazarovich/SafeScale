import { useState, useEffect, useRef, useCallback } from "react";
import type { ScanProgress } from "@/types";

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

interface UseScanProgressResult {
  progress: ScanProgress | null;
  isConnected: boolean;
  error: string | null;
}

export function useScanProgress(
  scanId: string | undefined,
): UseScanProgressResult {
  const [progress, setProgress] = useState<ScanProgress | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    if (!scanId) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws/scans/${scanId}/progress`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
      reconnectAttemptsRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ScanProgress;
        setProgress(data);
      } catch {
        setError("Failed to parse progress update");
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection error");
    };

    ws.onclose = (event) => {
      setIsConnected(false);
      wsRef.current = null;

      if (
        !event.wasClean &&
        reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS
      ) {
        reconnectAttemptsRef.current += 1;
        reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };
  }, [scanId]);

  useEffect(() => {
    connect();

    return () => {
      clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.close(1000, "Component unmounted");
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { progress, isConnected, error };
}
