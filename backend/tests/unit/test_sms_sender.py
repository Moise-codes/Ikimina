"""Tests for the SMS sender interface, the fake sender and the factory."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pytest

from app.core.config import Environment
from app.notifications.sms import FakeSmsSender, SmsSender, build_sms_sender

#: Module logger the fake writes to; scoping caplog to it keeps the assertions
#: independent of whatever else logs during a test run.
_LOGGER = "app.notifications.sms.fake"
_PHONE = "+250788123456"
_MASKED_PHONE = "+250788***456"
_BODY = "Ikimina: your verification code is 123456"


@pytest.mark.unit
def test_interface_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        SmsSender()  # type: ignore[abstract]


@pytest.mark.unit
def test_send_records_the_message_and_returns_an_id() -> None:
    sender = FakeSmsSender(environment=Environment.local)

    first = sender.send(to=_PHONE, body="one")
    second = sender.send(to=_PHONE, body="two")

    assert first == "fake-sms-1"
    assert second == "fake-sms-2"
    assert [message.body for message in sender.outbox] == ["one", "two"]
    assert sender.outbox[0].to == _PHONE


@pytest.mark.unit
@pytest.mark.parametrize("environment", [Environment.local, Environment.development])
def test_body_is_logged_in_developer_environments(
    environment: Environment, caplog: pytest.LogCaptureFixture
) -> None:
    sender = FakeSmsSender(environment=environment)

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        sender.send(to=_PHONE, body=_BODY)

    assert "123456" in caplog.text
    # The recipient is masked; the full number must never be logged.
    assert _MASKED_PHONE in caplog.text
    assert _PHONE not in caplog.text


@pytest.mark.unit
@pytest.mark.parametrize("environment", [Environment.staging, Environment.production])
def test_body_is_redacted_outside_developer_environments(
    environment: Environment, caplog: pytest.LogCaptureFixture
) -> None:
    sender = FakeSmsSender(environment=environment)

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        sender.send(to=_PHONE, body=_BODY)

    assert "123456" not in caplog.text
    assert _BODY not in caplog.text
    assert _PHONE not in caplog.text
    assert "redacted" in caplog.text


@pytest.mark.unit
def test_factory_builds_the_fake_in_developer_environments(
    make_settings: Callable[..., Any],
) -> None:
    sender = build_sms_sender(make_settings(environment=Environment.local))
    assert isinstance(sender, FakeSmsSender)


@pytest.mark.unit
@pytest.mark.parametrize("environment", [Environment.staging, Environment.production])
def test_factory_refuses_to_build_a_sender_without_a_provider(
    environment: Environment, make_settings: Callable[..., Any]
) -> None:
    with pytest.raises(RuntimeError):
        build_sms_sender(make_settings(environment=environment))
