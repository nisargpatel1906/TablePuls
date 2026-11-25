"""Per-table temporal debounce, service SLA, cleaning, and UNKNOWN fallback state machine."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class TableState(StrEnum):
    FREE = "FREE"
    OCCUPIED = "OCCUPIED"
    NEEDS_SERVICE = "NEEDS_SERVICE"
    NEEDS_CLEANING = "NEEDS_CLEANING"
    RESERVED = "RESERVED"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True)
class TableRuleConfig:
    occupancy_debounce_sec: float = 10.0
    departure_debounce_sec: float = 20.0
    unattended_service_sec: float = 300.0
    cleaning_alert_delay_sec: float = 120.0
    clean_confirm_sec: float = 10.0
    staff_visit_dwell_sec: float = 4.0
    min_confidence: float = 0.65
    camera_stale_s: float = 30.0
    require_bussing_confirmation: bool = False


@dataclass(slots=True)
class TableObservation:
    """Single-frame observation mapped to a table ROI."""

    timestamp_s: float
    seated_guest_count: int
    staff_at_perimeter: bool
    cleanliness_label: str  # "CLEAN" | "DIRTY" | "UNKNOWN"
    cleanliness_conf: float
    detection_conf: float
    camera_online: bool = True


@dataclass(slots=True)
class StateTransitionEvent:
    table_id: str
    previous_state: TableState
    new_state: TableState
    guest_count: int
    confidence: float
    source: str
    session_id: str | None
    occurred_at_s: float
    reason: str
    enqueue_review: bool = False


@dataclass(slots=True)
class TableTrackerState:
    table_id: str
    state: TableState = TableState.FREE
    guest_count: int = 0
    confidence: float = 1.0
    session_id: str | None = None
    occupied_since_s: float | None = None
    last_staff_visit_s: float | None = None
    manual_override: bool = False

    # Internal debounce timers
    _seated_candidate_since_s: float | None = field(default=None)
    _empty_candidate_since_s: float | None = field(default=None)
    _clean_candidate_since_s: float | None = field(default=None)
    _low_conf_since_s: float | None = field(default=None)
    _high_conf_recovery_since_s: float | None = field(default=None)
    _staff_dwell_since_s: float | None = field(default=None)


class TableStateMachine:
    """Deterministic per-table state engine satisfying FR-006 through FR-010."""

    def __init__(self, rules: TableRuleConfig | None = None) -> None:
        self.rules = rules or TableRuleConfig()

    def step(
        self,
        tracker: TableTrackerState,
        obs: TableObservation,
    ) -> StateTransitionEvent | None:
        now = obs.timestamp_s
        prev = tracker.state
        conf = min(obs.detection_conf, obs.cleanliness_conf)
        tracker.confidence = conf

        # 1. Camera offline -> immediate UNKNOWN (never silently FREE)
        if not obs.camera_online:
            tracker._seated_candidate_since_s = None
            tracker._empty_candidate_since_s = None
            tracker._clean_candidate_since_s = None
            if prev != TableState.UNKNOWN and not tracker.manual_override:
                tracker.state = TableState.UNKNOWN
                return StateTransitionEvent(
                    table_id=tracker.table_id,
                    previous_state=prev,
                    new_state=TableState.UNKNOWN,
                    guest_count=tracker.guest_count,
                    confidence=0.0,
                    source="SYSTEM",
                    session_id=tracker.session_id,
                    occurred_at_s=now,
                    reason="camera_offline",
                    enqueue_review=True,
                )
            return None

        # 2. Manual override hold (RESERVED or manual override holds until ML >= 0.80 for 30s)
        if tracker.state == TableState.RESERVED:
            if obs.seated_guest_count > 0:
                if tracker._seated_candidate_since_s is None:
                    tracker._seated_candidate_since_s = now
                if (now - tracker._seated_candidate_since_s) >= self.rules.occupancy_debounce_sec:
                    tracker.manual_override = False
                    return self._enter_occupied(tracker, obs, now, "reserved_party_seated")
            else:
                tracker._seated_candidate_since_s = None
            return None

        if tracker.manual_override:
            if conf >= 0.80:
                if tracker._high_conf_recovery_since_s is None:
                    tracker._high_conf_recovery_since_s = now
                if (now - tracker._high_conf_recovery_since_s) >= 30.0:
                    tracker.manual_override = False
                    tracker._high_conf_recovery_since_s = None
            else:
                tracker._high_conf_recovery_since_s = None
            if tracker.manual_override:
                return None

        # 3. Low-confidence tracking (> camera_stale_s / 30s -> UNKNOWN + review queue)
        if conf < self.rules.min_confidence:
            if tracker._low_conf_since_s is None:
                tracker._low_conf_since_s = now
            if (
                prev != TableState.UNKNOWN
                and (now - tracker._low_conf_since_s) >= self.rules.camera_stale_s
            ):
                tracker.state = TableState.UNKNOWN
                return StateTransitionEvent(
                    table_id=tracker.table_id,
                    previous_state=prev,
                    new_state=TableState.UNKNOWN,
                    guest_count=tracker.guest_count,
                    confidence=conf,
                    source="AI",
                    session_id=tracker.session_id,
                    occurred_at_s=now,
                    reason="low_confidence",
                    enqueue_review=True,
                )
            return None
        else:
            tracker._low_conf_since_s = None

        # 4. Recovery from UNKNOWN once confidence >= min_confidence
        if tracker.state == TableState.UNKNOWN:
            if obs.seated_guest_count > 0:
                return self._enter_occupied(tracker, obs, now, "recovered_occupied")
            if obs.cleanliness_label == "DIRTY":
                tracker.state = TableState.NEEDS_CLEANING
                tracker.guest_count = 0
                return StateTransitionEvent(
                    table_id=tracker.table_id,
                    previous_state=prev,
                    new_state=TableState.NEEDS_CLEANING,
                    guest_count=0,
                    confidence=conf,
                    source="AI",
                    session_id=tracker.session_id,
                    occurred_at_s=now,
                    reason="recovered_dirty",
                )
            tracker.state = TableState.FREE
            tracker.guest_count = 0
            tracker.occupied_since_s = None
            tracker.last_staff_visit_s = None
            tracker.session_id = None
            return StateTransitionEvent(
                table_id=tracker.table_id,
                previous_state=prev,
                new_state=TableState.FREE,
                guest_count=0,
                confidence=conf,
                source="AI",
                session_id=None,
                occurred_at_s=now,
                reason="recovered_free",
            )

        # 5. Normal state transitions
        if tracker.state == TableState.FREE:
            if obs.seated_guest_count > 0:
                if tracker._seated_candidate_since_s is None:
                    tracker._seated_candidate_since_s = now
                if (now - tracker._seated_candidate_since_s) >= self.rules.occupancy_debounce_sec:
                    return self._enter_occupied(tracker, obs, now, "guests_seated")
            else:
                tracker._seated_candidate_since_s = None
            return None

        if tracker.state in (TableState.OCCUPIED, TableState.NEEDS_SERVICE):
            # Staff visit detection (>= 4s at table perimeter)
            if obs.staff_at_perimeter:
                if tracker._staff_dwell_since_s is None:
                    tracker._staff_dwell_since_s = now
                if (now - tracker._staff_dwell_since_s) >= self.rules.staff_visit_dwell_sec:
                    tracker.last_staff_visit_s = now
                    if tracker.state == TableState.NEEDS_SERVICE:
                        tracker.state = TableState.OCCUPIED
                        return StateTransitionEvent(
                            table_id=tracker.table_id,
                            previous_state=prev,
                            new_state=TableState.OCCUPIED,
                            guest_count=obs.seated_guest_count or tracker.guest_count,
                            confidence=conf,
                            source="AI",
                            session_id=tracker.session_id,
                            occurred_at_s=now,
                            reason="staff_visit_detected",
                        )
            else:
                tracker._staff_dwell_since_s = None

            if obs.seated_guest_count > 0:
                tracker._empty_candidate_since_s = None
                tracker.guest_count = obs.seated_guest_count
                # Check unattended service SLA
                if (
                    tracker.state == TableState.OCCUPIED
                    and tracker.last_staff_visit_s is None
                    and tracker.occupied_since_s is not None
                    and (now - tracker.occupied_since_s) >= self.rules.unattended_service_sec
                ):
                    tracker.state = TableState.NEEDS_SERVICE
                    return StateTransitionEvent(
                        table_id=tracker.table_id,
                        previous_state=prev,
                        new_state=TableState.NEEDS_SERVICE,
                        guest_count=tracker.guest_count,
                        confidence=conf,
                        source="AI",
                        session_id=tracker.session_id,
                        occurred_at_s=now,
                        reason="unattended_service_sla",
                    )
                return None

            # Guests departed (0 seated) -> wait departure_debounce_sec
            if tracker._empty_candidate_since_s is None:
                tracker._empty_candidate_since_s = now
            if (now - tracker._empty_candidate_since_s) >= self.rules.departure_debounce_sec:
                tracker.guest_count = 0
                tracker._empty_candidate_since_s = None
                needs_clean = (
                    obs.cleanliness_label == "DIRTY"
                    and obs.cleanliness_conf >= self.rules.min_confidence
                ) or self.rules.require_bussing_confirmation
                if needs_clean:
                    tracker.state = TableState.NEEDS_CLEANING
                    tracker._clean_candidate_since_s = None
                    return StateTransitionEvent(
                        table_id=tracker.table_id,
                        previous_state=prev,
                        new_state=TableState.NEEDS_CLEANING,
                        guest_count=0,
                        confidence=conf,
                        source="AI",
                        session_id=tracker.session_id,
                        occurred_at_s=now,
                        reason="party_departed_needs_cleaning",
                    )
                tracker.state = TableState.FREE
                tracker.occupied_since_s = None
                tracker.last_staff_visit_s = None
                tracker.session_id = None
                return StateTransitionEvent(
                    table_id=tracker.table_id,
                    previous_state=prev,
                    new_state=TableState.FREE,
                    guest_count=0,
                    confidence=conf,
                    source="AI",
                    session_id=None,
                    occurred_at_s=now,
                    reason="party_departed_clean",
                )
            return None

        if tracker.state == TableState.NEEDS_CLEANING:
            if obs.seated_guest_count > 0:
                if tracker._seated_candidate_since_s is None:
                    tracker._seated_candidate_since_s = now
                if (now - tracker._seated_candidate_since_s) >= self.rules.occupancy_debounce_sec:
                    return self._enter_occupied(tracker, obs, now, "new_guests_seated")
                return None
            tracker._seated_candidate_since_s = None

            if (
                not self.rules.require_bussing_confirmation
                and obs.cleanliness_label == "CLEAN"
                and obs.cleanliness_conf >= self.rules.min_confidence
                and not obs.staff_at_perimeter
            ):
                if tracker._clean_candidate_since_s is None:
                    tracker._clean_candidate_since_s = now
                if (now - tracker._clean_candidate_since_s) >= self.rules.clean_confirm_sec:
                    tracker.state = TableState.FREE
                    tracker.occupied_since_s = None
                    tracker.last_staff_visit_s = None
                    tracker.session_id = None
                    tracker._clean_candidate_since_s = None
                    return StateTransitionEvent(
                        table_id=tracker.table_id,
                        previous_state=prev,
                        new_state=TableState.FREE,
                        guest_count=0,
                        confidence=conf,
                        source="AI",
                        session_id=None,
                        occurred_at_s=now,
                        reason="table_cleaned",
                    )
            else:
                tracker._clean_candidate_since_s = None

        return None

    def _enter_occupied(
        self,
        tracker: TableTrackerState,
        obs: TableObservation,
        now: float,
        reason: str,
    ) -> StateTransitionEvent:
        prev = tracker.state
        tracker.state = TableState.OCCUPIED
        tracker.guest_count = max(1, obs.seated_guest_count)
        tracker.occupied_since_s = now
        tracker.last_staff_visit_s = None
        tracker.session_id = str(uuid.uuid4())
        tracker._seated_candidate_since_s = None
        tracker._empty_candidate_since_s = None
        return StateTransitionEvent(
            table_id=tracker.table_id,
            previous_state=prev,
            new_state=TableState.OCCUPIED,
            guest_count=tracker.guest_count,
            confidence=tracker.confidence,
            source="AI",
            session_id=tracker.session_id,
            occurred_at_s=now,
            reason=reason,
        )
