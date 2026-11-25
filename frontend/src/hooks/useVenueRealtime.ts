"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiBaseUrl, apiFetch, ApiError } from "@/lib/api";
import type { ConnectionState } from "@/components/AppShell";
import type { FloorSnapshot, FloorTable } from "@/types/floor";

function toWsUrl(httpUrl: string): string {
  if (httpUrl.startsWith("https://")) {
    return "wss://" + httpUrl.slice("https://".length);
  }
  if (httpUrl.startsWith("http://")) {
    return "ws://" + httpUrl.slice("http://".length);
  }
  return httpUrl;
}

function recomputeKpis(tables: FloorTable[], prevAlerts: number) {
  const total_tables = tables.length;
  const occupied_tables = tables.filter(
    (t) => t.current_state === "OCCUPIED" || t.current_state === "NEEDS_SERVICE",
  ).length;
  const total_seats = tables.reduce((acc, t) => acc + t.seat_capacity, 0);
  const seated_guests = tables
    .filter((t) => t.current_state === "OCCUPIED" || t.current_state === "NEEDS_SERVICE")
    .reduce((acc, t) => acc + t.current_guest_count, 0);
  const capacity_pct =
    total_seats > 0 ? Math.round((seated_guests / total_seats) * 1000) / 10 : 0;
  return {
    occupied_tables,
    total_tables,
    seated_guests,
    total_seats,
    capacity_pct,
    active_alerts: prevAlerts,
  };
}

export function useVenueRealtime(venueId: string | undefined, enabled = true) {
  const [snapshot, setSnapshot] = useState<FloorSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>("reconnecting");
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const retryCountRef = useRef(0);
  const pollTimerRef = useRef<number | null>(null);
  const toastTimerRef = useRef<number | null>(null);

  const pushToast = useCallback((msg: string) => {
    setToastMessage(msg);
    if (toastTimerRef.current) {
      window.clearTimeout(toastTimerRef.current);
    }
    toastTimerRef.current = window.setTimeout(() => setToastMessage(null), 5000);
  }, []);

  const fetchSnapshot = useCallback(async () => {
    if (!venueId) return;
    try {
      const data = await apiFetch<FloorSnapshot>(`/api/v1/venues/${venueId}/floor-state`);
      setSnapshot(data);
      setError(null);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Failed to load floor state from API";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [venueId]);

  useEffect(() => {
    if (!venueId || !enabled) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    let ws: WebSocket | null = null;
    let pingTimer: number | null = null;
    let reconnectTimer: number | null = null;

    const startPolling = () => {
      if (pollTimerRef.current) return;
      setConnectionState("polling");
      pollTimerRef.current = window.setInterval(() => {
        if (!cancelled) {
          void fetchSnapshot();
        }
      }, 5000);
    };

    const stopPolling = () => {
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };

    const connectWs = async () => {
      if (cancelled) return;
      try {
        const ticketRes = await apiFetch<{ ticket: string }>("/api/v1/auth/ws-ticket", {
          method: "POST",
        });
        if (cancelled) return;

        const baseWs =
          process.env.NEXT_PUBLIC_WS_BASE_URL || toWsUrl(apiBaseUrl());
        const url = `${baseWs.replace(/\/$/, "")}/api/v1/ws/venues/${venueId}?ticket=${encodeURIComponent(ticketRes.ticket)}`;

        ws = new WebSocket(url);

        ws.onopen = () => {
          if (cancelled) return;
          retryCountRef.current = 0;
          stopPolling();
          setConnectionState("live");
          pingTimer = window.setInterval(() => {
            if (ws?.readyState === WebSocket.OPEN) {
              ws.send("ping");
            }
          }, 20000);
        };

        ws.onmessage = (evt) => {
          if (cancelled) return;
          try {
            const msg = JSON.parse(evt.data);
            if (msg.type === "floor.snapshot" && msg.data) {
              setSnapshot(msg.data as FloorSnapshot);
              setLoading(false);
              setError(null);
            } else if (msg.type === "table.state_changed" && msg.data) {
              const d = msg.data;
              setSnapshot((prev) => {
                if (!prev) return prev;
                const nextTables = prev.tables.map((tbl) =>
                  tbl.id === d.table_id
                    ? {
                        ...tbl,
                        current_state: d.new_state,
                        current_guest_count: d.guest_count ?? tbl.current_guest_count,
                        occupied_since:
                          "occupied_since" in d ? d.occupied_since : tbl.occupied_since,
                        current_confidence: d.confidence ?? tbl.current_confidence,
                      }
                    : tbl,
                );
                return {
                  ...prev,
                  tables: nextTables,
                  kpis: recomputeKpis(nextTables, prev.kpis.active_alerts),
                };
              });
              if (d.toast_message) {
                pushToast(String(d.toast_message));
              }
            } else if (msg.type === "alert.created" || msg.type === "alert.updated") {
              void fetchSnapshot();
              if (msg.data?.message) {
                pushToast(String(msg.data.message));
              }
            } else if (
              (msg.type === "system.ai_paused" || msg.type === "system.kill_switch_changed") &&
              msg.data
            ) {
              const enabled =
                "ai_inference_enabled" in msg.data
                  ? Boolean(msg.data.ai_inference_enabled)
                  : Boolean(msg.data.enabled);
              setSnapshot((prev) =>
                prev ? { ...prev, ai_inference_enabled: enabled } : prev,
              );
              pushToast(enabled ? "AI Inference Resumed" : "AI Inference Paused");
            }
          } catch {
            // Ignore malformed WS frame
          }
        };

        ws.onerror = () => {
          // Handled via onclose backoff
        };

        ws.onclose = () => {
          if (pingTimer) {
            window.clearInterval(pingTimer);
            pingTimer = null;
          }
          if (cancelled) return;

          retryCountRef.current += 1;
          if (retryCountRef.current >= 3) {
            startPolling();
            return;
          }
          setConnectionState("reconnecting");
          const backoffMs = Math.min(1000 * retryCountRef.current, 4000);
          reconnectTimer = window.setTimeout(() => {
            void connectWs();
          }, backoffMs);
        };
      } catch {
        retryCountRef.current += 1;
        if (retryCountRef.current >= 3) {
          startPolling();
        } else {
          setConnectionState("reconnecting");
          reconnectTimer = window.setTimeout(() => {
            void connectWs();
          }, 1500);
        }
      }
    };

    void fetchSnapshot();
    void connectWs();

    return () => {
      cancelled = true;
      if (pingTimer) window.clearInterval(pingTimer);
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      stopPolling();
      if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
      if (ws) {
        ws.close();
      }
    };
  }, [venueId, enabled, fetchSnapshot, pushToast]);

  return {
    snapshot,
    loading,
    error,
    connectionState,
    toastMessage,
    refresh: fetchSnapshot,
    clearToast: () => setToastMessage(null),
  };
}
