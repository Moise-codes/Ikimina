"""Typed application settings loaded from environment variables.

Why this file exists
--------------------
Configuration is the one place where "fail fast" matters most. If a secret is
missing, too short, or a database URL points at the wrong driver, we want the
process to refuse to start rather than behave unpredictably at runtime.

All values come from environment variables (12-factor style). In local
development we also read a `.env` file for convenience; that file is never
committed. Every secret is held in a pydantic ``SecretStr`` so it cannot leak
into logs by accident.
"""

from __future__ import annotations

import base64
import binascii
from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MIN_SECRET_KEY_LENGTH = 32
ENCRYPTION_KEY_BYTES = 32
_PLACEHOLDER_PREFIXES = ("change-me", "changeme", "replace-me", "placeholder")


class Environment(StrEnum):
    """Deployment environment. Controls safe defaults such as exposing docs."""

    local = "local"
    development = "development"
    staging = "staging"
    production = "production"


class Settings(BaseSettings):
    """All runtime configuration, validated once at startup."""

    model_config = SettingsConfigDict(
        # Look for a .env in the current directory and one level up (so the app
        # works whether it is started from the repo root or from backend/).
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore unrelated variables such as POSTGRES_USER
    )

    # --- Application ---------------------------------------------------------
    project_name: str = "Ikimina API"
    version: str = "0.1.0"
    environment: Environment = Environment.local
    api_v1_prefix: str = "/api/v1"

    # --- Database ------------------------------------------------------------
    database_url: str
    test_database_url: str | None = None
    postgres_test_db: str = "ikimina_test"
    db_pool_size: int = Field(default=5, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_recycle_seconds: int = Field(default=1800, ge=-1)

    # --- Redis ---------------------------------------------------------------
    redis_url: str

    # --- Secrets -------------------------------------------------------------
    secret_key: SecretStr
    encryption_key: SecretStr

    # --- Token lifetimes -----------------------------------------------------
    access_token_expire_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=30, ge=1, le=365)

    # --- OTP -----------------------------------------------------------------
    otp_expire_minutes: int = Field(default=5, ge=1, le=60)
    otp_max_attempts: int = Field(default=5, ge=1, le=10)
    otp_resend_cooldown_seconds: int = Field(default=60, ge=0, le=3600)

    # --- Login lockout -------------------------------------------------------
    lockout_max_failed_attempts: int = Field(default=5, ge=1, le=100)
    lockout_minutes: int = Field(default=15, ge=1)

    # --- Rate limits ---------------------------------------------------------
    rate_limit_login_per_minute: int = Field(default=5, ge=1)
    rate_limit_register_per_hour: int = Field(default=5, ge=1)
    rate_limit_otp_send_per_hour: int = Field(default=5, ge=1)
    rate_limit_otp_verify_per_minute: int = Field(default=10, ge=1)
    rate_limit_password_reset_per_hour: int = Field(default=5, ge=1)

    # --- HTTP security -------------------------------------------------------
    # Comma-separated lists in the environment; NoDecode stops pydantic-settings
    # from trying to parse them as JSON.
    cors_origins: Annotated[list[str], NoDecode] = []
    trusted_hosts: Annotated[list[str], NoDecode] = []
    # None means "decide from the environment" (see expose_docs).
    docs_enabled: bool | None = None

    # --- Money limits (whole RWF) -------------------------------------------
    min_contribution_rwf: int = Field(default=100, ge=1)
    max_transaction_rwf: int = Field(default=100_000_000, ge=1)

    # --- Localisation --------------------------------------------------------
    timezone: str = "Africa/Kigali"

    # -- Validators -----------------------------------------------------------
    @field_validator("cors_origins", "trusted_hosts", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        """Accept both a real list and a comma-separated string."""
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters long")
        if raw.lower().startswith(_PLACEHOLDER_PREFIXES):
            raise ValueError("SECRET_KEY still contains a placeholder; generate a real secret")
        return value

    @field_validator("encryption_key")
    @classmethod
    def _validate_encryption_key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if raw.lower().startswith(_PLACEHOLDER_PREFIXES):
            raise ValueError("ENCRYPTION_KEY still contains a placeholder; generate a real key")
        # Tolerate missing base64 padding before validating the length.
        padded = raw + "=" * (-len(raw) % 4)
        try:
            decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        except (binascii.Error, ValueError) as exc:
            raise ValueError("ENCRYPTION_KEY must be valid url-safe base64") from exc
        if len(decoded) != ENCRYPTION_KEY_BYTES:
            raise ValueError(f"ENCRYPTION_KEY must decode to exactly {ENCRYPTION_KEY_BYTES} bytes")
        return value

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _validate_database_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError(
                "database URL must use the psycopg 3 driver, e.g. "
                "postgresql+psycopg://user:password@host:5432/dbname"
            )
        return value

    @field_validator("redis_url")
    @classmethod
    def _validate_redis_url(cls, value: str) -> str:
        if not value.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must start with redis:// or rediss://")
        return value

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone: {value!r}") from exc
        return value

    @model_validator(mode="after")
    def _validate_cross_field(self) -> Settings:
        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS must not contain '*'; list explicit origins instead")
        if self.min_contribution_rwf >= self.max_transaction_rwf:
            raise ValueError("MIN_CONTRIBUTION_RWF must be smaller than MAX_TRANSACTION_RWF")
        return self

    # -- Derived values -------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.environment is Environment.production

    @property
    def expose_docs(self) -> bool:
        """Whether /docs, /redoc and /openapi.json should be served."""
        if self.docs_enabled is not None:
            return self.docs_enabled
        return self.environment in (Environment.local, Environment.development)

    @property
    def effective_test_database_url(self) -> str:
        """The test database URL: explicit value, or DATABASE_URL with the test DB name."""
        if self.test_database_url:
            return self.test_database_url
        url, _, query = self.database_url.partition("?")
        base, _, _ = url.rpartition("/")
        derived = f"{base}/{self.postgres_test_db}"
        return f"{derived}?{query}" if query else derived


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, constructed once and cached.

    ``lru_cache`` means the environment is read a single time per process, so
    startup is the only moment configuration validation happens.
    """
    return Settings()
