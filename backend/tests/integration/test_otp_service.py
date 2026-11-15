"""OTP service tests (require a running PostgreSQL).

These exercise the real schema: the HMAC-only storage, the single-use rule, the
attempt counter, expiry, the resend cooldown and the constant-time comparison.
Time is injected so the tests never sleep.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import otp as otp_module
from app.auth.models import OtpChallenge, OtpPurpose
from app.auth.otp import OtpService
from app.core.errors import AppError

pytestmark = pytest.mark.integration

PHONE = "+250788123456"
OTHER_PHONE = "+250788999999"


@pytest.fixture
def service(db_session: Session, make_settings: Callable[..., Any]) -> OtpService:
    return OtpService(db_session, make_settings())


def _stored(session: Session, phone: str, purpose: OtpPurpose) -> OtpChallenge:
    statement = select(OtpChallenge).where(
        OtpChallenge.phone == phone, OtpChallenge.purpose == purpose.value
    )
    return session.execute(statement).scalar_one()


def test_issue_returns_a_six_digit_code_and_stores_only_its_hmac(
    service: OtpService, db_session: Session
) -> None:
    code = service.issue(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE)

    assert code.isdigit()
    assert len(code) == 6

    challenge = _stored(db_session, PHONE, OtpPurpose.VERIFY_PHONE)
    assert challenge.code_hmac != code
    assert len(challenge.code_hmac) == 64  # sha256 hex digest
    assert challenge.attempts == 0
    assert challenge.consumed_at is None
    assert challenge.expires_at > challenge.created_at


def test_verify_accepts_the_issued_code_and_consumes_it(service: OtpService) -> None:
    code = service.issue(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE)

    challenge = service.verify(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE, code=code)

    assert challenge.consumed_at is not None


def test_verify_rejects_a_wrong_code_and_counts_the_attempt(
    service: OtpService, db_session: Session
) -> None:
    service.issue(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE)

    with pytest.raises(AppError) as excinfo:
        service.verify(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE, code="000000")

    assert excinfo.value.code == "otp_invalid"
    assert _stored(db_session, PHONE, OtpPurpose.VERIFY_PHONE).attempts == 1


def test_verify_is_single_use(service: OtpService) -> None:
    code = service.issue(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE)
    service.verify(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE, code=code)

    with pytest.raises(AppError) as excinfo:
        service.verify(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE, code=code)

    assert excinfo.value.code == "otp_used"


def test_verify_rejects_an_expired_code(
    service: OtpService, make_settings: Callable[..., Any]
) -> None:
    settings = make_settings()
    start = datetime.now(UTC)
    code = service.issue(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE, now=start)

    later = start + timedelta(minutes=settings.otp_expire_minutes, seconds=1)
    with pytest.raises(AppError) as excinfo:
        service.verify(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE, code=code, now=later)

    assert excinfo.value.code == "otp_expired"


def test_verify_locks_after_the_attempt_limit(
    service: OtpService, make_settings: Callable[..., Any]
) -> None:
    settings = make_settings()
    code = service.issue(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE)

    for _ in range(settings.otp_max_attempts):
        with pytest.raises(AppError) as excinfo:
            service.verify(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE, code="000000")
        assert excinfo.value.code == "otp_invalid"

    # Even the correct code no longer works once the guesses are spent.
    with pytest.raises(AppError) as excinfo:
        service.verify(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE, code=code)
    assert excinfo.value.code == "otp_attempts_exceeded"


def test_verify_without_a_challenge_is_invalid(service: OtpService) -> None:
    with pytest.raises(AppError) as excinfo:
        service.verify(phone=OTHER_PHONE, purpose=OtpPurpose.VERIFY_PHONE, code="123456")

    assert excinfo.value.code == "otp_invalid"


def test_a_code_cannot_be_replayed_across_purposes(service: OtpService) -> None:
    code = service.issue(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE)

    with pytest.raises(AppError) as excinfo:
        service.verify(phone=PHONE, purpose=OtpPurpose.RESET_PASSWORD, code=code)

    assert excinfo.value.code == "otp_invalid"


def test_resend_is_blocked_during_the_cooldown(
    service: OtpService, make_settings: Callable[..., Any]
) -> None:
    settings = make_settings()
    start = datetime.now(UTC)
    service.issue(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE, now=start)

    with pytest.raises(AppError) as excinfo:
        service.issue(
            phone=PHONE,
            purpose=OtpPurpose.VERIFY_PHONE,
            now=start + timedelta(seconds=1),
        )

    error = excinfo.value
    assert error.status_code == 429
    assert error.code == "otp_resend_too_soon"
    assert error.headers is not None
    assert 0 < int(error.headers["Retry-After"]) <= settings.otp_resend_cooldown_seconds


def test_resend_is_allowed_once_the_cooldown_passes(
    service: OtpService, make_settings: Callable[..., Any], db_session: Session
) -> None:
    settings = make_settings()
    start = datetime.now(UTC)
    service.issue(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE, now=start)

    later = start + timedelta(seconds=settings.otp_resend_cooldown_seconds)
    service.issue(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE, now=later)

    statement = select(OtpChallenge).where(OtpChallenge.phone == PHONE)
    assert len(db_session.execute(statement).scalars().all()) == 2


def test_verification_uses_a_constant_time_comparison(
    service: OtpService, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str]] = []
    real_compare = hmac.compare_digest

    def spy(left: str, right: str) -> bool:
        calls.append((left, right))
        return real_compare(left, right)

    monkeypatch.setattr(otp_module.hmac, "compare_digest", spy)

    code = service.issue(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE)
    service.verify(phone=PHONE, purpose=OtpPurpose.VERIFY_PHONE, code=code)

    assert len(calls) == 1
