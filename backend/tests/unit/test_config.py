"""Unit tests for ``app.core.config``.

These tests pin down the "fail fast" contract: a misconfigured process must
refuse to start, and no secret may be accepted unless it looks real and strong.

Every case builds ``Settings`` with ``_env_file=None`` so the developer's local
``.env`` never leaks into the assertions. Explicit keyword arguments always win
over environment variables in pydantic-settings.
"""

from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from app.core.config import (
    ENCRYPTION_KEY_BYTES,
    MIN_SECRET_KEY_LENGTH,
    Environment,
    Settings,
    get_settings,
)

VALID_SECRET_KEY = "s" * MIN_SECRET_KEY_LENGTH
VALID_ENCRYPTION_KEY = base64.urlsafe_b64encode(b"0" * ENCRYPTION_KEY_BYTES).decode()
VALID_DATABASE_URL = "postgresql+psycopg://ikimina:pw@localhost:5432/ikimina"
VALID_REDIS_URL = "redis://:pw@localhost:6379/0"


def make_settings(**overrides: object) -> Settings:
    """Build Settings from a known-good baseline, applying ``overrides``."""
    base: dict[str, object] = {
        "secret_key": VALID_SECRET_KEY,
        "encryption_key": VALID_ENCRYPTION_KEY,
        "database_url": VALID_DATABASE_URL,
        "redis_url": VALID_REDIS_URL,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def test_valid_settings_load_with_expected_defaults() -> None:
    settings = make_settings()

    assert settings.environment is Environment.local
    assert settings.min_contribution_rwf == 100
    assert settings.max_transaction_rwf == 100_000_000
    assert settings.timezone == "Africa/Kigali"


def test_secrets_are_wrapped_and_do_not_leak_in_repr() -> None:
    settings = make_settings()

    assert settings.secret_key.get_secret_value() == VALID_SECRET_KEY
    assert VALID_SECRET_KEY not in repr(settings)


def test_missing_secret_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            encryption_key=VALID_ENCRYPTION_KEY,
            database_url=VALID_DATABASE_URL,
            redis_url=VALID_REDIS_URL,
        )


def test_short_secret_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY must be at least"):
        make_settings(secret_key="too-short")


def test_placeholder_secret_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        make_settings(secret_key="change-me-generate-a-real-secret-value")


def test_placeholder_encryption_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        make_settings(encryption_key="change-me-generate-a-key")


def test_encryption_key_with_wrong_length_is_rejected() -> None:
    short_key = base64.urlsafe_b64encode(b"0" * 16).decode()

    with pytest.raises(ValidationError, match="exactly"):
        make_settings(encryption_key=short_key)


def test_encryption_key_that_is_not_base64_is_rejected() -> None:
    with pytest.raises(ValidationError, match="base64"):
        make_settings(encryption_key="not base64 at all !!!")


@pytest.mark.parametrize(
    "bad_url",
    [
        "postgresql://ikimina:pw@localhost:5432/ikimina",  # asyncpg/psycopg2 default
        "postgresql+asyncpg://ikimina:pw@localhost:5432/ikimina",
        "sqlite:///./test.db",
    ],
)
def test_database_url_must_use_psycopg3(bad_url: str) -> None:
    with pytest.raises(ValidationError, match="psycopg 3"):
        make_settings(database_url=bad_url)


def test_redis_url_must_use_redis_scheme() -> None:
    with pytest.raises(ValidationError, match="redis"):
        make_settings(redis_url="http://localhost:6379")


def test_unknown_timezone_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown timezone"):
        make_settings(timezone="Mars/Kigali")


def test_cors_wildcard_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not contain"):
        make_settings(cors_origins="*")


def test_contribution_limit_must_be_below_transaction_limit() -> None:
    with pytest.raises(ValidationError, match="MIN_CONTRIBUTION_RWF"):
        make_settings(min_contribution_rwf=1000, max_transaction_rwf=1000)


def test_csv_string_is_split_into_list() -> None:
    settings = make_settings(
        cors_origins="http://localhost:3000, http://localhost:5173",
        trusted_hosts="localhost,127.0.0.1,testserver",
    )

    assert settings.cors_origins == ["http://localhost:3000", "http://localhost:5173"]
    assert settings.trusted_hosts == ["localhost", "127.0.0.1", "testserver"]


def test_docs_follow_environment_by_default() -> None:
    assert make_settings(environment="local").expose_docs is True
    assert make_settings(environment="development").expose_docs is True
    assert make_settings(environment="production").expose_docs is False


def test_docs_can_be_forced_off_but_never_silently_on_in_production() -> None:
    assert make_settings(environment="local", docs_enabled=False).expose_docs is False
    assert make_settings(environment="production", docs_enabled=True).expose_docs is True


def test_is_production_property() -> None:
    assert make_settings(environment="production").is_production is True
    assert make_settings(environment="local").is_production is False


def test_effective_test_database_url_is_derived_from_database_url() -> None:
    settings = make_settings(postgres_test_db="ikimina_test")

    assert settings.effective_test_database_url.endswith("/ikimina_test")


def test_effective_test_database_url_prefers_explicit_value() -> None:
    explicit = "postgresql+psycopg://ikimina:pw@localhost:5432/custom_test"
    settings = make_settings(test_database_url=explicit)

    assert settings.effective_test_database_url == explicit


def test_effective_test_database_url_preserves_query_string() -> None:
    settings = make_settings(
        database_url="postgresql+psycopg://ikimina:pw@localhost:5432/ikimina?sslmode=require",
    )

    assert settings.effective_test_database_url.endswith("/ikimina_test?sslmode=require")


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", VALID_SECRET_KEY)
    monkeypatch.setenv("ENCRYPTION_KEY", VALID_ENCRYPTION_KEY)
    monkeypatch.setenv("DATABASE_URL", VALID_DATABASE_URL)
    monkeypatch.setenv("REDIS_URL", VALID_REDIS_URL)
    get_settings.cache_clear()

    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()
