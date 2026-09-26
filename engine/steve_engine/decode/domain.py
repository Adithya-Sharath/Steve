"""Domain vocabulary for Decode: which words are places, times, numbers, amounts, negations and actions in a worker's day.

The lists in `domain.yaml` are working lists, every one `verified: false` (D36). `dont_touch` is the set of words the voice safety net must NEVER rewrite
silently (D41): negations, numbers, amounts and time words. Rewriting "not" or "five" without asking could reverse or corrupt an instruction, so those
can only lead to a clarifying question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

DOMAIN_PATH = Path(__file__).with_name("domain.yaml")
CATEGORIES = ("place", "time", "number", "amount", "negation", "action")
_DIGITS = re.compile(r"^\d+([.,:]\d+)?(st|nd|rd|th)?$")
_CLOCK = re.compile(r"^\d{1,2}([:.]\d{2})?(am|pm)$")


@dataclass(frozen=True)
class Domain:
    words: dict[str, frozenset[str]]
    place_triggers: frozenset[str]
    time_triggers: frozenset[str]
    determiners: frozenset[str]
    verified: bool = False
    dont_touch: frozenset[str] = field(default_factory=frozenset)

    def category(self, word: str) -> str | None:
        """The FIRST matching category in the order place, time, number, amount, negation, action (a word is counted once)."""
        w = word.lower()
        if _DIGITS.match(w) or _CLOCK.match(w):
            return "number"
        for c in CATEGORIES:
            if w in self.words[c]:
                return c
        return None

    def in_category(self, word: str, category: str) -> bool:
        w = word.lower()
        if category == "number" and (_DIGITS.match(w) or _CLOCK.match(w)):
            return True
        return w in self.words[category]

    def is_dont_touch(self, word: str) -> bool:
        w = word.lower()
        return w in self.dont_touch or bool(_DIGITS.match(w) or _CLOCK.match(w))


def load_domain(path: Path | str | None = None) -> Domain:
    data = yaml.safe_load(Path(path or DOMAIN_PATH).read_text(encoding="utf-8"))
    unknown = set(data["categories"]) - set(CATEGORIES)
    if unknown:
        raise ValueError(f"unknown domain categories: {sorted(unknown)}")
    for c in CATEGORIES:
        bad = [w for w in data["categories"].get(c, []) if not isinstance(w, str)]
        if bad:  # YAML reads a bare no / yes / on / off as a boolean: quote such words
            raise ValueError(f"domain category {c!r} has non-string entries {bad!r} (quote words like \"no\")")
    words = {c: frozenset(w.lower() for w in data["categories"].get(c, [])) for c in CATEGORIES}
    if data.get("verified") is not False:
        raise ValueError("domain.yaml must be verified: false until a reviewer signs it off (D36)")
    # units of time ("day", "hours") can be rewritten like any word; named times (weekdays, prayers, "tomorrow", "am") cannot
    units = {"time", "day", "days", "week", "weeks", "month", "months", "minute", "minutes", "hour", "hours"}
    dont = words["negation"] | words["number"] | words["amount"] | (words["time"] - units)
    return Domain(
        words=words,
        place_triggers=frozenset(data["place_triggers"]),
        time_triggers=frozenset(data["time_triggers"]),
        determiners=frozenset(data["determiners"]),
        verified=False,
        dont_touch=frozenset(dont),
    )


@lru_cache(maxsize=1)
def get_domain() -> Domain:
    return load_domain()
