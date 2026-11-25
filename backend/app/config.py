"""Application configuration loaded strictly from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    tablepulse_env: str = Field(default="development", validation_alias="TABLEPULSE_ENV")
    public_app_url: str = Field(default="http://localhost:3000", validation_alias="PUBLIC_APP_URL")
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        validation_alias="ALLOWED_ORIGINS",
    )
    demo_mode: bool = Field(default=False, validation_alias="DEMO_MODE")

    database_url: str = Field(
        default="postgresql+asyncpg://tablepulse:change_me_postgres_password@localhost:5432/tablepulse",
        validation_alias="DATABASE_URL",
    )
    valkey_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="VALKEY_URL",
    )

    secret_key: str = Field(
        default="dev_only_replace_with_64_hex_chars_for_jwt_signing_key_00000000",
        validation_alias="TABLEPULSE_SECRET_KEY",
    )
    data_key: str = Field(
        default="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        validation_alias="TABLEPULSE_DATA_KEY",
    )
    mediamtx_hook_secret: str = Field(
        default="dev_only_replace_with_mediamtx_internal_secret",
        validation_alias="MEDIAMTX_HOOK_SECRET",
    )

    mediamtx_internal_url: str = Field(
        default="rtsp://mediamtx:8554",
        validation_alias="MEDIAMTX_INTERNAL_URL",
    )
    mediamtx_webrtc_public_url: str = Field(
        default="http://localhost:8889",
        validation_alias="MEDIAMTX_WEBRTC_PUBLIC_URL",
    )

    snapshot_storage_dir: str = Field(
        default="/app/data/snapshots",
        validation_alias="SNAPSHOT_STORAGE_DIR",
    )
    ml_model_dir: str = Field(
        default="/app/data/models",
        validation_alias="ML_MODEL_DIR",
    )
    demo_video_path: str = Field(
        default="/app/data/demo/demo_floor.mp4",
        validation_alias="DEMO_VIDEO_PATH",
    )
    allow_private_webhook_hosts: bool = Field(
        default=False,
        validation_alias="ALLOW_PRIVATE_WEBHOOK_HOSTS",
    )

    # Fail-closed kill switches (missing => False)
    ai_inference_enabled: bool = Field(
        default_factory=lambda: _parse_bool_env("AI_INFERENCE_ENABLED", False),
        validation_alias="AI_INFERENCE_ENABLED",
    )
    webhooks_enabled: bool = Field(
        default_factory=lambda: _parse_bool_env("WEBHOOKS_ENABLED", False),
        validation_alias="WEBHOOKS_ENABLED",
    )
    review_crops_enabled: bool = Field(
        default_factory=lambda: _parse_bool_env("REVIEW_CROPS_ENABLED", False),
        validation_alias="REVIEW_CROPS_ENABLED",
    )

    smtp_host: str = Field(default="", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_user: str = Field(default="", validation_alias="SMTP_USER")
    smtp_pass: str = Field(default="", validation_alias="SMTP_PASS")
    smtp_from: str = Field(default="noreply@tablepulse.local", validation_alias="SMTP_FROM")

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @field_validator("secret_key")
    @classmethod
    def check_prod_secret(cls, v: str, info: object) -> str:
        # Enforced cleanly at startup in main.py when TABLEPULSE_ENV == "production"
        return v

    def assert_production_safe(self) -> None:
        if self.tablepulse_env.lower() == "production" or self.app_env.lower() == "production":
            placeholders = ("change_me", "replace_with", "dev_only")
            for name, val in (
                ("TABLEPULSE_SECRET_KEY", self.secret_key),
                ("TABLEPULSE_DATA_KEY", self.data_key),
                ("MEDIAMTX_HOOK_SECRET", self.mediamtx_hook_secret),
                ("DATABASE_URL", self.database_url),
            ):
                if any(p in val.lower() for p in placeholders) or len(val) < 16:
                    raise RuntimeError(f"Insecure placeholder secret for {name} in production")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
