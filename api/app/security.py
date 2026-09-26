"""Hardening basics (D35): security headers, a global request-body cap, a generic 500 handler that never leaks internals,
and log hygiene (mask `?key=`, redact configured secrets).

All of it is pure ASGI / logging code with no new dependencies, and none of it can change an engine verdict.
"""

from __future__ import annotations

import json
import logging
import re
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse

from .settings import settings

log = logging.getLogger("steve.security")

# ---- CORS -------------------------------------------------------------------------------------------------------

LOCALHOST_RE = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"


def cors_options() -> dict:
    """Keyword arguments for CORSMiddleware, from CORS_ORIGINS (list, or `*`) and CORS_ALLOW_LOCALHOST. Another site may call the API when its origin is listed (D47)."""
    origins = list(settings.cors_origins)
    everything = "*" in origins
    return {
        "allow_origins": ["*"] if everything else origins,
        "allow_origin_regex": LOCALHOST_RE if settings.cors_allow_localhost and not everything else None,
        "allow_credentials": False,  # the API uses keys in headers, never cookies
        "allow_methods": ["*"],
        "allow_headers": ["*"],  # X-Worker-Key, X-Sender-Key, X-Admin-Key, Content-Type
        "expose_headers": ["Retry-After"],
        "max_age": 600,
    }


# ---- headers ---------------------------------------------------------------------------------------------------

# A JSON API has no business loading anything: forbid every fetch and framing of its responses.
JSON_CSP = "default-src 'none'; frame-ancestors 'none'"
BASE_HEADERS = {b"x-content-type-options": b"nosniff", b"referrer-policy": b"no-referrer"}


def apply_security_headers(headers: dict[str, str]) -> None:
    """For responses built outside the middleware stack (the generic 500)."""
    headers["X-Content-Type-Options"] = "nosniff"
    headers["Referrer-Policy"] = "no-referrer"
    headers["Content-Security-Policy"] = JSON_CSP


class SecurityHeadersMiddleware:
    """`X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer` on every response; a minimal CSP on JSON ones
    (not on the HTML of /docs, which needs to load its own scripts)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in BASE_HEADERS]
                headers += list(BASE_HEADERS.items())
                ctype = next((v for k, v in headers if k.lower() == b"content-type"), b"")
                if ctype.lower().startswith(b"application/json"):
                    headers = [(k, v) for k, v in headers if k.lower() != b"content-security-policy"]
                    headers.append((b"content-security-policy", JSON_CSP.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


# ---- request size ----------------------------------------------------------------------------------------------

TOO_LARGE = {"detail": "That request is too large."}


class BodyLimitMiddleware:
    """Reject any request body over `max_bytes` (default 5 MB) with 413, whether it announces its size in Content-Length or
    streams it chunked/lying. The app's own answer is discarded once the limit is crossed (FastAPI would report a 400)."""

    def __init__(self, app, max_bytes: int | None = None):
        self.app = app
        self.max_bytes = max_bytes

    def _limit(self) -> int:
        return self.max_bytes if self.max_bytes is not None else settings.max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = self._limit()
        declared = next((v for k, v in scope["headers"] if k == b"content-length"), b"")
        if declared.isdigit() and int(declared) > limit:
            return await self._reject(send)

        received = 0
        exceeded = False
        responded = False

        async def counting_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    return {"type": "http.disconnect"}  # stop feeding the app; it may fail in any way it likes
            return message

        async def guarded_send(message):
            nonlocal responded
            if exceeded:
                if not responded:
                    responded = True
                    await self._reject(send)
                return
            if message["type"] == "http.response.start":
                responded = True
            await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
            # the app blew up on the cut-off body: that is our 413, not a 500
        if exceeded and not responded:  # the app returned without answering (disconnect): still tell the client
            await self._reject(send)

    @staticmethod
    async def _reject(send) -> None:
        body = json.dumps(TOO_LARGE).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), (b"connection", b"close")]})
        await send({"type": "http.response.body", "body": body})


# ---- errors ----------------------------------------------------------------------------------------------------

GENERIC_500 = "Something went wrong on our side. Please try again in a moment."


def _secrets() -> list[str]:
    return [s for s in (settings.gemini_api_key, settings.sarvam_api_key, settings.admin_key, settings.twilio_auth_token, settings.twilio_account_sid,
                        settings.worker_hash_secret) if s and len(s) >= 6]


def redact(text: str) -> str:
    """Remove configured secret values and `?key=` query values from any text headed for a log."""
    for s in _secrets():
        text = text.replace(s, "***")
    return mask_query_secrets(text)


_KEY_QUERY = re.compile(r"([?&](?:key|api_key|apikey|admin_key)=)[^&\s\"']*", re.I)
_SENDER_KEY = re.compile(r"\bsk_[A-Za-z0-9_-]{24,128}\b")


def mask_query_secrets(text: str) -> str:
    """`GET /messages/x/stream?key=sk_...` -> `...?key=***` (EventSource cannot send headers, so the key rides in the URL)."""
    return _SENDER_KEY.sub("sk_***", _KEY_QUERY.sub(r"\1***", text))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Any unexpected error: log the detail server-side (redacted), tell the client nothing about it."""
    trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log.error("Unhandled error on %s %s\n%s", request.method, request.url.path, redact(trace))
    response = JSONResponse({"detail": GENERIC_500}, status_code=500)
    apply_security_headers(response.headers)  # the 500 is built outside the middleware stack
    return response


# ---- logging ---------------------------------------------------------------------------------------------------


class MaskSecretsFilter(logging.Filter):
    """Masks `?key=` in uvicorn access-log request lines and redacts configured secrets from records and tracebacks."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "uvicorn.access" and isinstance(record.args, tuple) and len(record.args) >= 3 and isinstance(record.args[2], str):
            args = list(record.args)
            args[2] = mask_query_secrets(args[2])
            record.args = tuple(args)
        elif isinstance(record.msg, str):
            record.msg = redact(record.msg)
            if isinstance(record.args, tuple):
                record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        if record.exc_info and not record.exc_text:
            record.exc_text = redact("".join(traceback.format_exception(*record.exc_info)).rstrip())
            record.exc_info = None
        return True


def install_log_filters() -> None:
    f = MaskSecretsFilter()
    for name in ("uvicorn.access", "uvicorn.error", "uvicorn", "steve.extractor", "steve.security"):
        lg = logging.getLogger(name)
        if not any(isinstance(x, MaskSecretsFilter) for x in lg.filters):
            lg.addFilter(f)
