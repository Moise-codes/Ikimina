"""Outbound notifications (SMS now; receipts and reminders later).

Delivery is always expressed through a small interface so the rest of the
application never depends on a live provider. Local development and the test
suite use a fake that records messages instead of sending them, which keeps OTP
and notification code testable without a network.
"""
