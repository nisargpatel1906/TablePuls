"""CV Worker configuration (fail-closed kill switches)."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class CVSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    database_url: str = Field(
        default="postgresql+asyncpg://tablepulse:change_me_postgres_password@localhost:5432/tablepulse",
        validation_alias="DATABASE_URL",
    )
    valkey_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="VALKEY_URL",
    )
    ml_device: str = Field(default="cpu", validation_alias="ML_DEVICE")
    ml_model_dir: str = Field(default="/app/data/models", validation_alias="ML_MODEL_DIR")
    snapshot_storage_dir: str = Field(
        default="/app/data/snapshots", validation_alias="SNAPSHOT_STORAGE_DIR"
    )
    demo_video_path: str = Field(
        default="/app/data/demo/demo_floor.mp4", validation_alias="DEMO_VIDEO_PATH"
    )
    api_internal_url: str = Field(
        default="http://api:8000", validation_alias="API_INTERNAL_URL"
    )
    mediamtx_hook_secret: str = Field(
        default="dev_only_replace_with_mediamtx_internal_secret",
        validation_alias="MEDIAMTX_HOOK_SECRET",
    )
    demo_mode: bool = Field(default=False, validation_alias="DEMO_MODE")
    target_fps: int = Field(default=2, ge=1, le=5, validation_alias="TARGET_FPS")
    model_version: str = Field(
        default="tablepulse-detector-b1-0.1.0", validation_alias="MODEL_VERSION"
    )

    # Fail-closed kill switches: missing => False
    ai_inference_enabled: bool = Field(
        default_factory=lambda: _parse_bool_env("AI_INFERENCE_ENABLED", False),
        validation_alias="AI_INFERENCE_ENABLED",
    )
    review_crops_enabled: bool = Field(
        default_factory=lambda: _parse_bool_env("REVIEW_CROPS_ENABLED", False),
        validation_alias="REVIEW_CROPS_ENABLED",
    )


@lru_cache(maxsize=1)
def get_cv_settings() -> CVSettings:
    return CVSettings()
