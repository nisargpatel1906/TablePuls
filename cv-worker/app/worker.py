"""CV Worker pipeline coordinator: kill-switch guard, frame sampling, inference, Valkey Streams publisher."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog

from app.cleanliness import CleanlinessClassifier
from app.config import get_cv_settings
from app.detector import PersonAndObjectDetector
from app.privacy import FaceBlurError, encode_blurred_jpeg
from app.state_machine import (
    StateTransitionEvent,
    TableObservation,
    TableRuleConfig,
    TableStateMachine,
    TableTrackerState,
)
from app.tracker import (
    ByteTrackWrapper,
    TrackedPerson,
    point_in_polygon,
    point_near_polygon_perimeter,
)

logger = structlog.get_logger("cv_worker")


@dataclass(slots=True)
class TableROI:
    table_id: str
    table_code: str
    venue_id: str
    organization_id: str
    polygon: list[dict[str, float]]
    rules: TableRuleConfig


@dataclass(slots=True)
class CameraPipelineConfig:
    camera_id: str
    venue_id: str
    organization_id: str
    stream_url: str
    stream_type: str
    target_fps: int
    face_blur_enabled: bool
    exclusion_polygons: list[list[dict[str, float]]]
    tables: list[TableROI]


class KillSwitchClient:
    """Checks Valkey + env fail-closed kill switch before every inference batch."""

    def __init__(self, valkey_client: Any | None = None) -> None:
        self._vk = valkey_client

    def is_inference_enabled(self, organization_id: str | None = None) -> bool:
        settings = get_cv_settings()
        if not settings.ai_inference_enabled:
            return False
        if self._vk is None:
            return False
        try:
            if organization_id:
                org_val = self._vk.get(f"tp:kill_switch:{organization_id}")
                if org_val is not None:
                    return str(org_val).lower() == "true"
            glob_val = self._vk.get("tp:kill_switch:global")
            if glob_val is None:
                return False
            return str(glob_val).lower() == "true"
        except Exception:
            # Fail-safe paused when Valkey unreachable
            return False


class CameraProcessor:
    """Runs frame -> face-blur -> detector -> tracker -> ROI -> state machine."""

    def __init__(
        self,
        cam_cfg: CameraPipelineConfig,
        *,
        detector: PersonAndObjectDetector | None = None,
        cleanliness: CleanlinessClassifier | None = None,
        kill_switch: KillSwitchClient | None = None,
        valkey_client: Any | None = None,
    ) -> None:
        self.cfg = cam_cfg
        self.detector = detector or PersonAndObjectDetector(device=get_cv_settings().ml_device)
        self.cleanliness = cleanliness or CleanlinessClassifier(device=get_cv_settings().ml_device)
        self.tracker = ByteTrackWrapper()
        self.kill_switch = kill_switch or KillSwitchClient(valkey_client)
        self._vk = valkey_client
        self._table_states: dict[str, TableTrackerState] = {}
        self._state_machines: dict[str, TableStateMachine] = {}
        self.effective_fps: int = cam_cfg.target_fps
        self._high_latency_streak_s: float = 0.0

        for roi in cam_cfg.tables:
            self._table_states[roi.table_id] = TableTrackerState(table_id=roi.table_id)
            self._state_machines[roi.table_id] = TableStateMachine(roi.rules)

    def _in_exclusion_zone(self, x: float, y: float) -> bool:
        return any(point_in_polygon(x, y, poly) for poly in self.cfg.exclusion_polygons)

    def _crop_table_bgr(
        self, frame: np.ndarray[Any, Any], polygon: list[dict[str, float]]
    ) -> np.ndarray[Any, Any]:
        h, w = frame.shape[:2]
        xs = [int(max(0, min(w - 1, p["x"] * w))) for p in polygon]
        ys = [int(max(0, min(h - 1, p["y"] * h))) for p in polygon]
        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)
        if x2 <= x1 or y2 <= y1:
            return frame[0:0, 0:0]
        return frame[y1:y2, x1:x2]

    def process_frame(
        self,
        frame: np.ndarray[Any, Any] | None,
        *,
        timestamp_s: float,
        camera_online: bool = True,
    ) -> list[StateTransitionEvent]:
        """Process a single frame and return emitted StateTransitionEvents."""
        # 1. Fail-closed kill switch check BEFORE every inference batch
        if not self.kill_switch.is_inference_enabled(self.cfg.organization_id):
            return []

        t0 = time.perf_counter()
        events: list[StateTransitionEvent] = []

        if not camera_online or frame is None or frame.size == 0:
            for roi in self.cfg.tables:
                obs = TableObservation(
                    timestamp_s=timestamp_s,
                    seated_guest_count=0,
                    staff_at_perimeter=False,
                    cleanliness_label="UNKNOWN",
                    cleanliness_conf=0.0,
                    detection_conf=0.0,
                    camera_online=False,
                )
                ev = self._state_machines[roi.table_id].step(self._table_states[roi.table_id], obs)
                if ev is not None:
                    events.append(ev)
                    self._publish_event(roi, ev, crop_jpeg=None)
            return events

        detections = self.detector.detect(frame)
        tracked: list[TrackedPerson] = self.tracker.update(detections)

        h, w = frame.shape[:2]
        person_boxes_px = [
            (int(t.x1 * w), int(t.y1 * h), int(t.x2 * w), int(t.y2 * h)) for t in tracked
        ]

        for roi in self.cfg.tables:
            seated = 0
            staff_near = False
            det_confs: list[float] = []

            for person in tracked:
                cx, cy = person.center
                if self._in_exclusion_zone(cx, cy):
                    continue
                if point_in_polygon(cx, cy, roi.polygon):
                    if person.is_staff:
                        staff_near = True
                    else:
                        seated += 1
                    det_confs.append(person.confidence)
                elif point_near_polygon_perimeter(cx, cy, roi.polygon) and (
                    person.is_staff or person.aspect_ratio >= 1.5
                ):
                    staff_near = True

            det_conf = min(det_confs) if det_confs else 0.90
            crop = self._crop_table_bgr(frame, roi.polygon)
            clean_pred = self.cleanliness.classify_crop(crop)

            obs = TableObservation(
                timestamp_s=timestamp_s,
                seated_guest_count=seated,
                staff_at_perimeter=staff_near,
                cleanliness_label=clean_pred.label,
                cleanliness_conf=clean_pred.confidence,
                detection_conf=det_conf,
                camera_online=True,
            )
            ev = self._state_machines[roi.table_id].step(self._table_states[roi.table_id], obs)
            if ev is not None:
                crop_jpeg: bytes | None = None
                if ev.enqueue_review and get_cv_settings().review_crops_enabled and crop.size > 0:
                    try:
                        crop_jpeg = encode_blurred_jpeg(crop, person_boxes_px=person_boxes_px)
                    except FaceBlurError:
                        # Blur-or-drop rule: never emit unblurred frame/crop
                        crop_jpeg = None
                events.append(ev)
                self._publish_event(roi, ev, crop_jpeg=crop_jpeg)

        # Adaptive FPS back-pressure throttling (docs/09 §7)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        budget_ms = 250.0
        if elapsed_ms > budget_ms * 2:
            self._high_latency_streak_s += 1.0 / max(1, self.effective_fps)
            if self._high_latency_streak_s >= 60.0 and self.effective_fps > 1:
                self.effective_fps = 1
        else:
            self._high_latency_streak_s = 0.0
            self.effective_fps = self.cfg.target_fps

        return events

    def step_observation(self, table_id: str, obs: TableObservation) -> StateTransitionEvent | None:
        """Direct observation stepping (used for deterministic state-machine replay)."""
        if not self.kill_switch.is_inference_enabled(self.cfg.organization_id):
            return None
        ev = self._state_machines[table_id].step(self._table_states[table_id], obs)
        if ev is not None:
            roi = next(r for r in self.cfg.tables if r.table_id == table_id)
            self._publish_event(roi, ev, crop_jpeg=None)
        return ev

    def _publish_event(
        self,
        roi: TableROI,
        ev: StateTransitionEvent,
        *,
        crop_jpeg: bytes | None,
    ) -> None:
        if self._vk is None:
            return
        payload = {
            "table_id": ev.table_id,
            "table_code": roi.table_code,
            "venue_id": roi.venue_id,
            "organization_id": roi.organization_id,
            "camera_id": self.cfg.camera_id,
            "previous_state": ev.previous_state.value,
            "new_state": ev.new_state.value,
            "guest_count": str(ev.guest_count),
            "confidence": f"{ev.confidence:.4f}",
            "source": ev.source,
            "session_id": ev.session_id or "",
            "reason": ev.reason,
            "model_version": get_cv_settings().model_version,
            "enqueue_review": "1" if ev.enqueue_review else "0",
            "occurred_at_s": f"{ev.occurred_at_s:.3f}",
        }
        if crop_jpeg is not None:
            import base64

            payload["blurred_crop_b64"] = base64.b64encode(crop_jpeg).decode("ascii")
        try:
            self._vk.xadd("tp:cv:events", payload, maxlen=10000, approximate=True)
        except Exception as exc:
            logger.warning("valkey_publish_failed", error=str(exc))
