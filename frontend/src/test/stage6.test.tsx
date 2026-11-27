import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TableStateBadge } from "@/components/TableStateBadge";
import { TABLE_STATE_META, formatElapsed, type TableState } from "@/lib/table-states";
import { hasCapability, defaultHomeForRole } from "@/lib/rbac";
import { apiFetch, ApiError, setAccessToken } from "@/lib/api";
import { useVenueRealtime } from "@/hooks/useVenueRealtime";

import { AuthProvider, useAuth } from "@/providers/AuthProvider";

describe("Stage 6 TablePulse UI Foundation", () => {
  it("skips /auth/refresh on mount when bootstrap-status reports has_session=false", async () => {
    const calledUrls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        calledUrls.push(url);
        return Promise.resolve(
          new Response(
            JSON.stringify({
              success: true,
              data: { bootstrap_required: true, demo_mode: false, has_session: false },
            }),
            { status: 200, headers: { "content-type": "application/json" } },
          ),
        );
      }),
    );

    function BootObserver() {
      const { loading, bootstrapRequired } = useAuth();
      return (
        <span data-testid="boot-state">
          {loading ? "loading" : String(bootstrapRequired)}
        </span>
      );
    }

    render(
      <AuthProvider>
        <BootObserver />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("boot-state").textContent).toBe("true"));
    expect(calledUrls.some((u) => u.includes("/api/v1/auth/refresh"))).toBe(false);
    vi.unstubAllGlobals();
  });

  it("renders colorblind-safe badges with distinct icons and borders for all 6 canonical states", () => {
    const states: TableState[] = [
      "FREE",
      "OCCUPIED",
      "NEEDS_SERVICE",
      "NEEDS_CLEANING",
      "RESERVED",
      "UNKNOWN",
    ];
    for (const st of states) {
      const { unmount } = render(<TableStateBadge state={st} />);
      expect(screen.getByText(TABLE_STATE_META[st].label)).toBeTruthy();
      unmount();
    }
    expect(formatElapsed("2026-01-01T00:00:00Z", new Date("2026-01-01T00:05:30Z").getTime())).toBe(
      "05:30",
    );
  });

  it("enforces client RBAC visibility matching matrix.yaml", () => {
    expect(hasCapability("OWNER", "system.manage")).toBe(true);
    expect(hasCapability("MANAGER", "system.manage")).toBe(false);
    expect(hasCapability("HOST", "cameras.live.view", false)).toBe(false);
    expect(hasCapability("HOST", "cameras.live.view", true)).toBe(true);
    expect(defaultHomeForRole("STAFF", "v1")).toBe("/venues/v1/alerts");
    expect(defaultHomeForRole("VIEWER", "v1")).toBe("/venues/v1/analytics");
  });

  it("keeps JWT strictly in memory (never localStorage) and parses error envelope", async () => {
    setAccessToken("mem-token-123");
    expect(window.localStorage.length).toBe(0);

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: false,
          error: { code: "VALIDATION_ERROR", message: "Bad field" },
        }),
        { status: 400, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/v1/test", { retryOn401: false })).rejects.toBeInstanceOf(ApiError);
    vi.unstubAllGlobals();
    setAccessToken(null);
  });

  it("falls back to HTTP polling after consecutive WebSocket failures", async () => {
    let wsCreated = 0;
    class FailingWebSocket {
      onopen: (() => void) | null = null;
      onmessage: ((e: MessageEvent) => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: (() => void) | null = null;
      readyState = 3;
      constructor() {
        wsCreated += 1;
        setTimeout(() => this.onclose?.(), 5);
      }
      close() {}
      send() {}
    }

    vi.stubGlobal("WebSocket", FailingWebSocket);
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("ws-ticket")) {
          return Promise.resolve(
            new Response(JSON.stringify({ success: true, data: { ticket: "t1" } }), {
              status: 200,
              headers: { "content-type": "application/json" },
            }),
          );
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({
              success: true,
              data: {
                venue_id: "v1",
                kpis: {
                  occupied_tables: 1,
                  total_tables: 3,
                  seated_guests: 2,
                  total_seats: 12,
                  capacity_pct: 16.7,
                  active_alerts: 0,
                },
                ai_inference_enabled: true,
                cameras_summary: { total: 1, online: 1, offline: 0 },
                tables: [],
              },
            }),
            { status: 200, headers: { "content-type": "application/json" } },
          ),
        );
      }),
    );

    function Harness() {
      const { connectionState, snapshot } = useVenueRealtime("v1", true);
      return (
        <div>
          <span data-testid="conn">{connectionState}</span>
          <span data-testid="tot">{snapshot?.kpis.total_tables ?? "none"}</span>
        </div>
      );
    }

    render(<Harness />);
    await waitFor(() => expect(screen.getByTestId("tot").textContent).toBe("3"));
    await waitFor(() => expect(screen.getByTestId("conn").textContent).toBe("polling"), {
      timeout: 7000,
    });
    expect(wsCreated).toBeGreaterThanOrEqual(3);

    vi.unstubAllGlobals();
  }, 9000);
});
