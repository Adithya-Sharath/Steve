"""The messaging seam (D48): what the WhatsApp flow needs from a provider, so Twilio can be swapped for the Meta Cloud API later without touching the flow.

A provider knows how to (1) check that a webhook really came from the provider, (2) send a text reply, (3) download a media file the user sent.
`FakeProvider` is what the tests use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Incoming:
    """One inbound message. `sender` is the channel address (a phone number): it is hashed at once and NEVER logged, stored or shown again."""

    sender: str
    to: str  # our own number: replies are sent from it
    body: str
    sid: str  # provider message id (used only to ignore a duplicate delivery)
    media: tuple[tuple[str, str], ...] = ()  # (url, content type)


class MessagingProvider(Protocol):
    name: str

    def validate(self, url: str, params: dict[str, list[str]], signature: str) -> bool: ...

    def send(self, to: str, from_: str, body: str) -> None: ...

    def download(self, url: str, max_bytes: int) -> bytes:
        """Fetch a media file into memory. Raises MediaTooLarge when it is over `max_bytes`, MediaUnavailable when it cannot be fetched."""
        ...


class MediaTooLarge(Exception):
    pass


class MediaUnavailable(Exception):
    pass


@dataclass
class FakeProvider:
    """Offline provider for tests: records what would have been sent, serves media from a dict, and says whether signatures are valid."""

    name: str = "fake"
    valid: bool = True
    sent: list[tuple[str, str, str]] = field(default_factory=list)  # (to, from, body)
    media: dict[str, bytes] = field(default_factory=dict)
    fail_send: bool = False

    def validate(self, url: str, params: dict[str, list[str]], signature: str) -> bool:
        return self.valid

    def send(self, to: str, from_: str, body: str) -> None:
        if self.fail_send:
            raise RuntimeError("send failed")
        self.sent.append((to, from_, body))

    def download(self, url: str, max_bytes: int) -> bytes:
        data = self.media.get(url)
        if data is None:
            raise MediaUnavailable(url)
        if len(data) > max_bytes:
            raise MediaTooLarge(url)
        return data

    @property
    def bodies(self) -> list[str]:
        return [b for _, _, b in self.sent]
