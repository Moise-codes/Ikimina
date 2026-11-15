"""A fake SMS sender for local development and tests.

Nothing is sent over the network; messages are recorded in memory so tests can
assert on them. When the environment is a developer environment (local or
development) the message body is also written to the log, so a developer can
read an OTP straight from the console. In every other environment the body is
replaced with ``<redacted>``: a misconfigured deployment must never be able to
spill an OTP code into the logs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.common.phone import mask_phone
from app.core.config import Environment
from app.notifications.sms.base import SmsSender

logger = logging.getLogger(__name__)

#: Environments where the message body (and therefore any OTP code) may be
#: written to the log. Staging and production are deliberately excluded.
_BODY_LOGGING_ENVIRONMENTS: frozenset[Environment] = frozenset(
    {Environment.local, Environment.development}
)


@dataclass(frozen=True, slots=True)
class SentSms:
    """A message recorded by :class:`FakeSmsSender`."""

    to: str
    body: str
    message_id: str


class FakeSmsSender(SmsSender):
    """An SMS sender that delivers nothing; it only records and logs."""

    def __init__(self, *, environment: Environment) -> None:
        self._log_body = environment in _BODY_LOGGING_ENVIRONMENTS
        #: Messages in the order they were "sent".
        self.outbox: list[SentSms] = []

    def send(self, *, to: str, body: str) -> str | None:
        message_id = f"fake-sms-{len(self.outbox) + 1}"
        self.outbox.append(SentSms(to=to, body=body, message_id=message_id))
        # The recipient is masked so a phone number never lands in the logs in
        # full; the body is only logged where that is safe (see the module doc).
        if self._log_body:
            logger.info("sms.fake.sent to=%s body=%s", mask_phone(to), body)
        else:
            logger.info("sms.fake.sent to=%s body=<redacted>", mask_phone(to))
        return message_id
