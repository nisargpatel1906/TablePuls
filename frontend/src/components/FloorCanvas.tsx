"use client";

import React, { useEffect, useRef, useState } from "react";
import { Circle, Group, Layer, Rect, Stage, Text } from "react-konva";
import { Maximize2, ZoomIn, ZoomOut } from "lucide-react";
import { TABLE_STATE_META, formatElapsed } from "@/lib/table-states";
import { useAuth } from "@/providers/AuthProvider";
import type { FloorTable } from "@/types/floor";

interface FloorCanvasProps {
  tables: FloorTable[];
  selectedTableId: string | null;
  nowMs: number;
  onSelectTable: (table: FloorTable) => void;
}

export default function FloorCanvas({
  tables,
  selectedTableId,
  nowMs,
  onSelectTable,
}: FloorCanvasProps) {
  const { theme } = useAuth();
  const isDark = theme === "dark";
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 820, height: 500 });
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const updateSize = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width <= 120) return;
      const vh = typeof window !== "undefined" ? window.innerHeight : 800;
      const w = Math.max(300, Math.floor(rect.width));
      const h = Math.max(240, Math.min(390, Math.max(260, vh - 390), Math.floor(w * 0.42)));
      setSize((prev) =>
        Math.abs(prev.width - w) < 4 && Math.abs(prev.height - h) < 4
          ? prev
          : { width: w, height: h },
      );
    };
    updateSize();
    const obs = new ResizeObserver(updateSize);
    obs.observe(el);
    window.addEventListener("resize", updateSize);
    return () => {
      obs.disconnect();
      window.removeEventListener("resize", updateSize);
    };
  }, []);

  const placed: Array<{ x: number; y: number }> = [];
  const coords = tables.map((tbl, idx) => {
    const rawX = tbl.floor_x;
    const rawY = tbl.floor_y;
    let fx =
      rawX > 0 && rawX <= 1
        ? Math.max(24, Math.min(660, Math.round(rawX * 800 - 55)))
        : rawX > 1
          ? rawX
          : 70 + (idx % 4) * 190;
    let fy =
      rawY > 0 && rawY <= 1
        ? Math.max(24, Math.min(390, Math.round(rawY * 500 - 45)))
        : rawY > 1
          ? rawY
          : 70 + Math.floor(idx / 4) * 150;

    // De-collide overlapping cards (e.g. tables from multiple cameras sharing default coordinates)
    let guard = 0;
    while (
      placed.some((p) => Math.abs(p.x - fx) < 130 && Math.abs(p.y - fy) < 102) &&
      guard < 24
    ) {
      fx += 170;
      if (fx > 640) {
        fx = 60;
        fy += 130;
      }
      guard += 1;
    }
    const pos = { x: fx, y: fy };
    placed.push(pos);
    return pos;
  });
  const maxX = Math.max(800, ...coords.map((c) => c.x + 180));
  const maxY = Math.max(500, ...coords.map((c) => c.y + 150));
  const baseScale = Math.min(size.width / maxX, size.height / maxY);
  const effectiveScale = baseScale * zoom;

  return (
    <div
      ref={containerRef}
      className="tp-glass relative w-full overflow-hidden rounded-xl border p-3"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-[var(--text-secondary)]">
          Interactive Floor Canvas — click or tap any table
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.6, Math.round((z - 0.15) * 100) / 100))}
            className="rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-1.5 hover:opacity-80"
            aria-label="Zoom out floor canvas"
          >
            <ZoomOut className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => setZoom(1)}
            className="rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-1.5 hover:opacity-80"
            aria-label="Reset zoom"
          >
            <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(1.8, Math.round((z + 0.15) * 100) / 100))}
            className="rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-1.5 hover:opacity-80"
            aria-label="Zoom in floor canvas"
          >
            <ZoomIn className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
      </div>

      <Stage
        width={size.width - 24}
        height={size.height}
        scaleX={effectiveScale}
        scaleY={effectiveScale}
        className="rounded-lg bg-[var(--bg-canvas)]"
      >
        <Layer>
          {tables.map((tbl, idx) => {
            const meta = TABLE_STATE_META[tbl.current_state] ?? TABLE_STATE_META.UNKNOWN;
            const { x, y } = coords[idx] ?? {
              x: 70 + (idx % 4) * 190,
              y: 70 + Math.floor(idx / 4) * 150,
            };
            const isSelected = tbl.id === selectedTableId;
            const dash =
              tbl.current_state === "NEEDS_CLEANING" || tbl.current_state === "UNKNOWN"
                ? [8, 5]
                : tbl.current_state === "RESERVED"
                  ? [3, 4]
                  : undefined;

            const dwell =
              tbl.occupied_since &&
              (tbl.current_state === "OCCUPIED" || tbl.current_state === "NEEDS_SERVICE")
                ? formatElapsed(tbl.occupied_since, nowMs)
                : "";

            const cardWidth = tbl.shape === "BOOTH" ? 132 : 114;
            const textWidth = cardWidth - 16;

            return (
              <Group
                key={tbl.id}
                x={x}
                y={y}
                onClick={() => onSelectTable(tbl)}
                onTap={() => onSelectTable(tbl)}
              >
                {tbl.shape === "CIRCLE" ? (
                  <Circle
                    x={55}
                    y={48}
                    radius={48}
                    fill={meta.accentHex + (isDark ? "38" : "24")}
                    stroke={isSelected ? (isDark ? "#F8FAFC" : "#0F172A") : meta.accentHex}
                    strokeWidth={isSelected ? 4 : 2.5}
                    dash={dash}
                  />
                ) : (
                  <Rect
                    width={cardWidth}
                    height={92}
                    cornerRadius={tbl.shape === "BOOTH" ? 20 : 12}
                    fill={meta.accentHex + (isDark ? "38" : "24")}
                    stroke={isSelected ? (isDark ? "#F8FAFC" : "#0F172A") : meta.accentHex}
                    strokeWidth={isSelected ? 4 : 2.5}
                    dash={dash}
                  />
                )}
                <Text
                  x={8}
                  y={16}
                  width={tbl.shape === "CIRCLE" ? 94 : textWidth}
                  align="center"
                  text={tbl.table_code}
                  fontSize={16}
                  fontStyle="bold"
                  fill={isDark ? "#F8FAFC" : "#0F172A"}
                />
                <Text
                  x={8}
                  y={38}
                  width={tbl.shape === "CIRCLE" ? 94 : textWidth}
                  align="center"
                  text={`${tbl.current_guest_count}/${tbl.seat_capacity} guests`}
                  fontSize={12}
                  fill={isDark ? "#CBD5E1" : "#334155"}
                />
                <Text
                  x={8}
                  y={58}
                  width={tbl.shape === "CIRCLE" ? 94 : textWidth}
                  align="center"
                  text={dwell || meta.label}
                  fontSize={11}
                  fill={meta.accentHex}
                  fontStyle="bold"
                />
              </Group>
            );
          })}
        </Layer>
      </Stage>
    </div>
  );
}
