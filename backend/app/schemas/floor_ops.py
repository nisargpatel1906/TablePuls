"""Strict Pydantic v2 schemas for Floor Ops, Alerts, Waitlist, Alert Rules, ML Review, and System."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


TableStateLiteral = Literal[
    "FREE",
    "OCCUPIED",
    "NEEDS_SERVICE",
    "NEEDS_CLEANING",
    "RESERVED",
    "UNKNOWN",
]


class TableOverrideRequest(StrictSchema):
    new_state: TableStateLiteral
    guest_count: int | None = Field(default=None, ge=0, le=20)
    reason: str = Field(min_length=2, max_length=255)
    version: int = Field(ge=1)
    mark_service_attended: bool = False


class FlagDetectionRequest(StrictSchema):
    reason: str = Field(min_length=2, max_length=255)
    suggested_state: TableStateLiteral | None = None


class UpdateAlertRequest(StrictSchema):
    status: Literal["ACKNOWLEDGED", "RESOLVED"]


class CreateWaitlistRequest(StrictSchema):
    party_name: str = Field(min_length=1, max_length=80)
    party_size: int = Field(ge=1, le=20)
    phone: str | None = Field(default=None, max_length=32)
    quoted_wait_minutes: int | None = Field(default=None, ge=0, le=300)
    notes: str | None = Field(default=None, max_length=255)


class UpdateWaitlistRequest(StrictSchema):
    status: Literal["WAITING", "SEATED", "CANCELLED", "NO_SHOW"] | None = None
    assigned_table_id: uuid.UUID | None = None
    party_size: int | None = Field(default=None, ge=1, le=20)
    quoted_wait_minutes: int | None = Field(default=None, ge=0, le=300)
    notes: str | None = Field(default=None, max_length=255)


class UpdateAlertRuleRequest(StrictSchema):
    section_name: str | None = Field(default=None, max_length=60)
    unattended_service_sec: int | None = Field(default=None, ge=60, le=1800)
    cleaning_alert_delay_sec: int | None = Field(default=None, ge=0, le=900)
    occupancy_debounce_sec: int | None = Field(default=None, ge=3, le=60)
    departure_debounce_sec: int | None = Field(default=None, ge=5, le=120)
    min_confidence: float | None = Field(default=None, ge=0.30, le=0.95)
    require_bussing_confirmation: bool | None = None
    webhook_url: str | None = Field(default=None, max_length=512)
    webhook_secret: str | None = Field(default=None, max_length=256)
    quiet_hours_enabled: bool | None = None


class TestWebhookRequest(StrictSchema):
    webhook_url: str | None = Field(default=None, max_length=512)
    webhook_secret: str | None = Field(default=None, max_length=256)


class UpdateMLReviewRequest(StrictSchema):
    review_status: Literal["REVIEWED", "EXCLUDED"] = "REVIEWED"
    human_state: str = Field(min_length=2, max_length=32)
    human_guest_count: int | None = Field(default=None, ge=0, le=20)
    issue_tags: list[str] = Field(default_factory=list, max_length=10)


class UpdateSystemSettingsRequest(StrictSchema):
    ai_inference_enabled: bool | None = None
    face_blur_enforced: bool | None = None
    snapshot_retention_days: int | None = Field(default=None, ge=0, le=30)
    analytics_retention_days: int | None = Field(default=None, ge=30, le=1095)
