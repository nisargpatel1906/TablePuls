"""Strict output allowlist schema for Public Customer Digital Menu API (API-035)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PublicStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicMenuVariant(PublicStrictModel):
    name: str
    price_minor_units: int
    is_available: bool


class PublicMenuItem(PublicStrictModel):
    id: str
    name: str
    description: str | None
    price_minor_units: int
    compare_at_price_minor_units: int | None
    image_url: str | None
    thumb_url: str | None
    image_alt: str | None
    is_available: bool
    is_featured: bool
    dietary_tags: list[str]
    allergens: list[str]
    variants_json: list[PublicMenuVariant]
    prep_time_minutes: int | None
    calories_kcal: int | None


class PublicMenuCategory(PublicStrictModel):
    id: str
    name: str
    description: str | None
    items: list[PublicMenuItem]


class PublicMenuSection(PublicStrictModel):
    id: str
    name: str
    description: str | None
    categories: list[PublicMenuCategory]


class PublicVenueSummary(PublicStrictModel):
    name: str
    tagline: str | None
    logo_url: str | None
    currency_code: str
    timezone: str


class PublicTableSummary(PublicStrictModel):
    label: str


class PublicMenuResponse(PublicStrictModel):
    venue: PublicVenueSummary
    table: PublicTableSummary
    menu_public_enabled: bool
    show_unavailable_items: bool
    preview_mode: bool
    menu_revision: int
    menus: list[PublicMenuSection]
