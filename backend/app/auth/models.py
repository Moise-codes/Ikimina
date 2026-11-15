"""Authentication tables.

``otp_challenges`` records every one-time password we issue. The code itself is
never stored — only an HMAC-SHA256 of it under the server secret — so a database
leak does not hand an attacker a working code to verify a phone or reset a
password.

The database enforces the invariants that matter (a real Rwandan phone number, a
known purpose, a sane attempt counter) so a bug in the service cannot write an
invalid row.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.core.common.phone import E164_PATTERN
from app.core.database import Base, UUIDPrimaryKeyMixin


class OtpPurpose(StrEnum):
    """Why a one-time password was issued."""

    VERIFY_PHONE = "verify_phone"
    RESET_PASSWORD = "reset_password"  # noqa: S105 - an enum value, not a credential
    CHANGE_PHONE = "change_phone"


_PURPOSE_VALUES = tuple(purpose.value for purpose in OtpPurpose)

#: Mirrors ``E164_PATTERN`` in ``app.core.common.phone`` (kept as plain text so
#: the same pattern is valid in Python and in SQL).
_PHONE_SQL_PATTERN = E164_PATTERN.pattern

#: Hard ceiling for the attempt counter. The service stops incrementing at the
#: configured ``otp_max_attempts`` (which cannot exceed this), so the CHECK is a
#: safety net rather than the primary limit.
MAX_ATTEMPTS_CEILING = 10


class OtpChallenge(UUIDPrimaryKeyMixin, Base):
    """A single issued one-time password."""

    __tablename__ = "otp_challenges"

    phone: Mapped[str] = mapped_column(String(13), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    #: The user the code belongs to; NULL during registration, before the row
    #: has been confirmed.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    #: HMAC-SHA256 of ``purpose:phone:code``. The plaintext code is never stored.
    code_hmac: Mapped[str] = mapped_column(Text, nullable=False)

    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: Client address the request came from, kept for abuse control.
    request_ip: Mapped[str | None] = mapped_column(INET)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"phone ~ '{_PHONE_SQL_PATTERN}'", name="phone_format"),
        CheckConstraint(
            "purpose IN (" + ", ".join(f"'{value}'" for value in _PURPOSE_VALUES) + ")",
            name="purpose_valid",
        ),
        CheckConstraint(
            f"attempts >= 0 AND attempts <= {MAX_ATTEMPTS_CEILING}",
            name="attempts_range",
        ),
        # Throttling lookup: the most recent challenge for a phone and purpose.
        Index("ix_otp_challenges_phone_purpose_created_at", "phone", "purpose", "created_at"),
        # Cleanup job: expired rows.
        Index("ix_otp_challenges_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<OtpChallenge id={self.id!s} purpose={self.purpose} phone={self.phone}>"
