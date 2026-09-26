"""Request/response models. Mirrored by web/lib/types.ts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from steve_engine import Fact

Context = Literal["pharmacy", "workplace", "visa", "school", "other"]


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    sender_name: str = Field(default="", max_length=120)
    context: Context = "other"


class SuggestedFacts(BaseModel):
    message_id: str
    suggested_facts: list[Fact]
    extractor: str  # "regex" | "llm"
    note: str | None = None


class ConfirmIn(BaseModel):
    facts: list[Fact]


class ConfirmOut(BaseModel):
    reader_token: str
    reader_url: str


class ResultOut(BaseModel):
    fact_id: str
    status: str
    heard_value: Any | None = None
    expected_value: Any = None
    evidence: list[dict] = []
    confidence: float = 0
    reason: str = ""
    matched_terms: list[dict] = []
    flags: list[str] = []


class ReplyOut(BaseModel):
    id: str
    text: str
    source: str
    created_at: str
    results: list[ResultOut]


class LatestFact(BaseModel):
    fact_id: str
    status: str
    reply_id: str | None = None
    result: ResultOut | None = None


class MessageOut(BaseModel):
    id: str
    text: str
    sender_name: str
    context: str
    confirmed: bool
    demo: bool
    created_at: str
    reader_token: str | None = None
    reader_url: str | None = None
    facts: list[Fact]
    replies: list[ReplyOut] = []
    latest: list[LatestFact] = []
    aggregate: dict[str, int] = {}


class MessageSummary(BaseModel):
    id: str
    text: str
    sender_name: str
    context: str
    confirmed: bool
    demo: bool
    created_at: str
    reader_url: str | None = None
    fact_count: int
    reply_count: int
    aggregate: dict[str, int]


class FollowupOut(BaseModel):
    draft: str
    lang: str
    failed: list[dict]


class CheckIn(BaseModel):
    facts: list[Fact]
    reply: str = Field(max_length=4000)
    lang_hint: str | None = None
    message: str | None = Field(default=None, max_length=4000)  # the sender's text: enables copy-paste detection


class AnalyzeIn(BaseModel):
    reply: str = Field(max_length=4000)
    lang_hint: str | None = None
    facts: list[Fact] | None = None
    message: str | None = Field(default=None, max_length=4000)


class LlmToggle(BaseModel):
    enabled: bool


# ---- Decode (D45) -------------------------------------------------------------------------------------------------------------------------------

from steve_engine.decode import DecodedCard  # noqa: E402

REPLY_LANGUAGES = ("en", "ml", "hi", "ur", "tl", "bn")
ACCENT_HINTS = ("ar", "hi", "ml", "tl")
ReplyLanguage = Literal["en", "ml", "hi", "ur", "tl", "bn"]
NOT_SURE = "not_sure"


class DecodeIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    accent_hint: Literal["ar", "hi", "ml", "tl"] | None = None
    reply_language: ReplyLanguage | None = None


class TranslatedPhrase(BaseModel):
    phrase: str  # the local phrase as heard (kept as written: it is the thing being explained)
    literal: str
    social_meaning: str


class TranslatedCard(BaseModel):
    """The settled English card in the worker's language. Numbers, times, amounts and places are checked to match the English card exactly."""

    language: ReplyLanguage
    provider: str  # sarvam | gemini | fake
    verified_numbers: bool = True
    plain_english: str
    where: str | None = None
    when: str | None = None
    what: str | None = None
    how_much: str | None = None
    phrases: list[TranslatedPhrase] = []
    questions: list[str] = []
    tip: str | None = None


class DecodeResponse(BaseModel):
    card: DecodedCard | None = None  # None only when a voice note could not be decoded (see notes)
    translation: TranslatedCard | None = None
    transcript: str | None = None  # voice only
    decode_id: str | None = None  # present only while a clarifying question is open; expires after CLARIFY_TTL_SECONDS
    notes: list[str] = []  # human-readable fallbacks
    say_back: list[str] = []  # short plain English the worker can show the other person (text only)


class ClarifyIn(BaseModel):
    decode_id: str = Field(min_length=6, max_length=64)
    question_index: int = Field(ge=0, le=20)
    choice: str = Field(min_length=1, max_length=80)  # one of the question's options, or "not_sure"
