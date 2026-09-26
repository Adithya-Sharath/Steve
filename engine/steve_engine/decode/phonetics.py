"""Pronunciations, word frequencies and sound-alike words for Decode, from two pure-Python data packages that ship their data (no network, no keys):
`cmudict` (the CMU Pronouncing Dictionary) and `wordfreq` (word frequencies on the Zipf scale: 3 is about 1 word in a million, 5 is about 1 in 10,000).

`sound_alikes(word)` returns REAL, COMMON English words whose pronunciation is one phone edit away from the word's (substitution, deletion or insertion),
each with a cost: a vowel-for-vowel or consonant-for-consonant substitution costs 0.6, any other edit 1.0, and an edit that an accent-pack rule says is a
typical substitution for the speaker's background costs less (weight-scaled), never zero. Homophones are not sound-alikes (same sounds, nothing to repair).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

from .accents import ARPABET, Swap

COMMON_MIN_ZIPF = 3.0
VOWELS = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}
SUB_SAME_CLASS = 0.6
EDIT = 1.0
PACK_DISCOUNT = 0.7  # a rule of weight 1 cuts the cost of the matching edit by 70%
_WORD = re.compile(r"^[a-z]+(?:'[a-z]+)?$")
_PHONES = sorted(ARPABET)


@cache
def _cmu() -> dict[str, list[list[str]]]:
    import cmudict

    return cmudict.dict()


@cache
def zipf(word: str) -> float:
    from wordfreq import zipf_frequency

    return zipf_frequency(word.lower(), "en")


def pronunciations(word: str) -> list[tuple[str, ...]]:
    """All dictionary pronunciations of `word`, stress digits removed (empty if the word is not in the dictionary)."""
    out: list[tuple[str, ...]] = []
    for pron in _cmu().get(word.lower(), []):
        p = tuple(re.sub(r"\d", "", x) for x in pron)
        if p not in out:
            out.append(p)
    return out


def is_word(word: str) -> bool:
    """A real, reasonably common English word (in the dictionary and frequent enough)."""
    w = word.lower()
    return bool(_WORD.match(w)) and w in _cmu() and zipf(w) >= COMMON_MIN_ZIPF


@cache
def _index() -> dict[tuple[str, ...], frozenset[str]]:
    idx: dict[tuple[str, ...], set[str]] = {}
    for w in _cmu():
        if _WORD.match(w) and zipf(w) >= COMMON_MIN_ZIPF:
            for p in pronunciations(w):
                idx.setdefault(p, set()).add(w)
    return {k: frozenset(v) for k, v in idx.items()}


@dataclass(frozen=True)
class SoundAlike:
    word: str
    cost: float
    edits: tuple[tuple[str, str | None, str | None], ...]  # (kind, from phone, to phone)
    pack_rule: str | None = None  # "ar: b -> p" when an accent rule explains the edit


def _sub_cost(a: str, b: str) -> float:
    return SUB_SAME_CLASS if (a in VOWELS) == (b in VOWELS) else EDIT


def sound_alikes(word: str, swaps: tuple[Swap, ...] = (), max_pron: int = 2) -> list[SoundAlike]:
    """Real common words one phone edit from `word`, cheapest first. `swaps` are the active accent rules (heard -> meant, by ARPAbet phones)."""
    w = word.lower()
    heard_to_meant = {s.phones: s for s in swaps if s.phones}
    idx = _index()
    best: dict[str, SoundAlike] = {}

    def offer(cand_phones: tuple[str, ...], cost: float, edit: tuple, rule: str | None) -> None:
        for cand in idx.get(cand_phones, ()):
            if cand == w:
                continue
            cur = best.get(cand)
            if cur is None or cost < cur.cost:
                best[cand] = SoundAlike(cand, round(cost, 3), (edit,), rule)

    for p in pronunciations(w)[:max_pron]:
        for i, a in enumerate(p):
            for b in _PHONES:  # substitution
                if b == a:
                    continue
                cost, rule = _sub_cost(a, b), None
                swap = heard_to_meant.get((a, b))
                if swap:
                    cost, rule = cost * (1 - PACK_DISCOUNT * swap.weight), f"{swap.pack}: {swap.heard} -> {swap.meant}"
                offer(p[:i] + (b,) + p[i + 1 :], cost, ("sub", a, b), rule)
            offer(p[:i] + p[i + 1 :], EDIT, ("del", a, None), None)  # deletion
        for i in range(len(p) + 1):  # insertion
            for b in _PHONES:
                offer(p[:i] + (b,) + p[i:], EDIT, ("ins", None, b), None)
    return sorted(best.values(), key=lambda c: (c.cost, -zipf(c.word), c.word))


HOMOPHONE_COST = 0.15  # same sounds, different spelling (gate / gait, night / knight): a transcription slip, not a hearing one
MAX_ALIKE_COST = 2.2


def _edit_cost(heard: tuple[str, ...], meant: tuple[str, ...], rules: dict[tuple[str, str], Swap]) -> float:
    """Weighted phone edit distance from what was heard to a candidate word (substitution 0.6 / 1.0, accent-rule discount, insert/delete 1.0)."""
    n, m = len(heard), len(meant)
    d = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = i * EDIT
    for j in range(1, m + 1):
        d[0][j] = j * EDIT
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            a, b = heard[i - 1], meant[j - 1]
            if a == b:
                sub = 0.0
            else:
                sub = _sub_cost(a, b)
                swap = rules.get((a, b))
                if swap:
                    sub *= 1 - PACK_DISCOUNT * swap.weight
            d[i][j] = min(d[i - 1][j - 1] + sub, d[i - 1][j] + EDIT, d[i][j - 1] + EDIT)
    return d[n][m]


def vocab_alikes(word: str, vocab: list[str] | tuple[str, ...], swaps: tuple[Swap, ...] = (), max_cost: float = MAX_ALIKE_COST) -> list[SoundAlike]:
    """Words FROM `vocab` (for example the place words a slot expects) that sound like `word`, cheapest first, by weighted phone edit distance.
    Homophones are included at a tiny cost; the word itself is not."""
    w = word.lower()
    mine = pronunciations(w)
    if not mine:
        return []
    rules = {s.phones: s for s in swaps if s.phones}
    out: list[SoundAlike] = []
    for cand in vocab:
        if cand == w:
            continue
        best_cost, rule = None, None
        for c in pronunciations(cand):
            for p in mine[:2]:
                cost = HOMOPHONE_COST if p == c else _edit_cost(p, c, rules)
                if best_cost is None or cost < best_cost:
                    best_cost = cost
                    rule = None
                    if p != c:
                        for a, b in zip(p, c, strict=False):  # name the accent rule that explains a substitution, if one does
                            if a != b and (a, b) in rules:
                                s = rules[(a, b)]
                                rule = f"{s.pack}: {s.heard} -> {s.meant}"
                                break
        if best_cost is not None and best_cost <= max_cost:
            out.append(SoundAlike(cand, round(best_cost, 3), (), rule))
    return sorted(out, key=lambda c: (c.cost, -zipf(c.word), c.word))
