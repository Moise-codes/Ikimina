"""Issuing and verifying one-time passwords.

An OTP is six digits, valid for a few minutes, single use, and limited to a
small number of guesses. Only an HMAC-SHA256 of the code is stored and the
comparison is constant-time, so neither a leaked database nor a timing side
channel reveals the code.

The service works on a caller-supplied session and does not commit: the request
handler owns the transaction, so an OTP is only ever recorded together with the
rest of the work it belongs to.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import OtpChallenge, OtpPurpose
from app.core.config import Settings
from app.core.errors import AppError

#: Number of decimal digits in an OTP.
OTP_CODE_DIGITS = 6

#: Exclusive upper bound for the random code (10 ** digits).
_OTP_MODULUS = 10**OTP_CODE_DIGITS


def _invalid(message: str, code: str = "otp_invalid") -> AppError:
    return AppError(status_code=400, code=code, message=message)


class OtpService:
    """Creates and verifies OTP challenges for a single database session."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    # -- Issuing ----------------------------------------------------------

    def issue(
        self,
        *,
        phone: str,
        purpose: OtpPurpose,
        user_id: uuid.UUID | None = None,
        request_ip: str | None = None,
        now: datetime | None = None,
    ) -> str:
        """Create a challenge and return the plaintext code to send by SMS.

        The code is returned, not sent: delivery is the caller's job, so this
        method stays free of any provider dependency.
        """
        moment = now or datetime.now(UTC)
        self._enforce_resend_cooldown(phone=phone, purpose=purpose, now=moment)

        code = self._generate_code()
        challenge = OtpChallenge(
            phone=phone,
            purpose=purpose.value,
            user_id=user_id,
            code_hmac=self._hash_code(purpose=purpose, phone=phone, code=code),
            expires_at=moment + timedelta(minutes=self._settings.otp_expire_minutes),
            # Set explicitly (rather than the column default) so the resend
            # cooldown and the expiry are measured against the same clock.
            created_at=moment,
            request_ip=request_ip,
        )
        self._session.add(challenge)
        self._session.flush()
        return code

    # -- Verifying --------------------------------------------------------

    def verify(
        self,
        *,
        phone: str,
        purpose: OtpPurpose,
        code: str,
        now: datetime | None = None,
    ) -> OtpChallenge:
        """Check ``code`` against the newest challenge and consume it on success.

        Raises:
            AppError: ``otp_invalid`` when there is no challenge or the code is
                wrong, ``otp_used`` when it was already consumed, ``otp_expired``
                when it is past its lifetime, and ``otp_attempts_exceeded`` once
                the guess limit is reached.
        """
        moment = now or datetime.now(UTC)
        challenge = self._latest(phone=phone, purpose=purpose)

        if challenge is None:
            raise _invalid("The verification code is not valid")
        if challenge.consumed_at is not None:
            raise _invalid("This verification code has already been used", code="otp_used")
        if challenge.expires_at <= moment:
            raise _invalid("This verification code has expired", code="otp_expired")
        if challenge.attempts >= self._settings.otp_max_attempts:
            raise _invalid(
                "Too many incorrect attempts; request a new code",
                code="otp_attempts_exceeded",
            )

        provided = self._hash_code(purpose=purpose, phone=phone, code=code)
        if not hmac.compare_digest(challenge.code_hmac, provided):
            challenge.attempts += 1
            self._session.flush()
            raise _invalid("The verification code is not valid")

        challenge.consumed_at = moment
        self._session.flush()
        return challenge

    # -- Internals --------------------------------------------------------

    def _latest(self, *, phone: str, purpose: OtpPurpose) -> OtpChallenge | None:
        """Return the newest challenge for ``phone`` and ``purpose``, if any."""
        statement = (
            select(OtpChallenge)
            .where(OtpChallenge.phone == phone, OtpChallenge.purpose == purpose.value)
            .order_by(OtpChallenge.created_at.desc(), OtpChallenge.id.desc())
            .limit(1)
        )
        return self._session.execute(statement).scalar_one_or_none()

    def _enforce_resend_cooldown(self, *, phone: str, purpose: OtpPurpose, now: datetime) -> None:
        """Reject a resend while a previous, still-usable code is outstanding."""
        cooldown = self._settings.otp_resend_cooldown_seconds
        if cooldown <= 0:
            return
        challenge = self._latest(phone=phone, purpose=purpose)
        if challenge is None or challenge.consumed_at is not None:
            return
        elapsed = (now - challenge.created_at).total_seconds()
        if elapsed < cooldown:
            raise AppError(
                status_code=429,
                code="otp_resend_too_soon",
                message="Please wait before requesting another code",
                headers={"Retry-After": str(math.ceil(cooldown - elapsed))},
            )

    def _hash_code(self, *, purpose: OtpPurpose, phone: str, code: str) -> str:
        """HMAC-SHA256 over ``purpose:phone:code`` with the server secret.

        Binding the purpose and phone into the digest means a code issued for
        one flow cannot be replayed against another.
        """
        secret = self._settings.secret_key.get_secret_value()
        message = f"{purpose.value}:{phone}:{code}".encode()
        return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

    @staticmethod
    def _generate_code() -> str:
        """Return a uniformly random ``OTP_CODE_DIGITS``-digit code."""
        return f"{secrets.randbelow(_OTP_MODULUS):0{OTP_CODE_DIGITS}d}"
