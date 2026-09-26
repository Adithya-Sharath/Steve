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
from steve_engine.schema import Span  # noqa: E402

REPLY_LANGUAGES = ("en", "ml", "hi", "ur", "tl", "bn")
ACCENT_HINTS = ("ar", "hi", "ml", "tl")
ReplyLanguage = Literal["en", "ml", "hi", "ur", "tl", "bn"]
NOT_SURE = "not_sure"


class ErrorOut(BaseModel):
    """Every non-2xx answer has this shape (FastAPI's default): a human-readable `detail`. 429 also carries a `Retry-After` header (seconds)."""

    detail: str


class DecodeIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    accent_hint: Literal["ar", "hi", "ml", "tl"] | None = None
    reply_language: ReplyLanguage | None = None
    model_config = {"json_schema_extra": {"examples": [{"text": "yalla habibi come to the barking gate tree", "accent_hint": "ar", "reply_language": "ml"}]}}


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


class TranslationAvailability(BaseModel):
    available: bool
    languages: dict[str, list[str]] = {}  # language -> provider names that could serve it right now (names only)
    budget_remaining: int = -1


class DecodeHealthOut(BaseModel):
    """`GET /decode/health`: what works right now. No secrets, only names and numbers."""

    typed: bool
    voice: bool
    translation: TranslationAvailability
    languages: list[ReplyLanguage]
    accent_hints: list[Literal["ar", "hi", "ml", "tl"]]
    budget: dict[str, int]  # stt_remaining, stt_cap (-1 = unlimited)
    limits: dict[str, int]  # audio_seconds, audio_bytes, clarify_minutes


class ClarifyIn(BaseModel):
    decode_id: str = Field(min_length=6, max_length=64)
    question_index: int = Field(ge=0, le=20)
    choice: str = Field(min_length=1, max_length=80)  # one of the question's options, or "not_sure"
    model_config = {"json_schema_extra": {"examples": [{"decode_id": "kR3x9Q0aV2mZ", "question_index": 0, "choice": "parking"}]}}


class InspectIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    accent_hint: Literal["ar", "hi", "ml", "tl"] | None = None
    path: Literal["typed", "voice"] = "typed"
    model_config = {"json_schema_extra": {"examples": [{"text": "yalla habibi come to the barking gate tree", "accent_hint": "ar", "path": "typed"}]}}


class InspectToken(BaseModel):
    i: int
    text: str
    start: int
    end: int


class InspectGlossary(BaseModel):
    phrase: str
    span: Span
    category: str


class InspectSlot(BaseModel):
    token: str
    kind: str  # where | where_or_when | when | number | amount | what | action
    expects: list[str]  # the kinds of word the slot would normally hold
    trigger: str  # the word that created the slot ("to", "at", "gate" ...)


class InspectCandidate(BaseModel):
    word: str
    score: float


class InspectExamined(BaseModel):
    token: str
    slot: str
    decision: str  # fits | no_alternative | keep | rewrite | clarify
    best: str | None = None
    margin: float = 0.0
    options: list[str] = []
    candidates: list[InspectCandidate] = []
    original_score: float = 0.0


class InspectOut(BaseModel):
    """`POST /decode/inspect`: every stage of one decode (tokens, glossary, critical slots, candidates and the decision for each examined word, the words as meant, the card)."""

    path: Literal["typed", "voice"]
    tokens: list[InspectToken]
    glossary: list[InspectGlossary]
    slots: list[InspectSlot]
    examined: list[InspectExamined]
    effective_words: list[str]
    unresolved_tokens: list[int]
    card: DecodedCard


class EvalRow(BaseModel):
    metric: str
    value: str
    detail: str | None = None


class EvalSection(BaseModel):
    id: str
    title: str
    label: str  # the label that must travel with these numbers (synthetic, author-written, tuned on it ...)
    note: str | None = None
    rows: list[EvalRow]


class DecodeEvalOut(BaseModel):
    """`GET /decode/eval`: the Decode numbers, each section with its label, read from a committed results file."""

    available: bool
    message: str | None = None
    generated_from: list[str] = []
    caveats: list[str] = []
    sections: list[EvalSection] = []


class DecodeExample(BaseModel):
    """One ready-made input and what the engine returns for it RIGHT NOW (computed per request, never stored text)."""

    id: str
    label: str
    request: DecodeIn  # send this to POST /decode to get the same card, then answer any question with POST /decode/clarify
    response: DecodeResponse


class DecodeExamples(BaseModel):
    examples: list[DecodeExample]
    computed_live: bool = True
