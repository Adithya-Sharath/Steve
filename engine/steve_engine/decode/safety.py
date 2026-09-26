"""The voice safety net (D40, D41). Speech-to-text already turns most accent-shaped words into the intended ones, but it sometimes writes a DIFFERENT REAL
WORD ("barking" for "parking"). This module looks at a transcript and, only where a wrong word would change what a worker does, checks whether a
sound-alike word fits much better.

Policy (in this order):
  1. Only words inside a CRITICAL SPAN are examined (where / when / number / amount / object; see spans.py). Everything else is left exactly as transcribed,
     so "the barking dog is at the gate" keeps its "barking".
  2. A word that already belongs where it sits (a place after "to the") is never touched.
  3. Candidates are REAL common words one phone away (CMUdict), and must be the kind of word the slot expects. An accent rule lowers a candidate's cost.
  4. Each candidate is scored: frequency + a boost for fitting the slot - the sound-change cost. The transcript word is scored the same way.
  5. Rewrite only when the best alternative wins by REWRITE_MARGIN and neither word is in the DON'T-TOUCH set (negations, numbers, amounts, named times).
     A smaller win, or any win that involves a don't-touch word, becomes a CLARIFYING QUESTION ("Parking or barking?"). Otherwise keep the transcript.
Nothing here is tuned on L2-ARCTIC (a test set only, D41); the margins were set on synthetic domain sentences.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schema import Span
from .accents import Swap, active_swaps
from .domain import Domain, get_domain
from .phonetics import SoundAlike, vocab_alikes, zipf
from .schema import Change, Clarify
from .spans import Slot, find_slots
from .tokens import Token, tokenize


@dataclass(frozen=True)
class SafetyConfig:
    freq_weight: float = 0.35
    domain_boost: float = 2.0
    edit_weight: float = 1.0
    rewrite_margin: float = 1.6
    clarify_margin: float = 0.6
    close_gap: float = 0.3  # a second candidate this close to the best is a reason to ask
    other_domain_extra: float = 0.8  # a word that is itself workplace vocabulary of another kind ("at work") needs a bigger win before we question it
    max_cost: float = 1.0  # a candidate must be at most this far away in sound (about two same-class substitutions or one insert or delete)


@dataclass
class Examined:
    token: Token
    slot: Slot
    decision: str  # fits | no_alternative | keep | rewrite | clarify
    best: str | None = None
    margin: float = 0.0
    options: tuple[str, ...] = ()
    candidates: tuple[tuple[str, float], ...] = ()  # the best few alternatives with their total score (for the how-it-works inspector)
    original_score: float = 0.0  # the score of the word as it stands


@dataclass
class Review:
    text: str
    changes: list[Change] = field(default_factory=list)
    clarify: list[Clarify] = field(default_factory=list)
    examined: list[Examined] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)

    @property
    def corrected(self) -> str:
        return apply_changes(self.text, self.changes)


def fit(word: str, slot: Slot, dom: Domain, cfg: SafetyConfig) -> float:
    s = cfg.freq_weight * zipf(word)
    if dom.category(word) in slot.expects:
        s += cfg.domain_boost
    return s


def _match_case(original: str, new: str) -> str:
    if original.isupper() and len(original) > 1:
        return new.upper()
    return new.capitalize() if original[:1].isupper() else new


def apply_changes(text: str, changes: list[Change]) -> str:
    out, pos = [], 0
    for c in sorted(changes, key=lambda c: c.span.start):
        out += [text[pos : c.span.start], _match_case(c.span.text, c.meant)]
        pos = c.span.end
    return "".join(out) + text[pos:]


def _explain(tok: Token, cand: SoundAlike, slot: Slot, swaps: tuple[Swap, ...]) -> tuple[str, str | None]:
    why = f"'{tok.text}' does not fit {slot.label} here; '{cand.word}' does and sounds close"
    tip = None
    if cand.pack_rule:
        pack_id, rule = (x.strip() for x in cand.pack_rule.split(":", 1))
        heard, meant = (x.strip() for x in rule.split("->"))
        swap = next((s for s in swaps if s.pack == pack_id and s.heard == heard and s.meant == meant), None)
        if swap:
            why += f" ({swap.note})"
            tip = f"It often sounds like this: {swap.note}."
    return why + ".", tip


def explain_swap(tok: Token, meant: str, swaps: tuple[Swap, ...], slot: Slot | None) -> tuple[str, str | None]:
    """Reason and tip for a typed-text change: 'x' probably meant 'y', with the accent note that explains the spelling."""
    notes = list(dict.fromkeys(s.note for s in swaps))
    where = f" here ({slot.label} fits)" if slot is not None else ""
    why = f"'{tok.text}' probably meant '{meant}'{where}" + (f" ({'; '.join(notes)})" if notes else "") + "."
    return why, (f"It often sounds like this: {notes[0]}." if notes else None)


def _next_to_or(tokens: list[Token], i: int) -> bool:
    around = [tokens[k].norm for k in range(max(0, i - 4), min(len(tokens), i + 5)) if k != i]
    return "or" in around


def review_transcript(text: str, accent_hint: str | None = None, cfg: SafetyConfig | None = None, domain: Domain | None = None) -> Review:
    cfg, dom = cfg or SafetyConfig(), domain or get_domain()
    swaps = active_swaps(accent_hint)
    tokens = tokenize(text)
    review = Review(text)
    for i, slot in find_slots(tokens, dom, text).items():
        tok = tokens[i]
        if not tok.norm.isalpha():
            continue
        if dom.category(tok.norm) in slot.expects:
            review.examined.append(Examined(tok, slot, "fits"))
            continue
        vocab = sorted({w for cat in slot.expects for w in dom.words[cat] if w.isalpha()})
        cands = vocab_alikes(tok.norm, vocab, swaps, cfg.max_cost)
        if not cands:
            review.examined.append(Examined(tok, slot, "no_alternative"))
            continue
        base = fit(tok.norm, slot, dom, cfg)
        scored = sorted(((fit(c.word, slot, dom, cfg) - cfg.edit_weight * c.cost, c) for c in cands), key=lambda x: (-x[0], x[1].cost, x[1].word))
        top_score, best = scored[0]
        margin = top_score - base
        view = tuple((c.word, round(s, 2)) for s, c in scored[:4])
        if dom.category(tok.norm) is not None:
            margin -= cfg.other_domain_extra
        span = Span(start=tok.start, end=tok.end, text=tok.text)
        close = [c for s, c in scored[1:3] if top_score - s <= cfg.close_gap]
        touchy = dom.is_dont_touch(tok.norm) or dom.is_dont_touch(best.word)
        offered = _next_to_or(tokens, i)  # "the parking or the building": the speaker is offering choices, so never rewrite one of them
        if margin >= cfg.rewrite_margin and not touchy and not close and not offered:
            why, tip = _explain(tok, best, slot, swaps)
            review.changes.append(Change(span=span, heard=tok.text, meant=best.word, reason=why, confidence=round(min(0.95, 0.5 + margin / 6), 2), source="sound"))
            if tip:
                review.tips.append(tip)
            review.examined.append(Examined(tok, slot, "rewrite", best.word, margin, (best.word,), view, round(base, 2)))
        elif margin >= cfg.clarify_margin or (offered and margin > 0):
            options = tuple(dict.fromkeys([best.word, *(c.word for c in close), tok.norm]))
            question = " or ".join(o.capitalize() if k == 0 else o for k, o in enumerate(options)) + "?"
            review.clarify.append(Clarify(span=span, options=list(options), question=question, slot=slot.kind))
            review.examined.append(Examined(tok, slot, "clarify", best.word, margin, options, view, round(base, 2)))
        else:
            review.examined.append(Examined(tok, slot, "keep", best.word, margin, (), view, round(base, 2)))
    return review
