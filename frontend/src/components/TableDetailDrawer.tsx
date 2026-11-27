"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Check, ExternalLink, Flag, RefreshCw, ShieldCheck, X } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { hasCapability } from "@/lib/rbac";
import { formatElapsed, TABLE_STATE_META, type TableState } from "@/lib/table-states";
import { useAuth } from "@/providers/AuthProvider";
import { TableStateBadge } from "@/components/TableStateBadge";
import type { TableDetailData } from "@/types/floor";

const OVERRIDE_STATES: TableState[] = [
  "FREE",
  "OCCUPIED",
  "NEEDS_SERVICE",
  "NEEDS_CLEANING",
  "RESERVED",
];

interface TableDetailDrawerProps {
  venueId: string;
  tableId: string;
  standalone?: boolean;
  onClose?: () => void;
  onUpdated?: () => void;
}

export function TableDetailDrawer({
  venueId,
  tableId,
  standalone = false,
  onClose,
  onUpdated,
}: TableDetailDrawerProps) {
  const { user, loading: authLoading } = useAuth();
  const [detail, setDetail] = useState<TableDetailData | null>(null);
  const [snapUrl, setSnapUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [flagSubmitting, setFlagSubmitting] = useState(false);

  const [overrideState, setOverrideState] = useState<TableState>("FREE");
  const [guestCount, setGuestCount] = useState<number>(0);
  const [reason, setReason] = useState("Manual floor update");

  const [showFlag, setShowFlag] = useState(false);
  const [flagReason, setFlagReason] = useState("");
  const [flagSuggested, setFlagSuggested] = useState<TableState>("FREE");

  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const t = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  const loadDetail = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<TableDetailData>(
        `/api/v1/venues/${venueId}/tables/${tableId}`,
      );
      setDetail(data);
      setOverrideState(data.table.current_state);
      setGuestCount(data.table.current_guest_count);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load table details");
    } finally {
      setLoading(false);
    }
  }, [venueId, tableId]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadDetail();
    }
  }, [authLoading, user, loadDetail]);

  useEffect(() => {
    if (!detail || detail.table.id !== tableId || !detail.latest_snapshot_available) {
      setSnapUrl(null);
      return;
    }
    let active = true;
    let objUrl: string | null = null;
    apiFetch<Blob>(`/api/v1/venues/${venueId}/tables/${tableId}/latest-snapshot`)
      .then((blob) => {
        if (!active) return;
        objUrl = URL.createObjectURL(blob);
        setSnapUrl(objUrl);
      })
      .catch(() => {
        if (active) setSnapUrl(null);
      });
    return () => {
      active = false;
      if (objUrl) URL.revokeObjectURL(objUrl);
    };
  }, [venueId, tableId, detail?.latest_snapshot_available, detail?.table.version]);

  const canFullOverride = hasCapability(user?.role, "tables.override_full");
  const canQuickStaffAction = hasCapability(user?.role, "tables.mark_clean_or_served");
  const canFlagAi = hasCapability(user?.role, "tables.flag_ai");

  async function applyOverride(
    nextState: TableState,
    guests: number | undefined,
    overrideReason: string,
    markServiceAttended = false,
  ) {
    if (!detail) return;
    setSubmitting(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await apiFetch(`/api/v1/venues/${venueId}/tables/${tableId}/override`, {
        method: "PATCH",
        body: JSON.stringify({
          new_state: nextState,
          guest_count: guests,
          reason: overrideReason,
          version: detail.table.version,
          mark_service_attended: markServiceAttended,
        }),
      });
      setActionSuccess(`Table ${detail.table.table_code} updated to ${nextState}`);
      await loadDetail();
      onUpdated?.();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setActionError(
          "Version conflict: another user or AI worker updated this table. Refresh before saving.",
        );
      } else {
        setActionError(err instanceof ApiError ? err.message : "Failed to update table");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function submitFlag(e: React.FormEvent) {
    e.preventDefault();
    if (!detail) return;
    setFlagSubmitting(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await apiFetch(`/api/v1/venues/${venueId}/tables/${tableId}/flag`, {
        method: "POST",
        body: JSON.stringify({
          reason: flagReason.trim() || "Incorrect AI state",
          suggested_state: flagSuggested,
        }),
      });
      setActionSuccess("Flagged detection to the ML Review Queue.");
      setShowFlag(false);
      setFlagReason("");
      await loadDetail();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to submit flag");
    } finally {
      setFlagSubmitting(false);
    }
  }

  return (
    <section
      aria-label="Table Detail Inspector"
      className="tp-glass flex flex-col gap-4 rounded-xl border p-4 shadow-lg"
    >
      <div className="flex items-start justify-between gap-2 border-b border-[var(--border-subtle)] pb-3">
        <div>
          {standalone ? (
            <h1 className="text-xl font-bold">
              {detail ? `Table ${detail.table.table_code}` : "Loading Table..."}
            </h1>
          ) : (
            <h2 className="text-lg font-bold">
              {detail ? `Table ${detail.table.table_code}` : "Loading Table..."}
            </h2>
          )}
          {detail && (
            <p className="text-xs text-[var(--text-secondary)]">
              Section {detail.table.section_name} · Cap {detail.table.seat_capacity} · Version v
              {detail.table.version}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!standalone && (
            <Link
              href={`/venues/${venueId}/tables/${tableId}`}
              className="rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-1.5 text-xs hover:opacity-80"
              aria-label="Open full table detail page"
            >
              <ExternalLink className="h-4 w-4" aria-hidden="true" />
            </Link>
          )}
          <button
            type="button"
            onClick={() => void loadDetail()}
            className="rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-1.5 text-xs hover:opacity-80"
            aria-label="Refresh table detail"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
          </button>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-1.5 hover:opacity-80"
              aria-label="Close table detail"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      {loading && (
        <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-4 text-sm text-[var(--text-secondary)]">
          Loading table telemetry and recent transitions...
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800"
        >
          {error}
        </div>
      )}

      {actionError && (
        <div
          role="alert"
          className="flex items-center justify-between gap-2 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800"
        >
          <span>{actionError}</span>
          <button
            type="button"
            onClick={() => void loadDetail()}
            className="shrink-0 rounded bg-red-700 px-2.5 py-1 text-xs font-semibold text-white"
          >
            Refresh
          </button>
        </div>
      )}

      {actionSuccess && (
        <div
          role="status"
          className="flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800"
        >
          <Check className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {detail && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-3">
            <TableStateBadge state={detail.table.current_state} />
            <div className="flex flex-wrap items-center gap-3 text-xs font-medium">
              <span>
                Guests: <strong>{detail.table.current_guest_count}</strong> /{" "}
                {detail.table.seat_capacity}
              </span>
              <span className="font-mono">
                Dwell: {formatElapsed(detail.table.occupied_since, nowMs)}
              </span>
              <span>
                AI Conf:{" "}
                {detail.table.current_confidence !== null
                  ? `${Math.round(detail.table.current_confidence * 100)}%`
                  : "N/A"}
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-2.5 text-xs text-[var(--text-secondary)]">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-medium text-[var(--text-primary)]">
                <ShieldCheck className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                Privacy-Protected Zone Snapshot (Face Blur Active)
              </span>
              <span>
                {detail.latest_snapshot_available ? "Crop stored (TTL active)" : "No crop saved"}
              </span>
            </div>
            {snapUrl && (
              // Authenticated face-blurred crop fetched as Blob URL
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={snapUrl}
                alt={`Face-blurred zone crop for ${detail.table.table_code}`}
                className="max-h-[190px] w-full rounded-md object-contain bg-slate-950"
              />
            )}
          </div>

          {canQuickStaffAction && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={submitting || flagSubmitting}
                onClick={() => void applyOverride("FREE", 0, "Marked clean / ready for seating")}
                className="min-h-[44px] flex-1 whitespace-nowrap rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
              >
                Mark Clean (Free)
              </button>
              <button
                type="button"
                disabled={submitting || flagSubmitting}
                onClick={() =>
                  void applyOverride(
                    "OCCUPIED",
                    Math.max(1, detail.table.current_guest_count),
                    "Service attended",
                    true,
                  )
                }
                className="min-h-[44px] flex-1 whitespace-nowrap rounded-lg bg-amber-700 px-3 py-2 text-xs font-semibold text-white hover:bg-amber-800 disabled:opacity-50"
              >
                Mark Service Attended
              </button>
              {canFullOverride && (
                <button
                  type="button"
                  disabled={submitting || flagSubmitting}
                  onClick={() =>
                    void applyOverride(
                      detail.table.current_state === "RESERVED" ? "FREE" : "RESERVED",
                      0,
                      detail.table.current_state === "RESERVED"
                        ? "Released reservation"
                        : "Held as Reserved",
                    )
                  }
                  className="min-h-[44px] whitespace-nowrap rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-xs font-semibold hover:opacity-80 disabled:opacity-50"
                >
                  {detail.table.current_state === "RESERVED" ? "Unreserve" : "Mark Reserved"}
                </button>
              )}
            </div>
          )}

          {canFullOverride && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void applyOverride(overrideState, guestCount, reason);
              }}
              className="flex flex-col gap-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-3"
            >
              <h3 className="text-xs font-bold uppercase tracking-wide text-[var(--text-secondary)]">
                Manual Override
              </h3>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs font-medium">
                  Target State
                  <select
                    value={overrideState}
                    onChange={(e) => setOverrideState(e.target.value as TableState)}
                    className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-canvas)] px-2.5 py-2 text-sm"
                  >
                    {OVERRIDE_STATES.map((st) => (
                      <option key={st} value={st}>
                        {TABLE_STATE_META[st].label} ({st})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium">
                  Seated Guest Count
                  <input
                    type="number"
                    min={0}
                    max={20}
                    value={guestCount}
                    onChange={(e) => setGuestCount(Number(e.target.value))}
                    className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-canvas)] px-2.5 py-2 text-sm"
                  />
                </label>
              </div>
              <label className="flex flex-col gap-1 text-xs font-medium">
                Reason (audited)
                <input
                  type="text"
                  required
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-canvas)] px-2.5 py-2 text-sm"
                />
              </label>
              <button
                type="submit"
                disabled={submitting}
                className="min-h-[40px] rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
              >
                {submitting ? "Saving..." : "Apply Manual Override"}
              </button>
            </form>
          )}

          {canFlagAi && (
            <div className="border-t border-[var(--border-subtle)] pt-2">
              <button
                type="button"
                onClick={() => setShowFlag((v) => !v)}
                className="flex items-center gap-1.5 text-xs font-semibold text-[var(--accent-primary)] hover:underline"
              >
                <Flag className="h-3.5 w-3.5" aria-hidden="true" />
                {showFlag ? "Hide AI Flag Form" : "Flag Wrong AI Detection"}
              </button>
              {showFlag && (
                <form
                  onSubmit={submitFlag}
                  className="mt-2 flex flex-col gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-3"
                >
                  <label className="flex flex-col gap-1 text-xs font-medium">
                    Expected State
                    <select
                      value={flagSuggested}
                      onChange={(e) => setFlagSuggested(e.target.value as TableState)}
                      className="rounded border border-[var(--border-subtle)] bg-[var(--bg-canvas)] px-2 py-1.5 text-sm"
                    >
                      {OVERRIDE_STATES.map((st) => (
                        <option key={st} value={st}>
                          {st}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-xs font-medium">
                    Issue Description
                    <input
                      type="text"
                      required
                      placeholder="e.g., Coat left on chair counted as occupied"
                      value={flagReason}
                      onChange={(e) => setFlagReason(e.target.value)}
                      className="rounded border border-[var(--border-subtle)] bg-[var(--bg-canvas)] px-2.5 py-1.5 text-sm"
                    />
                  </label>
                  <button
                    type="submit"
                    disabled={flagSubmitting}
                    className="min-h-[44px] rounded-lg bg-amber-700 px-3 py-2 text-xs font-semibold text-white hover:bg-amber-800 disabled:opacity-50"
                  >
                    {flagSubmitting ? "Submitting..." : "Submit to ML Review Queue"}
                  </button>
                </form>
              )}
            </div>
          )}

          <div>
            <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-[var(--text-secondary)]">
              Recent State Transitions (Last 10)
            </h3>
            {detail.events.length === 0 ? (
              <p className="text-xs text-[var(--text-secondary)]">No recorded transitions yet.</p>
            ) : (
              <ul className="space-y-1.5 text-xs">
                {detail.events.map((evt) => (
                  <li
                    key={evt.id}
                    className="flex flex-col gap-0.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold">
                        {evt.previous_state} → {evt.new_state} ({evt.guest_count} guests)
                      </span>
                      <span className="rounded bg-[var(--bg-canvas)] px-1.5 py-0.5 font-mono text-[11px]">
                        {evt.source}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
                      <span>{evt.reason || "Automated transition"}</span>
                      <span>{new Date(evt.occurred_at).toLocaleTimeString()}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </section>
  );
}
