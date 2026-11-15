"""Tests for the ``otp_challenges`` model definition (metadata, not the database)."""

from __future__ import annotations

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint

from app.auth.models import OtpChallenge, OtpPurpose


@pytest.mark.unit
def test_table_and_columns() -> None:
    table = OtpChallenge.__table__
    assert table.name == "otp_challenges"
    assert set(table.columns.keys()) == {
        "id",
        "phone",
        "purpose",
        "user_id",
        "code_hmac",
        "attempts",
        "expires_at",
        "consumed_at",
        "request_ip",
        "created_at",
    }


@pytest.mark.unit
def test_primary_key_is_id() -> None:
    assert [column.name for column in OtpChallenge.__table__.primary_key.columns] == ["id"]


@pytest.mark.unit
def test_expected_check_constraints_exist() -> None:
    names = {
        constraint.name
        for constraint in OtpChallenge.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert names == {
        "ck_otp_challenges_phone_format",
        "ck_otp_challenges_purpose_valid",
        "ck_otp_challenges_attempts_range",
    }


@pytest.mark.unit
def test_user_id_foreign_key_cascades() -> None:
    foreign_keys = [
        constraint
        for constraint in OtpChallenge.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert [constraint.name for constraint in foreign_keys] == ["fk_otp_challenges_user_id_users"]
    assert foreign_keys[0].ondelete == "CASCADE"


@pytest.mark.unit
def test_indexes_support_throttling_and_cleanup() -> None:
    names = {index.name for index in OtpChallenge.__table__.indexes}
    assert names == {
        "ix_otp_challenges_phone_purpose_created_at",
        "ix_otp_challenges_expires_at",
    }


@pytest.mark.unit
def test_purpose_values_match_the_specification() -> None:
    assert {purpose.value for purpose in OtpPurpose} == {
        "verify_phone",
        "reset_password",
        "change_phone",
    }
