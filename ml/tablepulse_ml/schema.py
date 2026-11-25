"""Strict manifest & sample schema validator for TablePulse evaluation datasets."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

CANONICAL_STATES = frozenset(
    {"FREE", "OCCUPIED", "NEEDS_SERVICE", "NEEDS_CLEANING", "RESERVED", "UNKNOWN"}
)
LIGHTING_CONDITIONS = frozenset({"bright", "dim", "mixed"})


class TableLabel(BaseModel):
    table_id: str = Field(min_length=1, max_length=64)
    state: str
    guest_count: int = Field(ge=0, le=20)
    pred_state: str | None = None
    pred_guest_count: int | None = Field(default=None, ge=0, le=20)
    pred_probs: dict[str, float] | None = None
    latency_sec: float = Field(default=0.5, ge=0.0, le=60.0)
    turn_eta_actual_min: float | None = Field(default=None, ge=0.0, le=300.0)
    turn_eta_pred_min: float | None = Field(default=None, ge=0.0, le=300.0)

    @field_validator("state", "pred_state")
    @classmethod
    def check_state(cls, v: str | None) -> str | None:
        if v is not None and v not in CANONICAL_STATES:
            raise ValueError(f"Invalid canonical table state: {v}")
        return v


class EvalClip(BaseModel):
    clip_id: str = Field(min_length=1, max_length=128)
    venue_id: str = Field(min_length=1, max_length=64)
    camera_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=64)
    timestamp_epoch: int = Field(ge=0)
    lighting: str = "bright"
    frame_hash: str = Field(min_length=8, max_length=128)
    labels: list[TableLabel] = Field(min_length=1)

    @field_validator("lighting")
    @classmethod
    def check_lighting(cls, v: str) -> str:
        if v not in LIGHTING_CONDITIONS:
            raise ValueError(f"Invalid lighting '{v}'; expected {sorted(LIGHTING_CONDITIONS)}")
        return v


class DatasetManifest(BaseModel):
    dataset_version: str = Field(min_length=1, max_length=64)
    dataset_flag: Literal["PRODUCTION_LABELED", "FIXTURE-NOT-FOR-REPORTING"] = (
        "FIXTURE-NOT-FOR-REPORTING"
    )
    clips: list[EvalClip] = Field(min_length=1)

    def validate_unique_clips(self) -> None:
        seen: set[str] = set()
        for c in self.clips:
            if c.clip_id in seen:
                raise ValueError(f"Duplicate clip_id in manifest: {c.clip_id}")
            seen.add(c.clip_id)
