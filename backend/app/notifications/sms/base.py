"""The SMS sender interface.

Everything that needs to send an SMS depends on this abstraction, never on a
concrete provider. That keeps the OTP and notification code testable without a
network and lets a real adapter be dropped in later without touching callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SmsSender(ABC):
    """Sends a single text message to a phone number."""

    @abstractmethod
    def send(self, *, to: str, body: str) -> str | None:
        """Deliver ``body`` to ``to``.

        Args:
            to: Recipient number in E.164 form.
            body: The message text.

        Returns:
            The provider's message identifier when one is available, else
            ``None``.
        """
        raise NotImplementedError
