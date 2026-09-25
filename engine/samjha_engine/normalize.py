"""Cleaning and tokenization that KEEPS character offsets into the original text.

Offsets are Python code-point offsets into the untouched input (emoji, mixed case and all), so
evidence spans can always be sliced straight out of the reply the reader actually wrote.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

# Length-preserving (1 char -> 1 char) so offsets never drift.
_CHAR_MAP = {}
for _i, _c in enumerate("٠١٢٣٤٥٦٧٨٩"):  # Arabic-Indic
    _CHAR_MAP[ord(_c)] = str(_i)
for _i, _c in enumerate("۰۱۲۳۴۵۶۷۸۹"):  # Extended Arabic-Indic (Urdu/Persian)
    _CHAR_MAP[ord(_c)] = str(_i)
for _c in "’‘`´ʼ":
    _CHAR_MAP[ord(_c)] = "'"
_TRANSLATE = str.maketrans(_CHAR_MAP)

_TOKEN_RE = re.compile(
    r"""
    (?P<iso>\d{4}-\d{2}-\d{2})(?![^\W_])
  | (?P<clock>\d{1,2}:\d{2})(?![^\W_])
  | (?P<thousands>\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?![^\W_])
  | (?P<decimal>\d+\.\d+)(?![^\W_])
  | (?P<word>[^\W_]+(?:'[^\W_]+)*)
    """,
    re.VERBOSE,
)

_SENT_BREAK = re.compile(r"[.!?;\n\r؟।]")
_CLAUSE_BREAK = re.compile(r"[,:،\-–—/|()]")
_DIGITS = re.compile(r"^\d+$")
_GLUED = re.compile(r"^(\d+)([^\W\d_]+)$")


@dataclass
class Token:
    text: str  # original slice
    norm: str  # lowercased, digits normalised
    start: int
    end: int
    idx: int
    sent: int
    clause: int
    kind: str  # word | num | clock | iso
    num: float | None = None
    extra: dict = field(default_factory=dict)

    @property
    def is_word(self) -> bool:
        return self.kind == "word"


def clean_text(text: str) -> str:
    """Length-preserving normalisation of digits/quotes (used before tokenizing)."""
    return text.translate(_TRANSLATE)


def tokenize(text: str) -> list[Token]:
    cleaned = clean_text(text)
    tokens: list[Token] = []
    sent = 0
    clause = 0
    prev_end = 0
    for m in _TOKEN_RE.finditer(cleaned):
        gap = cleaned[prev_end : m.start()]
        if _SENT_BREAK.search(gap):
            sent += 1
            clause += 1
        elif _CLAUSE_BREAK.search(gap):
            clause += 1
        kind_name = m.lastgroup
        raw = cleaned[m.start() : m.end()]
        orig = text[m.start() : m.end()]
        num = None
        if kind_name == "word":
            if _DIGITS.match(raw):
                kind, num = "num", float(raw)
            else:
                kind = "word"
        elif kind_name in ("decimal", "thousands"):
            kind, num = "num", float(raw.replace(",", ""))
        elif kind_name == "clock":
            kind = "clock"
        else:
            kind = "iso"
        tokens.append(
            Token(
                text=orig,
                norm=raw.lower(),
                start=m.start(),
                end=m.end(),
                idx=len(tokens),
                sent=sent,
                clause=clause,
                kind=kind,
                num=num,
            )
        )
        prev_end = m.end()
    return tokens


def split_glued(tokens: list[Token], is_known: Callable[[str], bool]) -> list[Token]:
    """'5days' -> '5' + 'days', but leave lexicon words like '3ashra' / '7abba' alone."""
    out: list[Token] = []
    for t in tokens:
        m = _GLUED.match(t.norm) if t.kind == "word" else None
        if m and not is_known(t.norm):
            digits, letters = m.group(1), m.group(2)
            split_at = t.start + len(digits)
            out.append(
                Token(t.text[: len(digits)], digits, t.start, split_at, 0, t.sent, t.clause, "num", float(digits))
            )
            out.append(Token(t.text[len(digits) :], letters, split_at, t.end, 0, t.sent, t.clause, "word"))
        else:
            out.append(t)
    for i, t in enumerate(out):
        t.idx = i
    return out


# ---------------------------------------------------------------------------------------------
# Sound key: collapses "by ear" spelling differences (paanch/panch, arba3a/arbaa, vaikittu/vaikeettu)
# ---------------------------------------------------------------------------------------------
_DIGIT_SOUNDS = {"3": "a", "7": "h", "2": "a", "5": "kh", "9": "q", "6": "t", "8": "gh", "4": "a"}


def sound_key(word: str) -> str:
    w = word.lower().replace("'", "")
    w = "".join(_DIGIT_SOUNDS.get(c, c) if c.isdigit() else c for c in w)
    for a, b in (("th", "t"), ("dh", "d"), ("ph", "f"), ("kh", "kh"), ("sh", "sh"), ("gh", "g")):
        w = w.replace(a, b)
    w = w.replace("aa", "a").replace("ee", "i").replace("ii", "i").replace("oo", "u").replace("uu", "u")
    w = w.replace("ou", "u")
    w = w.translate(str.maketrans({"v": "w", "z": "j", "q": "k", "c": "k", "y": "i"}))
    w = w.replace("ck", "k")
    # collapse doubled letters
    out = []
    for c in w:
        if not out or out[-1] != c:
            out.append(c)
    return "".join(out)


def phrase_key(phrase: str) -> str:
    return " ".join(sound_key(p) for p in phrase.split())
