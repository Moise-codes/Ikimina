"""SMS delivery: the sender interface, the fake, and a settings-driven factory."""

from __future__ import annotations

from app.core.config import Environment, Settings
from app.notifications.sms.base import SmsSender
from app.notifications.sms.fake import FakeSmsSender, SentSms

__all__ = ["FakeSmsSender", "SentSms", "SmsSender", "build_sms_sender"]


def build_sms_sender(settings: Settings) -> SmsSender:
    """Return the SMS sender to use for ``settings``.

    Only the fake exists today. Refusing to build one outside a developer
    environment keeps a misconfigured staging or production deployment from
    silently "delivering" messages that go nowhere; real provider adapters are
    added here in a later phase.
    """
    if settings.environment in (Environment.local, Environment.development):
        return FakeSmsSender(environment=settings.environment)
    raise RuntimeError("no SMS provider is configured for this environment")
