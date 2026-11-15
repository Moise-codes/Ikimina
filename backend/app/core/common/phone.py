"""Rwandan mobile phone normalisation, validation and masking.

Rwanda uses a single country code (+250) and four mobile ranges: MTN on 078 and
079, Airtel on 072 and 073. No matter which form a user types — ``0788123456``,
``788123456``, ``250788123456`` or ``+250788123456``, with or without spaces,
dashes or parentheses — the one canonical form we store is **E.164**:
``+250788123456``.

Storing a single canonical form keeps ``users.phone`` a stable unique key and
makes equality checks (login lookups, duplicate detection) reliable. Numbers
from other countries and Rwandan fixed lines are rejected.
"""

from __future__ import annotations

import re

import phonenumbers

#: Region used to interpret numbers written in national form.
RWANDA_REGION = "RW"

#: Rwanda's country calling code.
RWANDA_COUNTRY_CODE = "250"

#: The only mobile prefixes Rwanda issues (MTN 72/73, Airtel 78/79).
MOBILE_PREFIXES: frozenset[str] = frozenset({"72", "73", "78", "79"})

#: Canonical E.164 shape, mirrored by the ``users.phone`` CHECK constraint.
E164_PATTERN = re.compile(r"^\+250(?:72|73|78|79)\d{7}$")

#: Characters users type as separators; they carry no meaning and are removed.
_SEPARATORS = re.compile(r"[\s\-().]")

#: After separators are removed only an optional "+" and digits may remain.
_DIGITS_ONLY = re.compile(r"\+?\d+")

#: A national significant number is nine digits (for example 788 123 456).
_NATIONAL_LENGTH = 9


class InvalidPhoneNumber(ValueError):
    """Raised when a value is not a valid Rwandan mobile number."""


def _strip_separators(raw: str) -> str:
    return _SEPARATORS.sub("", raw).strip()


def _to_international_form(candidate: str) -> str:
    """Turn a dialled string into a form ``phonenumbers`` can parse."""
    if candidate.startswith("00"):  # international access code
        return "+" + candidate[2:]
    if not candidate.startswith("+") and candidate.startswith(RWANDA_COUNTRY_CODE):
        # Country code typed without the leading "+" (250788123456).
        return "+" + candidate
    # National form (0788123456 / 788123456) is parsed with the RW region.
    return candidate


def normalize_phone(raw: str) -> str:
    """Return the E.164 form of a Rwandan mobile number.

    Args:
        raw: A phone number in any of the accepted notations.

    Returns:
        The normalized number, for example ``"+250788123456"``.

    Raises:
        InvalidPhoneNumber: If the value is empty, unparseable, belongs to
            another country, is not a mobile number, or is not a valid Rwandan
            mobile number.
    """
    if not isinstance(raw, str):
        raise InvalidPhoneNumber("Phone number must be a string")

    candidate = _strip_separators(raw)
    if not candidate:
        raise InvalidPhoneNumber("Phone number is required")
    # Reject letters and other stray characters outright instead of letting the
    # parser interpret them (it strips alphabetics by default).
    if not _DIGITS_ONLY.fullmatch(candidate):
        raise InvalidPhoneNumber("Not a valid Rwandan phone number")

    try:
        parsed = phonenumbers.parse(_to_international_form(candidate), RWANDA_REGION)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhoneNumber("Not a valid Rwandan phone number") from exc

    if str(parsed.country_code) != RWANDA_COUNTRY_CODE:
        raise InvalidPhoneNumber("Only Rwandan phone numbers are supported")

    national = str(parsed.national_number)
    # Enforce the mobile ranges explicitly: reject fixed lines and any prefix
    # the Rwandan numbering plan does not use for mobile services.
    if len(national) != _NATIONAL_LENGTH or national[:2] not in MOBILE_PREFIXES:
        raise InvalidPhoneNumber("Not a valid Rwandan mobile number")

    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumber("Not a valid Rwandan mobile number")

    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    if not E164_PATTERN.match(e164):
        raise InvalidPhoneNumber("Not a valid Rwandan mobile number")
    return e164


def is_valid_phone(raw: str) -> bool:
    """Return ``True`` if ``raw`` normalizes to a valid Rwandan mobile number."""
    try:
        normalize_phone(raw)
    except InvalidPhoneNumber:
        return False
    return True


def mask_phone(phone: str) -> str:
    """Mask a phone number for logs and audit records.

    Keeps the country code and the first three national digits so an operator can
    still recognise a number, and reveals only the last three digits::

        +250788123456  ->  +250788***456
    """
    try:
        canonical = normalize_phone(phone)
    except InvalidPhoneNumber:
        canonical = None

    if canonical is not None:
        digits = canonical.lstrip("+")
        return f"+{digits[:6]}***{digits[-3:]}"

    # Not a valid Rwandan number: mask generically, still keeping the last three.
    digits = _strip_separators(phone).lstrip("+")
    if len(digits) <= 3:
        return "***"
    return "***" + digits[-3:]
