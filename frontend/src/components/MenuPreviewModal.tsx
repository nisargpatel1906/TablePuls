// TODO(ui-asset): SCR-021
"use client";

import React, { useEffect, useState } from "react";
import { ExternalLink, Moon, Smartphone, Sun, X } from "lucide-react";
import { PublicDigitalMenu } from "@/components/PublicDigitalMenu";
import { apiFetch, ApiError } from "@/lib/api";
import type { AdminTableItem } from "@/types/floor";

interface MenuPreviewModalProps {
  open: boolean;
  venueId: string;
  onClose: () => void;
}

export function MenuPreviewModal({ open, venueId, onClose }: MenuPreviewModalProps) {
  const [tables, setTables] = useState<AdminTableItem[]>([]);
  const [selectedTableId, setSelectedTableId] = useState<string>("");
  const [previewInfo, setPreviewInfo] = useState<{
    qrToken: string;
    previewParam: string | null;
    fullPath: string;
  } | null>(null);
  const [previewTheme, setPreviewTheme] = useState<"light" | "dark">("light");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !venueId) return;
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await apiFetch<{ items: AdminTableItem[] }>(
          `/api/v1/venues/${venueId}/tables?status=active&page_size=50`,
        );
        if (!active) return;
        const rows = res.items || [];
        setTables(rows);
        if (rows[0]) {
          setSelectedTableId(rows[0].id);
        }
      } catch (err) {
        if (active) setError(err instanceof ApiError ? err.message : "Failed to load tables");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [open, venueId]);

  useEffect(() => {
    if (!open || !venueId || !selectedTableId) return;
    let active = true;
    async function issueLink() {
      setLoading(true);
      setError(null);
      try {
        const res = await apiFetch<{ preview_url: string }>(
          `/api/v1/venues/${venueId}/tables/${selectedTableId}/qr/preview-link`,
          { method: "POST" },
        );
        if (!active) return;
        const u = new URL(res.preview_url, window.location.origin);
        u.searchParams.set("theme", previewTheme);
        const tokenSeg = u.pathname.split("/").pop() || "";
        setPreviewInfo({
          qrToken: tokenSeg,
          previewParam: u.searchParams.get("p"),
          fullPath: `${u.pathname}${u.search}`,
        });
      } catch (err) {
        if (active) setError(err instanceof ApiError ? err.message : "Failed to create preview link");
      } finally {
        if (active) setLoading(false);
      }
    }
    void issueLink();
    return () => {
      active = false;
    };
  }, [open, venueId, selectedTableId, previewTheme]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Live Customer Menu Mobile Preview"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
    >
      <div className="flex max-h-[94vh] w-full max-w-lg flex-col rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-4 shadow-2xl">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] pb-3">
          <div className="flex items-center gap-2">
            <Smartphone className="h-4 w-4 text-[var(--accent-primary)]" aria-hidden="true" />
            <h2 className="text-sm font-bold">Mobile Preview (390×844)</h2>
          </div>
          <div className="flex items-center gap-2">
            <select
              aria-label="Preview table"
              value={selectedTableId}
              onChange={(e) => setSelectedTableId(e.target.value)}
              className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2 py-1 text-xs font-medium"
            >
              {tables.map((tItem) => (
                <option key={tItem.id} value={tItem.id}>
                  {tItem.table_code} ({tItem.section_name})
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setPreviewTheme((th) => (th === "light" ? "dark" : "light"))}
              className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-semibold"
              aria-label="Toggle preview theme"
            >
              {previewTheme === "light" ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
              {previewTheme === "light" ? "Dark" : "Light"}
            </button>
            {previewInfo && (
              <a
                href={previewInfo.fullPath}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent-primary)] px-2.5 py-1 text-xs font-semibold text-white"
              >
                <ExternalLink className="h-3 w-3" aria-hidden="true" />
                Open Tab
              </a>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close mobile preview"
              className="rounded-lg p-1.5 hover:bg-black/10"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="mt-3 flex flex-1 items-center justify-center overflow-auto">
          {error && (
            <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-xs text-red-800">
              {error}
            </div>
          )}
          {!error && loading && !previewInfo && (
            <p className="py-12 text-xs text-[var(--text-secondary)]">Issuing signed 15m preview URL...</p>
          )}
          {!error && previewInfo && (
            <div className="h-[680px] w-[390px] overflow-y-auto rounded-[28px] border-4 border-slate-800 shadow-xl">
              <PublicDigitalMenu
                qrToken={previewInfo.qrToken}
                previewParam={previewInfo.previewParam}
                initialTheme={previewTheme}
              />
            </div>
          )}
          {!error && !loading && tables.length === 0 && (
            <p className="py-12 text-xs text-[var(--text-secondary)]">
              Create an active table first to preview a table QR URL.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
