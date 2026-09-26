"""Output of Decode (D36): a `DecodedCard`. Wording rule: never "wrong" or "bad English"; say decoded, probably meant, often sounds like. No scores."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..schema import Span


class Change(BaseModel):
    span: Span
    heard: str
    meant: str
    reason: str
    confidence: float = Field(ge=0, le=1)
    source: str = "sound"  # sound | phrase | context


class PhraseHit(BaseModel):
    span: Span
    phrase: str
    literal: str
    social_meaning: str
    category: str = ""


class ActionValue(BaseModel):
    value: str
    evidence: Span | None = None


class Actions(BaseModel):
    where: ActionValue | None = None
    when: ActionValue | None = None
    what: ActionValue | None = None
    how_much: ActionValue | None = None


class Clarify(BaseModel):
    span: Span
    options: list[str]
    question: str
    slot: str = ""


class DecodedCard(BaseModel):
    original_text: str
    plain_english: str
    changes: list[Change] = []
    phrases: list[PhraseHit] = []
    actions: Actions = Actions()
    clarify: list[Clarify] = []
    tips: list[str] = []
    confidence: float = Field(default=1.0, ge=0, le=1)
    accent_used: str | None = None
    path: str = "typed"  # typed | voice
