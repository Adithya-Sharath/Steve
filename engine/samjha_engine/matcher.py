"""Match words BY EAR: exact -> suffix-stripped -> sound key -> guarded fuzzy.

Design notes
* Every candidate keeps its score and how it matched, so results are explainable.
* Short tokens (<= 3 chars) only ever match exactly: "no" must not become "do", "done" must not become "one".
* Fuzzy matching runs on sound keys, needs the same first sound, and is length-aware.
* Words that are also ordinary words elsewhere carry `ambiguous`/`adjacent_only`/`requires_near` flags in the
  lexicon and only survive when neighbouring evidence (same-language word, lang_hint) supports them.
* Suffix stripping ("dalawa"+"ng", "tablet"+"s", Malayalam "-il") is driven by the per-language config in
  lexicon.yaml, not by hard-coded if-chains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz

from .lexicon import Entry, Lexicon, get_lexicon
from .normalize import Token, phrase_key, sound_key, split_glued, tokenize
from .schema import Span

FUZZY_MIN_RATIO = 85
PHRASE_FUZZY_MIN_RATIO = 90
FUZZY_MIN_LEN = 5
SOUND_MIN_LEN = 4

TENS = {20, 30, 40, 50, 60, 70, 80, 90}


@dataclass
class Match:
    i: int  # first token idx
    j: int  # last token idx (inclusive)
    entry: Entry
    score: float
    kind: str  # exact | stem | sound | fuzzy | digits | merged
    surface: str
    start: int
    end: int
    alts: list[Entry] = field(default_factory=list)
    stem: str | None = None

    @property
    def category(self) -> str:
        return self.entry.category

    @property
    def value(self) -> Any:
        return self.entry.value

    @property
    def lang(self) -> str:
        return self.entry.lang

    @property
    def ambiguous_alts(self) -> bool:
        return bool(self.alts)

    def term(self) -> dict:
        v = self.entry.value
        if isinstance(v, bool) or v is None:
            lexeme = self.entry.canonical
        elif isinstance(v, float) and v.is_integer():
            lexeme = str(int(v))
        else:
            lexeme = str(v)
        return {
            "token": self.surface,
            "lexeme": lexeme,
            "category": self.category,
            "lang": self.lang,
            "score": round(self.score),
            "kind": self.kind,
        }

    def span(self) -> Span:
        return Span(start=self.start, end=self.end, text=self.surface)


def _pseudo(category: str, value: Any, canonical: str, lang: str = "digits") -> Entry:
    return Entry(canonical=canonical, category=category, value=value, lang=lang, verified=True)


@dataclass
class Ctx:
    """Everything the slot fillers / negation / compare stages need about one reply."""

    text: str
    tokens: list[Token]
    matches: list[Match]
    lang_hint: str | None = None
    cidx: list[int] = field(default_factory=list)
    match_at: dict[int, Match] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.matches.sort(key=lambda m: (m.i, m.j))
        for m in self.matches:
            for k in range(m.i, m.j + 1):
                self.match_at[k] = m
        c = 0
        self.cidx = []
        for t in self.tokens:
            m = self.match_at.get(t.idx)
            if not (m is not None and m.category == "filler"):
                c += 1
            self.cidx.append(c)

    def cdist(self, a: Match, b: Match) -> int:
        """Content-token distance (fillers are free). 99 across sentences."""
        ta, tb = self.tokens[a.i], self.tokens[b.i]
        if ta.sent != tb.sent:
            return 99
        if a.j < b.i:
            return self.cidx[b.i] - self.cidx[a.j]
        if b.j < a.i:
            return self.cidx[a.i] - self.cidx[b.j]
        return 0

    def by_category(self, *cats: str) -> list[Match]:
        return [m for m in self.matches if m.category in cats]

    def spans(self, matches: list[Match]) -> list[Span]:
        return merge_spans([m.span() for m in matches], self.text)


def merge_spans(spans: list[Span], text: str) -> list[Span]:
    """Merge touching / overlapping spans (only across whitespace) and re-slice from the original text."""
    out: list[Span] = []
    for s in sorted(spans, key=lambda s: (s.start, s.end)):
        if out and s.start <= out[-1].end + 1 and not text[out[-1].end : s.start].strip():
            last = out[-1]
            end = max(last.end, s.end)
            out[-1] = Span(start=last.start, end=end, text=text[last.start : end])
        else:
            out.append(Span(start=s.start, end=s.end, text=text[s.start : s.end]))
    return out


# ------------------------------------------------------------------------------------------------
# candidate generation
# ------------------------------------------------------------------------------------------------
Cand = tuple[Entry, float, str, "str | None"]


def _best(cands: dict[int, Cand], entry: Entry, score: float, kind: str, stem: str | None = None) -> None:
    key = id(entry)
    if key not in cands or cands[key][1] < score:
        cands[key] = (entry, score, kind, stem)


def _single_candidates(word: str, lex: Lexicon) -> list[Cand]:
    cands: dict[int, Cand] = {}
    for e in lex.by_form.get(word, ()):
        _best(cands, e, 100, "exact")
    if cands:
        return list(cands.values())

    # suffix stripping (config driven per language)
    for code, cfg in lex.langs.items():
        for suf in cfg.suffixes:
            if word.endswith(suf) and len(word) - len(suf) >= cfg.min_stem:
                stem = word[: -len(suf)]
                for e in lex.by_form.get(stem, ()):
                    if e.lang == code:
                        _best(cands, e, 94, "stem", stem)
                k = sound_key(stem)
                for form, e in lex.by_key.get(k, ()):
                    if e.lang == code and " " not in form and len(stem) >= SOUND_MIN_LEN:
                        _best(cands, e, 88, "stem", stem)
    if len(word) >= SOUND_MIN_LEN:
        key = sound_key(word)
        for form, e in lex.by_key.get(key, ()):
            if " " not in form:
                _best(cands, e, 92, "sound")
        if len(word) >= FUZZY_MIN_LEN and key:
            for form, fkey, e in lex.by_first.get(key[:1], ()):
                if " " in form or len(fkey) < 4 or abs(len(fkey) - len(key)) > 2:
                    continue
                # numbers are what the whole product turns on: a spurious digit-word is far worse than a missed one,
                # so short number words only match exactly / by sound key ("aankh" must never become 5)
                if e.category in ("number", "number_mult") and len(fkey) < 8:
                    continue
                r = fuzz.ratio(key, fkey)
                if r >= FUZZY_MIN_RATIO:
                    _best(cands, e, r - 3, "fuzzy")
    if len(word) == 4 and not cands:
        # negation words are safety-critical: tolerate one dropped letter ("hndi" -> "hindi", "huwg" -> "huwag")
        key4 = sound_key(word)
        for form, fkey, e in lex.by_first.get(key4[:1], ()):
            if e.category != "negation" or " " in form or len(fkey) - len(key4) != 1 or fkey[-1:] != key4[-1:]:
                continue
            r = fuzz.ratio(key4, fkey)
            if r >= 88:
                _best(cands, e, r - 4, "fuzzy")
    return list(cands.values())


def _phrase_candidates(words: list[str], lex: Lexicon) -> list[Cand]:
    text = " ".join(words)
    cands: dict[int, Cand] = {}
    for e in lex.by_form.get(text, ()):
        _best(cands, e, 100, "exact")
    if cands:
        return list(cands.values())
    key = phrase_key(text)
    for form, e in lex.by_key.get(key, ()):
        if form.count(" ") == len(words) - 1:
            _best(cands, e, 92, "sound")
    if len(text) >= 9 and key:
        for form, fkey, e in lex.by_first.get(key[:1], ()):
            if form.count(" ") != len(words) - 1 or abs(len(fkey) - len(key)) > 2:
                continue
            r = fuzz.ratio(key, fkey)
            if r >= PHRASE_FUZZY_MIN_RATIO:
                _best(cands, e, r - 4, "fuzzy")
    return list(cands.values())


# ------------------------------------------------------------------------------------------------
# main entry
# ------------------------------------------------------------------------------------------------
def _digit_match(t: Token) -> Match:
    if t.kind == "clock":
        return Match(t.idx, t.idx, _pseudo("clock", t.norm, t.norm), 100, "digits", t.text, t.start, t.end)
    if t.kind == "iso":
        return Match(t.idx, t.idx, _pseudo("isodate", t.norm, t.norm), 100, "digits", t.text, t.start, t.end)
    v = t.num
    canonical = t.norm
    return Match(t.idx, t.idx, _pseudo("number", v, canonical), 100, "digits", t.text, t.start, t.end)


def match_tokens(tokens: list[Token], text: str, lang_hint: str | None = None, lex: Lexicon | None = None) -> list[Match]:
    lex = lex or get_lexicon()
    n = len(tokens)

    # 1. candidates per span
    spans: dict[tuple[int, int], list[Cand]] = {}
    for i in range(n):
        t = tokens[i]
        if not t.is_word:
            continue
        c1 = _single_candidates(t.norm, lex)
        if c1:
            spans[(i, i)] = c1
        for size in range(2, lex.max_ngram + 1):
            j = i + size - 1
            if j >= n:
                break
            seg = tokens[i : j + 1]
            if not all(x.is_word for x in seg) or seg[0].clause != seg[-1].clause or seg[0].sent != seg[-1].sent:
                break
            c = _phrase_candidates([x.norm for x in seg], lex)
            if c:
                spans[(i, j)] = c

    # 2. contextual support / ambiguity filtering
    lang_at: dict[int, set[str]] = {}
    cat_at: dict[int, set[str]] = {}
    for (i, j), cands in spans.items():
        for e, s, _k, _st in cands:
            if s >= 88:
                cat_at.setdefault(i, set()).add(e.category)
                cat_at.setdefault(j, set()).add(e.category)
                if not e.ambiguous and e.category not in ("filler",) and not e.adjacent_only and not e.requires_near:
                    for k in range(i, j + 1):
                        lang_at.setdefault(k, set()).add(e.lang)

    def supported(e: Entry, i: int, j: int) -> bool:
        if lang_hint and e.lang == lang_hint:
            return True
        # code-mixing: "do bottle", "do puffs" (Hindi 2 + an English unit) - a number directly before a unit word
        if e.category == "number" and next_content_cat(j) & {"unit", "duration_unit", "currency"}:
            return True
        for k in range(max(0, i - 3), min(n, j + 4)):
            if tokens[k].sent != tokens[i].sent:
                continue
            if e.lang in lang_at.get(k, ()) and (k < i or k > j):
                return True
        return False

    def near_tokens(e: Entry, i: int, j: int) -> bool:
        want = set(e.requires_near)
        wantk = {sound_key(w) for w in want}
        for k in range(max(0, i - 2), min(n, j + 3)):
            if i <= k <= j:
                continue
            if tokens[k].norm in want or sound_key(tokens[k].norm) in wantk:
                return True
        return False

    def prev_content_cat(i: int) -> set[str]:
        k = i - 1
        while k >= 0 and "filler" in cat_at.get(k, ()) and not (cat_at.get(k, set()) - {"filler"}):
            k -= 1
        return cat_at.get(k, set()) if k >= 0 else set()

    def next_content_cat(j: int) -> set[str]:
        k = j + 1
        while k < n and "filler" in cat_at.get(k, ()) and not (cat_at.get(k, set()) - {"filler"}):
            k += 1
        return cat_at.get(k, set()) if k < n else set()

    filtered: dict[tuple[int, int], list[Cand]] = {}
    for (i, j), cands in spans.items():
        keep: list[Cand] = []
        for e, s, k, st in cands:
            if e.requires_near and not near_tokens(e, i, j):
                continue
            if e.ambiguous and not supported(e, i, j):
                continue
            if e.adjacent_only:
                if not (next_content_cat(j) & {"unit", "duration_unit"}):
                    continue
                # "twice a day" -> a rate; but "thrice daily for a week" -> a duration (raw word before 'a' is 'for')
                if prev_content_cat(i) & {"frequency_phrase"} and (i == 0 or tokens[i - 1].norm != "for"):
                    continue
            keep.append((e, s, k, st))
        if keep:
            filtered[(i, j)] = keep

    # 3. score with language context and resolve overlaps (longest span first, then score)
    def adjusted(e: Entry, s: float, i: int, j: int) -> float:
        bonus = 0.0
        if lang_hint and e.lang == lang_hint:
            bonus += 5
        near = 0
        for k in range(max(0, i - 3), min(n, j + 4)):
            if (k < i or k > j) and e.lang in lang_at.get(k, ()) and e.lang != "en":
                near += 1
        bonus += min(near, 2) * 3
        if e.ambiguous:
            bonus -= 3
        return s + bonus

    ranked: list[tuple[int, float, int, int, Cand, list[Cand]]] = []
    for (i, j), cands in filtered.items():
        scored = sorted(cands, key=lambda c: -adjusted(c[0], c[1], i, j))
        ranked.append((j - i + 1, adjusted(scored[0][0], scored[0][1], i, j), i, j, scored[0], scored))
    ranked.sort(key=lambda r: (-r[0], -r[1], r[2]))

    taken: set[int] = set()
    matches: list[Match] = []
    for _size, _adj, i, j, best, scored in ranked:
        rng = range(i, j + 1)
        if any(k in taken for k in rng):
            continue
        e, s, kind, stem = best
        alts = [
            c[0]
            for c in scored[1:]
            if (c[0].category, str(c[0].value)) != (e.category, str(e.value)) and c[1] >= s - 6
        ]
        start, end = tokens[i].start, tokens[j].end
        matches.append(Match(i, j, e, s, kind, text[start:end], start, end, alts=alts, stem=stem))
        taken.update(rng)

    # 4. digits / clocks / iso dates (not glued into lexicon words)
    for t in tokens:
        if t.kind != "word" and t.idx not in taken:
            matches.append(_digit_match(t))
            taken.add(t.idx)

    matches.sort(key=lambda m: (m.i, m.j))
    return merge_numbers(matches, tokens, text)


def merge_numbers(matches: list[Match], tokens: list[Token], text: str) -> list[Match]:
    """'twenty five' -> 25, 'one hundred fifty' -> 150, 'ek sau' -> 100. Words only; digits stay as written."""
    out: list[Match] = []
    i = 0

    def is_word_num(m: Match) -> bool:
        return m.category == "number" and m.kind != "digits" and float(m.value).is_integer()

    def adjacent(a: Match, b: Match) -> bool:
        if b.i == a.j + 1:
            return True
        # allow a single "and" between ("hundred and fifty")
        return b.i == a.j + 2 and tokens[a.j + 1].norm == "and" and tokens[a.j].sent == tokens[b.i].sent

    while i < len(matches):
        m = matches[i]
        nxt = matches[i + 1] if i + 1 < len(matches) else None
        merged: Match | None = None
        if nxt is not None and adjacent(m, nxt):
            if (is_word_num(m) or m.category == "number_mult") and nxt.category == "number_mult" and m.category == "number" and 0 < m.value < 100:
                val = m.value * nxt.value
                last = nxt
                nn = matches[i + 2] if i + 2 < len(matches) else None
                if nn is not None and adjacent(nxt, nn) and is_word_num(nn) and 0 < nn.value < 100:
                    val += nn.value
                    last = nn
                    i += 1
                merged = _combine(m, last, val, tokens, text)
                i += 1
            elif is_word_num(m) and m.value in TENS and is_word_num(nxt) and 1 <= nxt.value <= 9:
                merged = _combine(m, nxt, m.value + nxt.value, tokens, text)
                i += 1
        if merged is None and m.category == "number_mult":
            # bare "hundred" = 100 (optionally + following number)
            merged = _combine(m, m, m.value, tokens, text)
            merged.entry = _pseudo("number", m.value, m.entry.canonical, m.lang)
        out.append(merged or m)
        i += 1
    return out


def _combine(a: Match, b: Match, val: float, tokens: list[Token], text: str) -> Match:
    start, end = tokens[a.i].start, tokens[b.j].end
    ent = _pseudo("number", float(val), text[start:end].lower(), a.lang)
    return Match(a.i, b.j, ent, min(a.score, b.score), "merged", text[start:end], start, end)


def prepare(text: str, lang_hint: str | None = None, lex: Lexicon | None = None) -> Ctx:
    lex = lex or get_lexicon()
    toks = split_glued(tokenize(text), lex.has_form, lex.is_anchor_form)
    matches = match_tokens(toks, text, lang_hint, lex)
    return Ctx(text=text, tokens=toks, matches=matches, lang_hint=lang_hint)
