"""Hardening basics (D35): security headers, request-size cap, generic 500, log hygiene."""

import asyncio
import json
import logging

import pytest
from fastapi.testclient import TestClient
from test_api import MANGLISH, _flow

from app.main import app
from app.security import (
    GENERIC_500,
    JSON_CSP,
    BodyLimitMiddleware,
    MaskSecretsFilter,
    install_log_filters,
    mask_query_secrets,
    redact,
)
from app.settings import Settings, settings

KEY = "sk_" + "K" * 32


# ---- headers ---------------------------------------------------------------------------------------------------


def test_json_responses_carry_all_three_security_headers(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["content-security-policy"] == JSON_CSP == "default-src 'none'; frame-ancestors 'none'"


@pytest.mark.parametrize("make", [
    lambda c: c.get("/messages/does-not-exist"),  # 404
    lambda c: c.post("/messages", json={"text": ""}),  # 422
    lambda c: c.post("/settings/llm", json={"enabled": True}),  # 403
])
def test_error_responses_carry_them_too(client, make):
    r = make(client)
    assert r.status_code in (403, 404, 422)
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["content-security-policy"] == JSON_CSP


def test_rate_limited_and_preflight_responses_carry_them_too(anon, monkeypatch):
    monkeypatch.setattr(settings, "rl_default_per_min", 1)
    anon.get("/health")
    r = anon.get("/health")
    assert r.status_code == 429 and r.headers["x-content-type-options"] == "nosniff"
    pre = anon.options("/messages", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    assert pre.headers["x-content-type-options"] == "nosniff"


def test_the_csp_is_not_put_on_the_html_docs_page(anon):
    r = anon.get("/docs")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "content-security-policy" not in r.headers  # Swagger UI must be able to load its own scripts
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["referrer-policy"] == "no-referrer"


def test_headers_are_not_duplicated(client):
    r = client.get("/health")
    assert r.headers.raw.count((b"x-content-type-options", b"nosniff")) == 1


# ---- request size ----------------------------------------------------------------------------------------------


def test_default_limit_is_five_megabytes(monkeypatch):
    monkeypatch.delenv("MAX_BODY_BYTES", raising=False)
    assert Settings().max_body_bytes == 5 * 1024 * 1024


def test_a_body_over_the_limit_is_rejected_with_413(client, monkeypatch):
    monkeypatch.setattr(settings, "max_body_bytes", 2000)
    r = client.post("/messages", content=b'{"text": "' + b"a" * 3000 + b'"}', headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.json() == {"detail": "That request is too large."}
    assert r.headers["content-security-policy"] == JSON_CSP


def test_a_body_at_the_limit_is_accepted(client, monkeypatch):
    payload = json.dumps({"text": "Take 2 tablets.", "sender_name": "x", "context": "other"}).encode()
    monkeypatch.setattr(settings, "max_body_bytes", len(payload))
    assert client.post("/messages", content=payload, headers={"content-type": "application/json"}).status_code == 200
    monkeypatch.setattr(settings, "max_body_bytes", len(payload) - 1)
    assert client.post("/messages", content=payload, headers={"content-type": "application/json"}).status_code == 413


def test_the_real_default_rejects_five_megabytes_plus_one(client):
    r = client.post("/check", content=b"x" * (5 * 1024 * 1024 + 1), headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_a_large_audio_upload_is_a_413_not_a_400(client, monkeypatch):
    monkeypatch.setattr(settings, "max_body_bytes", 10_000)
    _, _, conf = _flow(client)
    r = client.post(f"/r/{conf['reader_token']}/reply", files={"audio": ("a.wav", b"R" * 50_000, "audio/wav")})
    assert r.status_code == 413
    assert client.post(f"/r/{conf['reader_token']}/reply", data={"text": MANGLISH}).status_code == 200  # small ones still fine


def _run(mw, headers, chunks):
    """Drive the raw ASGI middleware: returns (status, body) as the client would see them."""
    sent = []
    queue = [{"type": "http.request", "body": c, "more_body": i < len(chunks) - 1} for i, c in enumerate(chunks)]

    async def receive():
        return queue.pop(0) if queue else {"type": "http.disconnect"}

    async def send(m):
        sent.append(m)

    asyncio.run(mw({"type": "http", "method": "POST", "path": "/", "headers": headers}, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    return start["status"], b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")


async def _consuming_app(scope, receive, send):
    total = 0
    while True:
        m = await receive()
        if m["type"] != "http.request":
            raise RuntimeError("client went away")  # whatever the app does on a cut-off body
        total += len(m.get("body", b""))
        if not m.get("more_body"):
            break
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": str(total).encode()})


def test_a_lying_or_chunked_body_is_counted_not_trusted():
    mw = BodyLimitMiddleware(_consuming_app, max_bytes=100)
    assert _run(mw, [(b"content-length", b"10")], [b"x" * 60, b"x" * 60])[0] == 413  # says 10, sends 120
    assert _run(mw, [], [b"x" * 40, b"x" * 40, b"x" * 40])[0] == 413  # chunked, no Content-Length
    assert _run(mw, [(b"content-length", b"999999")], [b"x"])[0] == 413  # declared over the limit: refused up front
    assert _run(mw, [], [b"x" * 50, b"x" * 50]) == (200, b"100")  # exactly at the limit passes


# ---- generic 500 -----------------------------------------------------------------------------------------------


@pytest.fixture()
def boom(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "AIzaSySECRETSECRETSECRET")

    @app.get("/__boom", include_in_schema=False)
    def _boom():
        raise RuntimeError("upstream said: bad key AIzaSySECRETSECRETSECRET at /srv/steve/app/secret_module.py")

    yield
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/__boom"]


def test_an_unexpected_error_is_generic_and_leaks_nothing(boom, caplog):
    with caplog.at_level(logging.ERROR, logger="steve.security"), TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/__boom")
    assert r.status_code == 500 and r.json() == {"detail": GENERIC_500}
    body = r.text
    for leak in ("Traceback", "RuntimeError", "AIzaSy", "secret_module", "/srv/steve", "File \""):
        assert leak not in body, leak
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["content-security-policy"] == JSON_CSP
    logged = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "RuntimeError" in logged and "GET /__boom" in logged  # the operator still gets the detail ...
    assert "AIzaSySECRETSECRETSECRET" not in logged and "***" in logged  # ... with the key redacted


def test_client_errors_never_echo_keys_or_tracebacks(anon):
    bad = "sk_" + "Z" * 40 + "!"
    r = anon.get("/messages", headers={"X-Sender-Key": bad})
    assert r.status_code == 403 and bad not in r.text and "Traceback" not in r.text
    r = anon.get("/messages/x/stream", params={"key": bad})
    assert bad not in r.text
    r = anon.post("/settings/llm", json={"enabled": True}, headers={"X-Admin-Key": "guess-guess-guess"})
    assert "guess" not in r.text


# ---- logs ------------------------------------------------------------------------------------------------------


def test_key_query_values_are_masked():
    line = f"GET /messages/abc123/stream?key={KEY}&x=1 HTTP/1.1"
    out = mask_query_secrets(line)
    assert KEY not in out and "key=***&x=1" in out
    assert mask_query_secrets("/a?api_key=abc&b=2") == "/a?api_key=***&b=2"
    assert mask_query_secrets("/a?other=keep") == "/a?other=keep"
    assert mask_query_secrets(f"header value {KEY} leaked") == "header value sk_*** leaked"


def test_the_uvicorn_access_log_line_is_masked():
    """uvicorn formats the line from record.args; the filter must rewrite the request-line argument, keeping the shape."""
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "x", 1, '%s - "%s %s HTTP/%s" %d',
                            ("127.0.0.1:5000", "GET", f"/messages/abc/stream?key={KEY}", "1.1", 200), None)
    assert MaskSecretsFilter().filter(rec) is True
    assert len(rec.args) == 5 and rec.args[4] == 200
    assert KEY not in rec.getMessage() and "stream?key=***" in rec.getMessage()


def test_configured_secrets_are_redacted_from_records_and_tracebacks(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "AIzaSyABCDEF123456")
    monkeypatch.setattr(settings, "admin_key", "admin-secret-value-1234")
    assert redact("call failed for AIzaSyABCDEF123456 and admin-secret-value-1234") == "call failed for *** and ***"
    try:
        raise ValueError("boom AIzaSyABCDEF123456")
    except ValueError:
        import sys

        rec = logging.LogRecord("uvicorn.error", logging.ERROR, "x", 1, "Exception in ASGI application", (), sys.exc_info())
    MaskSecretsFilter().filter(rec)
    assert rec.exc_info is None and "AIzaSy" not in rec.exc_text and "ValueError" in rec.exc_text


def test_filters_are_installed_once_on_the_loggers_that_matter():
    install_log_filters()
    install_log_filters()
    for name in ("uvicorn.access", "uvicorn.error", "steve.extractor", "steve.security"):
        assert sum(isinstance(f, MaskSecretsFilter) for f in logging.getLogger(name).filters) == 1
