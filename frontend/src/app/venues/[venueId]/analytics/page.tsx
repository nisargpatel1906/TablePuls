"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Download, Lock, RefreshCw, Table as TableIcon } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, ApiError } from "@/lib/api";
import { hasCapability } from "@/lib/rbac";
import { useAuth } from "@/providers/AuthProvider";

interface HourlyRow {
  hour: string;
  avg_occupancy_pct: number;
  peak_seated_guests: number;
  recommended_servers: number;
  sample_count: number;
}

interface HeatmapCell {
  day_of_week: number;
  hour: number;
  avg_occupancy_pct: number;
}

interface PeakHoursResponse {
  venue_id: string;
  guests_per_server_ratio: number;
  kpis: {
    peak_occupancy_hour: string;
    avg_turn_minutes: number;
    avg_wait_minutes: number;
    sla_breach_rate_pct: number;
    unknown_pct: number;
  };
  hourly_series: HourlyRow[];
  heatmap: HeatmapCell[];
  total_samples: number;
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function PeakHoursAnalyticsPage() {
  const params = useParams<{ venueId: string }>();
  const venueId = params?.venueId || "";
  const { user, loading: authLoading } = useAuth();
  const canViewAnalytics = hasCapability(user?.role, "analytics.view_export");

  const [rangePreset, setRangePreset] = useState<"1d" | "7d" | "30d">("7d");
  const [ratio, setRatio] = useState<number>(16);
  const [showDataTable, setShowDataTable] = useState(false);
  const [data, setData] = useState<PeakHoursResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const buildQueryString = useCallback(
    (format: "json" | "csv") => {
      const now = new Date();
      const days = rangePreset === "1d" ? 1 : rangePreset === "7d" ? 7 : 30;
      const from = new Date(now.getTime() - days * 86400_000).toISOString();
      const qs = new URLSearchParams({
        from_date: from,
        to_date: now.toISOString(),
        guests_per_server_ratio: String(Math.min(50, Math.max(4, ratio))),
        format,
      });
      return qs.toString();
    },
    [rangePreset, ratio],
  );

  const loadAnalytics = useCallback(async () => {
    if (!venueId || !canViewAnalytics) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<PeakHoursResponse>(
        `/api/v1/venues/${venueId}/analytics/peak-hours?${buildQueryString("json")}`,
      );
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, [venueId, canViewAnalytics, buildQueryString]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadAnalytics();
    }
  }, [authLoading, user, loadAnalytics]);

  async function handleExportCsv() {
    setExporting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const blob = await apiFetch<Blob>(
        `/api/v1/venues/${venueId}/analytics/peak-hours?${buildQueryString("csv")}`,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `tablepulse-analytics-${venueId}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setSuccessMsg("CSV exported safely.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to export CSV");
    } finally {
      setExporting(false);
    }
  }

  return (
    <AppShell venueId={venueId}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Peak Hours & Staffing Analytics</h1>
            <p className="text-xs text-[var(--text-secondary)]">
              Historical occupancy density, SLA compliance, and server staffing curve
            </p>
          </div>
          {canViewAnalytics && (
            <div className="flex flex-wrap items-center gap-2">
              <select
                aria-label="Analytics time range"
                value={rangePreset}
                onChange={(e) => setRangePreset(e.target.value as "1d" | "7d" | "30d")}
                className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-medium"
              >
                <option value="1d">Today (24h)</option>
                <option value="7d">Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
              </select>

              <button
                type="button"
                aria-pressed={showDataTable}
                onClick={() => setShowDataTable((v) => !v)}
                className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold"
              >
                <TableIcon className="h-3.5 w-3.5" aria-hidden="true" />
                {showDataTable ? "View Chart" : "View as Data Table"}
              </button>

              <button
                type="button"
                disabled={exporting}
                onClick={() => void handleExportCsv()}
                className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
              >
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
                {exporting ? "Exporting..." : "Export CSV"}
              </button>

              <button
                type="button"
                onClick={() => void loadAnalytics()}
                className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-2"
                aria-label="Refresh analytics"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          )}
        </div>

        {!authLoading && user && !canViewAnalytics && (
          <div className="tp-glass flex flex-col items-center gap-3 rounded-xl border p-8 text-center">
            <Lock className="h-8 w-8 text-amber-600" aria-hidden="true" />
            <h2 className="text-base font-bold">Permission Denied</h2>
            <p className="text-sm text-[var(--text-secondary)]">
              Analytics requires MANAGER, OWNER, or VIEWER permissions.
            </p>
          </div>
        )}

        {successMsg && (
          <div role="status" className="rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">
            {successMsg}
          </div>
        )}
        {error && (
          <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800">
            {error}
          </div>
        )}

        {canViewAnalytics && loading && !data && (
          <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
            Aggregating occupancy snapshots...
          </div>
        )}

        {canViewAnalytics && data && (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <div className="tp-glass rounded-xl border p-3">
                <p className="text-xs font-medium text-[var(--text-secondary)]">Peak Occupancy Hour</p>
                <p className="mt-1 font-mono text-2xl font-bold">{data.kpis.peak_occupancy_hour}</p>
              </div>
              <div className="tp-glass rounded-xl border p-3">
                <p className="text-xs font-medium text-[var(--text-secondary)]">Avg Wait Time</p>
                <p className="mt-1 text-2xl font-bold">{data.kpis.avg_wait_minutes} min</p>
              </div>
              <div className="tp-glass rounded-xl border p-3">
                <p className="text-xs font-medium text-[var(--text-secondary)]">SLA Breach Rate</p>
                <p className="mt-1 text-2xl font-bold">{data.kpis.sla_breach_rate_pct}%</p>
              </div>
              <div className="tp-glass rounded-xl border p-3">
                <p className="text-xs font-medium text-[var(--text-secondary)]">Camera Unknown Rate</p>
                <p className="mt-1 text-2xl font-bold">{data.kpis.unknown_pct}%</p>
              </div>
            </div>

            <section className="tp-glass flex flex-col gap-3 rounded-xl border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-bold">
                    Hourly Occupancy & Recommended Waiter Curve
                  </h2>
                  <p className="text-xs text-[var(--text-secondary)]">
                    Total recorded samples in window: {data.total_samples} (Peak threshold ≥ 75%)
                  </p>
                </div>
                <label className="flex items-center gap-2 text-xs font-medium">
                  Guests per server ratio:
                  <input
                    type="number"
                    min={4}
                    max={50}
                    value={ratio}
                    onChange={(e) => setRatio(Number(e.target.value) || 16)}
                    className="w-20 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-sm"
                  />
                </label>
              </div>

              {showDataTable ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-[var(--border-subtle)] bg-[var(--surface-solid)] uppercase text-[var(--text-secondary)]">
                      <tr>
                        <th scope="col" className="px-3 py-2">Hour</th>
                        <th scope="col" className="px-3 py-2">Occupancy %</th>
                        <th scope="col" className="px-3 py-2">Peak Guests</th>
                        <th scope="col" className="px-3 py-2">Recommended Servers</th>
                        <th scope="col" className="px-3 py-2">Samples</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border-subtle)]">
                      {data.hourly_series.map((row) => (
                        <tr key={row.hour}>
                          <td className="px-3 py-2 font-mono">{row.hour}</td>
                          <td className="px-3 py-2 font-semibold">{row.avg_occupancy_pct}%</td>
                          <td className="px-3 py-2">{row.peak_seated_guests}</td>
                          <td className="px-3 py-2 font-semibold">{row.recommended_servers} srv</td>
                          <td className="px-3 py-2 text-[var(--text-secondary)]">{row.sample_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <div className="h-72 min-w-[560px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={data.hourly_series}>
                        <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                        <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                        <Tooltip />
                        <Bar dataKey="avg_occupancy_pct" name="Avg Occupancy %">
                          {data.hourly_series.map((entry) => (
                            <Cell
                              key={entry.hour}
                              fill={
                                entry.avg_occupancy_pct >= 75
                                  ? "#007AFF"
                                  : "rgba(0, 122, 255, 0.35)"
                              }
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </section>

            {data.heatmap.length > 0 && (
              <section className="tp-glass rounded-xl border p-4">
                <h2 className="mb-2 text-sm font-bold">Observed Day × Hour Density Cells</h2>
                <div className="flex flex-wrap gap-2">
                  {data.heatmap.slice(0, 48).map((cell) => (
                    <div
                      key={`${cell.day_of_week}-${cell.hour}`}
                      className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs"
                    >
                      <span className="font-semibold">{DAY_NAMES[cell.day_of_week] ?? "Day"}</span>{" "}
                      <span className="font-mono">{String(cell.hour).padStart(2, "0")}:00</span> →{" "}
                      <strong>{cell.avg_occupancy_pct}%</strong>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
