"""Word-level view of an L2-ARCTIC utterance: which words did the annotators hear differently, and is what they heard a DIFFERENT REAL WORD?

Inputs per utterance (from the sibling dataset `KoelLabs/L2Arctic`): `text` (the words), `g2p` (canonical phones of the whole utterance, no word
boundaries) and `ipa` (perceived phones). Steps:

1. Segment the canonical phones `g2p` into the words of `text` using CMUdict pronunciations (exact matches only; an utterance that does not
   segment cleanly is skipped and counted, never guessed).
2. Align canonical to perceived phones (`phones.align`) and give every word the perceived phones opposite its own.
3. A word is an ACCENT WORD when its perceived phones differ from its canonical pronunciation.
4. `spoken_as_heard` is written ONLY when the mapping is clear: the perceived phones spell exactly one dictionary word (via an inverse CMUdict
   lookup), and that word is not the intended one. That is a REAL-WORD SWAP ("pit" heard as "bit"). Anything else (a non-word such as "dis", or
   several homophones) is left unwritten.

Perceived schwa (ə) is treated as ʌ for the inverse lookup only, because the dictionary mapping has no schwa (AH is written ʌ); this is a stated
assumption, not a linguistic claim (D39).
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import functools

import phone_scoring as ps  # noqa: E402
import phones  # noqa: E402

_WORD = re.compile(r"[a-z]+(?:'[a-z]+)*")


def words_of(text: str) -> list[str]:
    return _WORD.findall((text or "").lower().replace("’", "'"))


def variants(word: str, lex: dict) -> list[list[str]]:
    out = []
    for pron in lex.get(word, []):
        toks: list[str] = []
        for p in pron:
            sym = ps.ARPA_TO_IPA.get(re.sub(r"\d", "", p))
            if sym:
                toks.extend(phones.tokenize(sym))
        if toks and toks not in out:
            out.append(toks)
    return out


MIN_ZIPF = 3.5  # a word must be at least this common (wordfreq Zipf scale, about 1 in 300,000 words) to count as something a listener could hear


def inverse_lexicon(lex: dict, min_zipf: float = MIN_ZIPF) -> dict[tuple[str, ...], set[str]]:
    """phone tuple -> the COMMON English words pronounced that way. The full CMUdict also holds names, abbreviations and obscure entries
    (waugh's, zehr, roque ...) that would make almost any distorted word look like a "real word"; the frequency floor keeps the ones a
    listener would plausibly hear. It is a filter, not a proof: some odd survivors remain, so the candidate list is shown to the owner."""
    from wordfreq import zipf_frequency

    inv: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for w in lex:
        if not _WORD.fullmatch(w) or zipf_frequency(w, "en") < min_zipf:
            continue
        for v in variants(w, lex):
            inv[tuple(v)].add(w)
    return inv


MAX_UNKNOWN = 3  # words per utterance whose pronunciation is not in the dictionary (or differs from the dataset's G2P)
MAX_UNKNOWN_PHONES = 14


def segment(words: list[str], canonical: list[str], lex: dict, max_unknown: int = 0) -> list[tuple[int, int, list[str], bool]] | None:
    """[(start, end, phones, exact)] per word over `canonical`, or None if the words do not tile it.

    Exact matches use the dictionary pronunciations (with backtracking over variants). With `max_unknown` > 0 up to that many words may
    instead take ANY stretch of phones (exact=False): their boundaries are anchored by the exact words around them, and they are never used as
    evidence of an accent."""

    n = len(words)

    @functools.cache
    def go(i: int, pos: int, unknown: int):
        if i == n:
            return () if pos == len(canonical) else None
        for v in variants(words[i], lex):
            if canonical[pos : pos + len(v)] == v:
                rest = go(i + 1, pos + len(v), unknown)
                if rest is not None:
                    return ((pos, pos + len(v), tuple(v), True), *rest)
        if unknown < max_unknown:
            for k in range(1, MAX_UNKNOWN_PHONES + 1):
                if pos + k > len(canonical):
                    break
                rest = go(i + 1, pos + k, unknown + 1)
                if rest is not None:
                    return ((pos, pos + k, tuple(canonical[pos : pos + k]), False), *rest)
        return None

    found = go(0, 0, 0)
    return None if found is None else [(s, e, list(v), ex) for s, e, v, ex in found]


@dataclass
class WordView:
    word: str
    canonical: list[str]
    heard: list[str]
    accent: bool
    swap_word: str | None  # the single real word the perceived phones spell, if clear and different from `word`
    exact: bool = True  # False: the word's pronunciation is not from the dictionary, so it is never used as accent evidence
    substitutions: list[tuple[str, str]] = field(default_factory=list)


def utterance_words(text: str, g2p: str, ipa: str, lex: dict, inv: dict, max_unknown: int = MAX_UNKNOWN) -> list[WordView] | None:
    words = words_of(text)
    canonical, perceived = phones.tokenize(g2p), phones.tokenize(ipa)
    spans = segment(words, canonical, lex, max_unknown)
    if spans is None:
        return None
    heard: list[list[str]] = [[] for _ in words]
    subs: list[list[tuple[str, str]]] = [[] for _ in words]
    owner = [i for i, (s, e, _, _) in enumerate(spans) for _ in range(s, e)]  # word index of every canonical position
    ci = -1
    last_word = 0
    for op in phones.align(canonical, perceived):
        if op.canonical is not None:
            ci += 1
            last_word = owner[ci]
            if op.perceived is not None:
                heard[last_word].append(op.perceived)
                if op.kind == "sub":
                    subs[last_word].append((op.canonical, op.perceived))
        elif op.perceived is not None:  # an added phone: attach it to the word before it
            heard[last_word].append(op.perceived)
    out = []
    for i, w in enumerate(words):
        canon, exact = spans[i][2], spans[i][3]
        h = heard[i]
        accent = exact and h != canon and h not in variants(w, lex)  # another accepted pronunciation of the word is not an accent
        swap = None
        if accent:
            key = tuple("ʌ" if p == "ə" else p for p in h)
            cands = inv.get(key, set()) - {w}
            if len(cands) == 1 and not inv.get(key, set()) & {w}:
                swap = next(iter(cands))
        out.append(WordView(word=w, canonical=canon, heard=h, accent=accent, swap_word=swap, substitutions=subs[i], exact=exact))
    return out
