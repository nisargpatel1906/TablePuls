"""Strict Pydantic v2 schemas for Auth, Invites, Users, and Audit Logs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

RoleLiteral = Literal["OWNER", "MANAGER", "HOST", "STAFF", "VIEWER"]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BootstrapRequest(StrictSchema):
    organization_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(StrictSchema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    totp_code: str | None = Field(default=None, min_length=6, max_length=8)


class ForgotPasswordRequest(StrictSchema):
    email: EmailStr


class ResetPasswordRequest(StrictSchema):
    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)


class AcceptInviteRequest(StrictSchema):
    token: str = Field(min_length=16, max_length=256)
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=128)


class InviteUserRequest(StrictSchema):
    email: EmailStr
    role: RoleLiteral
    venue_ids: list[uuid.UUID] = Field(default_factory=list)


class UpdateUserRequest(StrictSchema):
    role: RoleLiteral | None = None
    assigned_venue_ids: list[uuid.UUID] | None = None
    is_active: bool | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


class UserSummary(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    full_name: str
    role: RoleLiteral
    assigned_venue_ids: list[uuid.UUID]
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
