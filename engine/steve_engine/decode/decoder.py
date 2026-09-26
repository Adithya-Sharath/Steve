"""Decode (D36, D40, D41): understand the English a worker actually hears or types.

    decode(text, accent_hint=None, path="typed")   -> DecodedCard
    inspect_decode(text, accent_hint=None, path="typed") -> the stages, for the how-it-works page

path="voice"  the text is a speech-to-text TRANSCRIPT: STT -> glossary -> voice safety net (only critical spans, only when a sound-alike clearly fits
              better) -> actions -> clarify. The transcript is trusted unless a critical word fits its slot badly.
path="typed"  the text was TYPED by ear (WhatsApp): glossary -> full sound-swap decoding -> actions -> clarify.
Deterministic, no keys, no network. Nothing is ever translated (Phase 5 translates the settled plain English, never the original).
Wording: decoded, probably meant, often sounds like. Never "wrong" or "bad English". The `confidence` on the card is internal; nothing shows a score.
"""

from __future__ import annotations

from .actions import Eff, extract, parse_number
from .domain import get_domain
from .glossary import Hit, find_phrases, to_phrase_hit
from .safety import Review, SafetyConfig, _match_case, review_transcript
from .schema import Actions, Change, Clarify, DecodedCard
from .spans import NUMBERED, find_slots
from .tokens import Token, tokenize
from .typed import review_typed

COMMA_AFTER = {"greeting", "urgency", "address", "politeness", "agreement"}


def _effective(tokens: list[Token], changes: list[Change]) -> list[Eff]:
    meant = {c.span.start: c.meant for c in changes}
    return [Eff(t, meant.get(t.start, t.norm)) for t in tokens]


def _digits(effs: list[Eff]) -> dict[int, tuple[int, str]]:
    """Number words that a worker must read as digits (gate three, at five, fifty dirhams): first token index -> (last index, digits)."""
    words = [e.word for e in effs]
    out: dict[int, tuple[int, str]] = {}
    i = 0
    while i < len(words):
        n = parse_number(words, i)
        if not n:
            i += 1
            continue
        value, nxt = n
        prev = words[i - 1] if i else ""
        after = words[nxt] if nxt < len(words) else ""
        single_word_one = words[i] == "one" and nxt == i + 1
        wanted = prev in NUMBERED or prev == "at" or after in {"dirham", "dirhams", "aed", "riyal", "riyals", "rupee", "rupees", "dollar", "dollars", "o'clock", "oclock", "am", "pm"}
        if wanted and not (single_word_one and prev != "at" and prev not in NUMBERED and after not in {"dirham", "dirhams", "aed"}):
            out[i] = (nxt - 1, str(value))
        i = max(nxt, i + 1)
    return out


def _plain(text: str, effs: list[Eff], changes: list[Change], hits: list[Hit]) -> str:
    """The message in plain English: changes applied, glossary phrases replaced by their plain rendering, number words as digits."""
    repl: list[tuple[int, int, str]] = []
    covered: set[int] = set()
    digit_at = _digits(effs)
    for h in hits:
        if h.entry.substitute:
            follow = h.last + 1 < len(effs)
            text_plain = h.entry.plain + ("," if follow and h.entry.category in COMMA_AFTER else "")
            repl.append((h.span.start, h.span.end, text_plain))
            covered.update(range(h.first, h.last + 1))
    changed_start = {c.span.start for c in changes}
    for c in changes:
        # a changed word that is a number in a number position ("tree" -> "three" after "gate") is written as digits
        first = next((i for i, e in enumerate(effs) if e.token.start == c.span.start), None)
        if first is not None and first in digit_at and digit_at[first][0] == first:
            continue
        repl.append((c.span.start, c.span.end, _match_case(c.span.text, c.meant)))
    for first, (last, digits) in digit_at.items():
        if not any(k in covered for k in range(first, last + 1)) and (effs[first].token.start in changed_start or not any(r[0] == effs[first].token.start for r in repl)):
            repl.append((effs[first].token.start, effs[last].token.end, digits))
    out, pos = [], 0
    for s, e, new in sorted(repl):
        if s < pos:
            continue
        out += [text[pos:s], new]
        pos = e
    plain = "".join(out) + text[pos:]
    plain = " ".join(plain.split()).replace(" ,", ",")
    return plain[:1].upper() + plain[1:] if plain else plain


def _run(text: str, accent_hint: str | None, path: str, cfg: SafetyConfig | None, resolved: dict[int, str | None] | None = None):
    if path not in ("typed", "voice"):
        raise ValueError("path must be 'typed' or 'voice'")
    tokens = tokenize(text)
    hits = find_phrases(tokens, text)
    inside = {k for h in hits for k in range(h.first, h.last + 1)}
    review: Review = review_transcript(text, accent_hint, cfg) if path == "voice" else review_typed(text, accent_hint, cfg, skip=inside)
    changes = [c for c in review.changes if not any(h.span.start <= c.span.start < h.span.end for h in hits)]
    # answers to earlier questions (API /decode/clarify): a chosen word becomes a change, "not sure" (None) keeps the slot empty and the question aside
    skipped: list[Clarify] = []
    kept: list[Clarify] = []
    for q in review.clarify:
        if resolved is None or q.span.start not in resolved:
            kept.append(q)
            continue
        choice = resolved[q.span.start]
        if choice is None:
            skipped.append(q)
        elif choice.lower() != q.span.text.lower():
            changes.append(Change(span=q.span, heard=q.span.text, meant=choice, reason="Chosen from the question.", confidence=1.0, source="context"))
    open_and_skipped = kept + skipped
    review.clarify = kept
    effs = _effective(tokens, changes)
    by_start = {t.start: t.i for t in tokens}
    unresolved = {by_start[q.span.start] for q in open_and_skipped if q.span.start in by_start}
    return tokens, hits, review, changes, effs, unresolved, skipped


def decode(text: str, accent_hint: str | None = None, path: str = "typed", cfg: SafetyConfig | None = None,
           resolved: dict[int, str | None] | None = None) -> DecodedCard:
    """`resolved` = answers to earlier clarifying questions, keyed by the question's span start (code points): a word = that choice, None = "not sure"."""
    tokens, hits, review, changes, effs, unresolved, skipped = _run(text, accent_hint, path, cfg, resolved)
    actions = extract(effs, text, get_domain(), unresolved) if effs else Actions()
    open_slots = {q.slot for q in review.clarify} | {q.slot for q in skipped}
    if open_slots & {"where", "where_or_when"}:
        actions.where = None  # a question is open about the place: no silent guess
    if open_slots & {"when", "where_or_when"}:
        actions.when = None
    if "amount" in open_slots:
        actions.how_much = None
    if "negation" in open_slots:
        actions.what = None  # it is not clear whether this is an instruction or its opposite
    tips = list(dict.fromkeys(review.tips))[:1]
    confidence = 0.95
    if changes:
        confidence = min(confidence, min(c.confidence for c in changes))
    if review.clarify or skipped:
        confidence = min(confidence, 0.5)
    return DecodedCard(
        original_text=text, plain_english=_plain(text, effs, changes, hits), changes=changes, phrases=[to_phrase_hit(h) for h in hits], actions=actions,
        clarify=review.clarify, skipped=skipped, tips=tips, confidence=round(confidence, 2), accent_used=accent_hint, path=path,
    )


def inspect_decode(text: str, accent_hint: str | None = None, path: str = "typed", cfg: SafetyConfig | None = None) -> dict:
    """Every stage, for the how-it-works page: tokens, glossary hits, the slots, what was examined and decided, the effective words, the card."""
    tokens, hits, review, changes, effs, unresolved, _skipped = _run(text, accent_hint, path, cfg)
    slots = find_slots(tokens, get_domain(), text)
    return {
        "path": path,
        "tokens": [{"i": t.i, "text": t.text, "start": t.start, "end": t.end} for t in tokens],
        "glossary": [{"phrase": h.entry.phrase, "span": h.span.model_dump(), "category": h.entry.category} for h in hits],
        "slots": [{"token": tokens[i].text, "kind": s.kind, "expects": sorted(s.expects), "trigger": s.trigger} for i, s in slots.items()],
        "examined": [{"token": e.token.text, "slot": e.slot.kind, "decision": e.decision, "best": e.best, "margin": round(e.margin, 2), "options": list(e.options)} for e in review.examined],
        "effective_words": [e.word for e in effs],
        "unresolved_tokens": sorted(unresolved),
        "card": decode(text, accent_hint, path, cfg).model_dump(),
    }

