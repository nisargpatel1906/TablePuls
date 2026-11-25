"use client";

import React, { useEffect, useRef, useState } from "react";
import { Circle, Group, Layer, Rect, Stage, Text } from "react-konva";
import { Maximize2, ZoomIn, ZoomOut } from "lucide-react";
import { TABLE_STATE_META, formatElapsed } from "@/lib/table-states";
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
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 820, height: 500 });
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const obs = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      if (rect && rect.width > 120) {
        setSize({
          width: Math.max(320, Math.floor(rect.width)),
          height: Math.max(380, Math.min(540, Math.floor(rect.width * 0.56))),
        });
      }
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Compute bounding extent of coordinates so custom polygons/coords fit inside viewport cleanly
  const maxX = Math.max(800, ...tables.map((t) => (t.floor_x || 0) + 180));
  const maxY = Math.max(500, ...tables.map((t) => (t.floor_y || 0) + 150));
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
            const x = tbl.floor_x > 0 ? tbl.floor_x : 70 + (idx % 4) * 190;
            const y = tbl.floor_y > 0 ? tbl.floor_y : 70 + Math.floor(idx / 4) * 150;
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
                    fill={meta.accentHex + "24"}
                    stroke={isSelected ? "#0F172A" : meta.accentHex}
                    strokeWidth={isSelected ? 4 : 2.5}
                    dash={dash}
                  />
                ) : (
                  <Rect
                    width={tbl.shape === "BOOTH" ? 132 : 114}
                    height={92}
                    cornerRadius={tbl.shape === "BOOTH" ? 20 : 12}
                    fill={meta.accentHex + "24"}
                    stroke={isSelected ? "#0F172A" : meta.accentHex}
                    strokeWidth={isSelected ? 4 : 2.5}
                    dash={dash}
                  />
                )}
                <Text
                  x={10}
                  y={16}
                  width={94}
                  align="center"
                  text={tbl.table_code}
                  fontSize={16}
                  fontStyle="bold"
                  fill="#0F172A"
                />
                <Text
                  x={10}
                  y={38}
                  width={94}
                  align="center"
                  text={`${tbl.current_guest_count}/${tbl.seat_capacity} guests`}
                  fontSize={12}
                  fill="#334155"
                />
                <Text
                  x={10}
                  y={58}
                  width={94}
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
