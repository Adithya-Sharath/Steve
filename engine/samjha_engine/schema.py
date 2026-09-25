"""Public data model. Mirrors web/lib/types.ts — keep the two in sync."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FactType(str, Enum):
    dose = "dose"  # value: number, unit: tablet|ml|puff|drop|capsule|spoon (+ bottle|photo|form|copy, see DECISIONS D2)
    frequency = "frequency"  # value: times per day (float, e.g. 0.5 for alternate days)
    timing = "timing"  # value: tag or list of tags {before_food, after_food, morning, noon, evening, night, bedtime, empty_stomach}
    duration = "duration"  # value: number; unit day (default) | hour | minute
    date = "date"  # value: ISO date, weekday name, or clock time "HH:MM"
    amount = "amount"  # value: number, unit: currency code
    condition = "condition"  # value: {trigger, action: stop|call|come_back|continue|avoid, text}


class Status(str, Enum):
    understood = "understood"
    wrong = "wrong"
    missing = "missing"
    negated = "negated"
    unclear = "unclear"


class Fact(BaseModel):
    id: str
    type: FactType
    value: Any
    unit: str | None = None
    critical: bool = True
    label: str  # human label e.g. "2 tablets"


class Span(BaseModel):
    start: int  # code-point offsets into the ORIGINAL reply text
    end: int
    text: str


class FactResult(BaseModel):
    fact_id: str
    status: Status
    heard_value: Any | None = None
    expected_value: Any
    evidence: list[Span] = Field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""
    matched_terms: list[dict] = Field(default_factory=list)
