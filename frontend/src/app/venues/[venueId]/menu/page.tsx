// TODO(ui-asset): SCR-018
"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  ArrowDown,
  ArrowUp,
  Check,
  Clock,
  Copy,
  Download,
  Edit3,
  GripVertical,
  Lock,
  Plus,
  Search,
  Settings2,
  Smartphone,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { MenuItemDrawer } from "@/components/MenuItemDrawer";
import { MenuPreviewModal } from "@/components/MenuPreviewModal";
import { apiFetch, ApiError, getAccessToken } from "@/lib/api";
import { formatMinorUnits } from "@/lib/currency";
import { formatDietaryTag } from "@/lib/dietary";
import { t } from "@/lib/i18n";
import { hasCapability } from "@/lib/rbac";
import { useAuth } from "@/providers/AuthProvider";
import type {
  MenuCategoryDTO,
  MenuDTO,
  MenuItemDTO,
  VenueMenuSettings,
} from "@/types/floor";

const CURRENCIES = ["INR", "USD", "EUR", "GBP", "AED", "SGD", "CAD", "AUD", "JPY"];
const WEEKDAYS = [
  { id: 1, label: "Mon" },
  { id: 2, label: "Tue" },
  { id: 3, label: "Wed" },
  { id: 4, label: "Thu" },
  { id: 5, label: "Fri" },
  { id: 6, label: "Sat" },
  { id: 7, label: "Sun" },
];

interface SortableCategoryRowProps {
  cat: MenuCategoryDTO;
  selected: boolean;
  canManage: boolean;
  isFirst: boolean;
  isLast: boolean;
  onSelect: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onMove: (dir: -1 | 1) => void;
}

function SortableCategoryRow({
  cat,
  selected,
  canManage,
  isFirst,
  isLast,
  onSelect,
  onEdit,
  onDelete,
  onMove,
}: SortableCategoryRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: cat.id,
    disabled: !canManage,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex flex-wrap items-center justify-between gap-1.5 rounded-xl border px-2.5 py-2 text-xs transition ${
        selected
          ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/12 font-semibold"
          : "border-[var(--border-subtle)] bg-[var(--surface-solid)]"
      }`}
    >
      <div className="flex min-w-0 flex-1 items-center gap-1.5">
        {canManage && (
          <button
            type="button"
            {...attributes}
            {...listeners}
            aria-label={`Drag ${cat.name}`}
            className="inline-flex min-h-[44px] min-w-[44px] cursor-grab items-center justify-center p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] md:min-h-0 md:min-w-0"
          >
            <GripVertical className="h-3.5 w-3.5" />
          </button>
        )}
        <button
          type="button"
          onClick={onSelect}
          className="min-h-[44px] min-w-0 flex-1 truncate text-left md:min-h-0"
        >
          <span>{cat.name}</span>
          <span className="ml-1.5 text-[11px] text-[var(--text-secondary)]">
            ({cat.item_count})
          </span>
        </button>
      </div>
      {canManage && (
        <div className="flex flex-wrap items-center gap-0.5">
          <button
            type="button"
            disabled={isFirst}
            onClick={() => onMove(-1)}
            aria-label={`Move ${cat.name} up`}
            className="rounded p-1 hover:bg-black/10 disabled:opacity-30"
          >
            <ArrowUp className="h-3 w-3" />
          </button>
          <button
            type="button"
            disabled={isLast}
            onClick={() => onMove(1)}
            aria-label={`Move ${cat.name} down`}
            className="rounded p-1 hover:bg-black/10 disabled:opacity-30"
          >
            <ArrowDown className="h-3 w-3" />
          </button>
          <button
            type="button"
            onClick={onEdit}
            aria-label={`Edit category ${cat.name}`}
            className="rounded p-1 hover:bg-black/10"
          >
            <Edit3 className="h-3 w-3" />
          </button>
          <button
            type="button"
            onClick={onDelete}
            aria-label={`Delete category ${cat.name}`}
            className="rounded p-1 text-red-600 hover:bg-red-500/10"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
}

interface CsvPreviewRow {
  row_number: number;
  sku: string | null;
  name: string;
  category_name: string;
  action: "create" | "update" | "error";
  errors: string[];
}

interface CsvPreviewResult {
  import_id: string;
  mode: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  will_create: number;
  will_update: number;
  rows: CsvPreviewRow[];
}

export default function MenuStudioPage() {
  const params = useParams<{ venueId: string }>();
  const venueId = params?.venueId || "";
  const { user, policies, loading: authLoading, locale } = useAuth();
  const canRead = hasCapability(user?.role, "menu.read");
  const canManage =
    hasCapability(user?.role, "menu.manage") &&
    (user?.role !== "MANAGER" || policies.managers_can_manage_menu);
  const isOwner = user?.role === "OWNER";

  const [settings, setSettings] = useState<VenueMenuSettings | null>(null);
  const [menus, setMenus] = useState<MenuDTO[]>([]);
  const [selectedMenuId, setSelectedMenuId] = useState<string>("");
  const [categories, setCategories] = useState<MenuCategoryDTO[]>([]);
  const [selectedCatId, setSelectedCatId] = useState<string>("ALL");
  const [items, setItems] = useState<MenuItemDTO[]>([]);

  const [search, setSearch] = useState("");
  const [availFilter, setAvailFilter] = useState<"all" | "available" | "unavailable">("all");
  const [availPreset, setAvailPreset] = useState<"indefinite" | "2h" | "tomorrow">("indefinite");
  const [selectedItemIds, setSelectedItemIds] = useState<string[]>([]);
  const [bulkTargetCatId, setBulkTargetCatId] = useState<string>("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modals / Drawers
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<MenuItemDTO | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  // CSV Import Modal
  const [csvOpen, setCsvOpen] = useState(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvMode, setCsvMode] = useState<"create_only" | "upsert_by_sku">("upsert_by_sku");
  const [csvStrategy, setCsvStrategy] = useState<"all_or_nothing" | "skip_invalid">("all_or_nothing");
  const [csvPreview, setCsvPreview] = useState<CsvPreviewResult | null>(null);
  const [csvBusy, setCsvBusy] = useState(false);
  const [csvError, setCsvError] = useState<string | null>(null);

  // Settings Modal
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [cfgPublic, setCfgPublic] = useState(true);
  const [cfgShowSoldOut, setCfgShowSoldOut] = useState(true);
  const [cfgHost86, setCfgHost86] = useState(true);
  const [cfgGraceDays, setCfgGraceDays] = useState(7);
  const [cfgTagline, setCfgTagline] = useState("");
  const [cfgCurrency, setCfgCurrency] = useState("INR");
  const [confirmCurrencyOverride, setConfirmCurrencyOverride] = useState(false);

  // Menu create/edit modal
  const [menuModalOpen, setMenuModalOpen] = useState(false);
  const [editingMenu, setEditingMenu] = useState<MenuDTO | null>(null);
  const [menuName, setMenuName] = useState("");
  const [menuDesc, setMenuDesc] = useState("");
  const [menuHiName, setMenuHiName] = useState("");
  const [menuHiDesc, setMenuHiDesc] = useState("");
  const [menuStatus, setMenuStatus] = useState<"DRAFT" | "PUBLISHED" | "ARCHIVED">("DRAFT");
  const [menuDefault, setMenuDefault] = useState(false);
  const [schedEnabled, setSchedEnabled] = useState(false);
  const [schedDays, setSchedDays] = useState<number[]>([1, 2, 3, 4, 5, 6, 7]);
  const [schedStart, setSchedStart] = useState("11:00");
  const [schedEnd, setSchedEnd] = useState("23:00");

  // Category create/edit modal
  const [catModalOpen, setCatModalOpen] = useState(false);
  const [editingCat, setEditingCat] = useState<MenuCategoryDTO | null>(null);
  const [catName, setCatName] = useState("");
  const [catDesc, setCatDesc] = useState("");
  const [catHiName, setCatHiName] = useState("");
  const [catHiDesc, setCatHiDesc] = useState("");

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const canQuick86 = useMemo(() => {
    if (!user?.role) return false;
    if (hasCapability(user.role, "menu.availability")) return true;
    if (user.role === "HOST" && settings?.allow_host_menu_availability) return true;
    return false;
  }, [user, settings]);

  const loadMenus = useCallback(async () => {
    if (!venueId || !canRead) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{
        venue_settings: VenueMenuSettings;
        items: MenuDTO[];
      }>(`/api/v1/venues/${venueId}/menus`);
      setSettings(res.venue_settings);
      const list = res.items || [];
      setMenus(list);
      setSelectedMenuId((prev) =>
        prev && list.some((m) => m.id === prev) ? prev : list[0]?.id || "",
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load menus");
    } finally {
      setLoading(false);
    }
  }, [venueId, canRead]);

  const loadCategoriesAndItems = useCallback(async () => {
    if (!venueId || !canRead || !selectedMenuId) {
      setCategories([]);
      setItems([]);
      return;
    }
    try {
      const catRes = await apiFetch<{ items: MenuCategoryDTO[] }>(
        `/api/v1/venues/${venueId}/menus/${selectedMenuId}/categories`,
      );
      setCategories(catRes.items || []);

      const qs = new URLSearchParams({
        menu_id: selectedMenuId,
        available: availFilter,
      });
      if (selectedCatId !== "ALL") qs.set("category_id", selectedCatId);
      if (search.trim()) qs.set("search", search.trim());
      const itemRes = await apiFetch<{ items: MenuItemDTO[] }>(
        `/api/v1/venues/${venueId}/menu-items?${qs.toString()}`,
      );
      setItems(itemRes.items || []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load menu catalog");
    }
  }, [venueId, canRead, selectedMenuId, selectedCatId, availFilter, search]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadMenus();
    }
  }, [authLoading, user, loadMenus]);

  useEffect(() => {
    if (!authLoading && user && selectedMenuId) {
      void loadCategoriesAndItems();
    }
  }, [authLoading, user, selectedMenuId, loadCategoriesAndItems]);

  const activeMenu = useMemo(
    () => menus.find((m) => m.id === selectedMenuId) || null,
    [menus, selectedMenuId],
  );

  function openSettings() {
    if (!settings) return;
    setCfgPublic(settings.menu_public_enabled);
    setCfgShowSoldOut(settings.show_unavailable_items_public);
    setCfgHost86(settings.allow_host_menu_availability);
    setCfgGraceDays(settings.qr_grace_days);
    setCfgTagline(settings.menu_tagline || "");
    setCfgCurrency(settings.currency_code);
    setConfirmCurrencyOverride(false);
    setSettingsOpen(true);
  }

  async function saveSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!venueId) return;
    setError(null);
    setSuccessMsg(null);
    try {
      const updated = await apiFetch<VenueMenuSettings>(
        `/api/v1/venues/${venueId}/menu-settings`,
        {
          method: "PATCH",
          body: JSON.stringify({
            menu_public_enabled: cfgPublic,
            show_unavailable_items_public: cfgShowSoldOut,
            allow_host_menu_availability: cfgHost86,
            qr_grace_days: cfgGraceDays,
            menu_tagline: cfgTagline.trim() || null,
            ...(isOwner && cfgCurrency !== settings?.currency_code
              ? {
                  currency_code: cfgCurrency,
                  currency_override_confirm: confirmCurrencyOverride,
                }
              : {}),
          }),
        },
      );
      setSettings(updated);
      setSettingsOpen(false);
      setSuccessMsg("Updated venue menu settings.");
    } catch (err) {
      if (err instanceof ApiError && err.code === "CURRENCY_LOCKED") {
        setConfirmCurrencyOverride(true);
        setError(
          "Priced items already exist in this venue. Confirm currency override checkbox and save again if you intend to switch currency without auto-conversion.",
        );
      } else {
        setError(err instanceof ApiError ? err.message : "Failed to save settings");
      }
    }
  }

  function openMenuModal(m: MenuDTO | null) {
    setEditingMenu(m);
    if (m) {
      setMenuName(m.name);
      setMenuDesc(m.description || "");
      setMenuHiName(m.translations_json?.hi?.name || "");
      setMenuHiDesc(m.translations_json?.hi?.description || "");
      setMenuStatus((m.status as "DRAFT" | "PUBLISHED" | "ARCHIVED") || "DRAFT");
      setMenuDefault(m.is_default);
      const win = m.schedule_json?.windows?.[0];
      setSchedEnabled(Boolean(win));
      setSchedDays(win?.days || [1, 2, 3, 4, 5, 6, 7]);
      setSchedStart(win?.start || "11:00");
      setSchedEnd(win?.end || "23:00");
    } else {
      setMenuName("");
      setMenuDesc("");
      setMenuHiName("");
      setMenuHiDesc("");
      setMenuStatus("DRAFT");
      setMenuDefault(menus.length === 0);
      setSchedEnabled(false);
      setSchedDays([1, 2, 3, 4, 5, 6, 7]);
      setSchedStart("11:00");
      setSchedEnd("23:00");
    }
    setMenuModalOpen(true);
  }

  async function saveMenuModal(e: React.FormEvent) {
    e.preventDefault();
    if (!venueId) return;
    setError(null);
    const schedulePayload = schedEnabled
      ? { v: 1, windows: [{ days: schedDays, start: schedStart, end: schedEnd }] }
      : null;
    const hiMenuEntry: Record<string, string> = {};
    if (menuHiName.trim()) hiMenuEntry.name = menuHiName.trim();
    if (menuHiDesc.trim()) hiMenuEntry.description = menuHiDesc.trim();
    const translationsPayload = Object.keys(hiMenuEntry).length > 0 ? { hi: hiMenuEntry } : {};
    try {
      if (editingMenu) {
        await apiFetch(`/api/v1/venues/${venueId}/menus/${editingMenu.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: menuName.trim(),
            description: menuDesc.trim() || null,
            translations_json: translationsPayload,
            status: menuStatus,
            is_default: menuDefault,
            schedule_json: schedulePayload,
            clear_schedule: !schedEnabled,
          }),
        });
        setSuccessMsg(`Updated menu "${menuName.trim()}".`);
      } else {
        const created = await apiFetch<MenuDTO>(`/api/v1/venues/${venueId}/menus`, {
          method: "POST",
          body: JSON.stringify({
            name: menuName.trim(),
            description: menuDesc.trim() || null,
            translations_json: translationsPayload,
            status: menuStatus,
            is_default: menuDefault,
            schedule_json: schedulePayload,
          }),
        });
        setSelectedMenuId(created.id);
        setSelectedCatId("ALL");
        setSuccessMsg(`Created menu "${created.name}".`);
      }
      setMenuModalOpen(false);
      await loadMenus();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save menu");
    }
  }

  async function duplicateActiveMenu() {
    if (!venueId || !activeMenu) return;
    setError(null);
    try {
      const duplicated = await apiFetch<MenuDTO>(
        `/api/v1/venues/${venueId}/menus/${activeMenu.id}/duplicate`,
        { method: "POST" },
      );
      setSelectedMenuId(duplicated.id);
      setSelectedCatId("ALL");
      setSuccessMsg(`Duplicated menu "${activeMenu.name}" as DRAFT "${duplicated.name}".`);
      await loadMenus();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to duplicate menu");
    }
  }

  async function deleteActiveMenu() {
    if (!venueId || !activeMenu) return;
    if (!window.confirm(`Archive menu "${activeMenu.name}" and its categories?`)) return;
    try {
      await apiFetch(`/api/v1/venues/${venueId}/menus/${activeMenu.id}`, {
        method: "DELETE",
      });
      setSuccessMsg(`Archived menu "${activeMenu.name}".`);
      setSelectedCatId("ALL");
      await loadMenus();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete menu");
    }
  }

  async function saveCategoryModal(e: React.FormEvent) {
    e.preventDefault();
    if (!venueId || !selectedMenuId) return;
    const hiCatEntry: Record<string, string> = {};
    if (catHiName.trim()) hiCatEntry.name = catHiName.trim();
    if (catHiDesc.trim()) hiCatEntry.description = catHiDesc.trim();
    const translationsPayload = Object.keys(hiCatEntry).length > 0 ? { hi: hiCatEntry } : {};
    try {
      if (editingCat) {
        await apiFetch(`/api/v1/venues/${venueId}/categories/${editingCat.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: catName.trim(),
            description: catDesc.trim() || null,
            translations_json: translationsPayload,
          }),
        });
        setSuccessMsg(`Updated category "${catName.trim()}".`);
      } else {
        await apiFetch(`/api/v1/venues/${venueId}/menus/${selectedMenuId}/categories`, {
          method: "POST",
          body: JSON.stringify({
            name: catName.trim(),
            description: catDesc.trim() || null,
            translations_json: translationsPayload,
          }),
        });
        setSuccessMsg(`Added category "${catName.trim()}".`);
      }
      setCatModalOpen(false);
      await Promise.all([loadMenus(), loadCategoriesAndItems()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save category");
    }
  }

  async function handleDeleteCategory(cat: MenuCategoryDTO) {
    if (!venueId) return;
    if (!window.confirm(`Delete category "${cat.name}" and archive its ${cat.item_count} items?`)) {
      return;
    }
    try {
      await apiFetch(`/api/v1/venues/${venueId}/categories/${cat.id}`, {
        method: "DELETE",
      });
      if (selectedCatId === cat.id) setSelectedCatId("ALL");
      setSuccessMsg(`Deleted category "${cat.name}".`);
      await Promise.all([loadMenus(), loadCategoriesAndItems()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete category");
    }
  }

  async function persistCategoryOrder(nextCats: MenuCategoryDTO[]) {
    setCategories(nextCats);
    if (!venueId || !selectedMenuId) return;
    try {
      await apiFetch(`/api/v1/venues/${venueId}/menus/${selectedMenuId}/categories/reorder`, {
        method: "PATCH",
        body: JSON.stringify({ ids: nextCats.map((c) => c.id) }),
      });
      setSuccessMsg("Saved category display order.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save category order");
      await loadCategoriesAndItems();
    }
  }

  function handleCategoryDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = categories.findIndex((c) => c.id === active.id);
    const newIndex = categories.findIndex((c) => c.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    void persistCategoryOrder(arrayMove(categories, oldIndex, newIndex));
  }

  function moveCategoryByStep(idx: number, dir: -1 | 1) {
    const targetIdx = idx + dir;
    if (targetIdx < 0 || targetIdx >= categories.length) return;
    void persistCategoryOrder(arrayMove(categories, idx, targetIdx));
  }

  function computeUnavailableUntilIso(preset: "indefinite" | "2h" | "tomorrow"): string | null {
    if (preset === "indefinite") return null;
    if (preset === "2h") {
      return new Date(Date.now() + 2 * 3600 * 1000).toISOString();
    }
    const d = new Date();
    d.setDate(d.getDate() + 1);
    d.setHours(9, 0, 0, 0);
    return d.toISOString();
  }

  async function toggleQuick86(item: MenuItemDTO) {
    if (!venueId) return;
    const next = !item.is_available;
    const unavailIso = next ? null : computeUnavailableUntilIso(availPreset);
    setItems((prev) =>
      prev.map((x) =>
        x.id === item.id ? { ...x, is_available: next, unavailable_until: unavailIso } : x,
      ),
    );
    try {
      await apiFetch(`/api/v1/venues/${venueId}/menu-items/${item.id}/availability`, {
        method: "PATCH",
        body: JSON.stringify({ is_available: next, unavailable_until: unavailIso }),
      });
      setSuccessMsg(
        `${item.name}: ${
          next
            ? "In Stock"
            : unavailIso
              ? `Sold Out (auto-restores ${new Date(unavailIso).toLocaleTimeString()})`
              : "Sold Out (86'd)"
        }.`,
      );
    } catch (err) {
      setItems((prev) =>
        prev.map((x) =>
          x.id === item.id
            ? { ...x, is_available: !next, unavailable_until: item.unavailable_until }
            : x,
        ),
      );
      setError(err instanceof ApiError ? err.message : "Failed to toggle item availability");
    }
  }

  async function bulkSetAvailability(isAvailable: boolean) {
    if (!venueId || selectedItemIds.length === 0) return;
    const unavailIso = isAvailable ? null : computeUnavailableUntilIso(availPreset);
    try {
      const res = await apiFetch<{ updated_count: number }>(
        `/api/v1/venues/${venueId}/menu-items/bulk-availability`,
        {
          method: "PATCH",
          body: JSON.stringify({
            item_ids: selectedItemIds,
            is_available: isAvailable,
            unavailable_until: unavailIso,
          }),
        },
      );
      setSelectedItemIds([]);
      setSuccessMsg(
        `Marked ${res.updated_count} items as ${isAvailable ? "In Stock" : "Sold Out"}.`,
      );
      await loadCategoriesAndItems();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed bulk availability update");
    }
  }

  async function bulkItemAction(action: "delete" | "move") {
    if (!venueId || selectedItemIds.length === 0) return;
    const targetCat = bulkTargetCatId || categories[0]?.id || "";
    if (action === "move" && !targetCat) {
      setError("Select a destination category first.");
      return;
    }
    if (
      action === "delete" &&
      !window.confirm(`Archive ${selectedItemIds.length} selected dishes?`)
    ) {
      return;
    }
    try {
      const res = await apiFetch<{ affected: number }>(
        `/api/v1/venues/${venueId}/menu-items/bulk-action`,
        {
          method: "POST",
          body: JSON.stringify({
            action,
            item_ids: selectedItemIds,
            ...(action === "move" ? { target_category_id: targetCat } : {}),
          }),
        },
      );
      setSelectedItemIds([]);
      setSuccessMsg(
        action === "delete"
          ? `Archived ${res.affected} selected items.`
          : `Moved ${res.affected} selected items to target category.`,
      );
      await Promise.all([loadMenus(), loadCategoriesAndItems()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed bulk menu item action");
    }
  }

  async function downloadCsvTemplate() {
    if (!venueId) return;
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const token = getAccessToken();
      const res = await fetch(`${base}/api/v1/venues/${venueId}/menus/import/template`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "tablepulse-menu-import-template.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setCsvError("Failed to download CSV template");
    }
  }

  async function previewCsvImport() {
    if (!venueId || !selectedMenuId || !csvFile) return;
    if (csvFile.size > 2 * 1024 * 1024) {
      setCsvError("CSV file exceeds the 2 MB maximum upload limit.");
      return;
    }
    setCsvBusy(true);
    setCsvError(null);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const token = getAccessToken();
      const fd = new FormData();
      fd.append("file", csvFile);
      const res = await fetch(
        `${base}/api/v1/venues/${venueId}/menus/import/preview?menu_id=${encodeURIComponent(
          selectedMenuId,
        )}&mode=${encodeURIComponent(csvMode)}`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          credentials: "include",
          body: fd,
        },
      );
      const json = (await res.json()) as {
        success?: boolean;
        data?: CsvPreviewResult;
        error?: { message?: string };
      };
      if (!res.ok || !json.success || !json.data) {
        setCsvError(json.error?.message || `Preview failed (HTTP ${res.status})`);
        setCsvPreview(null);
        return;
      }
      setCsvPreview(json.data);
    } catch {
      setCsvError("Failed to upload and preview CSV file.");
    } finally {
      setCsvBusy(false);
    }
  }

  async function commitCsvImport() {
    if (!venueId || !csvPreview) return;
    setCsvBusy(true);
    setCsvError(null);
    try {
      const res = await apiFetch<{ created: number; updated: number; skipped: number }>(
        `/api/v1/venues/${venueId}/menus/import/${csvPreview.import_id}/commit`,
        {
          method: "POST",
          body: JSON.stringify({ strategy: csvStrategy }),
        },
      );
      setCsvOpen(false);
      setCsvFile(null);
      setCsvPreview(null);
      setSuccessMsg(
        `CSV import complete: ${res.created} created, ${res.updated} updated, ${res.skipped} skipped.`,
      );
      await Promise.all([loadMenus(), loadCategoriesAndItems()]);
    } catch (err) {
      setCsvError(err instanceof ApiError ? err.message : "Failed to commit CSV import");
    } finally {
      setCsvBusy(false);
    }
  }

  async function duplicateItem(item: MenuItemDTO) {
    if (!venueId) return;
    try {
      await apiFetch(`/api/v1/venues/${venueId}/menu-items/${item.id}/duplicate`, {
        method: "POST",
      });
      setSuccessMsg(`Duplicated "${item.name}".`);
      await Promise.all([loadMenus(), loadCategoriesAndItems()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to duplicate item");
    }
  }

  async function deleteItem(item: MenuItemDTO) {
    if (!venueId) return;
    if (!window.confirm(`Delete dish "${item.name}"?`)) return;
    try {
      await apiFetch(`/api/v1/venues/${venueId}/menu-items/${item.id}`, {
        method: "DELETE",
      });
      setSuccessMsg(`Archived dish "${item.name}".`);
      await Promise.all([loadMenus(), loadCategoriesAndItems()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete item");
    }
  }

  async function downloadCsvExport() {
    if (!venueId || !selectedMenuId) return;
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const token = getAccessToken();
      const res = await fetch(
        `${base}/api/v1/venues/${venueId}/menu-items?menu_id=${selectedMenuId}&format=csv`,
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
      a.download = `menu-${activeMenu?.name || "export"}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError("Failed to export menu CSV");
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

  const currency = settings?.currency_code || "INR";
  const baseMediaOrigin = process.env.NEXT_PUBLIC_API_BASE_URL || "";

  return (
    <AppShell venueId={venueId} toastMessage={successMsg}>
      <div className="flex flex-col gap-4">
        {/* Top bar */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">{t(locale, "p2.menu_title")}</h1>
            <p className="text-xs text-[var(--text-secondary)]">
              Manage digital menus, categories, dish photos, dietary tags, and live Quick-86 stock status.
              {settings && (
                <span className="ml-2 font-semibold">
                  Public Portal:{" "}
                  <span className={settings.menu_public_enabled ? "text-emerald-600" : "text-amber-600"}>
                    {settings.menu_public_enabled ? "LIVE" : "PAUSED"}
                  </span>{" "}
                  · Currency: {currency}
                </span>
              )}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setPreviewOpen(true)}
              className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-xs font-semibold hover:opacity-80"
            >
              <Smartphone className="h-3.5 w-3.5" aria-hidden="true" />
              {t(locale, "p2.preview_menu")}
            </button>
            <button
              type="button"
              onClick={() => void downloadCsvExport()}
              disabled={!selectedMenuId}
              className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-xs font-semibold hover:opacity-80 disabled:opacity-40"
            >
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
              Export CSV
            </button>
            {canManage && (
              <>
                <button
                  type="button"
                  disabled={!selectedMenuId}
                  onClick={() => {
                    setCsvFile(null);
                    setCsvPreview(null);
                    setCsvError(null);
                    setCsvOpen(true);
                  }}
                  className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-xs font-semibold hover:opacity-80 disabled:opacity-40"
                >
                  <Upload className="h-3.5 w-3.5" aria-hidden="true" />
                  Import CSV
                </button>
                <button
                  type="button"
                  onClick={openSettings}
                  className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-xs font-semibold hover:opacity-80"
                >
                  <Settings2 className="h-3.5 w-3.5" aria-hidden="true" />
                  Settings
                </button>
                <button
                  type="button"
                  onClick={() => openMenuModal(null)}
                  className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-3.5 py-2 text-xs font-semibold text-white hover:opacity-90"
                >
                  <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                  New Menu
                </button>
              </>
            )}
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
            {/* Menu Selector Tabs */}
            <div className="tp-glass flex flex-wrap items-center justify-between gap-2 rounded-xl border p-3">
              <div className="flex flex-wrap items-center gap-1.5">
                {menus.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => {
                      setSelectedMenuId(m.id);
                      setSelectedCatId("ALL");
                    }}
                    className={`inline-flex min-h-[40px] items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                      m.id === selectedMenuId
                        ? "bg-[var(--accent-primary)] text-white"
                        : "border border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                    }`}
                  >
                    <span>{m.name}</span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                        m.status === "PUBLISHED"
                          ? "bg-emerald-800 text-white"
                          : "bg-slate-800 text-white"
                      }`}
                    >
                      {m.status}
                    </span>
                  </button>
                ))}
              </div>
              {canManage && activeMenu && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => void duplicateActiveMenu()}
                    className="inline-flex min-h-[44px] items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1 text-xs font-semibold"
                  >
                    <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                    Duplicate Menu
                  </button>
                  <button
                    type="button"
                    onClick={() => openMenuModal(activeMenu)}
                    className="inline-flex min-h-[44px] items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1 text-xs font-semibold"
                  >
                    <Edit3 className="h-3.5 w-3.5" aria-hidden="true" />
                    Edit Menu
                  </button>
                  <button
                    type="button"
                    onClick={() => void deleteActiveMenu()}
                    className="inline-flex min-h-[44px] items-center gap-1 rounded-lg bg-red-500/15 px-2.5 py-1 text-xs font-semibold text-red-700 dark:text-red-300"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    Archive
                  </button>
                </div>
              )}
            </div>

            {loading && menus.length === 0 && (
              <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
                Loading menu studio...
              </div>
            )}

            {!loading && menus.length === 0 && (
              <div className="tp-glass rounded-xl border p-8 text-center">
                <h2 className="text-base font-bold">No digital menus created yet</h2>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  Create your primary Dine-In or Brunch menu to unlock live QR menus for your tables.
                </p>
                {canManage && (
                  <button
                    type="button"
                    onClick={() => openMenuModal(null)}
                    className="mt-4 inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white"
                  >
                    <Plus className="h-4 w-4" />
                    Create First Menu
                  </button>
                )}
              </div>
            )}

            {activeMenu && (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-[270px_1fr]">
                {/* Category Rail */}
                <aside className="tp-glass flex flex-col gap-2.5 rounded-xl border p-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                      Categories
                    </h2>
                    {canManage && (
                      <button
                        type="button"
                        onClick={() => {
                          setEditingCat(null);
                          setCatName("");
                          setCatDesc("");
                          setCatHiName("");
                          setCatHiDesc("");
                          setCatModalOpen(true);
                        }}
                        className="inline-flex min-h-[44px] items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1 text-[11px] font-semibold"
                      >
                        <Plus className="h-3 w-3" />
                        Add Category
                      </button>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => setSelectedCatId("ALL")}
                    className={`rounded-xl border px-3 py-2 text-left text-xs font-semibold ${
                      selectedCatId === "ALL"
                        ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/12"
                        : "border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                    }`}
                  >
                    All Categories ({activeMenu.item_count})
                  </button>

                  <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragEnd={handleCategoryDragEnd}
                  >
                    <SortableContext
                      items={categories.map((c) => c.id)}
                      strategy={verticalListSortingStrategy}
                    >
                      <div className="flex flex-col gap-1.5">
                        {categories.map((cat, idx) => (
                          <SortableCategoryRow
                            key={cat.id}
                            cat={cat}
                            selected={selectedCatId === cat.id}
                            canManage={canManage}
                            isFirst={idx === 0}
                            isLast={idx === categories.length - 1}
                            onSelect={() => setSelectedCatId(cat.id)}
                            onEdit={() => {
                              setEditingCat(cat);
                              setCatName(cat.name);
                              setCatDesc(cat.description || "");
                              setCatHiName(cat.translations_json?.hi?.name || "");
                              setCatHiDesc(cat.translations_json?.hi?.description || "");
                              setCatModalOpen(true);
                            }}
                            onDelete={() => void handleDeleteCategory(cat)}
                            onMove={(dir) => moveCategoryByStep(idx, dir)}
                          />
                        ))}
                      </div>
                    </SortableContext>
                  </DndContext>
                </aside>

                {/* Item Workspace */}
                <section className="flex min-w-0 flex-col gap-3">
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
                          placeholder="Search dishes..."
                          aria-label="Search menu dishes"
                          className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] py-1.5 pl-8 pr-3 text-xs"
                        />
                      </label>
                      <select
                        aria-label="Filter availability"
                        value={availFilter}
                        onChange={(e) =>
                          setAvailFilter(e.target.value as "all" | "available" | "unavailable")
                        }
                        className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-medium"
                      >
                        <option value="all">All Stock States</option>
                        <option value="available">In Stock Only</option>
                        <option value="unavailable">Sold Out (86)</option>
                      </select>

                      {canQuick86 && (
                        <select
                          aria-label="Quick-86 auto-restore preset"
                          value={availPreset}
                          onChange={(e) =>
                            setAvailPreset(e.target.value as "indefinite" | "2h" | "tomorrow")
                          }
                          className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-medium"
                        >
                          <option value="indefinite">86 Duration: Manual</option>
                          <option value="2h">86 for 2 Hours</option>
                          <option value="tomorrow">86 Until Tomorrow 09:00</option>
                        </select>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {canQuick86 && selectedItemIds.length > 0 && (
                        <>
                          <button
                            type="button"
                            onClick={() => void bulkSetAvailability(true)}
                            className="min-h-[44px] rounded-lg bg-emerald-700 px-2.5 py-1.5 text-xs font-semibold text-white"
                          >
                            Mark In Stock ({selectedItemIds.length})
                          </button>
                          <button
                            type="button"
                            onClick={() => void bulkSetAvailability(false)}
                            className="min-h-[44px] rounded-lg bg-amber-800 px-2.5 py-1.5 text-xs font-semibold text-white"
                          >
                            Mark 86 ({selectedItemIds.length})
                          </button>
                        </>
                      )}
                      {canManage && selectedItemIds.length > 0 && categories.length > 0 && (
                        <>
                          <select
                            aria-label="Target category for bulk move"
                            value={bulkTargetCatId || categories[0]?.id || ""}
                            onChange={(e) => setBulkTargetCatId(e.target.value)}
                            className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2 py-1.5 text-xs font-medium"
                          >
                            {categories.map((c) => (
                              <option key={c.id} value={c.id}>
                                Move to: {c.name}
                              </option>
                            ))}
                          </select>
                          <button
                            type="button"
                            onClick={() => void bulkItemAction("move")}
                            className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-semibold"
                          >
                            Move ({selectedItemIds.length})
                          </button>
                          <button
                            type="button"
                            onClick={() => void bulkItemAction("delete")}
                            className="min-h-[44px] rounded-lg bg-red-600/90 px-2.5 py-1.5 text-xs font-semibold text-white"
                          >
                            Delete ({selectedItemIds.length})
                          </button>
                        </>
                      )}
                      {canManage && categories.length > 0 && (
                        <button
                          type="button"
                          onClick={() => {
                            setEditingItem(null);
                            setDrawerOpen(true);
                          }}
                          className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-3.5 py-2 text-xs font-semibold text-white"
                        >
                          <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                          Add Dish
                        </button>
                      )}
                    </div>
                  </div>

                  {items.length === 0 ? (
                    <div className="tp-glass rounded-xl border p-8 text-center">
                      <h3 className="text-sm font-bold">No dishes in this view</h3>
                      <p className="mt-1 text-xs text-[var(--text-secondary)]">
                        {categories.length === 0
                          ? "Create a category on the left first, then add dishes."
                          : "Add your first dish or clear search filters."}
                      </p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      {items.map((item) => (
                        <article
                          key={item.id}
                          className={`tp-glass flex gap-3 rounded-xl border p-3 transition ${
                            !item.is_available ? "border-amber-700/60" : ""
                          }`}
                        >
                          {canQuick86 && (
                            <label className="inline-flex min-h-[44px] min-w-[44px] shrink-0 cursor-pointer items-center justify-center md:min-h-0 md:min-w-0">
                              <input
                                type="checkbox"
                                aria-label={`Select ${item.name}`}
                                checked={selectedItemIds.includes(item.id)}
                                onChange={() =>
                                  setSelectedItemIds((prev) =>
                                    prev.includes(item.id)
                                      ? prev.filter((x) => x !== item.id)
                                      : [...prev, item.id],
                                  )
                                }
                              />
                            </label>
                          )}

                          {item.thumb_url ? (
                            <img
                              src={`${baseMediaOrigin}${item.thumb_url}`}
                              alt={item.image_alt || item.name}
                              className="h-16 w-16 shrink-0 rounded-lg border border-[var(--border-subtle)] object-cover"
                            />
                          ) : (
                            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg border border-dashed border-[var(--border-subtle)] text-[10px] text-[var(--text-secondary)]">
                              No Photo
                            </div>
                          )}

                          <div className="flex min-w-0 flex-1 flex-col justify-between gap-1">
                            <div>
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <h3 className="truncate text-sm font-bold">{item.name}</h3>
                                  {item.sku && (
                                    <span className="font-mono text-[10px] text-[var(--text-secondary)]">
                                      SKU: {item.sku}
                                    </span>
                                  )}
                                </div>
                                <span className="shrink-0 font-mono text-xs font-bold">
                                  {formatMinorUnits(item.price_minor_units, currency, locale)}
                                </span>
                              </div>
                              {!item.is_available && item.unavailable_until && (
                                <p className="mt-0.5 inline-flex items-center gap-1 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800 dark:text-amber-300">
                                  <Clock className="h-2.5 w-2.5" aria-hidden="true" />
                                  Auto-restores {new Date(item.unavailable_until).toLocaleString()}
                                </p>
                              )}
                              {item.description && (
                                <p className="line-clamp-2 text-[11px] text-[var(--text-secondary)]">
                                  {item.description}
                                </p>
                              )}
                              {item.dietary_tags.length > 0 && (
                                <div className="mt-1 flex flex-wrap gap-1">
                                  {item.dietary_tags.map((tag) => (
                                    <span
                                      key={tag}
                                      className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300"
                                    >
                                      {formatDietaryTag(tag)}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>

                            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                              {canQuick86 ? (
                                <button
                                  type="button"
                                  aria-pressed={item.is_available}
                                  onClick={() => void toggleQuick86(item)}
                                  className={`min-h-[44px] rounded-full px-3 py-1 text-[11px] font-bold transition ${
                                    item.is_available
                                      ? "bg-emerald-800 text-white"
                                      : "bg-amber-800 text-white"
                                  }`}
                                >
                                  {item.is_available ? "In Stock" : "Sold Out (86)"}
                                </button>
                              ) : (
                                <span className="text-[11px] font-semibold">
                                  {item.is_available ? "In Stock" : "Sold Out"}
                                </span>
                              )}

                              {canManage && (
                                <div className="flex items-center gap-1">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setEditingItem(item);
                                      setDrawerOpen(true);
                                    }}
                                    aria-label={`Edit ${item.name}`}
                                    className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg border border-[var(--border-subtle)] p-1.5 hover:bg-black/10"
                                  >
                                    <Edit3 className="h-3.5 w-3.5" />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => void duplicateItem(item)}
                                    aria-label={`Duplicate ${item.name}`}
                                    className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg border border-[var(--border-subtle)] p-1.5 hover:bg-black/10"
                                  >
                                    <Copy className="h-3.5 w-3.5" />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => void deleteItem(item)}
                                    aria-label={`Delete ${item.name}`}
                                    className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg bg-red-500/15 p-1.5 text-red-600 hover:bg-red-500/25"
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            )}
          </>
        )}
      </div>

      {/* Item Drawer SCR-019 */}
      <MenuItemDrawer
        open={drawerOpen}
        venueId={venueId}
        currencyCode={currency}
        categories={categories}
        defaultCategoryId={selectedCatId !== "ALL" ? selectedCatId : categories[0]?.id || ""}
        item={editingItem}
        onClose={() => setDrawerOpen(false)}
        onSaved={() => void Promise.all([loadMenus(), loadCategoriesAndItems()])}
      />

      {/* Mobile Preview SCR-021 */}
      <MenuPreviewModal
        open={previewOpen}
        venueId={venueId}
        onClose={() => setPreviewOpen(false)}
      />

      {/* Venue Menu Settings Modal */}
      {settingsOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Venue Menu Settings"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
        >
          <form
            onSubmit={saveSettings}
            className="w-full max-w-md rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-5 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
              <h2 className="text-base font-bold">Venue Menu Settings</h2>
              <button
                type="button"
                onClick={() => setSettingsOpen(false)}
                aria-label="Close settings"
                className="rounded-lg p-1.5"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-4 space-y-3 text-xs">
              <label className="flex items-center gap-2 font-semibold">
                <input
                  type="checkbox"
                  checked={cfgPublic}
                  onChange={(e) => setCfgPublic(e.target.checked)}
                />
                Enable Public Digital Menu on Table QR Codes
              </label>
              <label className="flex items-center gap-2 font-semibold">
                <input
                  type="checkbox"
                  checked={cfgShowSoldOut}
                  onChange={(e) => setCfgShowSoldOut(e.target.checked)}
                />
                Show 86&apos;d / Sold-Out Items on Customer Menu (with badge)
              </label>
              <label className="flex items-center gap-2 font-semibold">
                <input
                  type="checkbox"
                  checked={cfgHost86}
                  onChange={(e) => setCfgHost86(e.target.checked)}
                />
                Allow HOST role to toggle Quick-86 stock status
              </label>
              <label className="flex flex-col gap-1 font-medium">
                Venue Tagline (shown on customer menu header)
                <input
                  maxLength={160}
                  value={cfgTagline}
                  onChange={(e) => setCfgTagline(e.target.value)}
                  className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1 font-medium">
                  Default QR Grace Days
                  <input
                    type="number"
                    min={0}
                    max={30}
                    value={cfgGraceDays}
                    onChange={(e) => setCfgGraceDays(Number(e.target.value) || 0)}
                    className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-1.5 text-sm"
                  />
                </label>
                <label className="flex flex-col gap-1 font-medium">
                  Currency {isOwner ? "(OWNER)" : "(Locked to OWNER)"}
                  <select
                    disabled={!isOwner}
                    value={cfgCurrency}
                    onChange={(e) => setCfgCurrency(e.target.value)}
                    className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-sm disabled:opacity-60"
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {isOwner && cfgCurrency !== settings?.currency_code && (
                <label className="flex items-center gap-2 rounded-lg border border-amber-400 bg-amber-50 p-2.5 text-amber-900">
                  <input
                    type="checkbox"
                    checked={confirmCurrencyOverride}
                    onChange={(e) => setConfirmCurrencyOverride(e.target.checked)}
                  />
                  Confirm switching currency without converting existing item prices
                </label>
              )}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setSettingsOpen(false)}
                className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="min-h-[42px] rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white"
              >
                Save Settings
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Menu Create / Edit Modal */}
      {menuModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={editingMenu ? "Edit Menu" : "New Menu"}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
        >
          <form
            onSubmit={saveMenuModal}
            className="w-full max-w-md rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-5 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
              <h2 className="text-base font-bold">
                {editingMenu ? `Edit ${editingMenu.name}` : "Create Digital Menu"}
              </h2>
              <button
                type="button"
                onClick={() => setMenuModalOpen(false)}
                aria-label="Close menu dialog"
                className="rounded-lg p-1.5"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-4 space-y-3 text-xs">
              <label className="flex flex-col gap-1 font-medium">
                Menu Name
                <input
                  required
                  maxLength={100}
                  value={menuName}
                  onChange={(e) => setMenuName(e.target.value)}
                  placeholder="All-Day Dine-In, Weekend Brunch..."
                  className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1 font-medium">
                Description
                <input
                  maxLength={300}
                  value={menuDesc}
                  onChange={(e) => setMenuDesc(e.target.value)}
                  className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <label className="flex flex-col gap-1 font-medium">
                  Hindi Menu Name (हिन्दी नाम, optional)
                  <input
                    maxLength={100}
                    value={menuHiName}
                    onChange={(e) => setMenuHiName(e.target.value)}
                    placeholder="पूरा दिन मेनू"
                    className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-1.5 text-sm"
                  />
                </label>
                <label className="flex flex-col gap-1 font-medium">
                  Hindi Description (optional)
                  <input
                    maxLength={300}
                    value={menuHiDesc}
                    onChange={(e) => setMenuHiDesc(e.target.value)}
                    className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-1.5 text-sm"
                  />
                </label>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1 font-medium">
                  Publication Status
                  <select
                    value={menuStatus}
                    onChange={(e) =>
                      setMenuStatus(e.target.value as "DRAFT" | "PUBLISHED" | "ARCHIVED")
                    }
                    className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-sm"
                  >
                    <option value="DRAFT">DRAFT</option>
                    <option value="PUBLISHED">PUBLISHED</option>
                    <option value="ARCHIVED">ARCHIVED</option>
                  </select>
                </label>
                <label className="flex items-center gap-2 pt-5 font-semibold">
                  <input
                    type="checkbox"
                    checked={menuDefault}
                    onChange={(e) => setMenuDefault(e.target.checked)}
                  />
                  Default Fallback Menu
                </label>
              </div>

              <label className="flex items-center gap-2 font-semibold">
                <input
                  type="checkbox"
                  checked={schedEnabled}
                  onChange={(e) => setSchedEnabled(e.target.checked)}
                />
                Enable Time-of-Day Schedule Window
              </label>

              {schedEnabled && (
                <div className="space-y-2 rounded-xl border border-[var(--border-subtle)] p-3">
                  <div className="flex flex-wrap gap-1">
                    {WEEKDAYS.map((wd) => {
                      const active = schedDays.includes(wd.id);
                      return (
                        <button
                          key={wd.id}
                          type="button"
                          onClick={() =>
                            setSchedDays((prev) =>
                              active && prev.length > 1
                                ? prev.filter((d) => d !== wd.id)
                                : prev.includes(wd.id)
                                  ? prev
                                  : [...prev, wd.id],
                            )
                          }
                          className={`rounded px-2 py-1 text-[11px] font-semibold ${
                            active
                              ? "bg-[var(--accent-primary)] text-white"
                              : "border border-[var(--border-subtle)]"
                          }`}
                        >
                          {wd.label}
                        </button>
                      );
                    })}
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <label className="flex flex-col gap-1">
                      Start (HH:MM)
                      <input
                        type="time"
                        value={schedStart}
                        onChange={(e) => setSchedStart(e.target.value)}
                        className="rounded border border-[var(--border-subtle)] bg-transparent px-2 py-1"
                      />
                    </label>
                    <label className="flex flex-col gap-1">
                      End (HH:MM)
                      <input
                        type="time"
                        value={schedEnd}
                        onChange={(e) => setSchedEnd(e.target.value)}
                        className="rounded border border-[var(--border-subtle)] bg-transparent px-2 py-1"
                      />
                    </label>
                  </div>
                </div>
              )}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setMenuModalOpen(false)}
                className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="inline-flex min-h-[42px] items-center gap-1 rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white"
              >
                <Check className="h-3.5 w-3.5" />
                Save Menu
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Category Modal */}
      {catModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={editingCat ? "Edit Category" : "Add Category"}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
        >
          <form
            onSubmit={saveCategoryModal}
            className="w-full max-w-sm rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-5 shadow-2xl"
          >
            <h2 className="text-base font-bold">
              {editingCat ? `Edit Category · ${editingCat.name}` : "Add Menu Category"}
            </h2>
            <div className="mt-3 space-y-3 text-xs">
              <label className="flex flex-col gap-1 font-medium">
                Category Name
                <input
                  required
                  maxLength={100}
                  value={catName}
                  onChange={(e) => setCatName(e.target.value)}
                  placeholder="Starters, Wood-Fired Mains, Drinks..."
                  className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1 font-medium">
                Description
                <input
                  maxLength={300}
                  value={catDesc}
                  onChange={(e) => setCatDesc(e.target.value)}
                  className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1 font-medium">
                Hindi Category Name (हिन्दी नाम, optional)
                <input
                  maxLength={100}
                  value={catHiName}
                  onChange={(e) => setCatHiName(e.target.value)}
                  placeholder="शुरुआती व्यंजन"
                  className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1 font-medium">
                Hindi Description (optional)
                <input
                  maxLength={300}
                  value={catHiDesc}
                  onChange={(e) => setCatHiDesc(e.target.value)}
                  className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setCatModalOpen(false)}
                className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="min-h-[44px] rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white"
              >
                Save Category
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Menu CSV Import Modal */}
      {csvOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Import Menu CSV"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
        >
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
              <div>
                <h2 className="text-base font-bold">Import Menu Dishes via CSV</h2>
                <p className="text-[11px] text-[var(--text-secondary)]">
                  Target menu: <strong>{activeMenu?.name || "Selected Menu"}</strong> · max 2 MB, 2,000 rows
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCsvOpen(false)}
                aria-label="Close CSV import"
                className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-1.5"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {csvError && (
              <div
                role="alert"
                className="mt-3 rounded-xl border border-red-300 bg-red-50 p-3 text-xs font-medium text-red-800"
              >
                {csvError}
              </div>
            )}

            <div className="mt-4 space-y-3 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => void downloadCsvTemplate()}
                  className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 font-semibold"
                >
                  <Download className="h-3.5 w-3.5" aria-hidden="true" />
                  Download CSV Template
                </button>
                <label className="flex items-center gap-2 font-medium">
                  Import Mode:
                  <select
                    aria-label="CSV import mode"
                    value={csvMode}
                    onChange={(e) => {
                      setCsvMode(e.target.value as "create_only" | "upsert_by_sku");
                      setCsvPreview(null);
                    }}
                    className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-medium"
                  >
                    <option value="upsert_by_sku">Upsert by SKU (create & update)</option>
                    <option value="create_only">Create New Dishes Only</option>
                  </select>
                </label>
              </div>

              <label className="flex flex-col gap-1 font-medium">
                Select CSV File (UTF-8, round-trips cleanly with Export CSV)
                <input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(e) => {
                    setCsvFile(e.target.files?.[0] || null);
                    setCsvPreview(null);
                    setCsvError(null);
                  }}
                  className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-transparent p-2 text-xs"
                />
              </label>

              <div className="flex justify-end">
                <button
                  type="button"
                  disabled={!csvFile || csvBusy}
                  onClick={() => void previewCsvImport()}
                  className="min-h-[44px] rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
                >
                  {csvBusy ? "Validating..." : "Validate & Preview Rows"}
                </button>
              </div>

              {csvPreview && (
                <div className="space-y-3 rounded-xl border border-[var(--border-subtle)] p-3">
                  <div className="flex flex-wrap gap-3 font-semibold">
                    <span>Total: {csvPreview.total_rows}</span>
                    <span className="text-emerald-700 dark:text-emerald-300">
                      Valid: {csvPreview.valid_rows} (Create {csvPreview.will_create} · Update{" "}
                      {csvPreview.will_update})
                    </span>
                    <span
                      className={
                        csvPreview.invalid_rows > 0
                          ? "text-red-700 dark:text-red-300"
                          : "text-[var(--text-secondary)]"
                      }
                    >
                      Invalid: {csvPreview.invalid_rows}
                    </span>
                  </div>

                  <div className="max-h-52 overflow-auto rounded-lg border border-[var(--border-subtle)]">
                    <table className="w-full text-left text-[11px]">
                      <thead className="bg-black/5">
                        <tr>
                          <th className="px-2 py-1.5">Row</th>
                          <th className="px-2 py-1.5">SKU</th>
                          <th className="px-2 py-1.5">Category / Dish</th>
                          <th className="px-2 py-1.5">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border-subtle)]">
                        {(csvPreview.rows ?? []).slice(0, 100).map((r) => (
                          <tr key={r.row_number}>
                            <td className="px-2 py-1.5 font-mono">{r.row_number}</td>
                            <td className="px-2 py-1.5 font-mono">{r.sku || "—"}</td>
                            <td className="px-2 py-1.5">
                              {r.category_name} · {r.name}
                            </td>
                            <td className="px-2 py-1.5">
                              {r.errors.length > 0 ? (
                                <span className="font-semibold text-red-700 dark:text-red-300">
                                  {r.errors.join("; ")}
                                </span>
                              ) : (
                                <span className="font-semibold uppercase text-emerald-700 dark:text-emerald-300">
                                  {r.action}
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                    <label className="flex items-center gap-2 font-medium">
                      Commit Strategy:
                      <select
                        aria-label="CSV commit strategy"
                        value={csvStrategy}
                        onChange={(e) =>
                          setCsvStrategy(e.target.value as "all_or_nothing" | "skip_invalid")
                        }
                        className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs"
                      >
                        <option value="all_or_nothing">All-or-nothing (reject if any error)</option>
                        <option value="skip_invalid">Import valid rows & skip invalid</option>
                      </select>
                    </label>
                    <button
                      type="button"
                      disabled={
                        csvBusy ||
                        csvPreview.valid_rows === 0 ||
                        (csvStrategy === "all_or_nothing" && csvPreview.invalid_rows > 0)
                      }
                      onClick={() => void commitCsvImport()}
                      className="min-h-[44px] rounded-lg bg-emerald-700 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      {csvBusy ? "Importing..." : `Commit Import (${csvPreview.valid_rows} rows)`}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
