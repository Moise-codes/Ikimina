"""Password hashing and policy.

Passwords are hashed with **Argon2id** (``argon2-cffi`` defaults: memory cost
64 MiB, time cost 3, parallelism 4), the current recommendation from the
Password Hashing Competition and OWASP. The plaintext password is never stored,
logged or returned.

Two details matter for security:

* **Timing-equalised login.** ``verify_password`` accepts ``None`` for the
  stored hash. When the account does not exist the caller passes ``None`` and we
  still perform a full verification against a dummy hash, so an unknown phone
  and a wrong password take about the same time and the response cannot be used
  to enumerate accounts.
* **A small deny-list.** The most common passwords are rejected outright; this
  is deliberately small and does not replace a breach-corpus check.
"""

from __future__ import annotations

import secrets
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

#: Minimum and maximum accepted password lengths (characters, not bytes).
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128

#: A deliberately small set of the most common passwords. Anything here is
#: guaranteed to be tried first by an attacker.
DENYLIST: frozenset[str] = frozenset(
    {
        "password",
        "password1",
        "password123",
        "1234567890",
        "123456789",
        "12345678",
        "qwertyuiop",
        "qwerty123",
        "letmein123",
        "iloveyou",
        "admin123",
        "administrator",
        "welcome123",
        "welcome1",
        "passw0rd",
        "p@ssw0rd",
        "1q2w3e4r",
        "1qaz2wsx",
        "qazwsx123",
        "abc123456",
        "ikimina",
        "ikimina123",
    }
)

#: Argon2id hasher with the library's current recommended parameters.
_hasher = PasswordHasher()

#: Precomputed hash used to equalise timing when no account exists. The value
#: it hashes is random and never reused, so it can never be a valid password.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))


class WeakPasswordError(ValueError):
    """Raised when a password does not meet the policy."""


def hash_password(password: str) -> str:
    """Return an Argon2id hash for ``password``."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Check ``password`` against ``password_hash`` in roughly constant time.

    Args:
        password: The plaintext candidate.
        password_hash: The stored hash, or ``None`` when no account/credential
            exists. ``None`` triggers a dummy verification (see module docs).

    Returns:
        ``True`` only when the hash is present and the password matches.
    """
    target = password_hash if password_hash else _DUMMY_HASH
    try:
        _hasher.verify(target, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    # A missing hash must never authenticate, even in the (astronomically
    # unlikely) event that the candidate matches the dummy hash.
    return password_hash is not None


def validate_password(password: str, *, phone: str | None = None) -> None:
    """Enforce the password policy, raising ``WeakPasswordError`` on failure.

    Args:
        password: The candidate password.
        phone: Optional related phone number (E.164 or national); a password
            equal to it is rejected because it is trivially guessable.
    """
    if not isinstance(password, str):
        raise WeakPasswordError("Password must be a string")
    # Normalise for the comparison only; the original is hashed unchanged.
    candidate = unicodedata.normalize("NFKC", password)
    if len(candidate) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(candidate) > MAX_PASSWORD_LENGTH:
        raise WeakPasswordError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters")
    if candidate.casefold() in DENYLIST:
        raise WeakPasswordError("Password is too common")
    if phone is not None and candidate in _phone_variants(phone):
        raise WeakPasswordError("Password must not be your phone number")


def _phone_variants(phone: str) -> set[str]:
    """Return the forms of ``phone`` a user might set as a password."""
    digits = "".join(char for char in phone if char.isdigit())
    variants = {phone, digits}
    if len(digits) >= 9:
        national = digits[-9:]
        variants.add(national)
        variants.add("0" + national)
    return variants
