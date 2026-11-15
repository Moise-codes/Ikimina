"""Tests for password hashing, policy and the timing-equalised login path."""

from __future__ import annotations

import pytest

from app.core.security import passwords
from app.core.security.passwords import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    WeakPasswordError,
    hash_password,
    validate_password,
    verify_password,
)

GOOD_PASSWORD = "correct-horse-battery"


@pytest.mark.unit
def test_hash_is_argon2id_and_not_plaintext() -> None:
    digest = hash_password(GOOD_PASSWORD)
    assert digest.startswith("$argon2id$")
    assert GOOD_PASSWORD not in digest


@pytest.mark.unit
def test_hash_is_salted() -> None:
    assert hash_password(GOOD_PASSWORD) != hash_password(GOOD_PASSWORD)


@pytest.mark.unit
def test_verify_accepts_correct_password() -> None:
    digest = hash_password(GOOD_PASSWORD)
    assert verify_password(GOOD_PASSWORD, digest) is True


@pytest.mark.unit
def test_verify_rejects_wrong_password() -> None:
    digest = hash_password(GOOD_PASSWORD)
    assert verify_password("wrong-password-here", digest) is False


@pytest.mark.unit
def test_verify_rejects_malformed_hash() -> None:
    assert verify_password(GOOD_PASSWORD, "not-a-valid-hash") is False


@pytest.mark.unit
def test_missing_hash_never_authenticates() -> None:
    assert verify_password(GOOD_PASSWORD, None) is False
    assert verify_password(GOOD_PASSWORD, "") is False


@pytest.mark.unit
def test_missing_hash_still_performs_a_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown account must burn the same hashing work as a real one.

    Rather than asserting wall-clock time (flaky), assert the mechanism: a full
    verification against the dummy hash is actually executed.
    """

    class SpyHasher:
        def __init__(self, inner: object) -> None:
            self.inner = inner
            self.calls: list[str] = []

        def verify(self, hash_str: str, password: str) -> bool:
            self.calls.append(hash_str)
            return bool(self.inner.verify(hash_str, password))  # type: ignore[attr-defined]

    spy = SpyHasher(passwords._hasher)
    monkeypatch.setattr(passwords, "_hasher", spy)

    assert verify_password("anything-at-all", None) is False
    assert spy.calls == [passwords._DUMMY_HASH]


@pytest.mark.unit
def test_validate_accepts_a_strong_password() -> None:
    validate_password(GOOD_PASSWORD)


@pytest.mark.unit
def test_validate_rejects_short_password() -> None:
    with pytest.raises(WeakPasswordError):
        validate_password("a" * (MIN_PASSWORD_LENGTH - 1))


@pytest.mark.unit
def test_validate_rejects_long_password() -> None:
    with pytest.raises(WeakPasswordError):
        validate_password("a" * (MAX_PASSWORD_LENGTH + 1))


@pytest.mark.unit
@pytest.mark.parametrize("password", ["password", "PASSWORD123", "Ikimina123", "qwerty123"])
def test_validate_rejects_common_passwords(password: str) -> None:
    with pytest.raises(WeakPasswordError):
        validate_password(password)


@pytest.mark.unit
def test_validate_rejects_password_equal_to_phone() -> None:
    for candidate in ("+250788123456", "0788123456", "788123456"):
        with pytest.raises(WeakPasswordError):
            validate_password(candidate, phone="+250788123456")


@pytest.mark.unit
def test_validate_allows_password_containing_but_not_equal_to_phone() -> None:
    validate_password("my788number", phone="+250788123456")


@pytest.mark.unit
def test_validate_rejects_non_string() -> None:
    with pytest.raises(WeakPasswordError):
        validate_password(12345678901)  # type: ignore[arg-type]
