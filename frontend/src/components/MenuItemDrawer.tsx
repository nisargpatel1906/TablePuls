// TODO(ui-asset): SCR-019
"use client";

import React, { useEffect, useState } from "react";
import { Check, ImagePlus, Plus, Trash2, X } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { minorUnitsToInputString, parseDisplayToMinorUnits } from "@/lib/currency";
import type { MenuCategoryDTO, MenuItemDTO, MenuItemVariantDTO } from "@/types/floor";

const DIETARY_OPTIONS = [
  { key: "VEG", label: "Veg" },
  { key: "NON_VEG", label: "Non-Veg" },
  { key: "VEGAN", label: "Vegan" },
  { key: "GLUTEN_FREE", label: "Gluten-Free" },
  { key: "DAIRY_FREE", label: "Dairy-Free" },
  { key: "NUT_FREE", label: "Nut-Free" },
  { key: "SPICY_MILD", label: "Mild" },
  { key: "SPICY_MEDIUM", label: "Medium" },
  { key: "SPICY_HOT", label: "Hot" },
  { key: "CHEF_SPECIAL", label: "Chef's Special" },
];

const ALLERGEN_OPTIONS = [
  "NUTS",
  "PEANUTS",
  "DAIRY",
  "GLUTEN",
  "SOY",
  "SHELLFISH",
  "FISH",
  "EGGS",
  "SESAME",
];

interface MenuItemDrawerProps {
  open: boolean;
  venueId: string;
  currencyCode: string;
  categories: MenuCategoryDTO[];
  defaultCategoryId: string;
  item: MenuItemDTO | null;
  onClose: () => void;
  onSaved: () => void;
}

export function MenuItemDrawer({
  open,
  venueId,
  currencyCode,
  categories,
  defaultCategoryId,
  item,
  onClose,
  onSaved,
}: MenuItemDrawerProps) {
  const [categoryId, setCategoryId] = useState(defaultCategoryId);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [priceText, setPriceText] = useState("0.00");
  const [compareText, setCompareText] = useState("");
  const [imageAssetId, setImageAssetId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageAlt, setImageAlt] = useState("");
  const [clearImageFlag, setClearImageFlag] = useState(false);

  const [isAvailable, setIsAvailable] = useState(true);
  const [isFeatured, setIsFeatured] = useState(false);
  const [dietaryTags, setDietaryTags] = useState<string[]>([]);
  const [allergens, setAllergens] = useState<string[]>([]);
  const [variants, setVariants] = useState<Array<{ name: string; priceStr: string; is_available: boolean }>>([]);
  const [prepMinutes, setPrepMinutes] = useState("");
  const [calories, setCalories] = useState("");

  const [dirty, setDirty] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (item) {
      setCategoryId(item.category_id);
      setName(item.name);
      setDescription(item.description || "");
      setPriceText(minorUnitsToInputString(item.price_minor_units, currencyCode));
      setCompareText(
        item.compare_at_price_minor_units !== null
          ? minorUnitsToInputString(item.compare_at_price_minor_units, currencyCode)
          : "",
      );
      setImageAssetId(item.image_asset_id);
      setPreviewUrl(item.thumb_url || item.image_url);
      setImageAlt(item.image_alt || "");
      setClearImageFlag(false);
      setIsAvailable(item.is_available);
      setIsFeatured(item.is_featured);
      setDietaryTags(item.dietary_tags || []);
      setAllergens(item.allergens || []);
      setVariants(
        (item.variants_json || []).map((v: MenuItemVariantDTO) => ({
          name: v.name,
          priceStr: minorUnitsToInputString(v.price_minor_units, currencyCode),
          is_available: v.is_available,
        })),
      );
      setPrepMinutes(item.prep_time_minutes !== null ? String(item.prep_time_minutes) : "");
      setCalories(item.calories_kcal !== null ? String(item.calories_kcal) : "");
    } else {
      setCategoryId(defaultCategoryId || categories[0]?.id || "");
      setName("");
      setDescription("");
      setPriceText(minorUnitsToInputString(0, currencyCode));
      setCompareText("");
      setImageAssetId(null);
      setPreviewUrl(null);
      setImageAlt("");
      setClearImageFlag(false);
      setIsAvailable(true);
      setIsFeatured(false);
      setDietaryTags([]);
      setAllergens([]);
      setVariants([]);
      setPrepMinutes("");
      setCalories("");
    }
    setDirty(false);
    setError(null);
  }, [open, item, defaultCategoryId, categories, currencyCode]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") {
        if (!dirty || window.confirm("Discard unsaved changes to this menu item?")) {
          onClose();
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, dirty, onClose]);

  if (!open) return null;

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !venueId) return;
    if (file.size > 5 * 1024 * 1024) {
      setError("Image file exceeds 5 MB maximum upload limit.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiFetch<{
        id: string;
        image_url: string;
        thumb_url: string;
      }>(`/api/v1/venues/${venueId}/menu/media`, {
        method: "POST",
        body: fd,
      });
      setImageAssetId(res.id);
      setPreviewUrl(res.thumb_url || res.image_url);
      setClearImageFlag(false);
      setDirty(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to upload WebP image");
    } finally {
      setUploading(false);
    }
  }

  function handleAttemptClose() {
    if (!dirty || window.confirm("Discard unsaved changes to this menu item?")) {
      onClose();
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!venueId || !categoryId) {
      setError("Please select a category.");
      return;
    }
    const priceMinor = parseDisplayToMinorUnits(priceText, currencyCode);
    if (priceMinor === null || priceMinor < 0) {
      setError("Enter a valid non-negative price.");
      return;
    }
    const compareMinor = compareText.trim()
      ? parseDisplayToMinorUnits(compareText, currencyCode)
      : null;
    if (compareText.trim() && (compareMinor === null || compareMinor <= priceMinor)) {
      setError("Compare-at price must be greater than base price.");
      return;
    }

    const parsedVariants: MenuItemVariantDTO[] = [];
    for (const v of variants) {
      if (!v.name.trim()) {
        setError("All variants must have a name.");
        return;
      }
      const vm = parseDisplayToMinorUnits(v.priceStr, currencyCode);
      if (vm === null || vm < 0) {
        setError(`Invalid price for variant "${v.name}".`);
        return;
      }
      parsedVariants.push({
        name: v.name.trim(),
        price_minor_units: vm,
        is_available: v.is_available,
      });
    }

    setSaving(true);
    setError(null);
    try {
      if (item) {
        await apiFetch(`/api/v1/venues/${venueId}/menu-items/${item.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            category_id: categoryId,
            name: name.trim(),
            description: description.trim() || null,
            price_minor_units: priceMinor,
            compare_at_price_minor_units: compareMinor,
            clear_compare_at_price: compareMinor === null,
            image_asset_id: clearImageFlag ? null : imageAssetId,
            clear_image: clearImageFlag,
            image_alt: imageAlt.trim() || null,
            is_available: isAvailable,
            is_featured: isFeatured,
            dietary_tags: dietaryTags,
            allergens,
            variants_json: parsedVariants,
            prep_time_minutes: prepMinutes.trim() ? Number(prepMinutes) : null,
            calories_kcal: calories.trim() ? Number(calories) : null,
            version: item.version,
          }),
        });
      } else {
        await apiFetch(`/api/v1/venues/${venueId}/menu-items`, {
          method: "POST",
          body: JSON.stringify({
            category_id: categoryId,
            name: name.trim(),
            description: description.trim() || null,
            price_minor_units: priceMinor,
            compare_at_price_minor_units: compareMinor,
            image_asset_id: imageAssetId,
            image_alt: imageAlt.trim() || null,
            is_available: isAvailable,
            is_featured: isFeatured,
            dietary_tags: dietaryTags,
            allergens,
            variants_json: parsedVariants,
            prep_time_minutes: prepMinutes.trim() ? Number(prepMinutes) : null,
            calories_kcal: calories.trim() ? Number(calories) : null,
          }),
        });
      }
      setDirty(false);
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save menu item");
    } finally {
      setSaving(false);
    }
  }

  const baseMediaOrigin = process.env.NEXT_PUBLIC_API_BASE_URL || "";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={item ? `Edit ${item.name}` : "Add Menu Item"}
      className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-sm"
    >
      <form
        onSubmit={handleSave}
        className="flex h-full w-full max-w-xl flex-col border-l border-[var(--border-subtle)] bg-[var(--surface-solid)] shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 className="text-base font-bold">
            {item ? `Edit Dish · ${item.name}` : "Add Menu Item"}
          </h2>
          <button
            type="button"
            onClick={handleAttemptClose}
            aria-label="Close item drawer"
            className="min-h-[40px] rounded-lg p-2 hover:bg-black/10"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {error && (
            <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-xs text-red-800">
              {error}
            </div>
          )}

          {/* Photo upload + preview */}
          <div className="rounded-xl border border-[var(--border-subtle)] p-3">
            <p className="text-xs font-bold text-[var(--text-secondary)]">
              Dish Photo (JPEG/PNG/WebP up to 5 MB · auto-encoded to WebP)
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              {previewUrl && !clearImageFlag ? (
                <img
                  src={previewUrl.startsWith("/") ? `${baseMediaOrigin}${previewUrl}` : previewUrl}
                  alt={imageAlt || name || "Dish preview"}
                  className="h-20 w-20 rounded-xl border border-[var(--border-subtle)] object-cover"
                />
              ) : (
                <div className="flex h-20 w-20 items-center justify-center rounded-xl border border-dashed border-[var(--border-subtle)] text-[var(--text-secondary)]">
                  <ImagePlus className="h-6 w-6" aria-hidden="true" />
                </div>
              )}

              <div className="flex flex-1 flex-col gap-2">
                <label className="inline-flex min-h-[40px] cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-black/5 px-3 py-1.5 text-xs font-semibold hover:opacity-80">
                  <ImagePlus className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{uploading ? "Uploading..." : "Upload Image"}</span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={uploading}
                    onChange={handleFileSelect}
                    className="sr-only"
                  />
                </label>
                {previewUrl && !clearImageFlag && (
                  <button
                    type="button"
                    onClick={() => {
                      setClearImageFlag(true);
                      setImageAssetId(null);
                      setPreviewUrl(null);
                      setDirty(true);
                    }}
                    className="inline-flex items-center gap-1 text-left text-[11px] font-semibold text-red-600 hover:underline"
                  >
                    <Trash2 className="h-3 w-3" aria-hidden="true" />
                    Remove image
                  </button>
                )}
              </div>
            </div>
            <label className="mt-2 flex flex-col gap-1 text-[11px] font-medium">
              Accessible Image Alt Text
              <input
                maxLength={160}
                value={imageAlt}
                onChange={(e) => {
                  setImageAlt(e.target.value);
                  setDirty(true);
                }}
                placeholder="Wood-fired margherita pizza with fresh basil"
                className="min-h-[38px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-2.5 py-1 text-xs"
              />
            </label>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs font-medium sm:col-span-2">
              Category
              <select
                value={categoryId}
                onChange={(e) => {
                  setCategoryId(e.target.value);
                  setDirty(true);
                }}
                className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-sm"
              >
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1 text-xs font-medium sm:col-span-2">
              Dish Name
              <input
                required
                maxLength={120}
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setDirty(true);
                }}
                placeholder="e.g. Paneer Tikka Platter"
                className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
              />
            </label>

            <label className="flex flex-col gap-1 text-xs font-medium sm:col-span-2">
              Description
              <textarea
                rows={2}
                maxLength={500}
                value={description}
                onChange={(e) => {
                  setDescription(e.target.value);
                  setDirty(true);
                }}
                className="rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-xs"
              />
            </label>

            <label className="flex flex-col gap-1 text-xs font-medium">
              Price ({currencyCode})
              <input
                required
                inputMode="decimal"
                value={priceText}
                onChange={(e) => {
                  setPriceText(e.target.value);
                  setDirty(true);
                }}
                className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 font-mono text-sm"
              />
            </label>

            <label className="flex flex-col gap-1 text-xs font-medium">
              Compare-at Price (optional)
              <input
                inputMode="decimal"
                value={compareText}
                onChange={(e) => {
                  setCompareText(e.target.value);
                  setDirty(true);
                }}
                placeholder="Strikethrough price"
                className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 font-mono text-sm"
              />
            </label>

            <label className="flex flex-col gap-1 text-xs font-medium">
              Prep Time (mins)
              <input
                type="number"
                min={1}
                max={240}
                value={prepMinutes}
                onChange={(e) => {
                  setPrepMinutes(e.target.value);
                  setDirty(true);
                }}
                className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
              />
            </label>

            <label className="flex flex-col gap-1 text-xs font-medium">
              Calories (kcal)
              <input
                type="number"
                min={0}
                max={10000}
                value={calories}
                onChange={(e) => {
                  setCalories(e.target.value);
                  setDirty(true);
                }}
                className="min-h-[42px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
              />
            </label>
          </div>

          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-xs font-semibold">
              <input
                type="checkbox"
                checked={isAvailable}
                onChange={(e) => {
                  setIsAvailable(e.target.checked);
                  setDirty(true);
                }}
              />
              In Stock (Available on Customer Menu)
            </label>
            <label className="flex items-center gap-2 text-xs font-semibold">
              <input
                type="checkbox"
                checked={isFeatured}
                onChange={(e) => {
                  setIsFeatured(e.target.checked);
                  setDirty(true);
                }}
              />
              Featured Highlight
            </label>
          </div>

          {/* Dietary Chips */}
          <div>
            <p className="text-xs font-bold text-[var(--text-secondary)]">Dietary Tags</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {DIETARY_OPTIONS.map((opt) => {
                const active = dietaryTags.includes(opt.key);
                return (
                  <button
                    key={opt.key}
                    type="button"
                    aria-pressed={active}
                    onClick={() => {
                      setDietaryTags((prev) =>
                        active ? prev.filter((x) => x !== opt.key) : [...prev, opt.key],
                      );
                      setDirty(true);
                    }}
                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
                      active
                        ? "bg-[var(--accent-primary)] text-white"
                        : "border border-[var(--border-subtle)] bg-transparent text-[var(--text-secondary)]"
                    }`}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Allergen Chips */}
          <div>
            <p className="text-xs font-bold text-[var(--text-secondary)]">Allergens</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {ALLERGEN_OPTIONS.map((alg) => {
                const active = allergens.includes(alg);
                return (
                  <button
                    key={alg}
                    type="button"
                    aria-pressed={active}
                    onClick={() => {
                      setAllergens((prev) =>
                        active ? prev.filter((x) => x !== alg) : [...prev, alg],
                      );
                      setDirty(true);
                    }}
                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
                      active
                        ? "bg-amber-600 text-white"
                        : "border border-[var(--border-subtle)] bg-transparent text-[var(--text-secondary)]"
                    }`}
                  >
                    {alg}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Variants */}
          <div className="rounded-xl border border-[var(--border-subtle)] p-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-bold text-[var(--text-secondary)]">
                Size / Portion Variants ({variants.length}/8)
              </p>
              {variants.length < 8 && (
                <button
                  type="button"
                  onClick={() => {
                    setVariants((v) => [...v, { name: "", priceStr: priceText, is_available: true }]);
                    setDirty(true);
                  }}
                  className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-[11px] font-semibold"
                >
                  <Plus className="h-3 w-3" aria-hidden="true" />
                  Add Variant
                </button>
              )}
            </div>
            {variants.length > 0 && (
              <div className="mt-2 space-y-2">
                {variants.map((v, idx) => (
                  <div key={idx} className="grid grid-cols-[1fr_100px_auto] items-center gap-2">
                    <input
                      value={v.name}
                      onChange={(e) => {
                        const val = e.target.value;
                        setVariants((prev) => prev.map((x, i) => (i === idx ? { ...x, name: val } : x)));
                        setDirty(true);
                      }}
                      placeholder="Half / Regular / Large"
                      aria-label={`Variant ${idx + 1} name`}
                      className="min-h-[38px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-2.5 text-xs"
                    />
                    <input
                      inputMode="decimal"
                      value={v.priceStr}
                      onChange={(e) => {
                        const val = e.target.value;
                        setVariants((prev) =>
                          prev.map((x, i) => (i === idx ? { ...x, priceStr: val } : x)),
                        );
                        setDirty(true);
                      }}
                      aria-label={`Variant ${idx + 1} price`}
                      className="min-h-[38px] rounded-lg border border-[var(--border-subtle)] bg-transparent px-2.5 font-mono text-xs"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setVariants((prev) => prev.filter((_, i) => i !== idx));
                        setDirty(true);
                      }}
                      aria-label={`Remove variant ${idx + 1}`}
                      className="rounded p-1.5 text-red-600 hover:bg-red-500/10"
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[var(--border-subtle)] px-5 py-3">
          <button
            type="button"
            onClick={handleAttemptClose}
            className="min-h-[44px] rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-xs font-semibold"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || uploading}
            className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
          >
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
            {saving ? "Saving..." : item ? "Save Dish" : "Create Dish"}
          </button>
        </div>
      </form>
    </div>
  );
}
