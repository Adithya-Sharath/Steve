"""The typed-text path (WhatsApp messages spelled by ear): full sound-swap decoding (D40).

There is no speech-to-text in front of typed words, so nothing has already normalised them. For each word we build candidates by undoing up to two
accent-pack SPELLING swaps ("barking" -> "parking" with b -> p, "fife" -> "five" with f -> v, "tree" -> "three" with t -> th) and keep only real common words.
A candidate must beat the word as typed by a margin; a real word that is not in a critical span (a barking dog) is never touched; a close call becomes a
clarifying question. Nothing here uses a model.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schema import Span
from .accents import Swap, active_swaps
from .domain import Domain, get_domain
from .phonetics import PACK_DISCOUNT, is_word, zipf
from .safety import Review, SafetyConfig, _next_to_or, explain_swap
from .schema import Change, Clarify
from .spans import Slot, find_slots
from .tokens import Token, tokenize

NONWORD_PENALTY = 1.0  # a word that is not a real English word starts behind any real candidate


@dataclass(frozen=True)
class SpellCand:
    word: str
    cost: float
    swaps: tuple[Swap, ...]


def spelling_candidates(word: str, swaps: tuple[Swap, ...], max_swaps: int = 2) -> list[SpellCand]:
    """Real common words reachable by undoing up to `max_swaps` accent swaps in the spelling of `word` (cheapest first)."""
    w = word.lower()
    frontier: dict[str, tuple[float, tuple[Swap, ...]]] = {w: (0.0, ())}
    found: dict[str, SpellCand] = {}
    for _ in range(max_swaps):
        nxt: dict[str, tuple[float, tuple[Swap, ...]]] = {}
        for cur, (cost, used) in frontier.items():
            for s in swaps:
                start = 0
                while (k := cur.find(s.heard, start)) != -1:
                    new = cur[:k] + s.meant + cur[k + len(s.heard) :]
                    start = k + 1
                    c = cost + (1 - PACK_DISCOUNT * s.weight)
                    if new not in nxt or c < nxt[new][0]:
                        nxt[new] = (c, (*used, s))
        for new, (c, used) in nxt.items():
            if new != w and is_word(new) and (new not in found or c < found[new].cost):
                found[new] = SpellCand(new, round(c, 3), used)
        frontier = nxt
    return sorted(found.values(), key=lambda c: (c.cost, -zipf(c.word), c.word))


def _fit(word: str, slot: Slot | None, dom: Domain, cfg: SafetyConfig) -> float:
    s = cfg.freq_weight * zipf(word)
    cat = dom.category(word)
    if slot is not None and cat in slot.expects:
        s += cfg.domain_boost
    elif cat is not None:
        s += 0.5  # workplace vocabulary is likelier than an arbitrary word
    return s


RESPELL_MIN_ZIPF = 6.0  # the intended word must be very common (the, this, that ...)
RESPELL_GAP = 2.4  # and the typed word far rarer than it (te / de for the: foreign-language words that wordfreq counts)


def _respelled_function_word(review: Review, tok, swaps: tuple[Swap, ...]) -> bool:
    """"te", "dis", "dat" typed for "the", "this", "that": a strong accent swap turns the typed word into a MUCH commoner English word, so we take it."""
    best = None
    for c in spelling_candidates(tok.norm, swaps, max_swaps=1):
        if zipf(c.word) >= RESPELL_MIN_ZIPF and zipf(c.word) - zipf(tok.norm) >= RESPELL_GAP and c.cost <= 0.6 and (best is None or c.cost < best.cost):
            best = c
    if best is not None:
        why, tip = explain_swap(tok, best.word, best.swaps, None)
        review.changes.append(Change(span=Span(start=tok.start, end=tok.end, text=tok.text), heard=tok.text, meant=best.word, reason=why, confidence=0.8, source="sound"))
        if tip:
            review.tips.append(tip)
    return best is not None


def review_typed(text: str, accent_hint: str | None = None, cfg: SafetyConfig | None = None, domain: Domain | None = None,
                 skip: set[int] | None = None) -> Review:
    """Sound-swap decoding of typed text. `skip` = token indexes already explained (glossary phrases)."""
    cfg, dom = cfg or SafetyConfig(), domain or get_domain()
    swaps = active_swaps(accent_hint)
    tokens = tokenize(text)
    review = Review(text)
    respelled: set[int] = set()
    for tok in tokens:  # pass 1: respelled function words ("te" -> "the"), so that the spans below are found on the words as meant
        if tok.norm.isalpha() and not (skip and tok.i in skip) and is_word(tok.norm) and _respelled_function_word(review, tok, swaps):
            respelled.add(tok.i)
    meant = {c.span.start: c.meant for c in review.changes}
    slots = find_slots([Token(t.i, t.text, meant.get(t.start, t.norm), t.start, t.end) for t in tokens], dom, text, include_action=True)
    for tok in tokens:
        if not tok.norm.isalpha() or (skip and tok.i in skip) or tok.i in respelled:
            continue
        slot = slots.get(tok.i)
        real = is_word(tok.norm)
        if real and slot is None:
            continue  # a real word outside a critical span is left alone
        if real and dom.category(tok.norm) in slot.expects:
            continue  # it already fits where it sits
        cands = spelling_candidates(tok.norm, swaps)
        if slot is not None:
            cands = [c for c in cands if dom.category(c.word) in slot.expects or not real]
        if not cands:
            continue
        base = _fit(tok.norm, slot, dom, cfg) - (0.0 if real else NONWORD_PENALTY)
        scored = sorted(((_fit(c.word, slot, dom, cfg) - cfg.edit_weight * c.cost, c) for c in cands), key=lambda x: (-x[0], x[1].cost, x[1].word))
        top, best = scored[0]
        margin = top - base
        close = [c for s, c in scored[1:3] if top - s <= cfg.close_gap]
        span = Span(start=tok.start, end=tok.end, text=tok.text)
        offered = _next_to_or(tokens, tok.i)  # "the barking or the building": choices are on offer, so ask instead of rewriting
        if margin >= cfg.rewrite_margin and not close and not offered:
            why, tip = explain_swap(tok, best.word, best.swaps, slot)
            review.changes.append(Change(span=span, heard=tok.text, meant=best.word, reason=why, confidence=round(min(0.95, 0.5 + margin / 6), 2), source="sound"))
            if tip:
                review.tips.append(tip)
        elif margin >= cfg.clarify_margin or (offered and margin > 0):
            options = tuple(dict.fromkeys([best.word, *(c.word for c in close), tok.norm]))
            question = " or ".join(o.capitalize() if k == 0 else o for k, o in enumerate(options)) + "?"
            review.clarify.append(Clarify(span=span, options=list(options), question=question, slot=slot.kind if slot else ""))
    return review

