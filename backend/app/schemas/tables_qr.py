"""Strict Pydantic v2 schemas for Phase 2 Advanced Table Management & QR Operations (API-024..API-025, API-032..API-034)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


ShapeLiteral = Literal["RECT", "CIRCLE", "BOOTH"]


class CreateTableRequest(StrictSchema):
    table_code: str = Field(min_length=1, max_length=20)
    display_name: str | None = Field(default=None, max_length=80)
    section_name: str = Field(default="Main", min_length=1, max_length=60)
    min_capacity: int = Field(default=1, ge=1, le=20)
    seat_capacity: int = Field(default=4, ge=1, le=20)
    shape: ShapeLiteral = "RECT"
    is_combinable: bool = False
    is_active: bool = True
    table_notes: str | None = Field(default=None, max_length=255)
    floor_x: float = Field(default=0.0, ge=0.0, le=1.0)
    floor_y: float = Field(default=0.0, ge=0.0, le=1.0)
    camera_id: uuid.UUID | None = None
    sort_order: int = Field(default=0, ge=0, le=100000)

    @model_validator(mode="after")
    def check_capacities(self) -> CreateTableRequest:
        if self.min_capacity > self.seat_capacity:
            raise ValueError("min_capacity cannot exceed seat_capacity")
        return self


class UpdateTableRequest(StrictSchema):
    table_code: str | None = Field(default=None, min_length=1, max_length=20)
    display_name: str | None = Field(default=None, max_length=80)
    section_name: str | None = Field(default=None, min_length=1, max_length=60)
    min_capacity: int | None = Field(default=None, ge=1, le=20)
    seat_capacity: int | None = Field(default=None, ge=1, le=20)
    shape: ShapeLiteral | None = None
    is_combinable: bool | None = None
    is_active: bool | None = None
    table_notes: str | None = Field(default=None, max_length=255)
    floor_x: float | None = Field(default=None, ge=0.0, le=1.0)
    floor_y: float | None = Field(default=None, ge=0.0, le=1.0)
    camera_id: uuid.UUID | None = None
    unlink_camera: bool = False
    sort_order: int | None = Field(default=None, ge=0, le=100000)
    version: int | None = Field(default=None, ge=1)


class BulkCreateTablesRequest(StrictSchema):
    prefix: str = Field(min_length=1, max_length=10)
    start_number: int = Field(default=1, ge=1, le=9999)
    count: int = Field(ge=1, le=50)
    zero_pad: int = Field(default=2, ge=1, le=4)
    section_name: str = Field(default="Main", min_length=1, max_length=60)
    min_capacity: int = Field(default=1, ge=1, le=20)
    seat_capacity: int = Field(default=4, ge=1, le=20)
    shape: ShapeLiteral = "RECT"
    is_combinable: bool = False

    @model_validator(mode="after")
    def check_capacities(self) -> BulkCreateTablesRequest:
        if self.min_capacity > self.seat_capacity:
            raise ValueError("min_capacity cannot exceed seat_capacity")
        return self


class BulkUpdateTablesRequest(StrictSchema):
    table_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    section_name: str | None = Field(default=None, min_length=1, max_length=60)
    is_active: bool | None = None


class RestoreTableRequest(StrictSchema):
    new_table_code: str | None = Field(default=None, min_length=1, max_length=20)


class RegenerateQRRequest(StrictSchema):
    reason: Literal["DAMAGED", "COMPROMISED", "REBRAND", "OTHER"] = "OTHER"
    grace_days: int | None = Field(default=None, ge=0, le=30)


class ExportQRPdfRequest(StrictSchema):
    table_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    layout: Literal["A4_4UP", "A4_6UP", "A6_1UP", "A4_STICKER_12UP", "LETTER_4UP"] = "A4_4UP"


class ExportQRZipRequest(StrictSchema):
    table_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    format: Literal["svg", "png", "both"] = "png"
    framed: bool = True
