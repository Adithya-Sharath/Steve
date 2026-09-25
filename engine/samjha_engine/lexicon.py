"""Load and index lexicon.yaml."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .normalize import phrase_key, sound_key

LEXICON_PATH = Path(__file__).with_name("lexicon.yaml")


@dataclass(frozen=True)
class Entry:
    canonical: str
    category: str
    value: Any
    lang: str
    verified: bool = False
    variants: tuple[str, ...] = ()
    ambiguous: bool = False
    adjacent_only: bool = False
    negates: bool = False
    implicit: float | None = None
    requires_near: tuple[str, ...] = ()

    @property
    def forms(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for f in (self.canonical, *self.variants):
            f = " ".join(str(f).lower().split())
            if f:
                seen.setdefault(f, None)
        return tuple(seen)

    @property
    def is_number(self) -> bool:
        return self.category == "number"


@dataclass
class LangConfig:
    code: str
    name: str
    verified: bool
    suffixes: tuple[str, ...]
    min_stem: int


@dataclass
class Lexicon:
    entries: list[Entry]
    langs: dict[str, LangConfig]
    by_form: dict[str, list[Entry]] = field(default_factory=dict)
    by_key: dict[str, list[tuple[str, Entry]]] = field(default_factory=dict)
    by_first: dict[str, list[tuple[str, str, Entry]]] = field(default_factory=dict)  # first key char -> (form, key, entry)
    max_ngram: int = 1

    def __post_init__(self) -> None:
        by_form: dict[str, list[Entry]] = defaultdict(list)
        by_key: dict[str, list[tuple[str, Entry]]] = defaultdict(list)
        by_first: dict[str, list[tuple[str, str, Entry]]] = defaultdict(list)
        for e in self.entries:
            for form in e.forms:
                n_words = form.count(" ") + 1
                self.max_ngram = max(self.max_ngram, n_words)
                by_form[form].append(e)
                key = phrase_key(form) if n_words > 1 else sound_key(form)
                by_key[key].append((form, e))
                by_first[key[:1]].append((form, key, e))
        self.by_form = dict(by_form)
        self.by_key = dict(by_key)
        self.by_first = dict(by_first)

    def has_form(self, norm: str) -> bool:
        return norm in self.by_form

    def entries_for(self, lang: str | None = None, category: str | None = None) -> list[Entry]:
        return [e for e in self.entries if (lang is None or e.lang == lang) and (category is None or e.category == category)]


def _entry(raw: dict, lang: str, verified_default: bool) -> Entry:
    return Entry(
        canonical=str(raw["canonical"]),
        category=raw["category"],
        value=raw.get("value"),
        lang=lang,
        verified=bool(raw.get("verified", verified_default)),
        variants=tuple(str(v) for v in raw.get("variants", []) or []),
        ambiguous=bool(raw.get("ambiguous", False)),
        adjacent_only=bool(raw.get("adjacent_only", False)),
        negates=bool(raw.get("negates", False)),
        implicit=raw.get("implicit"),
        requires_near=tuple(str(x) for x in raw.get("requires_near", []) or []),
    )


def load_lexicon(path: Path | str | None = None) -> Lexicon:
    data = yaml.safe_load(Path(path or LEXICON_PATH).read_text(encoding="utf-8"))
    entries: list[Entry] = []
    langs: dict[str, LangConfig] = {}
    for code, block in data["languages"].items():
        verified = bool(block.get("verified", False))
        langs[code] = LangConfig(
            code=code,
            name=block.get("name", code),
            verified=verified,
            suffixes=tuple(sorted(block.get("suffixes", []) or [], key=len, reverse=True)),
            min_stem=int(block.get("min_stem", 4)),
        )
        for raw in block["entries"]:
            entries.append(_entry(raw, code, verified))
    return Lexicon(entries=entries, langs=langs)


@lru_cache(maxsize=1)
def get_lexicon() -> Lexicon:
    return load_lexicon()
