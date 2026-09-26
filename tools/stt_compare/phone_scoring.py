"""Phone-level "kept / fixed / garbled" scoring, for sources that have phone annotations but no word gold (L2-ARCTIC spontaneous).

For each clip we know the CANONICAL phones (`g2p`, what the words should sound like) and the PERCEIVED phones (`ipa`, what the annotators heard).
Wherever they differ by substitution (say /p/ heard as /b/) we ask what the speech-to-text transcript did at that spot, by turning the
transcript back into phones with a pronunciation dictionary (CMUdict) and aligning it to the canonical sequence:

    kept     the transcript has the phone that was actually heard (the accent survived into the text)
    fixed    the transcript has the canonical phone (the recogniser "corrected" it)
    garbled  something else
    no counterpart   the aligner found no transcript phone at that spot (a dropped word, for instance)

This is a PROXY for the word-level question ("barking" kept or turned into "parking"), used because this dataset has no word-level gold: it
works on sounds, needs the transcript's words to be in CMUdict (coverage is reported), and picks the first dictionary pronunciation of each
word. Treat the numbers as directional (D39).
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "importers"))
import phones  # noqa: E402

KEPT, FIXED, GARBLED, NONE = "kept", "fixed", "garbled", "no counterpart"

# ARPABet (CMUdict, stress digits removed) -> the IPA symbols used by the L2-ARCTIC dataset's `g2p` field
ARPA_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ", "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "EH": "ɛ", "ER": "ɝ",
    "EY": "eɪ", "F": "f", "G": "ɡ", "HH": "h", "IH": "ɪ", "IY": "i", "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ",
    "OW": "oʊ", "OY": "ɔɪ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ", "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v", "W": "w",
    "Y": "j", "Z": "z", "ZH": "ʒ",
}
_WORD = re.compile(r"[a-z]+(?:'[a-z]+)*")
_dict = None


def pronunciations():
    global _dict
    if _dict is None:
        import cmudict

        _dict = cmudict.dict()
    return _dict


def transcript_phones(text: str, lexicon: dict | None = None) -> tuple[list[str], int, int]:
    """-> (phone tokens, words found in the dictionary, words total). Words not in the dictionary contribute nothing."""
    lex = lexicon if lexicon is not None else pronunciations()
    out: list[str] = []
    found = total = 0
    for w in _WORD.findall((text or "").lower().replace("’", "'")):
        total += 1
        prons = lex.get(w)
        if not prons:
            continue
        found += 1
        for p in prons[0]:
            sym = ARPA_TO_IPA.get(re.sub(r"\d", "", p))
            if sym:
                out.extend(phones.tokenize(sym))
    return out, found, total


@dataclass
class ClipScore:
    accent: str
    variant: str
    accent_positions: list[tuple[str, str, str | None, str]] = field(default_factory=list)  # (canonical, perceived, transcript, kind)
    per_vs_canonical: float | None = None
    per_vs_perceived: float | None = None
    words_found: int = 0
    words_total: int = 0


def _per(ref: list[str], hyp: list[str]) -> float | None:
    if not ref:
        return None
    ops = phones.align(ref, hyp)
    return sum(1 for o in ops if o.kind != "match") / len(ref)


def score_clip(accent: str, variant: str, g2p: str, ipa: str, transcript: str, lexicon: dict | None = None) -> ClipScore:
    canonical, perceived = phones.tokenize(g2p), phones.tokenize(ipa)
    t, found, total = transcript_phones(transcript, lexicon)
    s = ClipScore(accent, variant, words_found=found, words_total=total)
    if not t:
        return s  # nothing to compare: no phones from the transcript
    s.per_vs_canonical, s.per_vs_perceived = _per(canonical, t), _per(perceived, t)
    # map each canonical position to the transcript phone the aligner puts opposite it (None if deleted)
    opposite: dict[int, str | None] = {}
    i = 0
    for o in phones.align(canonical, t):
        if o.canonical is not None:
            opposite[i] = o.perceived
            i += 1
    i = 0
    for o in phones.align(canonical, perceived):
        if o.canonical is None:
            continue
        if o.kind == "sub":
            got = opposite.get(i)
            kind = NONE if got is None else KEPT if got == o.perceived else FIXED if got == o.canonical else GARBLED
            s.accent_positions.append((o.canonical, o.perceived, got, kind))
        i += 1
    return s


@dataclass
class Tally:
    clips: int = 0
    positions: int = 0
    kinds: Counter = field(default_factory=Counter)
    per_c: list[float] = field(default_factory=list)
    per_p: list[float] = field(default_factory=list)
    words_found: int = 0
    words_total: int = 0

    def classified(self) -> int:
        return self.kinds[KEPT] + self.kinds[FIXED] + self.kinds[GARBLED]

    def pct(self, kind: str) -> float | None:
        n = self.classified()
        return 100 * self.kinds[kind] / n if n else None


def tally(scores: list[ClipScore]) -> Tally:
    t = Tally()
    for s in scores:
        t.clips += 1
        t.positions += len(s.accent_positions)
        t.kinds.update(k for *_, k in s.accent_positions)
        if s.per_vs_canonical is not None:
            t.per_c.append(s.per_vs_canonical)
        if s.per_vs_perceived is not None:
            t.per_p.append(s.per_vs_perceived)
        t.words_found += s.words_found
        t.words_total += s.words_total
    return t


def by_pair(scores: list[ClipScore]) -> dict[tuple[str, str], Counter]:
    out: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for s in scores:
        for c, p, _, k in s.accent_positions:
            out[(c, p)][k] += 1
    return out
