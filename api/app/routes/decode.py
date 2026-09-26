"""Decode API (D45): `POST /decode`, `POST /decode/clarify`, `GET /decode/health`.

Text (JSON) or audio (multipart) in; a `DecodeResponse` out. Audio goes through Sarvam `transcribe` (en-IN) and then `decode(path="voice")`; text goes
through `decode(path="typed")`. Neither the text nor the audio is stored or logged; a clarifying question keeps the ORIGINAL TEXT in memory for 10 minutes
(see `services/decode_sessions.py`). Every worker is a device key `X-Worker-Key: wk_...` (only its hash is used).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.formparsers import MultiPartParser

from ..auth import worker_hash
from ..budget import snapshot, stt_budget
from ..ratelimit import limit, limit_worker
from ..schemas import ACCENT_HINTS, NOT_SURE, REPLY_LANGUAGES, ClarifyIn, DecodeIn, DecodeResponse
from ..services import decode_translation
from ..services.audio import duration_seconds
from ..services.decode_flow import respond, run_decode
from ..services.decode_sessions import Session, store
from ..services.stt import STTUnavailable, get_decode_stt
from ..settings import settings

# Starlette spools multipart files larger than 1 MB to a temp file on DISK. Audio is never stored (D45): keep uploads in memory (the body cap is 5 MB).
MultiPartParser.spool_max_size = 8 * 1024 * 1024

router = APIRouter(tags=["decode"])

VOICE_UNAVAILABLE = "Voice isn't available right now, please type or paste the message."
VOICE_LIMIT = "Voice is busy for today, please type or paste the message."
VOICE_FAILED = "I couldn't listen to that voice note, please try again or type the message."
NOTHING_HEARD = "I couldn't find anything to decode. Try again or paste the message."
NOT_SURE_HELP = "That's fine. You can show the other person the phrase below and ask again."


def _bad(msg: str, code: int = 422) -> HTTPException:
    return HTTPException(code, msg)


def _validate(hint: str | None, lang: str | None) -> None:
    if hint is not None and hint not in ACCENT_HINTS:
        raise _bad(f"accent_hint must be one of {', '.join(ACCENT_HINTS)}.")
    if lang is not None and lang not in REPLY_LANGUAGES:
        raise _bad(f"reply_language must be one of {', '.join(REPLY_LANGUAGES)}.")


async def _read_request(request: Request) -> tuple[str | None, bytes | None, str, str | None, str | None]:
    """-> (text, audio bytes, audio content type, accent_hint, reply_language)"""
    ctype = request.headers.get("content-type", "").lower()
    if ctype.startswith(("multipart/form-data", "application/x-www-form-urlencoded")):
        form = await request.form()
        upload = form.get("audio")
        audio, audio_type = None, ""
        if upload is not None and hasattr(upload, "read"):
            audio = await upload.read()
            audio_type = getattr(upload, "content_type", "") or ""
            await upload.close()
        raw = [form.get("text"), form.get("accent_hint"), form.get("reply_language")]
        await form.close()
        text, hint, lang = [v if isinstance(v, str) and v.strip() else None for v in raw]
        if not audio and not text:
            raise _bad("Send an audio file or some text.")
        _validate(hint, lang)
        return text, audio or None, audio_type, hint, lang
    try:
        body = DecodeIn.model_validate(json.loads(await request.body() or b"{}"))
    except (ValueError, ValidationError):
        raise _bad('Send JSON like {"text": "..."} or a multipart form with an audio file.') from None
    return body.text, None, "", body.accent_hint, body.reply_language


def _transcribe(audio: bytes, content_type: str) -> tuple[str, str | None]:
    """-> (transcript, note). Never raises: a voice problem becomes a friendly note."""
    stt = get_decode_stt()
    if not stt.enabled:
        return "", VOICE_UNAVAILABLE
    if not stt_budget.try_spend():
        return "", VOICE_LIMIT
    try:
        return stt.transcribe(audio, content_type, "en").strip(), None
    except STTUnavailable:
        return "", VOICE_FAILED


@router.post(
    "/decode",
    response_model=DecodeResponse,
    dependencies=[
        Depends(limit("decode", per_minute=lambda: settings.rl_decode_per_min, per_day=lambda: settings.rl_decode_per_day)),
        Depends(limit_worker("decode_worker", per_day=lambda: settings.decode_per_worker_day)),
    ],
)
async def decode_endpoint(request: Request, worker: str = Depends(worker_hash)) -> DecodeResponse:
    text, audio, audio_type, hint, lang = await _read_request(request)
    notes: list[str] = []
    transcript: str | None = None
    path = "typed"

    if audio is not None:
        if len(audio) > settings.decode_max_audio_bytes:
            raise HTTPException(413, "That voice note is too large. Please keep it under 30 seconds.")
        seconds = duration_seconds(audio)
        if seconds is not None and seconds > settings.decode_max_audio_seconds:
            raise HTTPException(413, f"That voice note is too long. Please keep it under {settings.decode_max_audio_seconds} seconds.")
        heard, note = await run_in_threadpool(_transcribe, audio, audio_type)
        del audio  # audio is never kept
        if note:
            notes.append(note)
        if heard:
            text, transcript, path = heard, heard, "voice"
        elif not text:
            return DecodeResponse(notes=notes or [NOTHING_HEARD])  # no card: the client falls back to typing
    if text is None or not text.strip():
        raise _bad("There is no text to decode.")

    session = Session(worker=worker, text=text, accent_hint=hint, path=path, reply_language=lang)
    card = await run_in_threadpool(run_decode, session)
    return respond(card, session=session, decode_id=None, transcript=transcript, notes=notes)


@router.post("/decode/clarify", response_model=DecodeResponse)
async def clarify_endpoint(body: ClarifyIn, worker: str = Depends(worker_hash)) -> DecodeResponse:
    session = store.get(body.decode_id, worker)
    if session is None:
        raise HTTPException(404, "That question has expired. Please decode the message again.")
    card = await run_in_threadpool(run_decode, session)
    if body.question_index >= len(card.clarify):
        raise _bad("There is no such question.")
    q = card.clarify[body.question_index]
    choice = body.choice.strip()
    notes: list[str] = []
    if choice.lower() == NOT_SURE:
        session.resolved[q.span.start] = None
        notes.append(NOT_SURE_HELP)
    else:
        match = next((o for o in q.options if o.lower() == choice.lower()), None)
        if match is None:
            raise _bad("That is not one of the choices.")
        session.resolved[q.span.start] = match
    card = await run_in_threadpool(run_decode, session)
    transcript = session.text if session.path == "voice" else None
    return respond(card, session=session, decode_id=body.decode_id, transcript=transcript, notes=notes)


@router.get("/decode/health")
def decode_health() -> dict:
    """What works right now, with no secrets: features, languages and today's remaining budgets (numbers only)."""
    budget = snapshot()
    return {
        "typed": True,
        "voice": bool(get_decode_stt().enabled and budget["stt_remaining"] != 0),
        "translation": decode_translation.availability(),
        "languages": list(REPLY_LANGUAGES),
        "accent_hints": list(ACCENT_HINTS),
        "budget": {"stt_remaining": budget["stt_remaining"], "stt_cap": budget["stt_cap"]},
        "limits": {"audio_seconds": settings.decode_max_audio_seconds, "audio_bytes": settings.decode_max_audio_bytes,
                   "clarify_minutes": settings.clarify_ttl_seconds // 60},
    }
