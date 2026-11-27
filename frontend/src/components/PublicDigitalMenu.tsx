// TODO(ui-asset): SCR-022
"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Clock,
  Flame,
  Languages,
  Moon,
  RefreshCw,
  Search,
  Sparkles,
  Sun,
  Utensils,
  X,
} from "lucide-react";
import { formatMinorUnits } from "@/lib/currency";
import type { PublicMenuItemDTO, PublicMenuPayload } from "@/types/floor";

interface PublicDigitalMenuProps {
  qrToken: string;
  previewParam?: string | null;
  initialTheme?: "light" | "dark";
}

const PUBLIC_LABELS = {
  en: {
    searchPlaceholder: "Search dishes or ingredients...",
    veg: "Veg",
    nonVeg: "Non-Veg",
    vegan: "Vegan",
    glutenFree: "Gluten-Free",
    spicy: "Spicy",
    chefSpecial: "Chef Special",
    soldOut: "Sold Out",
    featured: "Featured",
    prepTime: "Prep time",
    mins: "min",
    calories: "Calories",
    variants: "Sizes & Portions",
    allergens: "Allergens",
    noMatches: "No dishes match your current filters.",
    clearFilters: "Clear filters",
    pausedTitle: "Digital Menu Paused",
    pausedBody: "This restaurant's digital menu is temporarily paused. Please ask your server for assistance.",
    revokedTitle: "Table QR Replaced",
    revokedBody: "This table QR sticker has been rotated. Please scan the updated code placed on your table.",
    notFoundTitle: "QR Code Not Found",
    notFoundBody: "We could not recognize this menu code. Please rescan the QR code on your table.",
    tableInactiveTitle: "Table Unavailable",
    tableInactiveBody: "This table is currently inactive. Please check with the host stand.",
    errorTitle: "Menu Temporarily Unavailable",
    retry: "Try Again",
    previewBanner: "Staff Preview Mode — scans are not counted",
    disclaimer:
      "Menu items, prices, and availability are provided by the restaurant and may change. Please notify your server of any severe food allergies before ordering.",
  },
  hi: {
    searchPlaceholder: "व्यंजन या सामग्री खोजें...",
    veg: "शाकाहारी",
    nonVeg: "मांसाहारी",
    vegan: "वीगन",
    glutenFree: "ग्लूटेन-फ्री",
    spicy: "तीखा",
    chefSpecial: "शेफ स्पेशल",
    soldOut: "समाप्त (Sold Out)",
    featured: "विशेष",
    prepTime: "तैयारी समय",
    mins: "मिनट",
    calories: "कैलोरी",
    variants: "आकार / विकल्प",
    allergens: "एलर्जी चेतावनी",
    noMatches: "आपके फ़िल्टर से कोई व्यंजन नहीं मिला।",
    clearFilters: "फ़िल्टर हटाएँ",
    pausedTitle: "डिजिटल मेनू अस्थायी रूप से बंद है",
    pausedBody: "इस रेस्टोरेंट का डिजिटल मेनू अभी बंद है। कृपया अपने सर्वर से सहायता लें।",
    revokedTitle: "टेबल QR बदला जा चुका है",
    revokedBody: "यह टेबल QR स्टिकर बदल दिया गया है। कृपया अपनी टेबल पर नया QR स्कैन करें।",
    notFoundTitle: "QR कोड नहीं मिला",
    notFoundBody: "यह मेनू कोड मान्य नहीं है। कृपया अपनी टेबल पर QR दोबारा स्कैन करें।",
    tableInactiveTitle: "टेबल उपलब्ध नहीं है",
    tableInactiveBody: "यह टेबल अभी निष्क्रिय है। कृपया होस्ट से संपर्क करें।",
    errorTitle: "मेनू अस्थायी रूप से अनुपलब्ध है",
    retry: "पुनः प्रयास करें",
    previewBanner: "स्टाफ़ पूर्वावलोकन मोड — स्कैन गिने नहीं जाते",
    disclaimer:
      "व्यंजन, मूल्य और उपलब्धता रेस्टोरेंट द्वारा प्रदान की गई हैं। किसी भी फ़ूड एलर्जी की जानकारी ऑर्डर से पहले अवश्य दें।",
  },
} as const;

const DIETARY_CHIPS = [
  { key: "VEG", labelKey: "veg" as const },
  { key: "NON_VEG", labelKey: "nonVeg" as const },
  { key: "VEGAN", labelKey: "vegan" as const },
  { key: "GLUTEN_FREE", labelKey: "glutenFree" as const },
  { key: "SPICY", labelKey: "spicy" as const },
  { key: "CHEF_SPECIAL", labelKey: "chefSpecial" as const },
];

function itemMatchesDietaryFilter(tags: string[], filterKey: string): boolean {
  if (filterKey === "SPICY") {
    return tags.some((t) => t.startsWith("SPICY_"));
  }
  return tags.includes(filterKey);
}

export function PublicDigitalMenu({
  qrToken,
  previewParam,
  initialTheme = "light",
}: PublicDigitalMenuProps) {
  const [theme, setTheme] = useState<"light" | "dark">(initialTheme);
  const [locale, setLocale] = useState<"en" | "hi">("en");
  const [data, setData] = useState<PublicMenuPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [activeMenuId, setActiveMenuId] = useState<string>("");
  const [search, setSearch] = useState("");
  const [dietFilter, setDietFilter] = useState<string | null>(null);
  const [activeItem, setActiveItem] = useState<PublicMenuItemDTO | null>(null);

  useEffect(() => {
    setTheme(initialTheme);
  }, [initialTheme]);

  const loadMenu = useCallback(async () => {
    if (!qrToken) return;
    setLoading(true);
    setErrorCode(null);
    setErrorMsg(null);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const qs = previewParam ? `?p=${encodeURIComponent(previewParam)}` : "";
      const res = await fetch(`${base}/api/v1/public/menu/${encodeURIComponent(qrToken)}${qs}`, {
        method: "GET",
        credentials: "omit",
        referrerPolicy: "no-referrer",
      });
      const json = (await res.json()) as {
        success?: boolean;
        data?: PublicMenuPayload;
        error?: { code?: string; message?: string };
      };
      if (!res.ok || !json.success || !json.data) {
        setErrorCode(json.error?.code || `HTTP_${res.status}`);
        setErrorMsg(json.error?.message || "Unable to load digital menu");
        setData(null);
        return;
      }
      setData(json.data);
      const firstMenu = json.data.menus[0];
      setActiveMenuId((prev) =>
        prev && json.data?.menus.some((m) => m.id === prev) ? prev : firstMenu?.id || "",
      );
    } catch {
      setErrorCode("NETWORK_ERROR");
      setErrorMsg("Network unreachable");
    } finally {
      setLoading(false);
    }
  }, [qrToken, previewParam]);

  useEffect(() => {
    void loadMenu();
  }, [loadMenu]);

  useEffect(() => {
    if (!activeItem) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setActiveItem(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeItem]);

  const lbl = PUBLIC_LABELS[locale];
  const currentMenu = useMemo(
    () => data?.menus.find((m) => m.id === activeMenuId) || data?.menus[0] || null,
    [data, activeMenuId],
  );

  const filteredCategories = useMemo(() => {
    if (!currentMenu) return [];
    const q = search.trim().toLowerCase();
    return currentMenu.categories
      .map((cat) => ({
        ...cat,
        items: cat.items.filter((it) => {
          if (dietFilter && !itemMatchesDietaryFilter(it.dietary_tags, dietFilter)) {
            return false;
          }
          if (q) {
            const hay = `${it.name} ${it.description || ""}`.toLowerCase();
            if (!hay.includes(q)) return false;
          }
          return true;
        }),
      }))
      .filter((cat) => cat.items.length > 0);
  }, [currentMenu, search, dietFilter]);

  const baseMediaOrigin = process.env.NEXT_PUBLIC_API_BASE_URL || "";

  return (
    <div
      data-theme={theme}
      className="min-h-screen w-full bg-[var(--bg-canvas)] text-[var(--text-primary)] transition-colors"
    >
      {/* Top Preview Banner */}
      {data?.preview_mode && (
        <div className="bg-amber-600 px-4 py-1.5 text-center text-xs font-semibold text-white">
          {lbl.previewBanner}
        </div>
      )}

      {/* Header + Hero */}
      <header className="border-b border-[var(--border-subtle)] bg-[var(--surface-solid)] px-4 py-4">
        <div className="mx-auto flex max-w-2xl items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            {data?.venue.logo_url ? (
              <img
                src={`${baseMediaOrigin}${data.venue.logo_url}`}
                alt={data.venue.name}
                className="h-12 w-12 shrink-0 rounded-xl border border-[var(--border-subtle)] object-cover"
              />
            ) : (
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-primary)] text-white">
                <Utensils className="h-5 w-5" aria-hidden="true" />
              </div>
            )}
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="truncate text-lg font-bold tracking-tight">
                  {data?.venue.name || "Digital Menu"}
                </h1>
                {data?.table.label && (
                  <span className="rounded-full bg-[var(--accent-primary)] px-2.5 py-0.5 text-[11px] font-bold text-white">
                    {data.table.label}
                  </span>
                )}
              </div>
              {data?.venue.tagline && (
                <p className="mt-0.5 line-clamp-2 text-xs text-[var(--text-secondary)]">
                  {data.venue.tagline}
                </p>
              )}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              onClick={() => setLocale((l) => (l === "en" ? "hi" : "en"))}
              aria-label="Toggle language"
              className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-canvas)] px-3 py-2 text-xs font-semibold"
            >
              <Languages className="h-3.5 w-3.5" aria-hidden="true" />
              {locale.toUpperCase()}
            </button>
            <button
              type="button"
              onClick={() => setTheme((th) => (th === "light" ? "dark" : "light"))}
              aria-label="Toggle theme"
              className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-canvas)]"
            >
              {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 pb-16 pt-4">
        {/* Loading Skeleton */}
        {loading && (
          <div className="space-y-3" aria-busy="true">
            {[1, 2, 3, 4].map((n) => (
              <div
                key={n}
                className="h-24 animate-pulse rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-solid)]"
              />
            ))}
          </div>
        )}

        {/* Error / Special QR States */}
        {!loading && errorCode && (
          <section className="tp-glass mt-6 rounded-2xl border p-6 text-center">
            <AlertCircle className="mx-auto h-10 w-10 text-amber-600" aria-hidden="true" />
            <h2 className="mt-3 text-base font-bold">
              {errorCode === "QR_CODE_REVOKED"
                ? lbl.revokedTitle
                : errorCode === "TABLE_UNAVAILABLE"
                  ? lbl.tableInactiveTitle
                  : errorCode === "QR_CODE_NOT_FOUND"
                    ? lbl.notFoundTitle
                    : lbl.errorTitle}
            </h2>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              {errorCode === "QR_CODE_REVOKED"
                ? lbl.revokedBody
                : errorCode === "TABLE_UNAVAILABLE"
                  ? lbl.tableInactiveBody
                  : errorCode === "QR_CODE_NOT_FOUND"
                    ? lbl.notFoundBody
                    : errorMsg}
            </p>
            <button
              type="button"
              onClick={() => void loadMenu()}
              className="mt-4 inline-flex min-h-[44px] items-center gap-1.5 rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              {lbl.retry}
            </button>
          </section>
        )}

        {/* Paused Menu */}
        {!loading && data && !data.menu_public_enabled && !data.preview_mode && (
          <section className="tp-glass mt-6 rounded-2xl border p-6 text-center">
            <Utensils className="mx-auto h-10 w-10 text-[var(--text-secondary)]" aria-hidden="true" />
            <h2 className="mt-3 text-base font-bold">{lbl.pausedTitle}</h2>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">{lbl.pausedBody}</p>
          </section>
        )}

        {/* Active Catalog */}
        {!loading && data && (data.menu_public_enabled || data.preview_mode) && (
          <>
            {/* Menu Selector Tabs */}
            {data.menus.length > 1 && (
              <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
                {data.menus.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setActiveMenuId(m.id)}
                    className={`min-h-[44px] shrink-0 rounded-full px-4 py-2 text-xs font-bold transition ${
                      m.id === currentMenu?.id
                        ? "bg-[var(--accent-primary)] text-white"
                        : "border border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                    }`}
                  >
                    {m.name}
                  </button>
                ))}
              </div>
            )}

            {/* Sticky Search + Dietary + Jump Pills */}
            <div className="tp-glass sticky top-2 z-20 mb-4 space-y-2.5 rounded-2xl border p-3">
              <label className="relative flex items-center">
                <Search
                  className="pointer-events-none absolute left-3 h-4 w-4 text-[var(--text-secondary)]"
                  aria-hidden="true"
                />
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={lbl.searchPlaceholder}
                  aria-label={lbl.searchPlaceholder}
                  className="min-h-[44px] w-full rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] py-2 pl-9 pr-3 text-sm"
                />
              </label>

              <div className="flex gap-1.5 overflow-x-auto pb-0.5">
                {DIETARY_CHIPS.map((chip) => {
                  const active = dietFilter === chip.key;
                  return (
                    <button
                      key={chip.key}
                      type="button"
                      aria-pressed={active}
                      onClick={() => setDietFilter((prev) => (prev === chip.key ? null : chip.key))}
                      className={`min-h-[44px] shrink-0 rounded-full px-3.5 py-2 text-xs font-semibold transition ${
                        active
                          ? "bg-[var(--accent-primary)] text-white"
                          : "border border-[var(--border-subtle)] bg-[var(--surface-solid)] text-[var(--text-secondary)]"
                      }`}
                    >
                      {lbl[chip.labelKey]}
                    </button>
                  );
                })}
              </div>

              {filteredCategories.length > 1 && (
                <nav aria-label="Menu categories" className="flex gap-1.5 overflow-x-auto pt-0.5">
                  {filteredCategories.map((cat) => (
                    <a
                      key={cat.id}
                      href={`#cat-${cat.id}`}
                      className="inline-flex min-h-[44px] shrink-0 items-center px-2 text-xs font-bold text-[var(--accent-primary)] hover:underline"
                    >
                      {cat.name}
                    </a>
                  ))}
                </nav>
              )}
            </div>

            {filteredCategories.length === 0 ? (
              <div className="tp-glass rounded-2xl border p-8 text-center">
                <p className="text-sm font-semibold">{lbl.noMatches}</p>
                {(search || dietFilter) && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearch("");
                      setDietFilter(null);
                    }}
                    className="mt-3 min-h-[44px] rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-4 py-2 text-xs font-semibold"
                  >
                    {lbl.clearFilters}
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-6">
                {filteredCategories.map((cat) => (
                  <section key={cat.id} id={`cat-${cat.id}`} className="scroll-mt-36">
                    <div className="mb-2.5">
                      <h2 className="text-base font-bold tracking-tight">{cat.name}</h2>
                      {cat.description && (
                        <p className="text-xs text-[var(--text-secondary)]">{cat.description}</p>
                      )}
                    </div>

                    <div className="space-y-3">
                      {cat.items.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => setActiveItem(item)}
                          className={`tp-glass flex min-h-[96px] w-full gap-3 rounded-2xl border p-3 text-left transition hover:border-[var(--accent-primary)] ${
                            !item.is_available ? "border-amber-700/50" : ""
                          }`}
                        >
                          <div className="flex min-w-0 flex-1 flex-col justify-between gap-1">
                            <div>
                              <div className="flex flex-wrap items-center gap-1.5">
                                <span className="text-sm font-bold">{item.name}</span>
                                {item.is_featured && (
                                  <span className="inline-flex items-center gap-0.5 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-900 dark:bg-amber-900 dark:text-amber-100">
                                    <Sparkles className="h-2.5 w-2.5" aria-hidden="true" />
                                    {lbl.featured}
                                  </span>
                                )}
                                {!item.is_available && (
                                  <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-900 dark:bg-red-900 dark:text-red-100">
                                    {lbl.soldOut}
                                  </span>
                                )}
                              </div>
                              {item.description && (
                                <p className="mt-0.5 line-clamp-2 text-xs text-[var(--text-secondary)]">
                                  {item.description}
                                </p>
                              )}
                            </div>

                            <div className="mt-1 flex flex-wrap items-center gap-2">
                              <span className="font-mono text-sm font-bold text-[var(--text-primary)]">
                                {formatMinorUnits(
                                  item.price_minor_units,
                                  data.venue.currency_code,
                                  locale,
                                )}
                              </span>
                              {item.compare_at_price_minor_units !== null && (
                                <span className="font-mono text-xs text-[var(--text-secondary)] line-through">
                                  {formatMinorUnits(
                                    item.compare_at_price_minor_units,
                                    data.venue.currency_code,
                                    locale,
                                  )}
                                </span>
                              )}
                              {item.dietary_tags.slice(0, 3).map((tag) => (
                                <span
                                  key={tag}
                                  className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-900 dark:bg-emerald-900 dark:text-emerald-100"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </div>

                          {item.thumb_url && (
                            <img
                              src={`${baseMediaOrigin}${item.thumb_url}`}
                              alt={item.image_alt || item.name}
                              loading="lazy"
                              className="h-24 w-24 shrink-0 rounded-xl border border-[var(--border-subtle)] object-cover"
                            />
                          )}
                        </button>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            )}

            <footer className="mt-10 border-t border-[var(--border-subtle)] pt-4 text-[11px] leading-relaxed text-[var(--text-secondary)]">
              {lbl.disclaimer}
            </footer>
          </>
        )}
      </main>

      {/* Item Detail Bottom Sheet Modal */}
      {activeItem && data && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={activeItem.name}
          onClick={() => setActiveItem(null)}
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/55 backdrop-blur-sm sm:items-center sm:p-4"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="max-h-[88vh] w-full max-w-lg overflow-y-auto rounded-t-3xl border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-5 shadow-2xl sm:rounded-3xl"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="text-lg font-bold">{activeItem.name}</h2>
                <div className="mt-1 flex items-center gap-2">
                  <span className="font-mono text-base font-bold">
                    {formatMinorUnits(
                      activeItem.price_minor_units,
                      data.venue.currency_code,
                      locale,
                    )}
                  </span>
                  {activeItem.compare_at_price_minor_units !== null && (
                    <span className="font-mono text-xs text-[var(--text-secondary)] line-through">
                      {formatMinorUnits(
                        activeItem.compare_at_price_minor_units,
                        data.venue.currency_code,
                        locale,
                      )}
                    </span>
                  )}
                  {!activeItem.is_available && (
                    <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-bold text-red-900 dark:bg-red-900 dark:text-red-100">
                      {lbl.soldOut}
                    </span>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActiveItem(null)}
                aria-label="Close dish details"
                className="min-h-[44px] min-w-[44px] rounded-xl border border-[var(--border-subtle)] p-2.5 hover:bg-black/10"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {activeItem.image_url && (
              <img
                src={`${baseMediaOrigin}${activeItem.image_url}`}
                alt={activeItem.image_alt || activeItem.name}
                className="mt-4 max-h-60 w-full rounded-2xl border border-[var(--border-subtle)] object-cover"
              />
            )}

            {activeItem.description && (
              <p className="mt-3 text-sm leading-relaxed text-[var(--text-secondary)]">
                {activeItem.description}
              </p>
            )}

            <div className="mt-4 flex flex-wrap gap-3 text-xs text-[var(--text-secondary)]">
              {activeItem.prep_time_minutes !== null && (
                <span className="inline-flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                  {lbl.prepTime}: {activeItem.prep_time_minutes} {lbl.mins}
                </span>
              )}
              {activeItem.calories_kcal !== null && (
                <span className="inline-flex items-center gap-1">
                  <Flame className="h-3.5 w-3.5" aria-hidden="true" />
                  {lbl.calories}: {activeItem.calories_kcal} kcal
                </span>
              )}
            </div>

            {activeItem.variants_json.length > 0 && (
              <div className="mt-4 rounded-xl border border-[var(--border-subtle)] p-3">
                <h3 className="text-xs font-bold uppercase text-[var(--text-secondary)]">
                  {lbl.variants}
                </h3>
                <ul className="mt-2 divide-y divide-[var(--border-subtle)] text-xs">
                  {activeItem.variants_json.map((v) => (
                    <li key={v.name} className="flex items-center justify-between py-2">
                      <span className={!v.is_available ? "line-through opacity-60" : "font-medium"}>
                        {v.name}
                      </span>
                      <span className="font-mono font-bold">
                        {formatMinorUnits(
                          v.price_minor_units,
                          data.venue.currency_code,
                          locale,
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {activeItem.allergens.length > 0 && (
              <div className="mt-4 rounded-xl border border-amber-400/50 bg-amber-500/10 p-3">
                <h3 className="text-xs font-bold uppercase text-amber-800 dark:text-amber-300">
                  {lbl.allergens}
                </h3>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {activeItem.allergens.map((alg) => (
                    <span
                      key={alg}
                      className="rounded-full bg-amber-800 px-2.5 py-0.5 text-[11px] font-bold text-white"
                    >
                      {alg}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
