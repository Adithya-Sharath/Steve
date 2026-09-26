"""Phone-level helpers for the L2-ARCTIC importers: tokenise the dataset's IPA strings and align a canonical phone sequence with the
perceived one, to find which sounds were substituted, dropped or added.

The dataset's `ipa` field is the annotators' PERCEIVED phones (concatenated, no word boundaries) and `g2p` the canonical ones (D38). The
`ipa` strings carry stress marks (ˈ ˌ) at odd places (about 16 per clip); they are noise for this purpose and are stripped.
"""

from __future__ import annotations

from dataclasses import dataclass

STRESS = "ˈˌ"
# multi-character units used by the dataset's IPA mapping (ARPABet diphthongs and affricates); anything else is one character
UNITS = ("tʃ", "dʒ", "aɪ", "aʊ", "eɪ", "oʊ", "ɔɪ")
VOWELS = set("aeiouæɑɔəɛɝɚɪʊʌ")


def tokenize(ipa: str) -> list[str]:
    s = "".join(ch for ch in ipa if ch not in STRESS and not ch.isspace())
    out: list[str] = []
    i = 0
    while i < len(s):
        two = s[i : i + 2]
        if two in UNITS:
            out.append(two)
            i += 2
        else:
            out.append(s[i])
            i += 1
    return out


def is_vowel(p: str) -> bool:
    return p[0] in VOWELS


@dataclass(frozen=True)
class Op:
    kind: str  # match | sub | del | ins
    canonical: str | None
    perceived: str | None


def _sub_cost(a: str, b: str) -> float:
    if a == b:
        return 0.0
    return 0.6 if is_vowel(a) == is_vowel(b) else 1.0  # a vowel for a vowel or a consonant for a consonant is the likelier confusion


def align(canonical: list[str], perceived: list[str]) -> list[Op]:
    """Global minimum-cost alignment (substitution 0.6/1, insertion and deletion 1). Ties prefer match/substitution."""
    n, m = len(canonical), len(perceived)
    d = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = float(i)
    for j in range(1, m + 1):
        d[0][j] = float(j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j - 1] + _sub_cost(canonical[i - 1], perceived[j - 1]), d[i - 1][j] + 1.0, d[i][j - 1] + 1.0)
    ops: list[Op] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and abs(d[i][j] - (d[i - 1][j - 1] + _sub_cost(canonical[i - 1], perceived[j - 1]))) < 1e-9:
            a, b = canonical[i - 1], perceived[j - 1]
            ops.append(Op("match" if a == b else "sub", a, b))
            i, j = i - 1, j - 1
        elif i > 0 and abs(d[i][j] - (d[i - 1][j] + 1.0)) < 1e-9:
            ops.append(Op("del", canonical[i - 1], None))
            i -= 1
        else:
            ops.append(Op("ins", None, perceived[j - 1]))
            j -= 1
    return ops[::-1]


def substitutions(ops: list[Op]) -> list[tuple[str, str]]:
    return [(o.canonical, o.perceived) for o in ops if o.kind == "sub"]
