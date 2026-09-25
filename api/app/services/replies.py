"""Shared logic: load a message with facts/replies, run the engine on a reply, aggregate per-fact status."""

from __future__ import annotations

import uuid

from samjha_engine import Fact, check_reply
from sqlmodel import Session, select

from ..db import Fact as FactRow
from ..db import FactResultRow, Message, ReaderLink, Reply
from ..schemas import LatestFact, MessageOut, MessageSummary, ReplyOut, ResultOut
from ..settings import settings

STATUSES = ("understood", "wrong", "missing", "negated", "unclear")


def facts_for(session: Session, message_id: str) -> list[Fact]:
    rows = session.exec(select(FactRow).where(FactRow.message_id == message_id).order_by(FactRow.position)).all()
    return [
        Fact(id=r.fact_id, type=r.type, value=r.value, unit=r.unit, critical=r.critical, label=r.label) for r in rows
    ]


def reader_link(session: Session, message_id: str) -> ReaderLink | None:
    return session.exec(select(ReaderLink).where(ReaderLink.message_id == message_id)).first()


def _result_out(r: FactResultRow) -> ResultOut:
    return ResultOut(
        fact_id=r.fact_id, status=r.status, heard_value=r.heard_value, expected_value=r.expected_value,
        evidence=r.evidence or [], confidence=r.confidence, reason=r.reason, matched_terms=r.matched_terms or [],
    )


def replies_for(session: Session, message_id: str) -> list[ReplyOut]:
    replies = session.exec(select(Reply).where(Reply.message_id == message_id).order_by(Reply.created_at)).all()
    rows = session.exec(select(FactResultRow).where(FactResultRow.message_id == message_id)).all()
    by_reply: dict[str, list[FactResultRow]] = {}
    for r in rows:
        by_reply.setdefault(r.reply_id, []).append(r)
    return [
        ReplyOut(
            id=rp.id, text=rp.text, source=rp.source, created_at=rp.created_at.isoformat(),
            results=[_result_out(r) for r in sorted(by_reply.get(rp.id, []), key=lambda x: x.pk or 0)],
        )
        for rp in replies
    ]


def aggregate(facts: list[Fact], replies: list[ReplyOut]) -> list[LatestFact]:
    """Per fact: the most recent result that is not `missing`. A later reply that simply doesn't mention a fact
    never erases an earlier understood/wrong result."""
    state: dict[str, LatestFact] = {f.id: LatestFact(fact_id=f.id, status="missing") for f in facts}
    for rp in replies:
        for res in rp.results:
            if res.fact_id in state and res.status != "missing":
                state[res.fact_id] = LatestFact(fact_id=res.fact_id, status=res.status, reply_id=rp.id, result=res)
    return list(state.values())


def counts(latest: list[LatestFact]) -> dict[str, int]:
    c = {s: 0 for s in STATUSES}
    for x in latest:
        c[x.status] = c.get(x.status, 0) + 1
    c["total"] = len(latest)
    return c


def message_out(session: Session, m: Message) -> MessageOut:
    facts = facts_for(session, m.id)
    replies = replies_for(session, m.id)
    latest = aggregate(facts, replies)
    link = reader_link(session, m.id)
    return MessageOut(
        id=m.id, text=m.text, sender_name=m.sender_name, context=m.context, confirmed=m.confirmed, demo=m.demo,
        created_at=m.created_at.isoformat(),
        reader_token=link.token if link else None,
        reader_url=f"{settings.public_web_url}/r/{link.token}" if link else None,
        facts=facts, replies=replies, latest=latest, aggregate=counts(latest),
    )


def message_summary(session: Session, m: Message) -> MessageSummary:
    out = message_out(session, m)
    return MessageSummary(
        id=m.id, text=m.text, sender_name=m.sender_name, context=m.context, confirmed=m.confirmed, demo=m.demo,
        created_at=out.created_at, reader_url=out.reader_url, fact_count=len(out.facts),
        reply_count=len(out.replies), aggregate=out.aggregate,
    )


def process_reply(session: Session, m: Message, text: str, source: str = "text", lang_hint: str | None = None) -> ReplyOut:
    facts = facts_for(session, m.id)
    results = check_reply(facts, text, lang_hint)
    reply = Reply(id=uuid.uuid4().hex[:12], message_id=m.id, text=text, source=source)
    session.add(reply)
    session.flush()
    for r in results:
        d = r.model_dump(mode="json")
        session.add(
            FactResultRow(
                reply_id=reply.id, message_id=m.id, fact_id=r.fact_id, status=r.status.value,
                heard_value=d["heard_value"], expected_value=d["expected_value"], evidence=d["evidence"],
                confidence=r.confidence, reason=r.reason, matched_terms=d["matched_terms"],
            )
        )
    session.commit()
    session.refresh(reply)
    return ReplyOut(
        id=reply.id, text=reply.text, source=reply.source, created_at=reply.created_at.isoformat(),
        results=[ResultOut(**r.model_dump(mode="json")) for r in results],
    )
