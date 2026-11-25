"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Check, Download, Lock, RefreshCw, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, ApiError } from "@/lib/api";
import { hasCapability } from "@/lib/rbac";
import type { TableState } from "@/lib/table-states";
import { useAuth } from "@/providers/AuthProvider";

interface MLReviewItemDTO {
  id: string;
  table_id: string;
  camera_id: string;
  has_snapshot: boolean;
  predicted_state: TableState;
  predicted_guest_count: number;
  confidence: number;
  trigger_reason: string;
  review_status: "PENDING" | "REVIEWED" | "EXCLUDED" | string;
  human_state: string | null;
  human_guest_count: number | null;
  issue_tags: string[];
  created_at: string;
  reviewed_at: string | null;
}

const LABEL_CHOICES: Array<{ key: string; state: TableState; label: string }> = [
  { key: "1", state: "FREE", label: "[1] FREE" },
  { key: "2", state: "OCCUPIED", label: "[2] OCCUPIED" },
  { key: "3", state: "NEEDS_CLEANING", label: "[3] NEEDS CLEANING" },
  { key: "4", state: "NEEDS_SERVICE", label: "[4] NEEDS SERVICE" },
];

export default function MLReviewPage() {
  const params = useParams<{ venueId: string }>();
  const venueId = params?.venueId || "";
  const { user, loading: authLoading } = useAuth();
  const canLabel = hasCapability(user?.role, "ml_review.label");
  const canExport = hasCapability(user?.role, "ml_review.export");

  const [items, setItems] = useState<MLReviewItemDTO[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null);
  const [agreementRate, setAgreementRate] = useState<number | null>(null);
  const [chosenState, setChosenState] = useState<TableState>("OCCUPIED");
  const [guestCount, setGuestCount] = useState<number>(2);
  const [excludeDataset, setExcludeDataset] = useState(false);

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const selectedItem = items.find((i) => i.id === selectedId) || items[0] || null;

  const loadQueue = useCallback(async () => {
    if (!venueId || !canLabel) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{
        items: MLReviewItemDTO[];
        agreement_rate: number | null;
      }>(`/api/v1/venues/${venueId}/ml-review?review_status=PENDING&page_size=50`);
      setItems(res.items);
      setAgreementRate(res.agreement_rate);
      const first = res.items[0];
      if (first) {
        setSelectedId((prev) =>
          res.items.some((x) => x.id === prev) ? prev : first.id,
        );
        setChosenState(first.predicted_state);
        setGuestCount(first.predicted_guest_count);
      } else {
        setSelectedId(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load ML review queue");
    } finally {
      setLoading(false);
    }
  }, [venueId, canLabel]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadQueue();
    }
  }, [authLoading, user, loadQueue]);

  useEffect(() => {
    if (!venueId || !selectedItem?.id || !selectedItem.has_snapshot) {
      setSnapshotUrl(null);
      return;
    }
    let active = true;
    let objUrl: string | null = null;
    apiFetch<Blob>(`/api/v1/venues/${venueId}/ml-review/${selectedItem.id}/snapshot`)
      .then((blob) => {
        if (!active) return;
        objUrl = URL.createObjectURL(blob);
        setSnapshotUrl(objUrl);
      })
      .catch(() => {
        if (active) setSnapshotUrl(null);
      });
    return () => {
      active = false;
      if (objUrl) URL.revokeObjectURL(objUrl);
    };
  }, [venueId, selectedItem?.id, selectedItem?.has_snapshot]);

  const submitLabel = useCallback(async () => {
    if (!selectedItem || !canLabel) return;
    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await apiFetch(`/api/v1/venues/${venueId}/ml-review/${selectedItem.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          review_status: excludeDataset ? "EXCLUDED" : "REVIEWED",
          human_state: chosenState,
          human_guest_count: guestCount,
          issue_tags: excludeDataset ? ["exclude_from_training"] : [],
        }),
      });
      setSuccessMsg(`Saved label ${chosenState} for review item.`);
      await loadQueue();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save label");
    } finally {
      setSubmitting(false);
    }
  }, [selectedItem, canLabel, venueId, excludeDataset, chosenState, guestCount, loadQueue]);

  // Keyboard shortcuts 1-4 and Enter
  useEffect(() => {
    if (!canLabel || !selectedItem) return;
    const onKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      const choice = LABEL_CHOICES.find((c) => c.key === e.key);
      if (choice) {
        e.preventDefault();
        setChosenState(choice.state);
      } else if (e.key === "Enter" && !submitting) {
        e.preventDefault();
        void submitLabel();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [canLabel, selectedItem, submitting, submitLabel]);

  async function handleExportZip() {
    setError(null);
    try {
      const blob = await apiFetch<Blob>(`/api/v1/venues/${venueId}/ml-review/export`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `tablepulse-review-${venueId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setSuccessMsg("Anonymized face-blurred training bundle downloaded.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Export failed");
    }
  }

  return (
    <AppShell venueId={venueId}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">ML Confidence & Human-Review Queue</h1>
            <p className="text-xs text-[var(--text-secondary)]">
              Label low-confidence and user-flagged predictions (shortcuts: 1–4 + Enter)
            </p>
          </div>
          {canLabel && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="tp-pill rounded-full border px-3 py-1.5 text-xs font-semibold">
                Pending: {items.length} · Agreement Rate:{" "}
                {agreementRate !== null ? `${Math.round(agreementRate * 1000) / 10}%` : "NOT YET MEASURED"}
              </span>
              {canExport && (
                <button
                  type="button"
                  onClick={() => void handleExportZip()}
                  className="inline-flex min-h-[38px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white"
                >
                  <Download className="h-3.5 w-3.5" aria-hidden="true" />
                  Export Labeled Bundle (ZIP)
                </button>
              )}
              <button
                type="button"
                onClick={() => void loadQueue()}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-2"
                aria-label="Refresh review queue"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          )}
        </div>

        {!authLoading && user && !canLabel && (
          <div className="tp-glass flex flex-col items-center gap-3 rounded-xl border p-8 text-center">
            <Lock className="h-8 w-8 text-amber-600" aria-hidden="true" />
            <h2 className="text-base font-bold">Permission Denied</h2>
            <p className="text-sm text-[var(--text-secondary)]">
              ML Review Queue is restricted to MANAGER and OWNER roles.
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

        {canLabel && loading && (
          <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
            Loading review queue...
          </div>
        )}

        {canLabel && !loading && items.length === 0 && (
          <div className="tp-glass rounded-xl border p-8 text-center">
            <Check className="mx-auto h-8 w-8 text-emerald-600" aria-hidden="true" />
            <h2 className="mt-2 text-base font-bold">All caught up!</h2>
            <p className="text-xs text-[var(--text-secondary)]">
              No pending ML review items right now. Flag detections on the Live Floor Map to queue samples.
            </p>
          </div>
        )}

        {canLabel && !loading && selectedItem && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
            <aside className="tp-glass flex flex-col gap-2 rounded-xl border p-3">
              <h2 className="text-xs font-bold uppercase text-[var(--text-secondary)]">
                Pending Queue ({items.length})
              </h2>
              <ul className="space-y-1.5">
                {items.map((item) => {
                  const selected = item.id === selectedItem.id;
                  return (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedId(item.id);
                          setChosenState(item.predicted_state);
                          setGuestCount(item.predicted_guest_count);
                        }}
                        className={`w-full rounded-lg border p-2.5 text-left text-xs transition ${
                          selected
                            ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/10"
                            : "border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                        }`}
                      >
                        <div className="flex items-center justify-between font-bold">
                          <span>{item.trigger_reason}</span>
                          <span>{Math.round(item.confidence * 100)}% conf</span>
                        </div>
                        <p className="mt-0.5 text-[11px] text-[var(--text-secondary)]">
                          Pred: {item.predicted_state} ({item.predicted_guest_count} guests)
                        </p>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </aside>

            <section className="tp-glass flex flex-col gap-4 rounded-xl border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] pb-3">
                <div>
                  <h2 className="text-base font-bold">
                    Inspecting {selectedItem.id.slice(0, 8)} · Pred {selectedItem.predicted_state}
                  </h2>
                  <p className="text-xs text-[var(--text-secondary)]">
                    Confidence {Math.round(selectedItem.confidence * 100)}% · Trigger{" "}
                    {selectedItem.trigger_reason} · {new Date(selectedItem.created_at).toLocaleString()}
                  </p>
                </div>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                  <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                  Face Blur Enforced
                </span>
              </div>

              <div className="flex aspect-video w-full items-center justify-center overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-slate-900 p-2 text-center text-xs text-slate-300">
                {snapshotUrl ? (
                  // Authenticated face-blurred review crop fetched as Blob URL
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={snapshotUrl}
                    alt={`Face-blurred review crop for ${selectedItem.predicted_state}`}
                    className="h-full w-full rounded-lg object-contain"
                  />
                ) : selectedItem.has_snapshot ? (
                  "Loading encrypted face-blurred review crop..."
                ) : (
                  "Metadata-only review sample (no image frame persisted)."
                )}
              </div>

              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {LABEL_CHOICES.map((c) => (
                  <button
                    key={c.key}
                    type="button"
                    aria-pressed={chosenState === c.state}
                    onClick={() => setChosenState(c.state)}
                    className={`min-h-[44px] rounded-lg border px-3 py-2 text-xs font-bold transition ${
                      chosenState === c.state
                        ? "border-[var(--accent-primary)] bg-[var(--accent-primary)] text-white"
                        : "border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                    }`}
                  >
                    {c.label}
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <label className="flex items-center gap-2 text-xs font-medium">
                  Verified Guest Count:
                  <input
                    type="number"
                    min={0}
                    max={20}
                    value={guestCount}
                    onChange={(e) => setGuestCount(Number(e.target.value))}
                    className="w-20 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-sm"
                  />
                </label>
                <label className="flex items-center gap-2 text-xs font-medium">
                  <input
                    type="checkbox"
                    checked={excludeDataset}
                    onChange={(e) => setExcludeDataset(e.target.checked)}
                  />
                  Exclude from training dataset
                </label>
              </div>

              <button
                type="button"
                disabled={submitting}
                onClick={() => void submitLabel()}
                className="min-h-[44px] rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
              >
                {submitting ? "Saving..." : "Save & Next (Enter)"}
              </button>
            </section>
          </div>
        )}
      </div>
    </AppShell>
  );
}
