from __future__ import annotations

import asyncio
import hmac
import json
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, delete, select

from ..auth import FORBIDDEN, sender_hash, sender_hash_header_or_query
from ..db import Fact as FactRow
from ..db import Message, ReaderLink, get_session
from ..schemas import (
    ConfirmIn,
    ConfirmOut,
    FollowupOut,
    MessageIn,
    MessageOut,
    MessageSummary,
    SuggestedFacts,
)
from ..services import replies as svc
from ..services.broker import broker
from ..services.extractor import suggest_facts
from ..services.followup import build_followup
from ..settings import settings

router = APIRouter(tags=["messages"])


def _get(session: Session, message_id: str, owner: str) -> Message:
    """Load a message the caller owns. Unknown id -> 404; someone else's (or legacy) message -> 403."""
    m = session.get(Message, message_id)
    if not m:
        raise HTTPException(404, "Message not found")
    if not m.owner_hash or not hmac.compare_digest(m.owner_hash, owner):
        raise HTTPException(403, FORBIDDEN)
    return m


@router.post("/messages", response_model=SuggestedFacts)
def create_message(body: MessageIn, owner: str = Depends(sender_hash), session: Session = Depends(get_session)):
    m = Message(id=uuid.uuid4().hex[:10], text=body.text.strip(), sender_name=body.sender_name.strip(), context=body.context, owner_hash=owner)
    session.add(m)
    session.commit()
    facts, extractor, note = suggest_facts(m.text)
    return SuggestedFacts(message_id=m.id, suggested_facts=facts, extractor=extractor, note=note)


@router.post("/messages/{message_id}/confirm", response_model=ConfirmOut)
def confirm(message_id: str, body: ConfirmIn, owner: str = Depends(sender_hash), session: Session = Depends(get_session)):
    m = _get(session, message_id, owner)
    if not body.facts:
        raise HTTPException(422, "Add at least one fact to check.")
    ids = [f.id for f in body.facts]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Fact ids must be unique.")
    session.exec(delete(FactRow).where(FactRow.message_id == m.id))
    for i, f in enumerate(body.facts):
        session.add(
            FactRow(message_id=m.id, fact_id=f.id, type=f.type.value, value=f.value, unit=f.unit,
                    critical=f.critical, label=f.label, position=i)
        )
    m.confirmed = True
    session.add(m)
    link = svc.reader_link(session, m.id)
    if not link:
        link = ReaderLink(token=secrets.token_urlsafe(9), message_id=m.id)
        session.add(link)
    session.commit()
    return ConfirmOut(reader_token=link.token, reader_url=f"{settings.public_web_url}/r/{link.token}")


@router.get("/messages", response_model=list[MessageSummary])
def list_messages(owner: str = Depends(sender_hash), session: Session = Depends(get_session), limit: int = Query(50, le=200)):
    rows = session.exec(
        select(Message).where(Message.confirmed == True, Message.owner_hash == owner).order_by(Message.created_at.desc()).limit(limit)  # noqa: E712
    ).all()
    return [svc.message_summary(session, m) for m in rows]


@router.get("/messages/{message_id}", response_model=MessageOut)
def get_message(message_id: str, owner: str = Depends(sender_hash), session: Session = Depends(get_session)):
    return svc.message_out(session, _get(session, message_id, owner))


@router.get("/messages/{message_id}/stream")
async def stream(message_id: str, owner: str = Depends(sender_hash_header_or_query), session: Session = Depends(get_session)):
    _get(session, message_id, owner)
    q = broker.subscribe(message_id)

    async def gen():
        try:
            yield "retry: 3000\n\n"
            yield f"event: ready\ndata: {json.dumps({'message_id': message_id})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"event: reply\ndata: {json.dumps(event)}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            broker.unsubscribe(message_id, q)

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/messages/{message_id}/followup", response_model=FollowupOut)
def followup(message_id: str, lang: str | None = None, owner: str = Depends(sender_hash), session: Session = Depends(get_session)):
    m = _get(session, message_id, owner)
    out = svc.message_out(session, m)
    latest = {x.fact_id: x.status for x in out.latest}
    draft, used_lang, failed = build_followup(m.text, [{"fact_id": f.id, "label": f.label} for f in out.facts], latest, lang)
    return FollowupOut(draft=draft, lang=used_lang, failed=failed)
