"use client";

import React, { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Check, Lock, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import type { CalibrationTable } from "@/components/PolygonEditorCanvas";
import { apiFetch, ApiError } from "@/lib/api";
import { hasCapability } from "@/lib/rbac";
import { useAuth } from "@/providers/AuthProvider";
import type { PolygonPoint } from "@/types/floor";

const PolygonEditorCanvas = dynamic(() => import("@/components/PolygonEditorCanvas"), {
  ssr: false,
  loading: () => (
    <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
      Loading calibration canvas...
    </div>
  ),
});

function segmentsIntersect(a: PolygonPoint, b: PolygonPoint, c: PolygonPoint, d: PolygonPoint): boolean {
  const ccw = (p1: PolygonPoint, p2: PolygonPoint, p3: PolygonPoint) =>
    (p3.y - p1.y) * (p2.x - p1.x) > (p2.y - p1.y) * (p3.x - p1.x);
  return ccw(a, c, d) !== ccw(b, c, d) && ccw(a, b, c) !== ccw(a, b, d);
}

function validatePolygonPoints(pts: PolygonPoint[]): string | null {
  if (pts.length < 3) return "Polygon requires at least 3 vertices";
  for (const p of pts) {
    if (p.x < 0 || p.x > 1 || p.y < 0 || p.y > 1) {
      return "Coordinates must stay within 0.0 to 1.0";
    }
  }
  const n = pts.length;
  for (let i = 0; i < n; i += 1) {
    const p1 = pts[i];
    const p2 = pts[(i + 1) % n];
    if (!p1 || !p2) continue;
    for (let j = i + 2; j < n; j += 1) {
      if (i === 0 && j === n - 1) continue;
      const p3 = pts[j];
      const p4 = pts[(j + 1) % n];
      if (!p3 || !p4) continue;
      if (segmentsIntersect(p1, p2, p3, p4)) {
        return "Polygon edges cannot self-intersect";
      }
    }
  }
  return null;
}

function roundTables(items: CalibrationTable[]): CalibrationTable[] {
  return items.map((tbl) => ({
    ...tbl,
    polygon_json: (tbl.polygon_json || []).map((pt) => ({
      x: Math.round(pt.x * 1000) / 1000,
      y: Math.round(pt.y * 1000) / 1000,
    })),
  }));
}

export default function PolygonCalibrationPage() {
  const params = useParams<{ venueId: string; cameraId: string }>();
  const venueId = params?.venueId || "";
  const cameraId = params?.cameraId || "";
  const { user, loading: authLoading } = useAuth();
  const canCalibrate = hasCapability(user?.role, "polygons.calibrate");

  const [tables, setTables] = useState<CalibrationTable[]>([]);
  const [exclusionZones, setExclusionZones] = useState<PolygonPoint[][]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [previewBase64, setPreviewBase64] = useState<string | null>(null);
  const [mode, setMode] = useState<"draw" | "edit" | "exclusion">("edit");
  const [draftPoints, setDraftPoints] = useState<PolygonPoint[]>([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const selectedTable = tables[selectedIndex] || null;

  const loadCalibration = useCallback(async () => {
    if (!venueId || !cameraId || !canCalibrate) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const polyRes = await apiFetch<{
        exclusion_polygons_json: PolygonPoint[][];
        tables: CalibrationTable[];
      }>(`/api/v1/venues/${venueId}/cameras/${cameraId}/polygons`);
      setTables(roundTables(polyRes.tables));
      setExclusionZones(polyRes.exclusion_polygons_json || []);

      try {
        const snap = await apiFetch<{ preview_jpeg_base64: string }>(
          `/api/v1/venues/${venueId}/cameras/${cameraId}/test`,
          { method: "POST" },
        );
        setPreviewBase64(snap.preview_jpeg_base64);
      } catch {
        setPreviewBase64(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load calibration data");
    } finally {
      setLoading(false);
    }
  }, [venueId, cameraId, canCalibrate]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadCalibration();
    }
  }, [authLoading, user, loadCalibration]);

  function finishDraftPolygon() {
    const err = validatePolygonPoints(draftPoints);
    if (err) {
      setError(err);
      return;
    }
    if (mode === "exclusion") {
      setExclusionZones((prev) => [...prev, draftPoints]);
      setDraftPoints([]);
      setMode("edit");
      return;
    }
    const nextCode = `T${tables.length + 1}`;
    const avgX = draftPoints.reduce((s, p) => s + p.x, 0) / Math.max(1, draftPoints.length);
    const avgY = draftPoints.reduce((s, p) => s + p.y, 0) / Math.max(1, draftPoints.length);
    const nextTbl: CalibrationTable = {
      table_code: nextCode,
      section_name: "Main",
      seat_capacity: 4,
      polygon_json: draftPoints,
      floor_x: Math.round(Math.max(0.05, Math.min(0.95, avgX)) * 1000) / 1000,
      floor_y: Math.round(Math.max(0.05, Math.min(0.95, avgY)) * 1000) / 1000,
      shape: "RECT",
      version: 1,
    };
    setTables((prev) => [...prev, nextTbl]);
    setSelectedIndex(tables.length);
    setDraftPoints([]);
    setMode("edit");
    setError(null);
  }

  function addDefaultBoxTable() {
    const offset = (tables.length % 4) * 0.16;
    const x0 = Math.min(0.7, 0.1 + offset);
    const nextTbl: CalibrationTable = {
      table_code: `T${tables.length + 1}`,
      section_name: "Main",
      seat_capacity: 4,
      polygon_json: [
        { x: x0, y: 0.18 },
        { x: Math.min(0.95, x0 + 0.18), y: 0.18 },
        { x: Math.min(0.95, x0 + 0.18), y: 0.42 },
        { x: x0, y: 0.42 },
      ],
      floor_x: Math.round(Math.min(0.9, x0 + 0.09) * 1000) / 1000,
      floor_y: 0.3,
      shape: "RECT",
      version: 1,
    };
    setTables((prev) => [...prev, nextTbl]);
    setSelectedIndex(tables.length);
  }

  async function handleSave() {
    setError(null);
    setSuccessMsg(null);
    const normalizedTables = tables.map((tbl) => ({
      ...tbl,
      floor_x:
        tbl.floor_x > 1
          ? Math.max(0, Math.min(1, Math.round((tbl.floor_x / 800) * 1000) / 1000))
          : Math.max(0, Math.min(1, Math.round(tbl.floor_x * 1000) / 1000)),
      floor_y:
        tbl.floor_y > 1
          ? Math.max(0, Math.min(1, Math.round((tbl.floor_y / 500) * 1000) / 1000))
          : Math.max(0, Math.min(1, Math.round(tbl.floor_y * 1000) / 1000)),
    }));
    for (const tbl of normalizedTables) {
      const err = validatePolygonPoints(tbl.polygon_json);
      if (err) {
        setError(`Table ${tbl.table_code}: ${err}`);
        return;
      }
    }
    setSaving(true);
    try {
      const res = await apiFetch<{
        exclusion_polygons_json: PolygonPoint[][];
        tables: CalibrationTable[];
      }>(`/api/v1/venues/${venueId}/cameras/${cameraId}/polygons`, {
        method: "PUT",
        body: JSON.stringify({
          exclusion_polygons_json: exclusionZones,
          tables: normalizedTables,
        }),
      });
      setTables(roundTables(res.tables));
      setExclusionZones(res.exclusion_polygons_json);
      setSuccessMsg(`Saved calibration for ${res.tables.length} tables.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save calibration");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell venueId={venueId}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <Link
              href={`/venues/${venueId}/settings/cameras`}
              className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--accent-primary)] hover:underline"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
              Back to Cameras
            </Link>
            <h1 className="mt-1 text-xl font-bold tracking-tight">
              Interactive Table Polygon & ROI Editor
            </h1>
          </div>
          {canCalibrate && (
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setMode("edit")}
                aria-pressed={mode === "edit"}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
                  mode === "edit"
                    ? "bg-[var(--accent-primary)] text-white"
                    : "border border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                }`}
              >
                Edit Vertex
              </button>
              <button
                type="button"
                onClick={() => {
                  setDraftPoints([]);
                  setMode("draw");
                }}
                aria-pressed={mode === "draw"}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
                  mode === "draw"
                    ? "bg-[var(--accent-primary)] text-white"
                    : "border border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                }`}
              >
                Draw Polygon
              </button>
              <button
                type="button"
                onClick={() => {
                  setDraftPoints([]);
                  setMode("exclusion");
                }}
                aria-pressed={mode === "exclusion"}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
                  mode === "exclusion"
                    ? "bg-[var(--accent-primary)] text-white"
                    : "border border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                }`}
              >
                Exclusion Zone
              </button>
              <button
                type="button"
                onClick={addDefaultBoxTable}
                className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Quick Add Table
              </button>
              {draftPoints.length >= 3 && (
                <button
                  type="button"
                  onClick={finishDraftPolygon}
                  className="inline-flex items-center gap-1 rounded-lg bg-amber-700 px-3 py-1.5 text-xs font-semibold text-white"
                >
                  <Check className="h-3.5 w-3.5" aria-hidden="true" />
                  Complete Shape ({draftPoints.length} pts)
                </button>
              )}
              <button
                type="button"
                onClick={() => void loadCalibration()}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-2"
                aria-label="Refresh snapshot"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => void handleSave()}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
              >
                <Save className="h-3.5 w-3.5" aria-hidden="true" />
                {saving ? "Saving..." : "Save Calibration"}
              </button>
            </div>
          )}
        </div>

        {!authLoading && user && !canCalibrate && (
          <div className="tp-glass flex flex-col items-center gap-3 rounded-xl border p-8 text-center">
            <Lock className="h-8 w-8 text-amber-600" aria-hidden="true" />
            <h2 className="text-base font-bold">Permission Denied</h2>
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

        {canCalibrate && !loading && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_310px]">
            <div className="flex flex-col gap-3">
              <PolygonEditorCanvas
                previewBase64={previewBase64}
                tables={tables}
                exclusionZones={exclusionZones}
                selectedIndex={selectedIndex}
                mode={mode}
                draftPoints={draftPoints}
                onAddPoint={(pt) => setDraftPoints((prev) => [...prev, pt])}
                onSelectTable={(idx) => setSelectedIndex(idx)}
                onMoveVertex={(tIdx, vIdx, pt) => {
                  setTables((prev) =>
                    prev.map((t, i) =>
                      i === tIdx
                        ? {
                            ...t,
                            polygon_json: t.polygon_json.map((p, vi) => (vi === vIdx ? pt : p)),
                          }
                        : t,
                    ),
                  );
                }}
              />

              <div className="flex flex-wrap gap-1.5">
                {tables.map((tbl, idx) => (
                  <button
                    key={tbl.id || `${tbl.table_code}-${idx}`}
                    type="button"
                    onClick={() => setSelectedIndex(idx)}
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      idx === selectedIndex
                        ? "bg-[var(--accent-primary)] text-white"
                        : "border border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                    }`}
                  >
                    Select {tbl.table_code}
                  </button>
                ))}
              </div>
            </div>

            <aside className="tp-glass flex flex-col gap-3 rounded-xl border p-4">
              <h2 className="text-sm font-bold">
                Polygon Inspector {selectedTable ? `· ${selectedTable.table_code}` : ""}
              </h2>
              {!selectedTable ? (
                <p className="text-xs text-[var(--text-secondary)]">
                  No table polygon selected. Click Draw Polygon or Quick Add Table.
                </p>
              ) : (
                <>
                  <label className="flex flex-col gap-1 text-xs font-medium">
                    Table Code
                    <input
                      type="text"
                      value={selectedTable.table_code}
                      onChange={(e) => {
                        const val = e.target.value.toUpperCase();
                        setTables((prev) =>
                          prev.map((t, i) =>
                            i === selectedIndex ? { ...t, table_code: val } : t,
                          ),
                        );
                      }}
                      className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-sm"
                    />
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <label className="flex flex-col gap-1 text-xs font-medium">
                      Section
                      <input
                        type="text"
                        value={selectedTable.section_name}
                        onChange={(e) => {
                          const val = e.target.value;
                          setTables((prev) =>
                            prev.map((t, i) =>
                              i === selectedIndex ? { ...t, section_name: val } : t,
                            ),
                          );
                        }}
                        className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-sm"
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-xs font-medium">
                      Seats (1–20)
                      <input
                        type="number"
                        min={1}
                        max={20}
                        value={selectedTable.seat_capacity}
                        onChange={(e) => {
                          const val = Number(e.target.value);
                          setTables((prev) =>
                            prev.map((t, i) =>
                              i === selectedIndex ? { ...t, seat_capacity: val } : t,
                            ),
                          );
                        }}
                        className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-sm"
                      />
                    </label>
                  </div>

                  <div className="space-y-2 border-t border-[var(--border-subtle)] pt-2">
                    <p className="text-xs font-bold text-[var(--text-secondary)]">
                      Keyboard Vertex Coordinates (Fallback 0.00–1.00)
                    </p>
                    {selectedTable.polygon_json.map((pt, vIdx) => (
                      <div key={vIdx} className="grid grid-cols-[44px_1fr_1fr] items-center gap-2">
                        <span className="font-mono text-xs">V{vIdx + 1}</span>
                        <input
                          type="number"
                          step="0.01"
                          min={0}
                          max={1}
                          aria-label={`Vertex ${vIdx + 1} X`}
                          value={Number.isFinite(pt.x) ? Number(pt.x.toFixed(3)) : 0}
                          onChange={(e) => {
                            const nx = Number(e.target.value);
                            setTables((prev) =>
                              prev.map((t, i) =>
                                i === selectedIndex
                                  ? {
                                      ...t,
                                      polygon_json: t.polygon_json.map((p, vi) =>
                                        vi === vIdx ? { ...p, x: nx } : p,
                                      ),
                                    }
                                  : t,
                              ),
                            );
                          }}
                          className="rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2 py-1 font-mono text-xs"
                        />
                        <input
                          type="number"
                          step="0.01"
                          min={0}
                          max={1}
                          aria-label={`Vertex ${vIdx + 1} Y`}
                          value={Number.isFinite(pt.y) ? Number(pt.y.toFixed(3)) : 0}
                          onChange={(e) => {
                            const ny = Number(e.target.value);
                            setTables((prev) =>
                              prev.map((t, i) =>
                                i === selectedIndex
                                  ? {
                                      ...t,
                                      polygon_json: t.polygon_json.map((p, vi) =>
                                        vi === vIdx ? { ...p, y: ny } : p,
                                      ),
                                    }
                                  : t,
                              ),
                            );
                          }}
                          className="rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2 py-1 font-mono text-xs"
                        />
                      </div>
                    ))}
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      setTables((prev) => prev.filter((_, i) => i !== selectedIndex));
                      setSelectedIndex(0);
                    }}
                    className="mt-2 inline-flex items-center justify-center gap-1.5 rounded-lg bg-red-500/15 px-3 py-2 text-xs font-semibold text-red-700 hover:bg-red-500/25"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    Delete Polygon
                  </button>
                </>
              )}
            </aside>
          </div>
        )}
      </div>
    </AppShell>
  );
}
