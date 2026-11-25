"""ByteTrack multi-object tracking wrapper and normalized ROI geometry mapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.detector import Detection


@dataclass(slots=True)
class TrackedPerson:
    track_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    is_staff: bool = False

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def aspect_ratio(self) -> float:
        w = max(1e-5, self.x2 - self.x1)
        h = max(1e-5, self.y2 - self.y1)
        return h / w


def point_in_polygon(x: float, y: float, polygon: list[dict[str, float]]) -> bool:
    """Ray-casting point-in-polygon check on normalized [0..1] vertices."""
    if len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]["x"], polygon[i]["y"]
        xj, yj = polygon[j]["x"], polygon[j]["y"]
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) if abs(yj - yi) > 1e-9 else 1e-9) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def point_near_polygon_perimeter(
    x: float, y: float, polygon: list[dict[str, float]], margin: float = 0.05
) -> bool:
    """Check if a standing person is within `margin` of table ROI (for staff visit detection)."""
    if not polygon or point_in_polygon(x, y, polygon):
        return False
    xs = [p["x"] for p in polygon]
    ys = [p["y"] for p in polygon]
    return (min(xs) - margin) <= x <= (max(xs) + margin) and (min(ys) - margin) <= y <= (
        max(ys) + margin
    )


class ByteTrackWrapper:
    """Ephemeral in-memory tracker via supervision.ByteTrack (MIT) with IoU fallback."""

    def __init__(self) -> None:
        self._sv_tracker: Any = None
        self._sv: Any = None
        try:
            import supervision as sv

            self._sv = sv
            self._sv_tracker = sv.ByteTrack()  # type: ignore[attr-defined]
        except Exception:
            self._sv_tracker = None
        self._next_id = 1
        self._prev_tracks: list[TrackedPerson] = []

    def update(self, detections: list[Detection]) -> list[TrackedPerson]:
        people = [d for d in detections if d.class_name == "person"]
        if not people:
            return []

        if self._sv_tracker is not None and self._sv is not None:
            xyxy = np.array([[d.x1, d.y1, d.x2, d.y2] for d in people], dtype=np.float32) * 1000.0
            conf = np.array([d.confidence for d in people], dtype=np.float32)
            cls_id = np.zeros(len(people), dtype=int)
            sv_dets = self._sv.Detections(xyxy=xyxy, confidence=conf, class_id=cls_id)
            tracked = self._sv_tracker.update_with_detections(sv_dets)
            out: list[TrackedPerson] = []
            tids = (
                tracked.tracker_id if tracked.tracker_id is not None else range(len(tracked.xyxy))
            )
            for idx, box in enumerate(tracked.xyxy):
                tid = int(tids[idx]) if idx < len(tids) else idx + 1
                c = float(tracked.confidence[idx]) if tracked.confidence is not None else 0.8
                t = TrackedPerson(
                    track_id=tid,
                    x1=float(box[0] / 1000.0),
                    y1=float(box[1] / 1000.0),
                    x2=float(box[2] / 1000.0),
                    y2=float(box[3] / 1000.0),
                    confidence=c,
                )
                t.is_staff = t.aspect_ratio >= 2.0
                out.append(t)
            return out

        # Deterministic IoU fallback (ephemeral memory only)
        assigned: list[TrackedPerson] = []
        for det in people:
            best_id = None
            best_iou = 0.25
            for prev in self._prev_tracks:
                iou = _iou((det.x1, det.y1, det.x2, det.y2), (prev.x1, prev.y1, prev.x2, prev.y2))
                if iou > best_iou:
                    best_iou = iou
                    best_id = prev.track_id
            if best_id is None:
                best_id = self._next_id
                self._next_id += 1
            tp = TrackedPerson(
                track_id=best_id,
                x1=det.x1,
                y1=det.y1,
                x2=det.x2,
                y2=det.y2,
                confidence=det.confidence,
            )
            tp.is_staff = tp.aspect_ratio >= 2.0
            assigned.append(tp)
        self._prev_tracks = assigned
        return assigned


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(1e-6, (a[2] - a[0]) * (a[3] - a[1]))
    area_b = max(1e-6, (b[2] - b[0]) * (b[3] - b[1]))
    return inter / max(1e-6, area_a + area_b - inter)
