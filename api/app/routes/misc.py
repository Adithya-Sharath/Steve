"""health, stateless check/analyze, eval results, demo seed, runtime LLM toggle."""

from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, delete, select
from steve_engine import check_reply, inspect_reply, lexicon_stats

from ..auth import admin_required, sender_hash
from ..budget import snapshot
from ..db import Fact as FactRow
from ..db import FactResultRow, Message, ReaderLink, Reply, get_session
from ..ratelimit import limit
from ..schemas import AnalyzeIn, CheckIn, LlmToggle
from ..services.replies import process_reply
from ..services.stt import get_stt
from ..settings import settings

router = APIRouter()


@router.get("/health", tags=["health"])
def health():
    return {
        "status": "ok",
        "llm_enabled": settings.llm_available,
        "llm_switch": settings.llm_enabled,
        "llm_key_present": bool(settings.gemini_api_key),
        "admin_toggle_available": bool(settings.admin_key),
        "budget": snapshot(),  # numbers only: daily caps and calls left (-1 = unlimited)
        "stt_enabled": get_stt().enabled,
        "lexicon": lexicon_stats(),
        "version": "0.1.0",
    }


@router.post("/settings/llm", tags=["settings"])
def set_llm(body: LlmToggle, _admin: None = Depends(admin_required)):
    """Runtime toggle for the wrapper test: with it OFF, everything still works. GLOBAL, so admin-only (X-Admin-Key)."""
    settings.llm_enabled = body.enabled
    return {"llm_switch": settings.llm_enabled, "llm_enabled": settings.llm_available}


@router.post("/check", tags=["engine"], dependencies=[Depends(limit("check", per_minute=lambda: settings.rl_check_per_min))])
def check(body: CheckIn):
    """Stateless: {facts, reply} -> per-fact results. Used by the landing playground and the eval."""
    return [r.model_dump(mode="json") for r in check_reply(body.facts, body.reply, body.lang_hint, message=body.message)]


@router.post("/analyze", tags=["engine"], dependencies=[Depends(limit("analyze", per_minute=lambda: settings.rl_check_per_min))])
def analyze(body: AnalyzeIn):
    """Stage-by-stage view (tokens, lexicon matches, slots, results) for /how-it-works."""
    return inspect_reply(body.reply, body.lang_hint, body.facts, message=body.message)


@router.get("/eval/results", tags=["eval"])
def eval_results():
    path = settings.eval_dir / "latest.json"
    if not path.exists():
        return {"available": False, "message": "No evaluation results yet. Run `make eval`."}
    return {"available": True, **json.loads(path.read_text(encoding="utf-8"))}


def _scenarios() -> list[dict]:
    path = settings.data_dir / "scenarios.json"
    if not path.exists():
        raise HTTPException(404, "scenarios.json not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/demo/scenarios", tags=["demo"])
def demo_scenarios():
    return _scenarios()


@router.post("/demo/seed", tags=["demo"], dependencies=[Depends(limit("seed", per_minute=lambda: settings.rl_seed_per_min))])
def demo_seed(owner: str = Depends(sender_hash), session: Session = Depends(get_session)):
    """(Re)load data/scenarios.json as confirmed demo messages OWNED BY THE CALLER (ids carry a per-sender suffix).
    The first one gets a pre-baked 'subtle mistake' reply."""
    suffix = owner[:6]
    for old in session.exec(select(Message).where(Message.demo == True, Message.owner_hash == owner)).all():  # noqa: E712
        mid = old.id
        session.exec(delete(FactResultRow).where(FactResultRow.message_id == mid))
        session.exec(delete(Reply).where(Reply.message_id == mid))
        session.exec(delete(FactRow).where(FactRow.message_id == mid))
        session.exec(delete(ReaderLink).where(ReaderLink.message_id == mid))
        session.exec(delete(Message).where(Message.id == mid))
    session.commit()

    seeded = []
    for i, sc in enumerate(_scenarios()):
        m = Message(id=f"demo-{sc['id']}-{suffix}", text=sc["text"], sender_name=sc["sender_name"], context=sc["context"],
                    confirmed=True, demo=True, owner_hash=owner)
        session.add(m)
        for pos, f in enumerate(sc["facts"]):
            session.add(FactRow(message_id=m.id, fact_id=f["id"], type=f["type"], value=f["value"], unit=f.get("unit"),
                                critical=f.get("critical", True), label=f["label"], position=pos))
        link = ReaderLink(token=f"demo-{sc['id']}-{secrets.token_urlsafe(4)}", message_id=m.id)
        session.add(link)
        session.commit()
        if i == 0:
            preset = next(p for p in sc["presets"] if p["kind"] == "subtle_mistake")
            process_reply(session, m, preset["text"], "text", None)
        seeded.append({"message_id": m.id, "reader_token": link.token, "scenario": sc["id"]})
    return {"seeded": seeded}
