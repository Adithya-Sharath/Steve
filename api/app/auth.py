"""Sender authentication: an unguessable per-browser key (capability), never a password.

The browser generates `sk_<random>` once and sends it as the `X-Sender-Key` header. The server stores only its SHA-256
hash on each message (`Message.owner_hash`); a request is allowed when the hash of the presented key matches. Missing,
malformed or non-matching keys get **403**. Readers never need a key: `/r/{token}` stays open by token.

EventSource cannot set headers, so the SSE stream alone also accepts `?key=`.
"""

from __future__ import annotations

import hashlib
import hmac
import re

from fastapi import Header, HTTPException, Query

from .settings import settings

KEY_RE = re.compile(r"^sk_[A-Za-z0-9_-]{24,128}$")
FORBIDDEN = "Sender key required. Open Steve in the browser where you created this message."
ADMIN_FORBIDDEN = "Admin key required."


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _check(key: str | None) -> str:
    if not key or not KEY_RE.match(key):
        raise HTTPException(403, FORBIDDEN)
    return hash_key(key)


WORKER_KEY_RE = re.compile(r"^wk_[A-Za-z0-9_-]{24,128}$")
WORKER_FORBIDDEN = "Worker key required. Open Steve in the browser where you started."


def worker_hash(x_worker_key: str | None = Header(default=None)) -> str:
    """Decode identity: a device key `wk_<random>` generated in the browser (D45). Like the sender key it is a capability, not a password:
    only its SHA-256 hash is ever used, and nothing about the worker is stored."""
    if not x_worker_key or not WORKER_KEY_RE.match(x_worker_key):
        raise HTTPException(403, WORKER_FORBIDDEN)
    return hash_key(x_worker_key)


def sender_hash(x_sender_key: str | None = Header(default=None)) -> str:
    return _check(x_sender_key)


def sender_hash_header_or_query(x_sender_key: str | None = Header(default=None), key: str | None = Query(default=None)) -> str:
    return _check(x_sender_key or key)


def admin_required(x_admin_key: str | None = Header(default=None)) -> None:
    """Gate for settings that affect EVERYONE (the global LLM switch). A self-issued sender key is not enough:
    the operator sets ADMIN_KEY in the environment. Unset => nobody can use it (403). Compared in constant time."""
    configured = settings.admin_key
    if not configured or not x_admin_key or not hmac.compare_digest(x_admin_key.encode("utf-8"), configured.encode("utf-8")):
        raise HTTPException(403, ADMIN_FORBIDDEN)
