"""Tests for Rwandan phone normalisation, validation and masking."""

from __future__ import annotations

import pytest

from app.core.common.phone import (
    E164_PATTERN,
    InvalidPhoneNumber,
    is_valid_phone,
    mask_phone,
    normalize_phone,
)

# Every accepted notation normalizes to the same canonical E.164 value.
CANONICAL = "+250788123456"

VALID_NUMBERS = [
    "0788123456",
    "788123456",
    "250788123456",
    "+250788123456",
    "0788 123 456",
    "0788-123-456",
    "+250-788-123-456",
    "(0788) 123 456",
    "  0788123456  ",
    "+250788123456",
]


@pytest.mark.unit
@pytest.mark.parametrize("raw", VALID_NUMBERS)
def test_accepted_notations_normalize_to_e164(raw: str) -> None:
    assert normalize_phone(raw) == CANONICAL


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0721234567", "+250721234567"),  # Airtel 72
        ("0731234567", "+250731234567"),  # Airtel 73
        ("0781234567", "+250781234567"),  # MTN 78
        ("0791234567", "+250791234567"),  # MTN 79
    ],
)
def test_all_mobile_ranges_are_accepted(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.unit
def test_normalizing_is_idempotent() -> None:
    assert normalize_phone(CANONICAL) == CANONICAL
    assert normalize_phone(normalize_phone("0788123456")) == CANONICAL


@pytest.mark.unit
def test_output_always_matches_stored_shape() -> None:
    assert E164_PATTERN.match(normalize_phone("0788123456"))


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw",
    [
        "",  # empty
        "   ",  # whitespace only
        "078812345",  # too short
        "07881234567",  # too long
        "0788123456789",  # much too long
        "0751234567",  # 75 is not a mobile range
        "0741234567",  # 74 is not a mobile range
        "0701234567",  # 70 is not a mobile range
        "0711234567",  # 71 is not a mobile range
        "+250212345678",  # Rwandan fixed line, not mobile
        "abc",
        "phone",
        "0788abc456",
        "0788123 45678",
        "+",
        "0",
    ],
)
def test_invalid_values_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone(raw)


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw",
    [
        "+254712345678",  # Kenya
        "+255712345678",  # Tanzania
        "+256712345678",  # Uganda
        "+14155552671",  # United States
        "+447911123456",  # United Kingdom
        "00254712345678",  # Kenya, international access code
    ],
)
def test_other_countries_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone(raw)


@pytest.mark.unit
@pytest.mark.parametrize("raw", [None, 250788123456, b"0788123456", ["0788123456"]])
def test_non_string_input_is_rejected(raw: object) -> None:
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone(raw)  # type: ignore[arg-type]


@pytest.mark.unit
def test_is_valid_phone_return_value() -> None:
    assert is_valid_phone("0788123456") is True
    assert is_valid_phone("+250788123456") is True
    assert is_valid_phone("0751234567") is False
    assert is_valid_phone("+254712345678") is False
    assert is_valid_phone("") is False


@pytest.mark.unit
def test_mask_phone_matches_documented_shape() -> None:
    assert mask_phone("+250788123456") == "+250788***456"
    assert mask_phone("0788123456") == "+250788***456"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+250788123456", "+250788***456"),
        ("0788123456", "+250788***456"),
        ("+250721234567", "+250721***567"),
    ],
)
def test_mask_phone_examples(raw: str, expected: str) -> None:
    assert mask_phone(raw) == expected


@pytest.mark.unit
def test_mask_phone_never_reveals_middle_digits() -> None:
    masked = mask_phone("+250788123456")
    assert "123" not in masked
    assert masked.endswith("456")


@pytest.mark.unit
def test_mask_phone_handles_short_input() -> None:
    assert mask_phone("") == "***"
    assert mask_phone("12") == "***"
