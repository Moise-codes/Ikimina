"""Tests for the ``users`` model definition (metadata, not the live database)."""

from __future__ import annotations

import pytest
from sqlalchemy import UniqueConstraint

from app.users.models import User, UserLocale, UserStatus


@pytest.mark.unit
def test_table_and_columns() -> None:
    table = User.__table__
    assert table.name == "users"
    assert set(table.columns.keys()) == {
        "id",
        "full_name",
        "phone",
        "phone_verified_at",
        "email",
        "email_verified_at",
        "password_hash",
        "preferred_language",
        "status",
        "is_platform_admin",
        "privacy_notice_version",
        "privacy_accepted_at",
        "failed_login_count",
        "locked_until",
        "last_login_at",
        "anonymized_at",
        "created_at",
        "updated_at",
    }


@pytest.mark.unit
def test_primary_key_is_id() -> None:
    assert [column.name for column in User.__table__.primary_key.columns] == ["id"]


@pytest.mark.unit
def test_expected_check_constraints_exist() -> None:
    names = {
        constraint.name
        for constraint in User.__table__.constraints
        if type(constraint).__name__ == "CheckConstraint"
    }
    assert names == {
        "ck_users_full_name_length",
        "ck_users_phone_format",
        "ck_users_phone_required_unless_anonymized",
        "ck_users_status_valid",
        "ck_users_preferred_language_valid",
        "ck_users_failed_login_count_non_negative",
    }


@pytest.mark.unit
def test_unique_constraints_on_phone_and_email() -> None:
    unique_names = {
        constraint.name
        for constraint in User.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_names == {"uq_users_phone", "uq_users_email"}


@pytest.mark.unit
def test_email_uses_citext_for_case_insensitive_uniqueness() -> None:
    assert User.__table__.c.email.type.__class__.__name__ == "CITEXT"


@pytest.mark.unit
def test_enum_values_match_the_specification() -> None:
    assert {status.value for status in UserStatus} == {
        "active",
        "locked",
        "deactivated",
        "anonymized",
    }
    assert {locale.value for locale in UserLocale} == {"rw", "en", "fr"}
