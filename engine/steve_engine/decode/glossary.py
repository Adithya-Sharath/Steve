"""The UAE phrase glossary (Decode, D36): yalla, khalas, inshallah, "one minute" ... Loaded from `glossary.yaml`; every entry is `verified: false` until a
native speaker reviews it. Matching is by ear: exact for short words, fuzzy for words of five letters or more (yalla / yala / yallah), and a run of
words matches even when spaces differ ("in sha allah" / "inshallah"). Plain English words are never matched fuzzily.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml
from rapidfuzz.distance import Levenshtein

from ..schema import Span
from .phonetics import zipf
from .schema import PhraseHit
from .tokens import Token

GLOSSARY_PATH = Path(__file__).with_name("glossary.yaml")
CATEGORIES = {"greeting", "urgency", "agreement", "time", "religious-expression", "workplace", "address", "politeness"}
NO_SUBSTITUTION = {"time", "workplace"}  # their `plain` explains the phrase; it is not a word-for-word replacement
MAX_WORDS = 4
_STRIP = re.compile(r"[^a-z0-9 ]")


@dataclass(frozen=True)
class Entry:
    phrase: str
    variants: tuple[str, ...]
    plain: str
    literal: str
    social_meaning: str
    example: str
    category: str

    @property
    def substitute(self) -> bool:
        return self.category not in NO_SUBSTITUTION


def _norm(s: str) -> tuple[str, ...]:
    return tuple(_STRIP.sub("", s.lower().replace("’", "'").replace("'", "")).split())


@cache
def load_glossary(path: str | None = None) -> tuple[Entry, ...]:
    data = yaml.safe_load(Path(path or GLOSSARY_PATH).read_text(encoding="utf-8"))
    if data.get("verified") is not False:
        raise ValueError("glossary.yaml must be verified: false until a native speaker signs it off (D36)")
    seen: set[str] = set()
    out = []
    for raw in data["entries"]:
        if raw.get("verified") is not False:
            raise ValueError(f"glossary entry {raw.get('phrase')!r} must be verified: false")
        for key in ("phrase", "plain", "literal", "social_meaning", "example", "category"):
            if not str(raw.get(key) or "").strip():
                raise ValueError(f"glossary entry {raw.get('phrase')!r} is missing {key}")
        if raw["category"] not in CATEGORIES:
            raise ValueError(f"glossary entry {raw['phrase']!r}: unknown category {raw['category']!r}")
        if raw["phrase"] in seen:
            raise ValueError(f"glossary entry {raw['phrase']!r} is listed twice")
        seen.add(raw["phrase"])
        out.append(Entry(raw["phrase"], tuple(str(v) for v in raw.get("variants") or ()), raw["plain"], raw["literal"], raw["social_meaning"], raw["example"], raw["category"]))
    return tuple(out)


@cache
def _index() -> tuple[dict[tuple[str, ...], Entry], dict[str, Entry], dict[str, Entry]]:
    """exact word-tuple index, joined-string index (spaces ignored) and single-word fuzzy index."""
    exact: dict[tuple[str, ...], Entry] = {}
    joined: dict[str, Entry] = {}
    single: dict[str, Entry] = {}
    for e in load_glossary():
        for form in (e.phrase, *e.variants):
            t = _norm(form)
            if not t or len(t) > MAX_WORDS:
                continue
            exact.setdefault(t, e)
            joined.setdefault("".join(t), e)
            if len(t) == 1:
                single.setdefault(t[0], e)
    return exact, joined, single


def _fuzzy_single(word: str, single: dict[str, Entry]) -> Entry | None:
    """A spelling-by-ear match for a word of five letters or more that is not itself a common English word."""
    if len(word) < 5 or (zipf(word) >= 3.5):
        return None
    limit = 1 if len(word) <= 6 else 2
    best, best_d = None, limit + 1
    for key, e in single.items():
        if len(key) >= 5 and abs(len(key) - len(word)) <= limit:
            d = Levenshtein.distance(word, key, score_cutoff=limit)
            if d <= limit and d < best_d:
                best, best_d = e, d
    return best


@dataclass(frozen=True)
class Hit:
    entry: Entry
    first: int  # token indexes, inclusive
    last: int
    span: Span


def find_phrases(tokens: list[Token], text: str) -> list[Hit]:
    exact, joined, single = _index()
    used: set[int] = set()
    hits: list[Hit] = []
    for n in range(MAX_WORDS, 0, -1):
        for i in range(0, len(tokens) - n + 1):
            if any(k in used for k in range(i, i + n)):
                continue
            words = tuple(t.norm.replace("'", "") for t in tokens[i : i + n])
            entry = exact.get(words) or (joined.get("".join(words)) if n > 1 else None)
            if entry is None and n == 1:
                entry = _fuzzy_single(words[0], single)
            if entry is None:
                continue
            used.update(range(i, i + n))
            start, end = tokens[i].start, tokens[i + n - 1].end
            hits.append(Hit(entry, i, i + n - 1, Span(start=start, end=end, text=text[start:end])))
    return sorted(hits, key=lambda h: h.first)


def to_phrase_hit(h: Hit) -> PhraseHit:
    e = h.entry
    return PhraseHit(span=h.span, phrase=e.phrase, literal=e.literal, social_meaning=e.social_meaning, category=e.category)
