"""A small English tokenizer with CODE-POINT offsets into the original text (so emoji and other astral characters cannot shift a span)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN = re.compile(r"\d+(?:[.:]\d+)?(?:st|nd|rd|th|am|pm)?|[A-Za-z]+(?:['’][A-Za-z]+)*", re.I)


@dataclass(frozen=True)
class Token:
    i: int  # index in the token list
    text: str  # as written
    norm: str  # lower-case, curly apostrophes straightened
    start: int  # code-point offsets into the original string
    end: int


def tokenize(text: str) -> list[Token]:
    out = []
    for m in _TOKEN.finditer(text):
        raw = m.group()
        out.append(Token(len(out), raw, raw.lower().replace("’", "'"), m.start(), m.end()))
    return out
