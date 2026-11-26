"use client";

import React, { useEffect, useRef, useState } from "react";
import { Circle, Image as KonvaImage, Layer, Line, Stage, Text } from "react-konva";
import type { PolygonPoint } from "@/types/floor";

export interface CalibrationTable {
  id?: string;
  table_code: string;
  section_name: string;
  seat_capacity: number;
  polygon_json: PolygonPoint[];
  floor_x: number;
  floor_y: number;
  shape: string;
  version: number;
}

interface PolygonEditorCanvasProps {
  previewBase64: string | null;
  tables: CalibrationTable[];
  exclusionZones: PolygonPoint[][];
  selectedIndex: number;
  mode: "draw" | "edit" | "exclusion";
  draftPoints: PolygonPoint[];
  onAddPoint: (pt: PolygonPoint) => void;
  onSelectTable: (idx: number) => void;
  onMoveVertex: (tableIdx: number, vertexIdx: number, pt: PolygonPoint) => void;
}

export default function PolygonEditorCanvas({
  previewBase64,
  tables,
  exclusionZones,
  selectedIndex,
  mode,
  draftPoints,
  onAddPoint,
  onSelectTable,
  onMoveVertex,
}: PolygonEditorCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 720, height: 405 });
  const [bgImage, setBgImage] = useState<HTMLImageElement | null>(null);

  useEffect(() => {
    if (!previewBase64) {
      setBgImage(null);
      return;
    }
    const img = new window.Image();
    img.onload = () => setBgImage(img);
    img.src = `data:image/jpeg;base64,${previewBase64}`;
  }, [previewBase64]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const updateSize = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width <= 120) return;
      const vh = typeof window !== "undefined" ? window.innerHeight : 800;
      const maxH = Math.max(220, Math.min(440, vh - 260));
      const maxWByH = Math.floor((maxH * 16) / 9);
      const w = Math.max(280, Math.min(Math.floor(rect.width - 16), maxWByH));
      const h = Math.round((w * 9) / 16);
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

  return (
    <div
      ref={containerRef}
      className="tp-glass flex w-full justify-center overflow-hidden rounded-xl border p-2"
    >
      <Stage
        width={size.width}
        height={size.height}
        className="rounded-lg bg-slate-900"
        onClick={(e) => {
          if (mode !== "draw" && mode !== "exclusion") return;
          const stage = e.target.getStage();
          const pos = stage?.getPointerPosition();
          if (!pos) return;
          const nx = Math.min(1, Math.max(0, Math.round((pos.x / size.width) * 1000) / 1000));
          const ny = Math.min(1, Math.max(0, Math.round((pos.y / size.height) * 1000) / 1000));
          onAddPoint({ x: nx, y: ny });
        }}
      >
        <Layer>
          {bgImage && <KonvaImage image={bgImage} width={size.width} height={size.height} />}

          {exclusionZones.map((zone, idx) => (
            <Line
              key={`ex-${idx}`}
              points={zone.flatMap((p) => [p.x * size.width, p.y * size.height])}
              closed
              fill="rgba(100, 116, 139, 0.35)"
              stroke="#94A3B8"
              strokeWidth={2}
              dash={[6, 4]}
            />
          ))}

          {tables.map((tbl, idx) => {
            const pts = tbl.polygon_json ?? [];
            const isSel = idx === selectedIndex;
            const flatPts = pts.flatMap((p) => [p.x * size.width, p.y * size.height]);
            const cx =
              pts.length > 0
                ? (pts.reduce((a, p) => a + p.x, 0) / pts.length) * size.width
                : 40;
            const cy =
              pts.length > 0
                ? (pts.reduce((a, p) => a + p.y, 0) / pts.length) * size.height
                : 40;

            return (
              <React.Fragment key={tbl.id || `${tbl.table_code}-${idx}`}>
                <Line
                  points={flatPts}
                  closed
                  fill={isSel ? "rgba(0, 122, 255, 0.28)" : "rgba(52, 199, 89, 0.22)"}
                  stroke={isSel ? "#007AFF" : "#34C759"}
                  strokeWidth={isSel ? 3 : 2}
                  onClick={() => onSelectTable(idx)}
                  onTap={() => onSelectTable(idx)}
                />
                <Text
                  x={cx - 32}
                  y={cy - 8}
                  width={64}
                  align="center"
                  text={`${tbl.table_code} (${tbl.seat_capacity})`}
                  fontSize={12}
                  fontStyle="bold"
                  fill="#FFFFFF"
                />
                {mode === "edit" &&
                  isSel &&
                  pts.map((pt, vIdx) => (
                    <Circle
                      key={`v-${idx}-${vIdx}`}
                      x={pt.x * size.width}
                      y={pt.y * size.height}
                      radius={7}
                      fill="#FFFFFF"
                      stroke="#007AFF"
                      strokeWidth={2.5}
                      draggable
                      onDragEnd={(evt) => {
                        const nx = Math.min(
                          1,
                          Math.max(0, Math.round((evt.target.x() / size.width) * 1000) / 1000),
                        );
                        const ny = Math.min(
                          1,
                          Math.max(0, Math.round((evt.target.y() / size.height) * 1000) / 1000),
                        );
                        onMoveVertex(idx, vIdx, { x: nx, y: ny });
                      }}
                    />
                  ))}
              </React.Fragment>
            );
          })}

          {draftPoints.length > 0 && (
            <Line
              points={draftPoints.flatMap((p) => [p.x * size.width, p.y * size.height])}
              stroke="#FF9500"
              strokeWidth={2.5}
            />
          )}
        </Layer>
      </Stage>
    </div>
  );
}
