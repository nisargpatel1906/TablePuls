"""Strict Pydantic v2 schemas for Phase 2 Menu, Category, Item, and Settings APIs (API-026..API-031)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALLOWED_DIETARY_TAGS = {
    "VEG",
    "NON_VEG",
    "VEGAN",
    "GLUTEN_FREE",
    "DAIRY_FREE",
    "NUT_FREE",
    "SPICY_MILD",
    "SPICY_MEDIUM",
    "SPICY_HOT",
    "CHEF_SPECIAL",
}

ALLOWED_ALLERGENS = {
    "NUTS",
    "PEANUTS",
    "DAIRY",
    "GLUTEN",
    "SOY",
    "SHELLFISH",
    "FISH",
    "EGGS",
    "SESAME",
}

ALLOWED_CURRENCIES = {
    "INR",
    "USD",
    "EUR",
    "GBP",
    "AED",
    "SGD",
    "CAD",
    "AUD",
    "JPY",
}

_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScheduleWindow(StrictSchema):
    days: list[int] = Field(min_length=1, max_length=7)
    start: str = Field(pattern=_HHMM_RE)
    end: str = Field(pattern=_HHMM_RE)

    @field_validator("days")
    @classmethod
    def check_days(cls, v: list[int]) -> list[int]:
        deduped = sorted(set(v))
        if any(d < 1 or d > 7 for d in deduped):
            raise ValueError("days must contain ISO weekdays 1..7")
        return deduped


class MenuScheduleV1(StrictSchema):
    v: Literal[1] = 1
    windows: list[ScheduleWindow] = Field(default_factory=list, max_length=14)


class CreateMenuRequest(StrictSchema):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=300)
    translations_json: dict[str, dict[str, str]] | None = None
    status: Literal["DRAFT", "PUBLISHED", "ARCHIVED"] = "DRAFT"
    is_active: bool = True
    is_default: bool = False
    schedule_json: MenuScheduleV1 | None = None
    sort_order: int = Field(default=0, ge=0, le=100000)


class UpdateMenuRequest(StrictSchema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=300)
    translations_json: dict[str, dict[str, str]] | None = None
    status: Literal["DRAFT", "PUBLISHED", "ARCHIVED"] | None = None
    is_active: bool | None = None
    is_default: bool | None = None
    schedule_json: MenuScheduleV1 | None = None
    clear_schedule: bool = False
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class UpdateMenuSettingsRequest(StrictSchema):
    menu_public_enabled: bool | None = None
    show_unavailable_items_public: bool | None = None
    menu_tagline: str | None = Field(default=None, max_length=160)
    logo_storage_key: str | None = Field(default=None, max_length=512)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    currency_override_confirm: bool = False
    allow_host_menu_availability: bool | None = None
    qr_grace_days: int | None = Field(default=None, ge=0, le=30)

    @field_validator("currency_code")
    @classmethod
    def check_currency(cls, v: str | None) -> str | None:
        if v is None:
            return None
        code = v.strip().upper()
        if code not in ALLOWED_CURRENCIES:
            raise ValueError(f"Unsupported currency_code '{code}'")
        return code


class CreateCategoryRequest(StrictSchema):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=300)
    translations_json: dict[str, dict[str, str]] | None = None
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=100000)


class UpdateCategoryRequest(StrictSchema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=300)
    translations_json: dict[str, dict[str, str]] | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class ReorderIdsRequest(StrictSchema):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class MenuItemVariantInput(StrictSchema):
    name: str = Field(min_length=1, max_length=60)
    price_minor_units: int = Field(ge=0, le=100_000_000)
    is_available: bool = True


class CreateMenuItemRequest(StrictSchema):
    category_id: uuid.UUID
    sku: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    translations_json: dict[str, dict[str, str]] | None = None
    price_minor_units: int = Field(ge=0, le=100_000_000)
    compare_at_price_minor_units: int | None = Field(default=None, ge=0, le=100_000_000)
    image_asset_id: uuid.UUID | None = None
    image_alt: str | None = Field(default=None, max_length=160)
    is_available: bool = True
    is_featured: bool = False
    dietary_tags: list[str] = Field(default_factory=list, max_length=10)
    allergens: list[str] = Field(default_factory=list, max_length=10)
    variants_json: list[MenuItemVariantInput] = Field(default_factory=list, max_length=8)
    prep_time_minutes: int | None = Field(default=None, ge=1, le=240)
    calories_kcal: int | None = Field(default=None, ge=0, le=10000)
    sort_order: int = Field(default=0, ge=0, le=100000)

    @field_validator("dietary_tags")
    @classmethod
    def check_dietary(cls, v: list[str]) -> list[str]:
        deduped: list[str] = []
        for tag in v:
            t = tag.strip().upper()
            if t not in ALLOWED_DIETARY_TAGS:
                raise ValueError(f"Unsupported dietary tag '{tag}'")
            if t not in deduped:
                deduped.append(t)
        return deduped

    @field_validator("allergens")
    @classmethod
    def check_allergens(cls, v: list[str]) -> list[str]:
        deduped: list[str] = []
        for item in v:
            a = item.strip().upper()
            if a not in ALLOWED_ALLERGENS:
                raise ValueError(f"Unsupported allergen '{item}'")
            if a not in deduped:
                deduped.append(a)
        return deduped

    @field_validator("variants_json")
    @classmethod
    def check_variants(cls, v: list[MenuItemVariantInput]) -> list[MenuItemVariantInput]:
        names = [x.name.strip().lower() for x in v]
        if len(names) != len(set(names)):
            raise ValueError("Variant names must be unique")
        return v

    @model_validator(mode="after")
    def check_compare_price(self) -> CreateMenuItemRequest:
        if (
            self.compare_at_price_minor_units is not None
            and self.compare_at_price_minor_units <= self.price_minor_units
        ):
            raise ValueError("compare_at_price_minor_units must exceed price_minor_units")
        return self


class UpdateMenuItemRequest(StrictSchema):
    category_id: uuid.UUID | None = None
    sku: str | None = Field(default=None, max_length=64)
    clear_sku: bool = False
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    translations_json: dict[str, dict[str, str]] | None = None
    price_minor_units: int | None = Field(default=None, ge=0, le=100_000_000)
    compare_at_price_minor_units: int | None = Field(default=None, ge=0, le=100_000_000)
    clear_compare_at_price: bool = False
    image_asset_id: uuid.UUID | None = None
    clear_image: bool = False
    image_alt: str | None = Field(default=None, max_length=160)
    is_available: bool | None = None
    is_featured: bool | None = None
    dietary_tags: list[str] | None = Field(default=None, max_length=10)
    allergens: list[str] | None = Field(default=None, max_length=10)
    variants_json: list[MenuItemVariantInput] | None = Field(default=None, max_length=8)
    prep_time_minutes: int | None = Field(default=None, ge=1, le=240)
    calories_kcal: int | None = Field(default=None, ge=0, le=10000)
    sort_order: int | None = Field(default=None, ge=0, le=100000)
    version: int | None = Field(default=None, ge=1)

    @field_validator("dietary_tags")
    @classmethod
    def check_dietary(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        deduped: list[str] = []
        for tag in v:
            t = tag.strip().upper()
            if t not in ALLOWED_DIETARY_TAGS:
                raise ValueError(f"Unsupported dietary tag '{tag}'")
            if t not in deduped:
                deduped.append(t)
        return deduped

    @field_validator("allergens")
    @classmethod
    def check_allergens(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        deduped: list[str] = []
        for item in v:
            a = item.strip().upper()
            if a not in ALLOWED_ALLERGENS:
                raise ValueError(f"Unsupported allergen '{item}'")
            if a not in deduped:
                deduped.append(a)
        return deduped

    @field_validator("variants_json")
    @classmethod
    def check_variants(
        cls, v: list[MenuItemVariantInput] | None
    ) -> list[MenuItemVariantInput] | None:
        if v is None:
            return None
        names = [x.name.strip().lower() for x in v]
        if len(names) != len(set(names)):
            raise ValueError("Variant names must be unique")
        return v


class ItemAvailabilityRequest(StrictSchema):
    is_available: bool
    unavailable_until: datetime | None = None


class BulkItemAvailabilityRequest(StrictSchema):
    item_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    is_available: bool


class BulkItemActionRequest(StrictSchema):
    item_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    action: Literal["delete", "move"]
    target_category_id: uuid.UUID | None = None


class CsvImportCommitRequest(StrictSchema):
    strategy: Literal["all_or_nothing", "skip_invalid"] = "all_or_nothing"
