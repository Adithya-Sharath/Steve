"""Sender authentication: an unguessable per-browser key (capability), never a password.

The browser generates `sk_<random>` once and sends it as the `X-Sender-Key` header. The server stores only its SHA-256
hash on each message (`Message.owner_hash`); a request is allowed when the hash of the presented key matches. Missing,
malformed or non-matching keys get **403**. Readers never need a key: `/r/{token}` stays open by token.

EventSource cannot set headers, so the SSE stream alone also accepts `?key=`.
"""

from __future__ import annotations

import hashlib
import re

from fastapi import Header, HTTPException, Query

KEY_RE = re.compile(r"^sk_[A-Za-z0-9_-]{24,128}$")
FORBIDDEN = "Sender key required. Open Samjha in the browser where you created this message."


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _check(key: str | None) -> str:
    if not key or not KEY_RE.match(key):
        raise HTTPException(403, FORBIDDEN)
    return hash_key(key)


def sender_hash(x_sender_key: str | None = Header(default=None)) -> str:
    return _check(x_sender_key)


def sender_hash_header_or_query(x_sender_key: str | None = Header(default=None), key: str | None = Query(default=None)) -> str:
    return _check(x_sender_key or key)
