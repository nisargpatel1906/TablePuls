"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Clock, Lock, Plus, RefreshCw, Users } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { TableStateBadge } from "@/components/TableStateBadge";
import { apiFetch, ApiError } from "@/lib/api";
import { hasCapability } from "@/lib/rbac";
import { useAuth } from "@/providers/AuthProvider";
import type { TurnoverPredictionItem, WaitlistItem } from "@/types/floor";

export default function WaitlistPage() {
  const params = useParams<{ venueId: string }>();
  const venueId = params?.venueId || "";
  const { user, loading: authLoading } = useAuth();
  const canManageWaitlist = hasCapability(user?.role, "waitlist.manage");

  const [entries, setEntries] = useState<WaitlistItem[]>([]);
  const [selectedEntry, setSelectedEntry] = useState<WaitlistItem | null>(null);
  const [partyFilterSize, setPartyFilterSize] = useState<number>(2);
  const [predictions, setPredictions] = useState<TurnoverPredictionItem[]>([]);
  const [baselineNote, setBaselineNote] = useState<string>("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [showAdd, setShowAdd] = useState(false);
  const [partyName, setPartyName] = useState("");
  const [partySize, setPartySize] = useState(2);
  const [phone, setPhone] = useState("");
  const [quotedWait, setQuotedWait] = useState(15);
  const [notes, setNotes] = useState("");

  const loadData = useCallback(
    async (targetSize = partyFilterSize) => {
      if (!venueId || !canManageWaitlist) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const [wlRes, predRes] = await Promise.all([
          apiFetch<{ items: WaitlistItem[] }>(
            `/api/v1/venues/${venueId}/waitlist?status=WAITING&page_size=50`,
          ),
          apiFetch<{ items: TurnoverPredictionItem[]; baseline_note: string }>(
            `/api/v1/venues/${venueId}/turnover-predictions?party_size=${targetSize}`,
          ),
        ]);
        setEntries(wlRes.items);
        setPredictions(predRes.items);
        setBaselineNote(predRes.baseline_note);
        const firstEntry = wlRes.items[0];
        if (!selectedEntry && firstEntry) {
          setSelectedEntry(firstEntry);
          setPartyFilterSize(firstEntry.party_size);
        }
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load waitlist");
      } finally {
        setLoading(false);
      }
    },
    [venueId, canManageWaitlist, partyFilterSize, selectedEntry],
  );

  useEffect(() => {
    if (!authLoading && user) {
      void loadData(partyFilterSize);
    }
  }, [authLoading, user, partyFilterSize, loadData]);

  async function handleAddParty(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const created = await apiFetch<WaitlistItem>(`/api/v1/venues/${venueId}/waitlist`, {
        method: "POST",
        body: JSON.stringify({
          party_name: partyName.trim(),
          party_size: partySize,
          phone: phone.trim() || null,
          quoted_wait_minutes: quotedWait,
          notes: notes.trim() || null,
        }),
      });
      setSuccessMsg(`Added ${created.party_name} (party of ${created.party_size})`);
      setPartyName("");
      setPhone("");
      setNotes("");
      setShowAdd(false);
      setSelectedEntry(created);
      setPartyFilterSize(created.party_size);
      await loadData(created.party_size);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add waitlist party");
    } finally {
      setSubmitting(false);
    }
  }

  async function seatOnTable(tableId: string) {
    if (!selectedEntry) {
      setError("Select a waiting party first before assigning a table.");
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await apiFetch(`/api/v1/venues/${venueId}/waitlist/${selectedEntry.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status: "SEATED",
          assigned_table_id: tableId,
        }),
      });
      setSuccessMsg(`Seated ${selectedEntry.party_name} cleanly!`);
      setSelectedEntry(null);
      await loadData(partyFilterSize);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to seat party");
    } finally {
      setSubmitting(false);
    }
  }

  async function updateWaitStatus(entryId: string, status: "CANCELLED" | "NO_SHOW") {
    setSubmitting(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/venues/${venueId}/waitlist/${entryId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setSuccessMsg(`Party marked ${status}`);
      if (selectedEntry?.id === entryId) setSelectedEntry(null);
      await loadData(partyFilterSize);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update entry");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AppShell venueId={venueId}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Waitlist & Turnover ETAs</h1>
            <p className="text-xs text-[var(--text-secondary)]">
              Match waiting parties against live table availability and predicted dwell release
            </p>
          </div>
          {canManageWaitlist && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void loadData(partyFilterSize)}
                className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                Refresh
              </button>
              <button
                type="button"
                onClick={() => setShowAdd((v) => !v)}
                className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Add Party
              </button>
            </div>
          )}
        </div>

        {!authLoading && user && !canManageWaitlist && (
          <div className="tp-glass flex flex-col items-center gap-3 rounded-xl border p-8 text-center">
            <Lock className="h-8 w-8 text-amber-600" aria-hidden="true" />
            <h2 className="text-base font-bold">Permission Denied</h2>
            <p className="text-sm text-[var(--text-secondary)]">
              Waitlist management requires HOST, MANAGER, or OWNER access.
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

        {canManageWaitlist && showAdd && (
          <form
            onSubmit={handleAddParty}
            className="tp-glass grid grid-cols-1 gap-3 rounded-xl border p-4 sm:grid-cols-2 lg:grid-cols-5"
          >
            <label className="flex flex-col gap-1 text-xs font-medium">
              Party Name *
              <input
                type="text"
                required
                value={partyName}
                onChange={(e) => setPartyName(e.target.value)}
                placeholder="e.g., Sharma"
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-2 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Party Size *
              <input
                type="number"
                min={1}
                max={20}
                value={partySize}
                onChange={(e) => setPartySize(Number(e.target.value))}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-2 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Phone (Encrypted AES-GCM)
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+15550100"
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-2 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Quoted Wait (min)
              <input
                type="number"
                min={1}
                max={240}
                value={quotedWait}
                onChange={(e) => setQuotedWait(Number(e.target.value))}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-2 text-sm"
              />
            </label>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={submitting}
                className="min-h-[40px] w-full rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
              >
                {submitting ? "Adding..." : "Save Party"}
              </button>
            </div>
          </form>
        )}

        {canManageWaitlist && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Left column: Waiting queue */}
            <section className="tp-glass flex flex-col gap-3 rounded-xl border p-4">
              <h2 className="text-sm font-bold">Waiting Queue ({entries.length})</h2>
              {loading ? (
                <p className="text-xs text-[var(--text-secondary)]">Loading waitlist...</p>
              ) : entries.length === 0 ? (
                <p className="text-xs text-[var(--text-secondary)]">No parties currently waiting.</p>
              ) : (
                <ul className="space-y-2">
                  {entries.map((item) => {
                    const isSelected = selectedEntry?.id === item.id;
                    return (
                      <li
                        key={item.id}
                        className={`rounded-lg border p-3 transition ${
                          isSelected
                            ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/10"
                            : "border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedEntry(item);
                              setPartyFilterSize(item.party_size);
                            }}
                            className="text-left"
                          >
                            <p className="font-bold">
                              {item.party_name}{" "}
                              <span className="inline-flex items-center gap-1 rounded bg-[var(--bg-canvas)] px-1.5 py-0.5 text-xs">
                                <Users className="h-3 w-3" aria-hidden="true" />
                                {item.party_size}
                              </span>
                            </p>
                            <p className="text-xs text-[var(--text-secondary)]">
                              Elapsed {item.elapsed_wait_minutes} min
                              {item.quoted_wait_minutes
                                ? ` · Quoted ${item.quoted_wait_minutes} min`
                                : ""}
                            </p>
                          </button>

                          <div className="flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => void updateWaitStatus(item.id, "NO_SHOW")}
                              className="rounded border border-[var(--border-subtle)] px-2 py-1 text-[11px] font-semibold"
                            >
                              No-Show
                            </button>
                            <button
                              type="button"
                              onClick={() => void updateWaitStatus(item.id, "CANCELLED")}
                              className="rounded border border-[var(--border-subtle)] px-2 py-1 text-[11px] font-semibold"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            {/* Right column: Turnover ETAs */}
            <section className="tp-glass flex flex-col gap-3 rounded-xl border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-bold">
                  Predicted Next Available (Party ≥ {partyFilterSize})
                </h2>
                <label className="flex items-center gap-1.5 text-xs">
                  Party Size:
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={partyFilterSize}
                    onChange={(e) => setPartyFilterSize(Math.max(1, Number(e.target.value)))}
                    className="w-16 rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2 py-1 text-xs"
                  />
                </label>
              </div>
              {baselineNote && (
                <p className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-[11px] text-[var(--text-secondary)]">
                  {baselineNote}
                </p>
              )}

              {predictions.length === 0 ? (
                <p className="text-xs text-[var(--text-secondary)]">
                  No qualifying tables match this party size.
                </p>
              ) : (
                <ul className="space-y-2">
                  {predictions.map((pred) => {
                    const canSeatNow = pred.current_state === "FREE" && Boolean(selectedEntry);
                    return (
                      <li
                        key={pred.table_id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-3"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold">Table {pred.table_code}</span>
                            <TableStateBadge state={pred.current_state} />
                          </div>
                          <p className="mt-1 flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                            <span>Cap {pred.seat_capacity}</span>
                            <span>·</span>
                            <span className="inline-flex items-center gap-1 font-semibold text-[var(--text-primary)]">
                              <Clock className="h-3 w-3" aria-hidden="true" />
                              {pred.eta_display}
                            </span>
                            <span>({pred.confidence_tier})</span>
                          </p>
                        </div>

                        <button
                          type="button"
                          disabled={!canSeatNow || submitting}
                          onClick={() => void seatOnTable(pred.table_id)}
                          className="min-h-[44px] rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {pred.current_state === "FREE" ? "Seat Party Here" : "Not Free Yet"}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </div>
        )}
      </div>
    </AppShell>
  );
}
