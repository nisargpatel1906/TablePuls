"""Stage 4 Verification: Deterministic state machine, detector license gate, face-blur-or-drop, kill switch."""

from __future__ import annotations

import numpy as np
import pytest

from app.detector import DetectorError, PersonAndObjectDetector
from app.eta import TurnoverETAPredictor
from app.privacy import FaceBlurError, blur_faces_in_frame, encode_blurred_jpeg
from app.state_machine import (
    TableObservation,
    TableRuleConfig,
    TableState,
    TableStateMachine,
    TableTrackerState,
)
from app.tracker import ByteTrackWrapper, point_in_polygon
from app.worker import CameraPipelineConfig, CameraProcessor, KillSwitchClient, TableROI


class FakeValkey:
    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self.kv: dict[str, str] = dict(initial or {})
        self.stream: list[dict[str, str]] = []

    def get(self, key: str) -> str | None:
        return self.kv.get(key)

    def xadd(self, _name: str, payload: dict[str, str], **_kw: object) -> str:
        self.stream.append(payload)
        return f"{len(self.stream)}-0"


def test_detector_rejects_restricted_rfdetr_sizes() -> None:
    for banned in ("atto", "femto", "pico", "xl", "2xl"):
        with pytest.raises(DetectorError):
            PersonAndObjectDetector(model_variant=banned)
    ok = PersonAndObjectDetector(model_variant="nano")
    assert ok.model_variant == "nano"


def test_deterministic_state_machine_transitions() -> None:
    sm = TableStateMachine(
        TableRuleConfig(
            occupancy_debounce_sec=10.0,
            departure_debounce_sec=20.0,
            unattended_service_sec=300.0,
            clean_confirm_sec=10.0,
            staff_visit_dwell_sec=4.0,
            min_confidence=0.65,
            camera_stale_s=30.0,
        )
    )
    tr = TableTrackerState(table_id="t1")

    # 1. Passerby for 8s (< 10s debounce) must remain FREE
    for t in (0.0, 4.0, 8.0):
        ev = sm.step(
            tr,
            TableObservation(
                timestamp_s=t,
                seated_guest_count=1,
                staff_at_perimeter=False,
                cleanliness_label="CLEAN",
                cleanliness_conf=0.9,
                detection_conf=0.9,
            ),
        )
        assert ev is None
    assert tr.state == TableState.FREE

    # Reset brief absence then seat for >= 10s -> OCCUPIED
    sm.step(tr, TableObservation(9.0, 0, False, "CLEAN", 0.9, 0.9))
    ev_start = sm.step(tr, TableObservation(10.0, 2, False, "CLEAN", 0.9, 0.9))
    assert ev_start is None
    ev_occ = sm.step(tr, TableObservation(20.0, 2, False, "CLEAN", 0.9, 0.9))
    assert ev_occ is not None
    assert ev_occ.new_state == TableState.OCCUPIED
    assert tr.guest_count == 2

    # 2. Unattended > 300s -> NEEDS_SERVICE
    ev_srv = sm.step(tr, TableObservation(321.0, 2, False, "CLEAN", 0.9, 0.9))
    assert ev_srv is not None
    assert ev_srv.new_state == TableState.NEEDS_SERVICE

    # 3. Staff visit >= 4s clears NEEDS_SERVICE -> OCCUPIED
    assert sm.step(tr, TableObservation(325.0, 2, True, "CLEAN", 0.9, 0.9)) is None
    ev_att = sm.step(tr, TableObservation(329.5, 2, True, "CLEAN", 0.9, 0.9))
    assert ev_att is not None
    assert ev_att.new_state == TableState.OCCUPIED

    # 4. Guests depart for >= 20s with dishes (DIRTY) -> NEEDS_CLEANING
    assert sm.step(tr, TableObservation(400.0, 0, False, "DIRTY", 0.85, 0.9)) is None
    ev_dirty = sm.step(tr, TableObservation(420.5, 0, False, "DIRTY", 0.85, 0.9))
    assert ev_dirty is not None
    assert ev_dirty.new_state == TableState.NEEDS_CLEANING

    # 5. Clean surface for 10s -> FREE
    assert sm.step(tr, TableObservation(430.0, 0, False, "CLEAN", 0.9, 0.9)) is None
    ev_free = sm.step(tr, TableObservation(440.5, 0, False, "CLEAN", 0.9, 0.9))
    assert ev_free is not None
    assert ev_free.new_state == TableState.FREE

    # 6. Low confidence > 30s -> UNKNOWN + review enqueue
    assert sm.step(tr, TableObservation(500.0, 0, False, "CLEAN", 0.4, 0.4)) is None
    ev_unk = sm.step(tr, TableObservation(531.0, 0, False, "CLEAN", 0.4, 0.4))
    assert ev_unk is not None
    assert ev_unk.new_state == TableState.UNKNOWN
    assert ev_unk.enqueue_review is True


def test_kill_switch_fail_safe_emits_zero_events(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_cv_settings

    # Missing kill switch -> False -> 0 events emitted
    monkeypatch.delenv("AI_INFERENCE_ENABLED", raising=False)
    get_cv_settings.cache_clear()

    vk = FakeValkey({})
    roi = TableROI(
        table_id="t1",
        table_code="T01",
        venue_id="v1",
        organization_id="org1",
        polygon=[
            {"x": 0.1, "y": 0.1},
            {"x": 0.4, "y": 0.1},
            {"x": 0.4, "y": 0.4},
            {"x": 0.1, "y": 0.4},
        ],
        rules=TableRuleConfig(),
    )
    proc = CameraProcessor(
        CameraPipelineConfig(
            camera_id="c1",
            venue_id="v1",
            organization_id="org1",
            stream_url="demo.mp4",
            stream_type="DEMO_MP4",
            target_fps=2,
            face_blur_enabled=True,
            exclusion_polygons=[],
            tables=[roi],
        ),
        kill_switch=KillSwitchClient(vk),
        valkey_client=vk,
    )
    assert proc.step_observation("t1", TableObservation(0.0, 2, False, "CLEAN", 0.9, 0.9)) is None
    assert proc.step_observation("t1", TableObservation(15.0, 2, False, "CLEAN", 0.9, 0.9)) is None
    assert len(vk.stream) == 0

    # Enable both env + Valkey kill switch -> emits transition to Valkey stream
    monkeypatch.setenv("AI_INFERENCE_ENABLED", "true")
    get_cv_settings.cache_clear()
    vk.kv["tp:kill_switch:org1"] = "true"
    assert proc.step_observation("t1", TableObservation(20.0, 2, False, "CLEAN", 0.9, 0.9)) is None
    ev = proc.step_observation("t1", TableObservation(31.0, 2, False, "CLEAN", 0.9, 0.9))
    assert ev is not None
    assert len(vk.stream) == 1
    assert vk.stream[0]["new_state"] == "OCCUPIED"


def test_privacy_blur_or_drop_and_eta_and_geometry() -> None:
    frame = np.full((480, 640, 3), 120, dtype=np.uint8)
    out = blur_faces_in_frame(frame, person_boxes_px=[(100, 50, 200, 300)])
    assert out.shape == frame.shape
    jpg = encode_blurred_jpeg(frame, person_boxes_px=[(100, 50, 200, 300)])
    assert len(jpg) > 100

    with pytest.raises(FaceBlurError):
        blur_faces_in_frame(np.zeros((0, 0, 3), dtype=np.uint8))

    assert point_in_polygon(
        0.2,
        0.2,
        [{"x": 0.1, "y": 0.1}, {"x": 0.5, "y": 0.1}, {"x": 0.5, "y": 0.5}, {"x": 0.1, "y": 0.5}],
    )
    assert not point_in_polygon(
        0.9,
        0.9,
        [{"x": 0.1, "y": 0.1}, {"x": 0.5, "y": 0.1}, {"x": 0.5, "y": 0.5}, {"x": 0.1, "y": 0.5}],
    )

    eta = TurnoverETAPredictor().predict(elapsed_minutes=25.0, seat_capacity=4, state="OCCUPIED")
    assert eta.min_minutes >= 1 and eta.max_minutes >= eta.min_minutes
    _ = ByteTrackWrapper()
