"""Public entry point: check_reply(facts, reply) -> list[FactResult].

Pipeline: clean/tokenize -> match by ear -> slot fill -> negation scope -> exact compare -> decide.
No network, no LLM, no randomness.
"""

from __future__ import annotations

from typing import Any

from . import fallback, negation
from .compare import EngineConfig, Env, compare_fact
from .lexicon import get_lexicon
from .matcher import Ctx, Match, prepare
from .schema import Fact, FactResult, FactType
from .slots import Heard, Slots, fill_slots

_ACTION_CATS = ("action_stop", "action_call", "action_return", "action_continue", "action_avoid")


def _coerce(facts: list[Any]) -> list[Fact]:
    return [f if isinstance(f, Fact) else Fact.model_validate(f) for f in facts]


def analyze(reply: str, lang_hint: str | None = None) -> tuple[Ctx, Slots, dict[int, Match]]:
    ctx = prepare(reply, lang_hint)
    slots = fill_slots(ctx)

    # everything a negator could reach
    targets: list[tuple[int, int]] = []
    owners: list[Heard | Match] = []
    for h in slots.all():
        if h.inferred:
            continue
        targets.append((h.first, h.last))
        owners.append(h)
    for m in ctx.matches:
        if m.category in _ACTION_CATS or m.category in ("symptom", "travel"):
            targets.append((m.i, m.j))
            owners.append(m)

    assigned = negation.assign(ctx, targets)
    match_neg: dict[int, Match] = {}
    for ti, neg in assigned.items():
        o = owners[ti]
        if isinstance(o, Heard):
            o.negated, o.neg_match = True, neg
        else:
            match_neg[id(o)] = neg
    return ctx, slots, match_neg


def check_reply(
    facts: list[Any],
    reply: str,
    lang_hint: str | None = None,
    config: EngineConfig | None = None,
) -> list[FactResult]:
    fs = _coerce(facts)
    ctx, slots, match_neg = analyze(reply or "", lang_hint)
    env = Env(ctx=ctx, slots=slots, match_neg=match_neg, cfg=config or EngineConfig(), facts=fs)
    results = []
    for f in fs:
        res = compare_fact(env, f)
        if f.type == FactType.condition:
            res = fallback.apply(f, res, reply or "")
        results.append(res)
    return results


def inspect_reply(reply: str, lang_hint: str | None = None, facts: list[Any] | None = None) -> dict:
    """Stage-by-stage view for the /how-it-works inspector (tokens, matches, slots, results)."""
    ctx, slots, match_neg = analyze(reply or "", lang_hint)
    out: dict[str, Any] = {
        "tokens": [
            {"text": t.text, "norm": t.norm, "start": t.start, "end": t.end, "kind": t.kind, "sentence": t.sent}
            for t in ctx.tokens
        ],
        "matches": [
            {
                "start": m.start,
                "end": m.end,
                "text": m.surface,
                "category": m.category,
                "value": m.value if not isinstance(m.value, float) or not m.value.is_integer() else int(m.value),
                "lang": m.lang,
                "score": round(m.score),
                "kind": m.kind,
                "canonical": m.entry.canonical,
                "ambiguous_with": [{"lang": a.lang, "category": a.category, "value": str(a.value)} for a in m.alts],
                "negated": id(m) in match_neg or m.entry.negates,
            }
            for m in ctx.matches
        ],
        "slots": [
            {
                "type": h.type.value,
                "value": h.value if not isinstance(h.value, float) or not h.value.is_integer() else int(h.value),
                "unit": h.unit,
                "text": h.surface(ctx.text),
                "confidence": h.confidence,
                "inferred": h.inferred,
                "negated": h.negated,
                "spans": [s.model_dump() for s in ctx.spans(h.matches)],
            }
            for h in slots.all()
        ],
        "bare_numbers": [m.surface for m in slots.bare_numbers],
    }
    if facts is not None:
        out["results"] = [r.model_dump(mode="json") for r in check_reply(facts, reply, lang_hint)]
    return out


def lexicon_stats() -> dict:
    lex = get_lexicon()
    by_lang: dict[str, int] = {}
    for e in lex.entries:
        by_lang[e.lang] = by_lang.get(e.lang, 0) + 1
    return {"entries": len(lex.entries), "by_language": by_lang}
