"use client";

import React, { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { LayoutGrid, List, RefreshCw, Search } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { TableDetailDrawer } from "@/components/TableDetailDrawer";
import { TableStateBadge } from "@/components/TableStateBadge";
import { useVenueRealtime } from "@/hooks/useVenueRealtime";
import { formatElapsed, TABLE_STATE_META, type TableState } from "@/lib/table-states";
import { useAuth } from "@/providers/AuthProvider";
import type { FloorTable } from "@/types/floor";

const FloorCanvas = dynamic(() => import("@/components/FloorCanvas"), {
  ssr: false,
  loading: () => (
    <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
      Initializing 2D floor canvas...
    </div>
  ),
});

const FILTER_STATES: Array<"ALL" | TableState> = [
  "ALL",
  "FREE",
  "OCCUPIED",
  "NEEDS_SERVICE",
  "NEEDS_CLEANING",
  "RESERVED",
  "UNKNOWN",
];

export default function LiveFloorPage() {
  const params = useParams<{ venueId: string }>();
  const venueId = params?.venueId;
  const { user, loading: authLoading } = useAuth();

  const { snapshot, loading, error, connectionState, toastMessage, refresh } =
    useVenueRealtime(venueId, Boolean(user));

  const [viewMode, setViewMode] = useState<"canvas" | "list">("canvas");
  const [sectionFilter, setSectionFilter] = useState("ALL");
  const [stateFilter, setStateFilter] = useState<"ALL" | TableState>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTableId, setSelectedTableId] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const t = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  const sections = useMemo(() => {
    const s = new Set<string>();
    for (const tbl of snapshot?.tables || []) {
      s.add(tbl.section_name);
    }
    return ["ALL", ...Array.from(s).sort()];
  }, [snapshot]);

  const filteredTables = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return (snapshot?.tables || []).filter((tbl) => {
      if (sectionFilter !== "ALL" && tbl.section_name !== sectionFilter) return false;
      if (stateFilter !== "ALL" && tbl.current_state !== stateFilter) return false;
      if (q && !tbl.table_code.toLowerCase().includes(q) && !tbl.section_name.toLowerCase().includes(q)) {
        return false;
      }
      return true;
    });
  }, [snapshot, sectionFilter, stateFilter, searchQuery]);

  const needsActionCount = useMemo(
    () =>
      (snapshot?.tables || []).filter(
        (t) => t.current_state === "NEEDS_SERVICE" || t.current_state === "NEEDS_CLEANING",
      ).length,
    [snapshot],
  );

  const occupiedSummary = snapshot
    ? `${snapshot.kpis.occupied_tables}/${snapshot.kpis.total_tables} tables · ${snapshot.kpis.seated_guests} guests`
    : undefined;

  if (!authLoading && !user) {
    return (
      <main className="mx-auto max-w-lg p-6 text-center">
        <h1 className="text-xl font-bold">Sign in required</h1>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Please sign in to access live floor operations.
        </p>
        <Link
          href="/login"
          className="mt-4 inline-block rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-sm font-semibold text-white"
        >
          Go to Login
        </Link>
      </main>
    );
  }

  return (
    <AppShell
      venueId={venueId}
      connectionState={connectionState}
      occupiedSummary={occupiedSummary}
      activeAlertsCount={snapshot?.kpis.active_alerts || 0}
      aiPaused={snapshot ? !snapshot.ai_inference_enabled : false}
      toastMessage={toastMessage}
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Live Floor Map</h1>
            <p className="text-xs text-[var(--text-secondary)]">
              Real-time occupancy, service timers, and manual floor overrides
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void refresh()}
              className="inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold hover:opacity-80"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              Refresh
            </button>
            <div
              role="group"
              aria-label="Floor view mode"
              className="inline-flex rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-0.5"
            >
              <button
                type="button"
                onClick={() => setViewMode("canvas")}
                aria-pressed={viewMode === "canvas"}
                className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-semibold ${
                  viewMode === "canvas"
                    ? "bg-[var(--accent-primary)] text-white"
                    : "text-[var(--text-secondary)]"
                }`}
              >
                <LayoutGrid className="h-3.5 w-3.5" aria-hidden="true" />
                Map
              </button>
              <button
                type="button"
                onClick={() => setViewMode("list")}
                aria-pressed={viewMode === "list"}
                className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-semibold ${
                  viewMode === "list"
                    ? "bg-[var(--accent-primary)] text-white"
                    : "text-[var(--text-secondary)]"
                }`}
              >
                <List className="h-3.5 w-3.5" aria-hidden="true" />
                List
              </button>
            </div>
          </div>
        </div>

        {/* Top 4 KPI summary cards */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="tp-glass rounded-xl border p-3">
            <p className="text-xs font-medium text-[var(--text-secondary)]">Occupied Tables</p>
            <p className="mt-1 text-2xl font-bold">
              {snapshot ? `${snapshot.kpis.occupied_tables} / ${snapshot.kpis.total_tables}` : "—"}
            </p>
          </div>
          <div className="tp-glass rounded-xl border p-3">
            <p className="text-xs font-medium text-[var(--text-secondary)]">Seated Guests</p>
            <p className="mt-1 text-2xl font-bold">
              {snapshot ? `${snapshot.kpis.seated_guests} / ${snapshot.kpis.total_seats}` : "—"}
            </p>
          </div>
          <div className="tp-glass rounded-xl border p-3">
            <p className="text-xs font-medium text-[var(--text-secondary)]">Needs Action</p>
            <p className="mt-1 text-2xl font-bold text-amber-600">{needsActionCount}</p>
          </div>
          <div className="tp-glass rounded-xl border p-3">
            <p className="text-xs font-medium text-[var(--text-secondary)]">Floor Capacity</p>
            <p className="mt-1 text-2xl font-bold">
              {snapshot ? `${snapshot.kpis.capacity_pct}%` : "—"}
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="tp-glass flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <label className="relative flex items-center">
              <Search
                className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-[var(--text-secondary)]"
                aria-hidden="true"
              />
              <input
                type="search"
                aria-label="Search tables"
                placeholder="Search table code..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] py-1.5 pl-8 pr-3 text-xs"
              />
            </label>
            <select
              aria-label="Filter by section"
              value={sectionFilter}
              onChange={(e) => setSectionFilter(e.target.value)}
              className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-medium"
            >
              {sections.map((sec) => (
                <option key={sec} value={sec}>
                  {sec === "ALL" ? "All Sections" : sec}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by state">
            {FILTER_STATES.map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStateFilter(st)}
                aria-pressed={stateFilter === st}
                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
                  stateFilter === st
                    ? "bg-[var(--accent-primary)] text-white"
                    : "border border-[var(--border-subtle)] bg-[var(--surface-solid)] text-[var(--text-secondary)]"
                }`}
              >
                {st === "ALL" ? "All States" : TABLE_STATE_META[st].label}
              </button>
            ))}
          </div>
        </div>

        {/* Error & Loading states */}
        {error && (
          <div
            role="alert"
            className="flex items-center justify-between rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-800"
          >
            <span>{error}</span>
            <button
              type="button"
              onClick={() => void refresh()}
              className="rounded-lg bg-red-700 px-3 py-1.5 text-xs font-semibold text-white"
            >
              Retry
            </button>
          </div>
        )}

        {loading && !snapshot && (
          <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
            Loading live floor snapshot...
          </div>
        )}

        {snapshot && snapshot.tables.length === 0 && (
          <div className="tp-glass rounded-xl border p-8 text-center">
            <h2 className="text-base font-bold">No tables calibrated yet</h2>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Add a camera and draw table polygons to begin live occupancy tracking.
            </p>
            <Link
              href={`/venues/${venueId}/settings/cameras`}
              className="mt-4 inline-block rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white"
            >
              Configure Cameras & Calibration
            </Link>
          </div>
        )}

        {snapshot && snapshot.tables.length > 0 && (
          <div
            className={`grid grid-cols-1 gap-4 ${
              selectedTableId ? "xl:grid-cols-[1fr_390px]" : ""
            }`}
          >
            <div className="flex flex-col gap-3">
              {viewMode === "canvas" ? (
                <FloorCanvas
                  tables={filteredTables}
                  selectedTableId={selectedTableId}
                  nowMs={nowMs}
                  onSelectTable={(tbl: FloorTable) => setSelectedTableId(tbl.id)}
                />
              ) : (
                <div className="tp-glass overflow-x-auto rounded-xl border">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-[var(--border-subtle)] bg-[var(--surface-solid)] text-xs uppercase text-[var(--text-secondary)]">
                      <tr>
                        <th className="px-4 py-3">Table</th>
                        <th className="px-4 py-3">Section</th>
                        <th className="px-4 py-3">State</th>
                        <th className="px-4 py-3">Guests</th>
                        <th className="px-4 py-3">Dwell</th>
                        <th className="px-4 py-3">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border-subtle)]">
                      {filteredTables.map((tbl) => (
                        <tr
                          key={tbl.id}
                          className="cursor-pointer hover:bg-[var(--surface-solid)]"
                          onClick={() => setSelectedTableId(tbl.id)}
                        >
                          <td className="px-4 py-3 font-bold">{tbl.table_code}</td>
                          <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">
                            {tbl.section_name}
                          </td>
                          <td className="px-4 py-3">
                            <TableStateBadge state={tbl.current_state} />
                          </td>
                          <td className="px-4 py-3 font-mono text-xs">
                            {tbl.current_guest_count}/{tbl.seat_capacity}
                          </td>
                          <td className="px-4 py-3 font-mono text-xs">
                            {tbl.occupied_since ? formatElapsed(tbl.occupied_since, nowMs) : "—"}
                          </td>
                          <td className="px-4 py-3">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedTableId(tbl.id);
                              }}
                              className="rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1 text-xs font-semibold hover:opacity-80"
                            >
                              Inspect
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Colorblind-safe State Legend */}
              <div className="tp-glass flex flex-wrap items-center gap-2 rounded-xl border p-3">
                <span className="mr-1 text-xs font-semibold text-[var(--text-secondary)]">
                  State Legend:
                </span>
                {(Object.keys(TABLE_STATE_META) as TableState[]).map((st) => (
                  <div key={st} className="flex items-center gap-1">
                    <TableStateBadge state={st} />
                    <span className="text-[11px] text-[var(--text-secondary)]">
                      ({TABLE_STATE_META[st].patternHint})
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {selectedTableId && venueId && (
              <TableDetailDrawer
                venueId={venueId}
                tableId={selectedTableId}
                onClose={() => setSelectedTableId(null)}
                onUpdated={() => void refresh()}
              />
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
