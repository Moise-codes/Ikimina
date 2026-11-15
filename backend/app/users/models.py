"""The ``users`` table.

One row per person. A user is identified by their phone number; the email is
optional. The row carries the credential hash, verification timestamps and the
lockout counters used by the login flow.

The database enforces the important invariants itself (format of the phone,
allowed status values, counters never negative) so that a bug in application
code cannot write an invalid row.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.common.phone import E164_PATTERN
from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserStatus(StrEnum):
    """Lifecycle of an account."""

    ACTIVE = "active"
    LOCKED = "locked"
    DEACTIVATED = "deactivated"
    ANONYMIZED = "anonymized"


class UserLocale(StrEnum):
    """Supported interface languages."""

    RW = "rw"  # Kinyarwanda
    EN = "en"
    FR = "fr"


_STATUS_VALUES = tuple(status.value for status in UserStatus)
_LOCALE_VALUES = tuple(locale.value for locale in UserLocale)

# The CHECK expression mirrors ``E164_PATTERN`` in ``app.core.common.phone``.
_PHONE_SQL_PATTERN = E164_PATTERN.pattern


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A registered person."""

    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(100), nullable=False)

    #: E.164 Rwandan mobile number. Unique; NULL only once anonymized.
    phone: Mapped[str | None] = mapped_column(String(13), nullable=True, unique=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: Optional email. CITEXT makes uniqueness case-insensitive.
    email: Mapped[str | None] = mapped_column(CITEXT, nullable=True, unique=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: Argon2id hash. Never returned by the API. NULL once anonymized.
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    preferred_language: Mapped[str] = mapped_column(
        String(2), nullable=False, server_default=text(f"'{UserLocale.RW.value}'")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text(f"'{UserStatus.ACTIVE.value}'")
    )
    is_platform_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    #: Proof of consent to the privacy notice (Law N° 058/2021).
    privacy_notice_version: Mapped[str] = mapped_column(String(16), nullable=False)
    privacy_accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    #: Login lockout bookkeeping.
    failed_login_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "char_length(full_name) BETWEEN 2 AND 100",
            name="full_name_length",
        ),
        CheckConstraint(
            f"phone IS NULL OR phone ~ '{_PHONE_SQL_PATTERN}'",
            name="phone_format",
        ),
        CheckConstraint(
            "phone IS NOT NULL OR status = 'anonymized'",
            name="phone_required_unless_anonymized",
        ),
        CheckConstraint(
            "status IN (" + ", ".join(f"'{value}'" for value in _STATUS_VALUES) + ")",
            name="status_valid",
        ),
        CheckConstraint(
            "preferred_language IN (" + ", ".join(f"'{value}'" for value in _LOCALE_VALUES) + ")",
            name="preferred_language_valid",
        ),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count_non_negative"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User id={self.id!s} status={self.status}>"
