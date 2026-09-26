"""Scoring for the STT reality test: word error rate against what was ACTUALLY said, and what happens to the accent-influenced
words (kept as spoken, "fixed" to the intended word, or garbled into something else).

Pure functions, no network, no third-party dependency except rapidfuzz (already an engine dependency).
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from rapidfuzz.distance import Levenshtein

SURVIVED, FIXED, GARBLED = "survived", "fixed", "garbled"
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'"})
_NON_WORD = re.compile(r"[^\w']+", re.UNICODE)


def normalize(text: str) -> list[str]:
    """Lowercase word tokens; punctuation and hyphens are separators, inner apostrophes stay (don't)."""
    t = unicodedata.normalize("NFKC", text or "").translate(_APOSTROPHES).lower()
    return [w.strip("'") for w in _NON_WORD.split(t) if w.strip("'")]


def edits(ref: list[str], hyp: list[str]) -> int:
    return Levenshtein.distance(ref, hyp)


def wer(ref: list[str], hyp: list[str]) -> float:
    return edits(ref, hyp) / len(ref) if ref else (0.0 if not hyp else 1.0)


@dataclass(frozen=True)
class Pair:
    """A word (or span) the speaker said differently from the intended one, e.g. heard "barking" / meant "parking"."""

    heard: str
    meant: str


def accent_pairs(spoken_as_heard: str, intended: str) -> list[Pair]:
    """Where `spoken_as_heard` and `intended_meaning` differ by REPLACEMENT. Equal-length replaced spans are paired word by word;
    unequal ones become one phrase pair ("yalla habibi" / "come on my friend"). Pure insertions and deletions are not accent
    evidence and are ignored."""
    h, m = normalize(spoken_as_heard), normalize(intended)
    pairs: list[Pair] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, h, m, autojunk=False).get_opcodes():
        if tag != "replace":
            continue
        hs, ms = h[i1:i2], m[j1:j2]
        if len(hs) == len(ms):
            pairs += [Pair(a, b) for a, b in zip(hs, ms, strict=True) if a != b]
        else:
            pairs.append(Pair(" ".join(hs), " ".join(ms)))
    return pairs


def _contains(hyp: Counter, span: list[str]) -> bool:
    need = Counter(span)
    return bool(span) and all(hyp[w] >= n for w, n in need.items())


def classify(pair: Pair, hyp_tokens: list[str]) -> str:
    """What the transcript did with an accent word.
    survived: the word as spoken is there; fixed: the intended word is there instead; garbled: neither.
    (If both appear, it counts as survived: the spoken form was kept.)"""
    hyp = Counter(hyp_tokens)
    if _contains(hyp, normalize(pair.heard)):
        return SURVIVED
    if _contains(hyp, normalize(pair.meant)):
        return FIXED
    return GARBLED


@dataclass
class FileResult:
    file: str
    accent: str
    variant: str
    hypothesis: str = ""
    error: str | None = None
    latency: float | None = None
    ref_len: int = 0
    edit_count: int = 0
    pairs: list[tuple[Pair, str]] = field(default_factory=list)


def score_file(file: str, accent: str, variant: str, spoken_as_heard: str, intended: str, hypothesis: str,
               latency: float | None) -> FileResult:
    ref, hyp = normalize(spoken_as_heard), normalize(hypothesis)
    return FileResult(
        file=file, accent=accent, variant=variant, hypothesis=hypothesis, latency=latency,
        ref_len=len(ref), edit_count=edits(ref, hyp),
        pairs=[(p, classify(p, hyp)) for p in accent_pairs(spoken_as_heard, intended)],
    )


@dataclass
class Summary:
    variant: str
    files: int = 0
    errors: int = 0
    wer: float | None = None
    pairs: int = 0
    survived: int = 0
    fixed: int = 0
    garbled: int = 0
    latency_mean: float | None = None
    latency_median: float | None = None
    latency_p95: float | None = None

    def pct(self, n: int) -> float | None:
        return 100.0 * n / self.pairs if self.pairs else None


def _p95(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(0.95 * (len(xs) - 1)))]


def summarise(results: list[FileResult], variant: str) -> Summary:
    rs = [r for r in results if r.variant == variant]
    ok = [r for r in rs if r.error is None]
    s = Summary(variant=variant, files=len(ok), errors=len(rs) - len(ok))
    ref = sum(r.ref_len for r in ok)
    s.wer = sum(r.edit_count for r in ok) / ref if ref else None
    kinds = Counter(k for r in ok for _, k in r.pairs)
    s.pairs = sum(kinds.values())
    s.survived, s.fixed, s.garbled = kinds[SURVIVED], kinds[FIXED], kinds[GARBLED]
    lat = [r.latency for r in ok if r.latency is not None]
    if lat:
        s.latency_mean, s.latency_median, s.latency_p95 = statistics.mean(lat), statistics.median(lat), _p95(lat)
    return s


def by_accent(results: list[FileResult], variant: str) -> dict[str, Summary]:
    accents = sorted({r.accent for r in results if r.variant == variant})
    out = {}
    for a in accents:
        sub = [r for r in results if r.variant == variant and r.accent == a]
        out[a] = summarise(sub, variant)
    return out
