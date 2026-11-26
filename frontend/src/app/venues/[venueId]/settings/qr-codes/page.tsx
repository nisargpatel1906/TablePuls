// TODO(ui-asset): SCR-020
"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  Check,
  Copy,
  Download,
  ExternalLink,
  FileDown,
  Lock,
  QrCode,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  X,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, ApiError, getAccessToken } from "@/lib/api";
import { t } from "@/lib/i18n";
import { hasCapability } from "@/lib/rbac";
import { useAuth } from "@/providers/AuthProvider";
import type { QRCodeItemDTO } from "@/types/floor";

function QrSvgThumbnail({ venueId, tableId, token }: { venueId: string; tableId: string; token: string | null }) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!venueId || !tableId || !token) {
      setSrc(null);
      return;
    }
    let active = true;
    let objUrl: string | null = null;
    async function loadThumb() {
      try {
        const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
        const authToken = getAccessToken();
        const res = await fetch(
          `${base}/api/v1/venues/${venueId}/tables/${tableId}/qr/download?format=svg&framed=false`,
          {
            headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
            credentials: "include",
          },
        );
        if (!res.ok || !active) return;
        const blob = await res.blob();
        if (!active) return;
        objUrl = URL.createObjectURL(blob);
        setSrc(objUrl);
      } catch {
        // Fallback icon displayed cleanly if offline
      }
    }
    void loadThumb();
    return () => {
      active = false;
      if (objUrl) URL.revokeObjectURL(objUrl);
    };
  }, [venueId, tableId, token]);

  if (!src) {
    return (
      <div className="flex h-24 w-24 shrink-0 items-center justify-center rounded-xl border border-dashed border-[var(--border-subtle)] bg-white p-2 text-slate-700">
        <QrCode className="h-10 w-10" aria-hidden="true" />
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={`QR code for table ${tableId}`}
      className="h-24 w-24 shrink-0 rounded-xl border border-[var(--border-subtle)] bg-white p-1.5 object-contain"
    />
  );
}

export default function QrCodesManagerPage() {
  const params = useParams<{ venueId: string }>();
  const venueId = params?.venueId || "";
  const { user, loading: authLoading, locale } = useAuth();
  const canRead = hasCapability(user?.role, "qr.read");
  const canManage = hasCapability(user?.role, "qr.manage");

  const [items, setItems] = useState<QRCodeItemDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [sectionFilter, setSectionFilter] = useState("ALL");
  const [neverScanned30d, setNeverScanned30d] = useState(false);

  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [pdfLayout, setPdfLayout] = useState<"A4_4UP" | "A4_6UP" | "LETTER_4UP">("A4_4UP");
  const [exportingPdf, setExportingPdf] = useState(false);

  // Regenerate modal
  const [regenTarget, setRegenTarget] = useState<QRCodeItemDTO | null>(null);
  const [regenReason, setRegenReason] = useState<"DAMAGED" | "COMPROMISED" | "REBRAND" | "OTHER">("DAMAGED");
  const [regenGraceDays, setRegenGraceDays] = useState(7);
  const [submitting, setSubmitting] = useState(false);

  const loadQrCodes = useCallback(async () => {
    if (!venueId || !canRead) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({
        never_scanned_30d: neverScanned30d ? "true" : "false",
      });
      if (sectionFilter !== "ALL") qs.set("section", sectionFilter);
      if (search.trim()) qs.set("search", search.trim());
      const res = await apiFetch<{ items: QRCodeItemDTO[]; total: number }>(
        `/api/v1/venues/${venueId}/qr-codes?${qs.toString()}`,
      );
      setItems(res.items || []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load table QR codes");
    } finally {
      setLoading(false);
    }
  }, [venueId, canRead, search, sectionFilter, neverScanned30d]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadQrCodes();
    }
  }, [authLoading, user, loadQrCodes]);

  const sections = useMemo(() => {
    const s = new Set<string>();
    for (const item of items) s.add(item.section_name);
    return Array.from(s).sort();
  }, [items]);

  async function downloadSingleAsset(tableId: string, tableCode: string, format: "svg" | "png") {
    if (!venueId) return;
    setError(null);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const token = getAccessToken();
      const res = await fetch(
        `${base}/api/v1/venues/${venueId}/tables/${tableId}/qr/download?format=${format}&framed=true`,
        {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          credentials: "include",
        },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `table-${tableCode}-qr.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setSuccessMsg(`Downloaded framed ${format.toUpperCase()} QR card for ${tableCode}.`);
    } catch {
      setError(`Failed to download ${format.toUpperCase()} for ${tableCode}`);
    }
  }

  async function handleExportBatchPdf() {
    if (!venueId || selectedIds.length === 0) return;
    setExportingPdf(true);
    setError(null);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const token = getAccessToken();
      const res = await fetch(`${base}/api/v1/venues/${venueId}/qr/export-pdf`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: "include",
        body: JSON.stringify({
          table_ids: selectedIds,
          layout: pdfLayout,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `table-qr-codes-${pdfLayout.toLowerCase()}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setSuccessMsg(`Generated print-ready ${pdfLayout} PDF for ${selectedIds.length} tables.`);
    } catch {
      setError("Failed to export printable QR PDF");
    } finally {
      setExportingPdf(false);
    }
  }

  async function handleCopyPreviewLink(item: QRCodeItemDTO) {
    if (!venueId) return;
    setError(null);
    try {
      const res = await apiFetch<{ preview_url: string }>(
        `/api/v1/venues/${venueId}/tables/${item.table_id}/qr/preview-link`,
        { method: "POST" },
      );
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(res.preview_url);
      }
      setSuccessMsg(`Copied 15-minute staff preview link for ${item.table_code}.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate preview link");
    }
  }

  async function handleCopyUrl(url: string, code: string) {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(url);
      }
      setSuccessMsg(`Copied QR URL for ${code}.`);
    } catch {
      setError("Clipboard permission unavailable in browser context");
    }
  }

  async function handleEndGrace(item: QRCodeItemDTO) {
    if (!venueId) return;
    setError(null);
    try {
      await apiFetch(`/api/v1/venues/${venueId}/tables/${item.table_id}/qr/end-grace`, {
        method: "POST",
      });
      setSuccessMsg(`Revoked grace QR token for ${item.table_code}.`);
      await loadQrCodes();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to end QR grace period");
    }
  }

  async function confirmRegenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!venueId || !regenTarget) return;
    setSubmitting(true);
    setError(null);
    try {
      const effectiveGrace = regenReason === "COMPROMISED" ? 0 : regenGraceDays;
      await apiFetch(`/api/v1/venues/${venueId}/tables/${regenTarget.table_id}/qr/regenerate`, {
        method: "POST",
        body: JSON.stringify({
          reason: regenReason,
          grace_days: effectiveGrace,
        }),
      });
      setSuccessMsg(
        effectiveGrace > 0
          ? `Regenerated QR for ${regenTarget.table_code} (${effectiveGrace}-day grace period on old code).`
          : `Immediately rotated QR for ${regenTarget.table_code}; old QR token revoked.`,
      );
      setRegenTarget(null);
      await loadQrCodes();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to regenerate QR code");
    } finally {
      setSubmitting(false);
    }
  }

  if (!authLoading && !user) {
    return (
      <main className="mx-auto max-w-lg p-6 text-center">
        <h1 className="text-xl font-bold">Sign in required</h1>
        <Link
          href="/login"
          className="mt-4 inline-block rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-sm font-semibold text-white"
        >
          Go to Login
        </Link>
      </main>
    );
  }

  const activeIds = items.filter((i) => i.is_active).map((i) => i.table_id);

  return (
    <AppShell venueId={venueId} toastMessage={successMsg}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">{t(locale, "p2.qr_title")}</h1>
            <p className="text-xs text-[var(--text-secondary)]">
              Unique table QR tokens with offline SVG/PNG cards, cut-guided multi-up print PDFs, and atomic grace rotation.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void loadQrCodes()}
              className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-xs font-semibold hover:opacity-80"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              {t(locale, "action.refresh")}
            </button>
          </div>
        </div>

        {!authLoading && user && !canRead && (
          <div className="tp-glass flex flex-col items-center gap-3 rounded-xl border p-8 text-center">
            <Lock className="h-8 w-8 text-amber-600" aria-hidden="true" />
            <h2 className="text-base font-bold">Permission Denied</h2>
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="flex items-center justify-between rounded-xl border border-red-300 bg-red-50 p-3 text-xs font-medium text-red-800"
          >
            <span>{error}</span>
            <button type="button" onClick={() => setError(null)} className="underline">
              Dismiss
            </button>
          </div>
        )}

        {canRead && (
          <>
            {/* Filter & Batch PDF Toolbar */}
            <div className="tp-glass flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <label className="relative flex items-center">
                  <Search
                    className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-[var(--text-secondary)]"
                    aria-hidden="true"
                  />
                  <input
                    type="search"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search tables..."
                    aria-label="Search QR tables"
                    className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] py-1.5 pl-8 pr-3 text-xs"
                  />
                </label>

                <select
                  aria-label="Filter QR section"
                  value={sectionFilter}
                  onChange={(e) => setSectionFilter(e.target.value)}
                  className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-medium"
                >
                  <option value="ALL">All Sections</option>
                  {sections.map((sec) => (
                    <option key={sec} value={sec}>
                      {sec}
                    </option>
                  ))}
                </select>

                <label className="inline-flex min-h-[40px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-medium">
                  <input
                    type="checkbox"
                    checked={neverScanned30d}
                    onChange={(e) => setNeverScanned30d(e.target.checked)}
                  />
                  Never scanned (30d)
                </label>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setSelectedIds(
                      selectedIds.length === activeIds.length ? [] : activeIds,
                    )
                  }
                  className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold"
                >
                  {selectedIds.length === activeIds.length && activeIds.length > 0
                    ? "Clear Selection"
                    : `Select All Active (${activeIds.length})`}
                </button>
                <select
                  aria-label="Print sheet layout"
                  value={pdfLayout}
                  onChange={(e) =>
                    setPdfLayout(e.target.value as "A4_4UP" | "A4_6UP" | "LETTER_4UP")
                  }
                  className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-medium"
                >
                  <option value="A4_4UP">A4 · 4-Up Table Tents</option>
                  <option value="A4_6UP">A4 · 6-Up Stickers</option>
                  <option value="LETTER_4UP">US Letter · 4-Up</option>
                </select>
                <button
                  type="button"
                  disabled={selectedIds.length === 0 || exportingPdf}
                  onClick={() => void handleExportBatchPdf()}
                  className="inline-flex min-h-[42px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-3.5 py-2 text-xs font-semibold text-white disabled:opacity-50"
                >
                  <FileDown className="h-3.5 w-3.5" aria-hidden="true" />
                  {exportingPdf
                    ? "Rendering PDF..."
                    : `Export Batch PDF (${selectedIds.length})`}
                </button>
              </div>
            </div>

            {loading && (
              <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
                Loading table QR codes...
              </div>
            )}

            {!loading && items.length === 0 && (
              <div className="tp-glass rounded-xl border p-8 text-center">
                <h2 className="text-base font-bold">No QR codes match current filters</h2>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  Add tables in Settings → Tables to auto-generate unique QR tokens.
                </p>
              </div>
            )}

            {!loading && items.length > 0 && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {items.map((item) => {
                  const isChecked = selectedIds.includes(item.table_id);
                  return (
                    <article
                      key={item.table_id}
                      className={`tp-glass flex flex-col justify-between gap-3 rounded-xl border p-4 ${
                        !item.is_active ? "opacity-65" : ""
                      }`}
                    >
                      <div className="flex gap-3">
                        <QrSvgThumbnail
                          venueId={venueId}
                          tableId={item.table_id}
                          token={item.token}
                        />
                        <div className="flex min-w-0 flex-1 flex-col justify-between">
                          <div>
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                <h2 className="text-base font-bold">
                                  {item.table_code}
                                  {!item.is_active && (
                                    <span className="ml-1.5 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">
                                      INACTIVE
                                    </span>
                                  )}
                                </h2>
                                <p className="text-xs text-[var(--text-secondary)]">
                                  {item.table_label} · {item.section_name}
                                </p>
                              </div>
                              <input
                                type="checkbox"
                                aria-label={`Include ${item.table_code} in batch PDF`}
                                checked={isChecked}
                                onChange={() =>
                                  setSelectedIds((prev) =>
                                    isChecked
                                      ? prev.filter((x) => x !== item.table_id)
                                      : [...prev, item.table_id],
                                  )
                                }
                              />
                            </div>

                            <div className="mt-2 flex flex-wrap gap-2 text-[11px] font-medium text-[var(--text-secondary)]">
                              <span>
                                7d scans: <strong className="text-[var(--text-primary)]">{item.scans_7d}</strong>
                              </span>
                              <span>·</span>
                              <span>
                                Total: <strong className="text-[var(--text-primary)]">{item.scan_count}</strong>
                              </span>
                            </div>
                          </div>

                          {item.grace_token_active && (
                            <div className="mt-2 flex flex-wrap items-center justify-between gap-1 rounded-lg border border-amber-400/50 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-800 dark:text-amber-300">
                              <span>
                                Old sticker in grace window
                                {item.grace_until
                                  ? ` until ${new Date(item.grace_until).toLocaleDateString()}`
                                  : ""}
                              </span>
                              {canManage && (
                                <button
                                  type="button"
                                  onClick={() => void handleEndGrace(item)}
                                  className="font-bold underline"
                                >
                                  End Grace Now
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      </div>

                      {item.qr_url && (
                        <div className="flex items-center justify-between gap-2 rounded-lg border border-[var(--border-subtle)] bg-black/5 px-2.5 py-1.5 font-mono text-[11px]">
                          <span className="truncate">{item.qr_url}</span>
                          <div className="flex shrink-0 items-center gap-1">
                            <button
                              type="button"
                              onClick={() => void handleCopyUrl(item.qr_url!, item.table_code)}
                              aria-label={`Copy QR URL for ${item.table_code}`}
                              className="rounded p-1 hover:bg-black/10"
                            >
                              <Copy className="h-3.5 w-3.5" />
                            </button>
                            <a
                              href={item.qr_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              aria-label={`Open customer menu for ${item.table_code}`}
                              className="rounded p-1 hover:bg-black/10"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          </div>
                        </div>
                      )}

                      <div className="flex flex-wrap items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() =>
                            void downloadSingleAsset(item.table_id, item.table_code, "png")
                          }
                          className="inline-flex min-h-[38px] items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1 text-xs font-semibold hover:opacity-80"
                        >
                          <Download className="h-3.5 w-3.5" aria-hidden="true" />
                          PNG
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            void downloadSingleAsset(item.table_id, item.table_code, "svg")
                          }
                          className="inline-flex min-h-[38px] items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1 text-xs font-semibold hover:opacity-80"
                        >
                          <Download className="h-3.5 w-3.5" aria-hidden="true" />
                          SVG
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleCopyPreviewLink(item)}
                          className="inline-flex min-h-[38px] items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1 text-xs font-semibold hover:opacity-80"
                        >
                          <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                          Preview Link
                        </button>
                        {canManage && (
                          <button
                            type="button"
                            onClick={() => {
                              setRegenTarget(item);
                              setRegenReason("DAMAGED");
                              setRegenGraceDays(7);
                            }}
                            className="ml-auto inline-flex min-h-[38px] items-center gap-1 rounded-lg bg-amber-600/15 px-2.5 py-1 text-xs font-semibold text-amber-800 hover:bg-amber-600/25 dark:text-amber-300"
                          >
                            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                            Regenerate
                          </button>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      {/* Regenerate QR Modal */}
      {regenTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Regenerate QR for ${regenTarget.table_code}`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
        >
          <form
            onSubmit={confirmRegenerate}
            className="w-full max-w-md rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-5 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
              <h2 className="text-base font-bold">
                Regenerate QR · {regenTarget.table_code}
              </h2>
              <button
                type="button"
                onClick={() => setRegenTarget(null)}
                aria-label="Close modal"
                className="rounded-lg p-1.5"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <label className="flex flex-col gap-1 font-medium">
                Rotation Reason
                <select
                  value={regenReason}
                  onChange={(e) =>
                    setRegenReason(
                      e.target.value as "DAMAGED" | "COMPROMISED" | "REBRAND" | "OTHER",
                    )
                  }
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-sm"
                >
                  <option value="DAMAGED">Damaged or Worn Sticker</option>
                  <option value="REBRAND">Rebrand / Layout Change</option>
                  <option value="COMPROMISED">Compromised / Anti-Quishing Tamper</option>
                  <option value="OTHER">Other</option>
                </select>
              </label>

              {regenReason === "COMPROMISED" ? (
                <div className="flex items-start gap-2 rounded-xl border border-red-400 bg-red-50 p-3 text-red-900">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <p>
                    <strong>Security Compromise Selected:</strong> Grace window is forced to{" "}
                    <strong>0 days</strong>. Existing printed QR stickers will return{" "}
                    <code>410 Gone</code> immediately.
                  </p>
                </div>
              ) : (
                <label className="flex flex-col gap-1 font-medium">
                  Grace Period for Previous Sticker (0–30 days)
                  <input
                    type="number"
                    min={0}
                    max={30}
                    value={regenGraceDays}
                    onChange={(e) => setRegenGraceDays(Number(e.target.value) || 0)}
                    className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                  />
                  <span className="text-[11px] text-[var(--text-secondary)]">
                    Set to 0 to revoke old QR immediately upon printing replacements.
                  </span>
                </label>
              )}

              {regenTarget.grace_token_active && (
                <div className="flex items-start gap-2 rounded-xl border border-amber-400 bg-amber-50 p-2.5 text-amber-900">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <p>An older grace token already exists and will be permanently revoked now.</p>
                </div>
              )}
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setRegenTarget(null)}
                className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
              >
                <Check className="h-3.5 w-3.5" aria-hidden="true" />
                {submitting ? "Rotating..." : "Confirm Rotation"}
              </button>
            </div>
          </form>
        </div>
      )}
    </AppShell>
  );
}
