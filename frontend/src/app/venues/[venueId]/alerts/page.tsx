"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Bell, CheckCircle2, Lock, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, ApiError } from "@/lib/api";
import { hasCapability } from "@/lib/rbac";
import { useAuth } from "@/providers/AuthProvider";
import type { AlertItem } from "@/types/floor";

const STATUS_TABS = ["ACTIVE", "ACKNOWLEDGED", "RESOLVED", "ALL"] as const;

export default function AlertsQueuePage() {
  const params = useParams<{ venueId: string }>();
  const venueId = params?.venueId || "";
  const { user, loading: authLoading } = useAuth();
  const canViewAlerts = hasCapability(user?.role, "alerts.view");
  const canResolveAlerts = hasCapability(user?.role, "alerts.resolve");

  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("ACTIVE");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const loadAlerts = useCallback(async () => {
    if (!venueId || !canViewAlerts) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({ page: "1", page_size: "50" });
      if (statusFilter !== "ALL") qs.set("status", statusFilter);
      if (typeFilter !== "ALL") qs.set("alert_type", typeFilter);
      const res = await apiFetch<{ items: AlertItem[] }>(
        `/api/v1/venues/${venueId}/alerts?${qs.toString()}`,
      );
      setAlerts(res.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load alerts");
    } finally {
      setLoading(false);
    }
  }, [venueId, canViewAlerts, statusFilter, typeFilter]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadAlerts();
    }
  }, [authLoading, user, loadAlerts]);

  async function updateStatus(alertId: string, status: "ACKNOWLEDGED" | "RESOLVED") {
    setBusyId(alertId);
    setError(null);
    setActionMsg(null);
    try {
      await apiFetch(`/api/v1/venues/${venueId}/alerts/${alertId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setActionMsg(`Alert marked ${status}`);
      await loadAlerts();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update alert");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <AppShell venueId={venueId}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Service & Cleaning Alerts</h1>
            <p className="text-xs text-[var(--text-secondary)]">
              Unattended guest notifications, bussing queues, and camera health incidents
            </p>
          </div>
          {canViewAlerts && (
            <button
              type="button"
              onClick={() => void loadAlerts()}
              className="inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              Refresh
            </button>
          )}
        </div>

        {!authLoading && user && !canViewAlerts && (
          <div className="tp-glass flex flex-col items-center gap-3 rounded-xl border p-8 text-center">
            <Lock className="h-8 w-8 text-amber-600" aria-hidden="true" />
            <h2 className="text-base font-bold">Permission Denied</h2>
            <p className="text-sm text-[var(--text-secondary)]">
              Alerts Queue is restricted to operational floor roles.
            </p>
          </div>
        )}

        {canViewAlerts && (
          <>
            <div className="tp-glass flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
              <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Alert status">
                {STATUS_TABS.map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setStatusFilter(tab)}
                    aria-pressed={statusFilter === tab}
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      statusFilter === tab
                        ? "bg-[var(--accent-primary)] text-white"
                        : "border border-[var(--border-subtle)] bg-[var(--surface-solid)] text-[var(--text-secondary)]"
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
              <select
                aria-label="Filter by alert type"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-medium"
              >
                <option value="ALL">All Types</option>
                <option value="UNATTENDED_TABLE">Unattended Service</option>
                <option value="NEEDS_CLEANING">Needs Cleaning</option>
                <option value="CAMERA_OFFLINE">Camera Offline</option>
                <option value="HIGH_OCCUPANCY">High Occupancy</option>
              </select>
            </div>

            {actionMsg && (
              <div
                role="status"
                className="rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800"
              >
                {actionMsg}
              </div>
            )}
            {error && (
              <div
                role="alert"
                className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800"
              >
                {error}
              </div>
            )}

            {loading ? (
              <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
                Loading alerts queue...
              </div>
            ) : alerts.length === 0 ? (
              <div className="tp-glass flex flex-col items-center gap-2 rounded-xl border p-8 text-center">
                <CheckCircle2 className="h-8 w-8 text-emerald-600" aria-hidden="true" />
                <h2 className="text-base font-bold">Queue Clear</h2>
                <p className="text-xs text-[var(--text-secondary)]">
                  No alerts match the current filter.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {alerts.map((al) => (
                  <article
                    key={al.id}
                    className="tp-glass flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4"
                  >
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <Bell className="h-4 w-4 text-amber-600" aria-hidden="true" />
                        <span className="rounded bg-[var(--surface-solid)] px-2 py-0.5 text-[11px] font-bold">
                          {al.alert_type}
                        </span>
                        <span className="text-xs font-semibold text-[var(--text-secondary)]">
                          {al.severity} · {al.status}
                        </span>
                        {al.table_code && (
                          <span className="rounded bg-[var(--accent-primary)]/15 px-2 py-0.5 text-xs font-bold">
                            Table {al.table_code}
                          </span>
                        )}
                      </div>
                      <p className="text-sm font-medium">{al.message}</p>
                      <p className="text-xs text-[var(--text-secondary)]">
                        Created {new Date(al.created_at).toLocaleString()}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {al.table_id && (
                        <Link
                          href={`/venues/${venueId}/tables/${al.table_id}`}
                          className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold"
                        >
                          Inspect Table
                        </Link>
                      )}
                      {canResolveAlerts && al.status === "ACTIVE" && (
                        <button
                          type="button"
                          disabled={busyId === al.id}
                          onClick={() => void updateStatus(al.id, "ACKNOWLEDGED")}
                          className="min-h-[38px] rounded-lg bg-amber-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-800 disabled:opacity-50"
                        >
                          Acknowledge
                        </button>
                      )}
                      {canResolveAlerts && al.status !== "RESOLVED" && (
                        <button
                          type="button"
                          disabled={busyId === al.id}
                          onClick={() => void updateStatus(al.id, "RESOLVED")}
                          className="min-h-[38px] rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
                        >
                          Resolve
                        </button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
