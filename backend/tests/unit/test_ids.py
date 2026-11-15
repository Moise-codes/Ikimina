"""Tests for UUIDv7 identifier generation."""

from __future__ import annotations

import time
import uuid

import pytest

from app.core.common.ids import uuid7


@pytest.mark.unit
def test_generates_version_7_rfc_variant_uuids() -> None:
    value = uuid7()
    assert isinstance(value, uuid.UUID)
    assert value.version == 7
    assert value.variant == uuid.RFC_4122


@pytest.mark.unit
def test_values_are_unique() -> None:
    generated = {uuid7() for _ in range(1000)}
    assert len(generated) == 1000


@pytest.mark.unit
def test_values_are_time_ordered() -> None:
    first = uuid7()
    time.sleep(0.005)  # cross a millisecond boundary
    second = uuid7()
    assert first < second
