// TODO(ui-asset): SCR-017
"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  Camera,
  Check,
  Copy,
  Edit3,
  Layers,
  Lock,
  Plus,
  QrCode,
  RefreshCw,
  RotateCcw,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, ApiError, getAccessToken } from "@/lib/api";
import { t } from "@/lib/i18n";
import { hasCapability } from "@/lib/rbac";
import { previewBulkCodes } from "@/lib/table-codes";
import { useAuth } from "@/providers/AuthProvider";
import type { AdminTableItem } from "@/types/floor";

interface TablesSummary {
  total_active: number;
  total_seats: number;
  mapped_count: number;
  inactive_count: number;
  sections: string[];
}

interface TablesListResponse {
  items: AdminTableItem[];
  total: number;
  page: number;
  page_size: number;
  summary: TablesSummary;
}

interface TableFormState {
  table_code: string;
  display_name: string;
  section_name: string;
  min_capacity: number;
  seat_capacity: number;
  shape: "RECT" | "CIRCLE" | "BOOTH";
  is_combinable: boolean;
  is_active: boolean;
  table_notes: string;
}

const DEFAULT_FORM: TableFormState = {
  table_code: "",
  display_name: "",
  section_name: "Main",
  min_capacity: 1,
  seat_capacity: 4,
  shape: "RECT",
  is_combinable: false,
  is_active: true,
  table_notes: "",
};

export default function TablesAdminPage() {
  const params = useParams<{ venueId: string }>();
  const venueId = params?.venueId || "";
  const { user, policies, loading: authLoading, locale } = useAuth();
  const canRead = hasCapability(user?.role, "tables.read");
  const canManage =
    hasCapability(user?.role, "tables.manage") &&
    (user?.role !== "MANAGER" || policies.managers_can_manage_tables);

  const [items, setItems] = useState<AdminTableItem[]>([]);
  const [summary, setSummary] = useState<TablesSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [sectionFilter, setSectionFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive" | "archived">("all");
  const [mappedFilter, setMappedFilter] = useState<"all" | "mapped" | "unmapped">("all");

  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkSectionValue, setBulkSectionValue] = useState("Patio");

  // Single create/edit modal
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingTable, setEditingTable] = useState<AdminTableItem | null>(null);
  const [form, setForm] = useState<TableFormState>(DEFAULT_FORM);
  const [submitting, setSubmitting] = useState(false);

  // Bulk create modal
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkPrefix, setBulkPrefix] = useState("P");
  const [bulkStart, setBulkStart] = useState(1);
  const [bulkCount, setBulkCount] = useState(6);
  const [bulkZeroPad, setBulkZeroPad] = useState(2);
  const [bulkSection, setBulkSection] = useState("Patio");
  const [bulkMinCap, setBulkMinCap] = useState(2);
  const [bulkMaxCap, setBulkMaxCap] = useState(4);
  const [bulkShape, setBulkShape] = useState<"RECT" | "CIRCLE" | "BOOTH">("RECT");

  // Delete / force-delete confirmation dialog
  const [deleteTarget, setDeleteTarget] = useState<AdminTableItem | null>(null);
  const [deleteInUseConflict, setDeleteInUseConflict] = useState(false);
  const [deleteReason, setDeleteReason] = useState("");

  // Restore conflict dialog (E-05 new_table_code)
  const [restoreTarget, setRestoreTarget] = useState<AdminTableItem | null>(null);
  const [restoreNewCode, setRestoreNewCode] = useState("");
  const [restoreConflictMsg, setRestoreConflictMsg] = useState<string | null>(null);

  const loadTables = useCallback(async () => {
    if (!venueId || !canRead) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({
        status: statusFilter,
        mapped: mappedFilter,
        page: "1",
        page_size: "200",
      });
      if (search.trim()) qs.set("search", search.trim());
      if (sectionFilter !== "ALL") qs.set("section", sectionFilter);
      const data = await apiFetch<TablesListResponse>(
        `/api/v1/venues/${venueId}/tables?${qs.toString()}`,
      );
      setItems(data.items || []);
      setSummary(data.summary || null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load tables");
    } finally {
      setLoading(false);
    }
  }, [venueId, canRead, search, sectionFilter, statusFilter, mappedFilter]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadTables();
    }
  }, [authLoading, user, loadTables]);

  const bulkPreview = useMemo(
    () => previewBulkCodes(bulkPrefix, bulkStart, bulkCount, bulkZeroPad),
    [bulkPrefix, bulkStart, bulkCount, bulkZeroPad],
  );

  function openCreateModal() {
    setEditingTable(null);
    setForm(DEFAULT_FORM);
    setError(null);
    setEditorOpen(true);
  }

  function openEditModal(tbl: AdminTableItem) {
    setEditingTable(tbl);
    setForm({
      table_code: tbl.table_code,
      display_name: tbl.display_name || "",
      section_name: tbl.section_name,
      min_capacity: tbl.min_capacity,
      seat_capacity: tbl.seat_capacity,
      shape: (tbl.shape as "RECT" | "CIRCLE" | "BOOTH") || "RECT",
      is_combinable: tbl.is_combinable,
      is_active: tbl.is_active,
      table_notes: tbl.table_notes || "",
    });
    setError(null);
    setEditorOpen(true);
  }

  async function handleSaveSingle(e: React.FormEvent) {
    e.preventDefault();
    if (!venueId) return;
    if (form.min_capacity > form.seat_capacity) {
      setError("Minimum party size cannot exceed max capacity.");
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      if (editingTable) {
        await apiFetch(`/api/v1/venues/${venueId}/tables/${editingTable.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            table_code: form.table_code.trim(),
            display_name: form.display_name.trim() || null,
            section_name: form.section_name.trim() || "Main",
            min_capacity: form.min_capacity,
            seat_capacity: form.seat_capacity,
            shape: form.shape,
            is_combinable: form.is_combinable,
            is_active: form.is_active,
            table_notes: form.table_notes.trim() || null,
            version: editingTable.version,
          }),
        });
        setSuccessMsg(`Updated table ${form.table_code.trim().toUpperCase()}.`);
      } else {
        await apiFetch(`/api/v1/venues/${venueId}/tables`, {
          method: "POST",
          body: JSON.stringify({
            table_code: form.table_code.trim(),
            display_name: form.display_name.trim() || null,
            section_name: form.section_name.trim() || "Main",
            min_capacity: form.min_capacity,
            seat_capacity: form.seat_capacity,
            shape: form.shape,
            is_combinable: form.is_combinable,
            is_active: form.is_active,
            table_notes: form.table_notes.trim() || null,
          }),
        });
        setSuccessMsg(`Created table ${form.table_code.trim().toUpperCase()} with auto-generated QR.`);
      }
      setEditorOpen(false);
      await loadTables();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(err.message);
      } else {
        setError(err instanceof ApiError ? err.message : "Failed to save table");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleBulkCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!venueId) return;
    if (bulkMinCap > bulkMaxCap) {
      setError("Bulk min capacity cannot exceed max capacity.");
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await apiFetch<{ created_count: number }>(
        `/api/v1/venues/${venueId}/tables/bulk`,
        {
          method: "POST",
          body: JSON.stringify({
            prefix: bulkPrefix.trim(),
            start_number: bulkStart,
            count: bulkCount,
            zero_pad: bulkZeroPad,
            section_name: bulkSection.trim() || "Main",
            min_capacity: bulkMinCap,
            seat_capacity: bulkMaxCap,
            shape: bulkShape,
            is_combinable: false,
          }),
        },
      );
      setSuccessMsg(`Created ${res.created_count} tables with unique QR codes.`);
      setBulkOpen(false);
      await loadTables();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to bulk create tables");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleBulkUpdate(payload: { section_name?: string; is_active?: boolean }) {
    if (!venueId || selectedIds.length === 0) return;
    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await apiFetch<{ updated_count: number }>(
        `/api/v1/venues/${venueId}/tables/bulk`,
        {
          method: "PATCH",
          body: JSON.stringify({
            table_ids: selectedIds,
            ...payload,
          }),
        },
      );
      setSelectedIds([]);
      setSuccessMsg(`Updated ${res.updated_count} selected tables.`);
      await loadTables();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to bulk update tables");
    } finally {
      setSubmitting(false);
    }
  }

  async function confirmDelete(force: boolean) {
    if (!venueId || !deleteTarget) return;
    setSubmitting(true);
    setError(null);
    try {
      const qs = new URLSearchParams({ force: force ? "true" : "false" });
      if (deleteReason.trim()) qs.set("reason", deleteReason.trim());
      await apiFetch(`/api/v1/venues/${venueId}/tables/${deleteTarget.id}?${qs.toString()}`, {
        method: "DELETE",
      });
      setSuccessMsg(`Archived table ${deleteTarget.table_code} and revoked its QR code.`);
      setDeleteTarget(null);
      setDeleteInUseConflict(false);
      setDeleteReason("");
      await loadTables();
    } catch (err) {
      if (err instanceof ApiError && err.code === "TABLE_IN_USE" && !force) {
        setDeleteInUseConflict(true);
      } else {
        setError(err instanceof ApiError ? err.message : "Failed to delete table");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDuplicateTable(tbl: AdminTableItem) {
    if (!venueId) return;
    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const created = await apiFetch<AdminTableItem>(
        `/api/v1/venues/${venueId}/tables/${tbl.id}/duplicate`,
        { method: "POST" },
      );
      setSuccessMsg(`Duplicated table ${tbl.table_code} → ${created.table_code}.`);
      await loadTables();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to duplicate table");
    } finally {
      setSubmitting(false);
    }
  }

  async function submitRestore(tbl: AdminTableItem, newCode?: string) {
    if (!venueId) return;
    setSubmitting(true);
    setError(null);
    setRestoreConflictMsg(null);
    try {
      const restored = await apiFetch<AdminTableItem>(
        `/api/v1/venues/${venueId}/tables/${tbl.id}/restore`,
        {
          method: "POST",
          body: JSON.stringify(newCode?.trim() ? { new_table_code: newCode.trim() } : {}),
        },
      );
      setRestoreTarget(null);
      setRestoreNewCode("");
      setSuccessMsg(`Restored table ${restored.table_code} and minted a fresh active QR code.`);
      await loadTables();
    } catch (err) {
      if (err instanceof ApiError && err.code === "DUPLICATE_TABLE_CODE") {
        setRestoreTarget(tbl);
        setRestoreNewCode((prev) => prev || `${tbl.table_code}R`);
        setRestoreConflictMsg(err.message);
      } else {
        setError(err instanceof ApiError ? err.message : "Failed to restore archived table");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePurgeTable(tbl: AdminTableItem) {
    if (!venueId) return;
    if (
      !window.confirm(
        `Permanently purge archived table "${tbl.table_code}"? This cannot be undone and fails if historical telemetry exists.`,
      )
    ) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/venues/${venueId}/tables/${tbl.id}/purge`, {
        method: "DELETE",
      });
      setSuccessMsg(`Permanently purged table ${tbl.table_code}.`);
      await loadTables();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to purge table");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleExportSelectedQrPdf() {
    if (!venueId || selectedIds.length === 0) return;
    setSubmitting(true);
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
        body: JSON.stringify({ table_ids: selectedIds, layout: "A4_4UP" }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "selected-table-qr-codes.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setSuccessMsg(`Exported A4 4-up QR PDF for ${selectedIds.length} tables.`);
    } catch {
      setError("Failed to export QR PDF for selected tables");
    } finally {
      setSubmitting(false);
    }
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  const allSelected = items.length > 0 && items.every((tItem) => selectedIds.includes(tItem.id));

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

  return (
    <AppShell venueId={venueId} toastMessage={successMsg}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">{t(locale, "p2.tables_title")}</h1>
            <p className="text-xs text-[var(--text-secondary)]">
              Create, configure, map to cameras, or manage non-camera tables alongside live QR tokens.
            </p>
          </div>
          {canManage && (
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => void loadTables()}
                className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-xs font-semibold hover:opacity-80"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                {t(locale, "action.refresh")}
              </button>
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  setBulkOpen(true);
                }}
                className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-xs font-semibold hover:opacity-80"
              >
                <Layers className="h-3.5 w-3.5" aria-hidden="true" />
                {t(locale, "p2.bulk_add")}
              </button>
              <button
                type="button"
                onClick={openCreateModal}
                className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-3.5 py-2 text-xs font-semibold text-white hover:opacity-90"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                {t(locale, "p2.add_table")}
              </button>
            </div>
          )}
        </div>

        {!authLoading && user && !canRead && (
          <div className="tp-glass flex flex-col items-center gap-3 rounded-xl border p-8 text-center">
            <Lock className="h-8 w-8 text-amber-600" aria-hidden="true" />
            <h2 className="text-base font-bold">Permission Denied</h2>
            <p className="text-sm text-[var(--text-secondary)]">
              Your role cannot view venue table directory settings.
            </p>
          </div>
        )}

        {canRead && (
          <>
            {/* KPI summary strip */}
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <div className="tp-glass rounded-xl border p-3">
                <p className="text-xs font-medium text-[var(--text-secondary)]">Active Tables</p>
                <p className="mt-1 text-2xl font-bold">{summary ? summary.total_active : "—"}</p>
              </div>
              <div className="tp-glass rounded-xl border p-3">
                <p className="text-xs font-medium text-[var(--text-secondary)]">Total Seats</p>
                <p className="mt-1 text-2xl font-bold">{summary ? summary.total_seats : "—"}</p>
              </div>
              <div className="tp-glass rounded-xl border p-3">
                <p className="text-xs font-medium text-[var(--text-secondary)]">Camera-Mapped</p>
                <p className="mt-1 text-2xl font-bold text-emerald-600">
                  {summary ? `${summary.mapped_count} / ${summary.total_active}` : "—"}
                </p>
              </div>
              <div className="tp-glass rounded-xl border p-3">
                <p className="text-xs font-medium text-[var(--text-secondary)]">Inactive</p>
                <p className="mt-1 text-2xl font-bold text-[var(--text-secondary)]">
                  {summary ? summary.inactive_count : "—"}
                </p>
              </div>
            </div>

            {/* Search & filters */}
            <div className="tp-glass flex flex-wrap items-center justify-between gap-2 rounded-xl border p-3">
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
                    placeholder="Search code, label, section..."
                    aria-label="Search tables"
                    className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] py-1.5 pl-8 pr-3 text-xs"
                  />
                </label>

                <select
                  aria-label="Filter by section"
                  value={sectionFilter}
                  onChange={(e) => setSectionFilter(e.target.value)}
                  className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-medium"
                >
                  <option value="ALL">All Sections</option>
                  {(summary?.sections || []).map((sec) => (
                    <option key={sec} value={sec}>
                      {sec}
                    </option>
                  ))}
                </select>

                <select
                  aria-label="Filter by status"
                  value={statusFilter}
                  onChange={(e) =>
                    setStatusFilter(e.target.value as "all" | "active" | "inactive" | "archived")
                  }
                  className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-medium"
                >
                  <option value="all">All Active/Inactive</option>
                  <option value="active">Active Only</option>
                  <option value="inactive">Inactive Only</option>
                  <option value="archived">Archived Only</option>
                </select>

                <select
                  aria-label="Filter by camera mapping"
                  value={mappedFilter}
                  onChange={(e) => setMappedFilter(e.target.value as "all" | "mapped" | "unmapped")}
                  className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-medium"
                >
                  <option value="all">All Mapping Modes</option>
                  <option value="mapped">Camera-Mapped</option>
                  <option value="unmapped">{t(locale, "p2.manual_mode")}</option>
                </select>
              </div>

              {canManage && selectedIds.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5">
                  <span className="text-xs font-bold">{selectedIds.length} selected</span>
                  <input
                    type="text"
                    aria-label="Target section name"
                    value={bulkSectionValue}
                    onChange={(e) => setBulkSectionValue(e.target.value)}
                    placeholder="Section..."
                    className="min-h-[44px] w-28 rounded border border-[var(--border-subtle)] bg-transparent px-2 py-1 text-xs"
                  />
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={() => void handleBulkUpdate({ section_name: bulkSectionValue.trim() || "Main" })}
                    className="min-h-[44px] rounded bg-[var(--accent-primary)] px-2.5 py-1 text-xs font-semibold text-white"
                  >
                    Move Section
                  </button>
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={() => void handleBulkUpdate({ is_active: false })}
                    className="min-h-[44px] rounded bg-amber-800 px-2.5 py-1 text-xs font-semibold text-white"
                  >
                    Deactivate
                  </button>
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={() => void handleBulkUpdate({ is_active: true })}
                    className="min-h-[44px] rounded bg-emerald-700 px-2.5 py-1 text-xs font-semibold text-white"
                  >
                    Activate
                  </button>
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={() => void handleExportSelectedQrPdf()}
                    className="inline-flex min-h-[44px] items-center gap-1 rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1 text-xs font-semibold"
                  >
                    <QrCode className="h-3.5 w-3.5" aria-hidden="true" />
                    Export QRs PDF
                  </button>
                </div>
              )}
            </div>

            {error && (
              <div
                role="alert"
                className="flex items-center justify-between rounded-xl border border-red-300 bg-red-50 p-3 text-xs font-medium text-red-800"
              >
                <span>{error}</span>
                <button
                  type="button"
                  onClick={() => setError(null)}
                  className="rounded px-2 py-1 text-xs underline"
                >
                  Dismiss
                </button>
              </div>
            )}

            {loading && (
              <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
                Loading venue tables...
              </div>
            )}

            {!loading && items.length === 0 && (
              <div className="tp-glass rounded-xl border p-8 text-center">
                <h2 className="text-base font-bold">No tables match current filters</h2>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  Add single tables, generate ranges with Bulk Add, or clear your search filters.
                </p>
              </div>
            )}

            {!loading && items.length > 0 && (
              <>
                {/* Desktop & Tablet Table */}
                <div className="tp-glass hidden overflow-x-auto rounded-xl border md:block">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-[var(--border-subtle)] bg-[var(--surface-solid)] text-[11px] uppercase text-[var(--text-secondary)]">
                      <tr>
                        {canManage && (
                          <th className="px-3 py-3">
                            <input
                              type="checkbox"
                              aria-label="Select all tables"
                              checked={allSelected}
                              onChange={(e) =>
                                setSelectedIds(e.target.checked ? items.map((x) => x.id) : [])
                              }
                            />
                          </th>
                        )}
                        <th className="px-3 py-3">Table</th>
                        <th className="px-3 py-3">Section</th>
                        <th className="px-3 py-3">Capacity</th>
                        <th className="px-3 py-3">Shape</th>
                        <th className="px-3 py-3">Tracking</th>
                        <th className="px-3 py-3">QR Status</th>
                        <th className="px-3 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border-subtle)]">
                      {items.map((tbl) => (
                        <tr key={tbl.id} className={!tbl.is_active ? "opacity-60" : undefined}>
                          {canManage && (
                            <td className="px-3 py-3">
                              <input
                                type="checkbox"
                                aria-label={`Select ${tbl.table_code}`}
                                checked={selectedIds.includes(tbl.id)}
                                onChange={() => toggleSelect(tbl.id)}
                              />
                            </td>
                          )}
                          <td className="px-3 py-3">
                            <div className="font-bold text-[var(--text-primary)]">
                              {tbl.table_code}
                            </div>
                            {tbl.display_name && (
                              <div className="text-[11px] text-[var(--text-secondary)]">
                                {tbl.display_name}
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-3">{tbl.section_name}</td>
                          <td className="px-3 py-3 font-mono">
                            {tbl.min_capacity}–{tbl.seat_capacity}
                          </td>
                          <td className="px-3 py-3">{tbl.shape}</td>
                          <td className="px-3 py-3">
                            {tbl.is_monitored ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
                                <Camera className="h-3 w-3" aria-hidden="true" />
                                Camera AI
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 rounded-full border border-dashed border-[var(--border-subtle)] px-2 py-0.5 text-[11px] font-semibold text-[var(--text-secondary)]">
                                {t(locale, "p2.manual_mode")}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-3">
                            <Link
                              href={`/venues/${venueId}/settings/qr-codes`}
                              className="inline-flex items-center gap-1 text-[var(--accent-primary)] hover:underline"
                            >
                              <QrCode className="h-3 w-3" aria-hidden="true" />
                              <span>{tbl.qr_status || "MISSING"}</span>
                              <span className="text-[var(--text-secondary)]">
                                ({tbl.qr_scan_count})
                              </span>
                            </Link>
                          </td>
                          <td className="px-3 py-3 text-right">
                            {canManage && (
                              <div className="inline-flex flex-wrap items-center justify-end gap-1.5">
                                {tbl.deleted_at ? (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() => void submitRestore(tbl)}
                                      className="inline-flex min-h-[44px] items-center gap-1 rounded-lg border border-emerald-600/40 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-500/20 dark:text-emerald-300"
                                    >
                                      <RotateCcw className="h-3 w-3" aria-hidden="true" />
                                      Restore
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => void handlePurgeTable(tbl)}
                                      className="inline-flex min-h-[44px] items-center gap-1 rounded-lg bg-red-500/15 px-2.5 py-1 text-xs font-semibold text-red-700 hover:bg-red-500/25 dark:text-red-300"
                                    >
                                      <Trash2 className="h-3 w-3" aria-hidden="true" />
                                      Purge
                                    </button>
                                  </>
                                ) : (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() => void handleDuplicateTable(tbl)}
                                      aria-label={`Duplicate ${tbl.table_code}`}
                                      className="inline-flex min-h-[44px] items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1 text-xs font-semibold hover:opacity-80"
                                    >
                                      <Copy className="h-3 w-3" aria-hidden="true" />
                                      Duplicate
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => openEditModal(tbl)}
                                      className="inline-flex min-h-[44px] items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1 text-xs font-semibold hover:opacity-80"
                                    >
                                      <Edit3 className="h-3 w-3" aria-hidden="true" />
                                      Edit
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setDeleteTarget(tbl);
                                        setDeleteInUseConflict(false);
                                        setDeleteReason("");
                                      }}
                                      aria-label={`Archive ${tbl.table_code}`}
                                      className="inline-flex min-h-[44px] items-center gap-1 rounded-lg bg-red-500/15 px-2.5 py-1 text-xs font-semibold text-red-700 hover:bg-red-500/25 dark:text-red-300"
                                    >
                                      <Trash2 className="h-3 w-3" aria-hidden="true" />
                                    </button>
                                  </>
                                )}
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile Cards (<768px) */}
                <div className="flex flex-col gap-3 md:hidden">
                  {items.map((tbl) => (
                    <article
                      key={tbl.id}
                      className={`tp-glass rounded-xl border p-4 ${!tbl.is_active ? "opacity-60" : ""}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-base font-bold">{tbl.table_code}</span>
                            {!tbl.is_active && (
                              <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">
                                INACTIVE
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-[var(--text-secondary)]">
                            {tbl.display_name ? `${tbl.display_name} · ` : ""}
                            {tbl.section_name} · {tbl.min_capacity}–{tbl.seat_capacity} seats · {tbl.shape}
                          </p>
                        </div>
                        {tbl.is_monitored ? (
                          <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
                            Camera AI
                          </span>
                        ) : (
                          <span className="rounded-full border border-dashed border-[var(--border-subtle)] px-2 py-0.5 text-[11px] font-semibold text-[var(--text-secondary)]">
                            {t(locale, "p2.manual_mode")}
                          </span>
                        )}
                      </div>
                      {canManage && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {tbl.deleted_at ? (
                            <>
                              <button
                                type="button"
                                onClick={() => void submitRestore(tbl)}
                                className="inline-flex min-h-[44px] flex-1 items-center justify-center gap-1 rounded-lg border border-emerald-600/40 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-700 dark:text-emerald-300"
                              >
                                <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                                Restore
                              </button>
                              <button
                                type="button"
                                onClick={() => void handlePurgeTable(tbl)}
                                className="inline-flex min-h-[44px] items-center justify-center gap-1 rounded-lg bg-red-500/15 px-3 py-2 text-xs font-semibold text-red-700 dark:text-red-300"
                              >
                                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                                Purge
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                type="button"
                                onClick={() => void handleDuplicateTable(tbl)}
                                className="inline-flex min-h-[44px] items-center justify-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-xs font-semibold"
                              >
                                <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                                Duplicate
                              </button>
                              <button
                                type="button"
                                onClick={() => openEditModal(tbl)}
                                className="inline-flex min-h-[44px] flex-1 items-center justify-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-xs font-semibold"
                              >
                                <Edit3 className="h-3.5 w-3.5" aria-hidden="true" />
                                Edit
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setDeleteTarget(tbl);
                                  setDeleteInUseConflict(false);
                                  setDeleteReason("");
                                }}
                                aria-label={`Archive ${tbl.table_code}`}
                                className="inline-flex min-h-[44px] items-center justify-center gap-1 rounded-lg bg-red-500/15 px-3 py-2 text-xs font-semibold text-red-700 dark:text-red-300"
                              >
                                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                                Archive
                              </button>
                            </>
                          )}
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>

      {/* Add / Edit Table Modal */}
      {editorOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={editingTable ? `Edit Table ${editingTable.table_code}` : "Add Table"}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
        >
          <form
            onSubmit={handleSaveSingle}
            className="w-full max-w-lg rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-5 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
              <h2 className="text-base font-bold">
                {editingTable ? `Edit Table ${editingTable.table_code}` : "Add Table"}
              </h2>
              <button
                type="button"
                onClick={() => setEditorOpen(false)}
                aria-label="Close modal"
                className="rounded-lg p-1.5 hover:bg-black/10"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-xs font-medium">
                Table Code
                <input
                  required
                  maxLength={20}
                  value={form.table_code}
                  onChange={(e) => setForm((f) => ({ ...f, table_code: e.target.value.toUpperCase() }))}
                  placeholder="e.g. T12 or P01"
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium">
                Display Name (optional)
                <input
                  maxLength={80}
                  value={form.display_name}
                  onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))}
                  placeholder="e.g. Window Booth 1"
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium">
                Section
                <input
                  required
                  maxLength={60}
                  value={form.section_name}
                  onChange={(e) => setForm((f) => ({ ...f, section_name: e.target.value }))}
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium">
                Shape
                <select
                  value={form.shape}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, shape: e.target.value as "RECT" | "CIRCLE" | "BOOTH" }))
                  }
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-sm"
                >
                  <option value="RECT">Rectangle</option>
                  <option value="CIRCLE">Circle</option>
                  <option value="BOOTH">Booth</option>
                </select>
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium">
                Min Party Size
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={form.min_capacity}
                  onChange={(e) => setForm((f) => ({ ...f, min_capacity: Number(e.target.value) || 1 }))}
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium">
                Max Seat Capacity
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={form.seat_capacity}
                  onChange={(e) => setForm((f) => ({ ...f, seat_capacity: Number(e.target.value) || 4 }))}
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>

              <label className="col-span-full flex flex-col gap-1 text-xs font-medium">
                Staff Notes (internal only)
                <input
                  maxLength={255}
                  value={form.table_notes}
                  onChange={(e) => setForm((f) => ({ ...f, table_notes: e.target.value }))}
                  placeholder="Wheelchair accessible, power outlet..."
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>

              <label className="flex items-center gap-2 text-xs font-medium">
                <input
                  type="checkbox"
                  checked={form.is_combinable}
                  onChange={(e) => setForm((f) => ({ ...f, is_combinable: e.target.checked }))}
                />
                Combinable for large parties
              </label>

              <label className="flex items-center gap-2 text-xs font-medium">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                />
                Active in floor operations
              </label>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditorOpen(false)}
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
                {submitting ? "Saving..." : editingTable ? "Save Changes" : "Create Table"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Bulk Add Tables Modal */}
      {bulkOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Bulk Add Tables"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
        >
          <form
            onSubmit={handleBulkCreate}
            className="w-full max-w-lg rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-5 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
              <h2 className="text-base font-bold">{t(locale, "p2.bulk_add")}</h2>
              <button
                type="button"
                onClick={() => setBulkOpen(false)}
                aria-label="Close bulk modal"
                className="rounded-lg p-1.5 hover:bg-black/10"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1 text-xs font-medium">
                Prefix
                <input
                  required
                  maxLength={10}
                  value={bulkPrefix}
                  onChange={(e) => setBulkPrefix(e.target.value.toUpperCase())}
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium">
                Start Number
                <input
                  type="number"
                  min={1}
                  max={9999}
                  value={bulkStart}
                  onChange={(e) => setBulkStart(Number(e.target.value) || 1)}
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium">
                Count (1–50)
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={bulkCount}
                  onChange={(e) => setBulkCount(Number(e.target.value) || 1)}
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium">
                Zero Padding (1–4)
                <input
                  type="number"
                  min={1}
                  max={4}
                  value={bulkZeroPad}
                  onChange={(e) => setBulkZeroPad(Number(e.target.value) || 2)}
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium">
                Section
                <input
                  required
                  maxLength={60}
                  value={bulkSection}
                  onChange={(e) => setBulkSection(e.target.value)}
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium">
                Shape
                <select
                  value={bulkShape}
                  onChange={(e) => setBulkShape(e.target.value as "RECT" | "CIRCLE" | "BOOTH")}
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-sm"
                >
                  <option value="RECT">Rectangle</option>
                  <option value="CIRCLE">Circle</option>
                  <option value="BOOTH">Booth</option>
                </select>
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium">
                Min Capacity
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={bulkMinCap}
                  onChange={(e) => setBulkMinCap(Number(e.target.value) || 1)}
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium">
                Max Seats
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={bulkMaxCap}
                  onChange={(e) => setBulkMaxCap(Number(e.target.value) || 4)}
                  className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
                />
              </label>
            </div>

            <div className="mt-4 rounded-xl border border-[var(--border-subtle)] bg-black/5 p-3">
              <p className="text-[11px] font-bold uppercase text-[var(--text-secondary)]">
                Live Preview ({bulkPreview.length} tables)
              </p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {bulkPreview.slice(0, 12).map((code) => (
                  <span
                    key={code}
                    className="rounded-md border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2 py-0.5 font-mono text-xs font-semibold"
                  >
                    {code}
                  </span>
                ))}
                {bulkPreview.length > 12 && (
                  <span className="px-1 text-xs text-[var(--text-secondary)]">
                    … +{bulkPreview.length - 12} more
                  </span>
                )}
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setBulkOpen(false)}
                className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || bulkPreview.length === 0}
                className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
              >
                <Layers className="h-3.5 w-3.5" aria-hidden="true" />
                {submitting ? "Creating..." : `Generate ${bulkPreview.length} Tables`}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Delete / Force Delete Modal */}
      {deleteTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Archive ${deleteTarget.table_code}`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
        >
          <div className="w-full max-w-md rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-5 shadow-2xl">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" aria-hidden="true" />
              <div>
                <h2 className="text-base font-bold">
                  {deleteInUseConflict
                    ? `Table ${deleteTarget.table_code} is Currently In Use`
                    : `Archive Table ${deleteTarget.table_code}?`}
                </h2>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  {deleteInUseConflict
                    ? `Table is currently ${deleteTarget.current_state} or assigned to an active waitlist party. Force archiving will resolve open alerts and revoke its QR token immediately.`
                    : "Archiving removes this table from active operations and immediately revokes its QR codes (returning 410 Gone to scans)."}
                </p>
              </div>
            </div>

            <label className="mt-4 flex flex-col gap-1 text-xs font-medium">
              Reason (optional, audit logged)
              <input
                maxLength={200}
                value={deleteReason}
                onChange={(e) => setDeleteReason(e.target.value)}
                placeholder="Section remodel, seasonal patio closed..."
                className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-xs"
              />
            </label>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setDeleteTarget(null);
                  setDeleteInUseConflict(false);
                }}
                className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={() => void confirmDelete(deleteInUseConflict)}
                className="min-h-[44px] rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
              >
                {submitting
                  ? "Archiving..."
                  : deleteInUseConflict
                    ? "Force Archive Table"
                    : "Archive Table"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Restore Table with Code Conflict Override Modal */}
      {restoreTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Restore ${restoreTarget.table_code}`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void submitRestore(restoreTarget, restoreNewCode);
            }}
            className="w-full max-w-md rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-5 shadow-2xl"
          >
            <h2 className="text-base font-bold">Restore Table {restoreTarget.table_code}</h2>
            <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
              {restoreConflictMsg ||
                "Enter a unique table code to restore this archived table without colliding with an active table."}
            </p>
            <label className="mt-4 flex flex-col gap-1 text-xs font-medium">
              New Table Code
              <input
                required
                maxLength={24}
                value={restoreNewCode}
                onChange={(e) => setRestoreNewCode(e.target.value)}
                className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
              />
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setRestoreTarget(null);
                  setRestoreConflictMsg(null);
                }}
                className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !restoreNewCode.trim()}
                className="min-h-[44px] rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
              >
                {submitting ? "Restoring..." : "Restore with New Code"}
              </button>
            </div>
          </form>
        </div>
      )}
    </AppShell>
  );
}
