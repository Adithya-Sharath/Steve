"""Messaging providers behind one interface (D48). Twilio's WhatsApp sandbox first; a seam for the Meta Cloud API later."""

from __future__ import annotations

from ...settings import settings
from .base import FakeProvider, Incoming, MediaTooLarge, MediaUnavailable, MessagingProvider
from .twilio import TwilioProvider, compute_signature

__all__ = ["FakeProvider", "Incoming", "MediaTooLarge", "MediaUnavailable", "MessagingProvider", "TwilioProvider", "compute_signature", "get_provider"]


def get_provider() -> MessagingProvider:
    """The configured provider (Twilio today). Tests replace this function with one that returns a FakeProvider."""
    return TwilioProvider(settings.twilio_account_sid, settings.twilio_auth_token)
