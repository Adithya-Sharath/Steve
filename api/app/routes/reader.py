"""Reader endpoints. The reader NEVER sees facts, statuses or scores: only the message and a friendly prompt."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlmodel import Session

from ..clientip import client_ip
from ..db import Message, ReaderLink, get_session
from ..services.broker import broker
from ..services.replies import process_reply
from ..services.stt import STTUnavailable, get_stt
from ..settings import settings

router = APIRouter(tags=["reader"])

MAX_AUDIO_BYTES = 4 * 1024 * 1024
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(key: str) -> None:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > settings.reply_rate_window:
        q.popleft()
    if len(q) >= settings.reply_rate_limit:
        raise HTTPException(429, "Too many replies. Please wait a moment and try again.")
    q.append(now)


def _link_and_message(session: Session, token: str) -> tuple[ReaderLink, Message]:
    link = session.get(ReaderLink, token)
    m = session.get(Message, link.message_id) if link else None
    if not link or not m:
        raise HTTPException(404, "This link is not valid.")
    return link, m


@router.get("/r/{token}")
def reader_view(token: str, session: Session = Depends(get_session)):
    _, m = _link_and_message(session, token)
    return {
        "text": m.text,
        "sender_name": m.sender_name,
        "context": m.context,
        "stt_enabled": get_stt().enabled,
        "prompt": {
            "title": "Tell us in your own words",
            "body": "What do you need to do? Any language is fine: Malayalam, Hindi, Arabic, Tagalog, English, or a mix.",
        },
    }


@router.post("/r/{token}/reply")
async def reader_reply(
    token: str,
    request: Request,
    text: str | None = Form(default=None),
    lang_hint: str | None = Form(default=None),
    audio: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
):
    _, m = _link_and_message(session, token)
    rate_limit(f"{token}:{client_ip(request)}")

    source = "text"
    if audio is not None and audio.filename:
        stt = get_stt()
        if not stt.enabled:
            raise HTTPException(400, "Voice replies are not available right now. Please type your reply.")
        data = await audio.read(MAX_AUDIO_BYTES + 1)  # held in memory only, never persisted
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "That recording is too long. Please keep it under 30 seconds.")
        try:
            text = stt.transcribe(data, audio.content_type or "audio/wav", lang_hint)
        except STTUnavailable as e:
            raise HTTPException(503, str(e)) from e
        source = "voice"
    text = (text or "").strip()
    if not text:
        raise HTTPException(422, "Please say or type something.")
    if len(text) > 4000:
        raise HTTPException(413, "That reply is too long.")

    reply = process_reply(session, m, text, source, lang_hint)
    broker.publish(m.id, {"message_id": m.id, "reply": reply.model_dump()})
    return {"received": True}
