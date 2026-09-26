"""Copy-paste detection: a reader who pastes the sender's message back has shown nothing about understanding.

similarity = rapidfuzz `token_set_ratio` on normalised text (0..1), as specified. On its own it is far too eager:
* it scores 100 whenever the reply's words are a SUBSET of the message's ("2 tablets after food" is a subset), and
* an honest English restatement ("1 drop 3 times a day for 10 days") reuses the message's words and also scores ~100.
So a reply is only a copy if it ALSO (a) is about as long as the message and (b) matches it in ORDER (`fuzz.ratio` on the
normalised strings > 0.85). Measured on our own data: real pastes score 97-100 on (b); genuine restatements <= 82.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from .normalize import clean_text

COPY_THRESHOLD = 0.85
MIN_LENGTH_RATIO = 0.6  # reply must have >= 60% as many words as the message
MIN_WORDS = 4
COPY_REASON = "Reply looks copied from the message; ask them to say it in their own words."
_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*")


def _words(text: str) -> list[str]:
    return _WORD.findall(clean_text(text).lower())


def copy_similarity(message: str, reply: str) -> float:
    m, r = _words(message), _words(reply)
    if not m or not r:
        return 0.0
    return fuzz.token_set_ratio(" ".join(m), " ".join(r)) / 100


def order_similarity(message: str, reply: str) -> float:
    m, r = _words(message), _words(reply)
    if not m or not r:
        return 0.0
    return fuzz.ratio(" ".join(m), " ".join(r)) / 100


def looks_copied(message: str | None, reply: str) -> bool:
    if not message or not reply.strip():
        return False
    m, r = _words(message), _words(reply)
    if len(r) < MIN_WORDS or len(r) < MIN_LENGTH_RATIO * len(m):
        return False
    return copy_similarity(message, reply) > COPY_THRESHOLD and order_similarity(message, reply) > COPY_THRESHOLD
