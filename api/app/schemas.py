"""Request/response models. Mirrored by web/lib/types.ts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from samjha_engine import Fact

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
