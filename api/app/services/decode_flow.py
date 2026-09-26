"""Turn a decoded card into the API response (D45): notes, the clarify state, "say it back" phrases, and (Phase 5) the translation.

Shared by `POST /decode`, `POST /decode/clarify` and the WhatsApp webhook, so all channels behave the same.
"""

from __future__ import annotations

import logging

from steve_engine.decode import DecodedCard, decode

from ..schemas import DecodeResponse
from .decode_sessions import Session, store

log = logging.getLogger("steve.decode")  # never log text, transcripts or audio here (tested)

SAY_SLOWLY = "Can you say that again slowly, please?"
WRITE_IT = "Can you write it down for me, please?"
MAX_SAY_BACK = 3


def say_back(card: DecodedCard) -> list[str]:
    """Short, plain English the worker can SHOW or read to the other person. Text only. Built from open questions ("Sorry, parking or barking?")."""
    out: list[str] = []
    for q in [*card.clarify, *card.skipped]:
        opts = [o for o in q.options if o]
        if len(opts) >= 2:
            out.append(f"Sorry, {opts[0].lower()} or {opts[1].lower()}?")
    if card.clarify or card.skipped or not card.plain_english.strip():
        out += [SAY_SLOWLY, WRITE_IT]
    else:
        out.append(SAY_SLOWLY)
    return list(dict.fromkeys(out))[:MAX_SAY_BACK]


def run_decode(session: Session) -> DecodedCard:
    return decode(session.text, session.accent_hint, session.path, resolved=session.resolved or None)


def respond(card: DecodedCard, *, session: Session, decode_id: str | None, transcript: str | None, notes: list[str]) -> DecodeResponse:
    """Build the response. Keeps or drops the clarify state depending on whether a question is still open."""
    from . import decode_translation  # local: Phase 5 seam

    if card.clarify:
        decode_id = decode_id or store.create(session)
    else:
        if decode_id:
            store.delete(decode_id)
        decode_id = None
    translation, extra = decode_translation.translate_for(card, session.reply_language)
    return DecodeResponse(card=card, translation=translation, transcript=transcript, decode_id=decode_id, notes=[*notes, *extra], say_back=say_back(card))
