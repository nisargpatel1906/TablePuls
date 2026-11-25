"""Strict Pydantic v2 schemas for Venues, Cameras, and Table Polygons (API-007..API-010)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateVenueRequest(StrictSchema):
    name: str = Field(min_length=2, max_length=120)
    timezone: str = Field(default="UTC", min_length=2, max_length=64)
    operating_hours_json: dict[str, Any] = Field(default_factory=dict)
    allow_host_camera_view: bool = False
    guests_per_server_ratio: int = Field(default=16, ge=4, le=50)


class UpdateVenueRequest(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    timezone: str | None = Field(default=None, min_length=2, max_length=64)
    operating_hours_json: dict[str, Any] | None = None
    allow_host_camera_view: bool | None = None
    guests_per_server_ratio: int | None = Field(default=None, ge=4, le=50)


class CreateCameraRequest(StrictSchema):
    name: str = Field(min_length=2, max_length=100)
    stream_type: Literal["RTSP", "RTSPS", "DEMO_MP4"]
    stream_url: str = Field(min_length=4, max_length=512)
    username: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, max_length=128)
    target_fps: int = Field(default=2, ge=1, le=5)
    face_blur_enabled: bool = True


class UpdateCameraRequest(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    stream_type: Literal["RTSP", "RTSPS", "DEMO_MP4"] | None = None
    stream_url: str | None = Field(default=None, min_length=4, max_length=512)
    username: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, max_length=128)
    target_fps: int | None = Field(default=None, ge=1, le=5)
    face_blur_enabled: bool | None = None
    status: Literal["ONLINE", "RECONNECTING", "OFFLINE", "DISABLED"] | None = None


class Point2D(StrictSchema):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class TablePolygonInput(StrictSchema):
    id: uuid.UUID | None = None
    table_code: str = Field(min_length=1, max_length=20)
    section_name: str = Field(default="Main", min_length=1, max_length=60)
    seat_capacity: int = Field(ge=1, le=20)
    polygon_json: list[Point2D] = Field(min_length=3, max_length=64)
    floor_x: float = Field(default=0.5, ge=0.0, le=1.0)
    floor_y: float = Field(default=0.5, ge=0.0, le=1.0)
    shape: Literal["RECT", "CIRCLE", "BOOTH"] = "RECT"
    version: int | None = Field(default=None, ge=1)


class BulkPolygonsRequest(StrictSchema):
    tables: list[TablePolygonInput]
    exclusion_polygons_json: list[list[Point2D]] = Field(default_factory=list)


class MediaAuthHookRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = "read"
    path: str = ""
    query: str = ""
    token: str = ""
