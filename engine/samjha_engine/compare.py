"""Exact comparison + status + human-readable reason.

Rules that matter for safety:
* numbers / dates / durations are compared EXACTLY (deterministic code, never an LLM);
* a conflicting second value for the same slot => `unclear`, never `understood`;
* confidence below the threshold => `unclear`;
* a heard value that belongs to ANOTHER fact of the same type is "claimed" by that fact and is never treated as
  evidence that THIS fact was heard wrong (see DECISIONS D4).
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz

from .matcher import Ctx, Match, prepare
from .normalize import sound_key
from .schema import Fact, FactResult, FactType, Span, Status
from .slots import MINUTES, Heard, Slots

SOLID_UNITS = {"tablet", "capsule"}
FOOD_TAGS = {"before_food", "after_food", "empty_stomach"}
TOD_TAGS = {"morning", "noon", "afternoon", "evening", "night", "bedtime"}
ACTION_CAT = {
    "stop": "action_stop",
    "call": "action_call",
    "come_back": "action_return",
    "continue": "action_continue",
    "avoid": "action_avoid",
}
OPPOSITE = {"stop": "continue", "continue": "stop"}
CONDITION_WINDOW = 12
TRIGGER_STOPWORDS = {"if", "you", "feel", "get", "gets", "have", "when", "any", "the", "your", "then", "until", "with", "that"}


@dataclass
class EngineConfig:
    unclear_threshold: float = field(default_factory=lambda: float(os.getenv("UNCLEAR_THRESHOLD", "0.6")))


@dataclass
class Env:
    ctx: Ctx
    slots: Slots
    match_neg: dict[int, Match]  # id(match) -> negator match
    cfg: EngineConfig
    facts: list[Fact]


# ------------------------------------------------------------------------------------------------
# formatting helpers
# ------------------------------------------------------------------------------------------------
def fmt(v: Any) -> str:
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:g}"
    return str(v)


def plural(unit: str | None, n: float) -> str:
    if not unit:
        return ""
    return unit if n == 1 else f"{unit}s"


def describe_value(t: FactType, value: Any, unit: str | None) -> str:
    if t == FactType.dose:
        return f"{fmt(value)} {plural(unit, float(value))}".strip()
    if t == FactType.frequency:
        v = float(value)
        if v == 1:
            return "once a day"
        if v.is_integer():
            return f"{fmt(v)} times a day"
        return f"{fmt(v)} times a day"
    if t == FactType.duration:
        return f"{fmt(value)} {plural(unit or 'day', float(value))}"
    if t == FactType.amount:
        return f"{fmt(value)} {unit or ''}".strip()
    if t == FactType.timing:
        vals = value if isinstance(value, list | tuple | set) else [value]
        return ", ".join(str(x).replace("_", " ") for x in vals)
    return str(value)


def describe_heard(env: Env, h: Heard) -> str:
    if h.type == FactType.duration and h.extra.get("raw_unit") in ("week", "month"):
        return describe_value(h.type, h.value, h.unit)
    return describe_value(h.type, h.value, h.unit)


def expected_desc(fact: Fact) -> str:
    return describe_value(fact.type, fact_value(fact), fact.unit)


def fact_value(fact: Fact) -> Any:
    if fact.type in (FactType.dose, FactType.frequency, FactType.duration, FactType.amount):
        try:
            return float(fact.value)
        except (TypeError, ValueError):
            return fact.value
    return fact.value


def jsonable(v: Any) -> Any:
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, set | frozenset):
        return sorted(v)
    return v


def _terms(matches: list[Match]) -> list[dict]:
    seen: set[int] = set()
    out = []
    for m in matches:
        if id(m) in seen:
            continue
        seen.add(id(m))
        if m.category == "filler":
            continue
        out.append(m.term())
    return out


def _result(fact: Fact, status: Status, heard: Any, evidence: list[Match], env: Env, conf: float, reason: str) -> FactResult:
    return FactResult(
        fact_id=fact.id,
        status=status,
        heard_value=jsonable(heard),
        expected_value=jsonable(fact.value if fact.type == FactType.condition else fact_value(fact)),
        evidence=env.ctx.spans(evidence),
        confidence=round(max(0.0, min(1.0, conf)), 3),
        reason=reason,
        matched_terms=_terms(evidence),
    )


# ------------------------------------------------------------------------------------------------
# equality per fact type
# ------------------------------------------------------------------------------------------------
def _unit_class(u: str | None) -> str | None:
    if u in SOLID_UNITS:
        return "solid"
    return u


def _norm_date(v: str) -> str:
    v = str(v).strip().lower()
    if len(v) == 10 and v[4] == "-":  # ISO YYYY-MM-DD
        return v
    if ":" in v:
        hh, mm = v.split(":")
        return f"{int(hh):02d}:{mm}"
    return v


def _date_eq(a: str, b: str) -> bool:
    a, b = _norm_date(a), _norm_date(b)
    if a == b:
        return True
    if len(a) == 10 and len(b) == 5 and b[2] == "-":
        return a[5:] == b
    if len(b) == 10 and len(a) == 5 and a[2] == "-":
        return b[5:] == a
    return False


def h_equals(h: Heard, fact: Fact) -> bool:
    if h.type != fact.type:
        return False
    t = fact.type
    if t == FactType.dose:
        return math.isclose(float(h.value), float(fact.value), abs_tol=1e-6) and (
            fact.unit is None or _unit_class(h.unit) == _unit_class(fact.unit)
        )
    if t == FactType.frequency:
        return math.isclose(float(h.value), float(fact.value), abs_tol=1e-3)
    if t == FactType.duration:
        hm = float(h.value) * MINUTES[h.unit or "day"]
        fm = float(fact.value) * MINUTES[fact.unit or "day"]
        return math.isclose(hm, fm, abs_tol=1e-6)
    if t == FactType.amount:
        return math.isclose(float(h.value), float(fact.value), abs_tol=1e-6) and (
            fact.unit is None or (h.unit or "").upper() == fact.unit.upper()
        )
    if t == FactType.date:
        return _date_eq(str(h.value), str(fact.value))
    return False


def _claimed_by_other(env: Env, h: Heard, fact: Fact) -> bool:
    return any(o.id != fact.id and o.type == fact.type and h_equals(h, o) for o in env.facts)


def _bare_numbers_reason(env: Env) -> str:
    nums = ", ".join(f"'{m.surface}'" for m in env.slots.bare_numbers[:3])
    return f"Heard a number ({nums}) with no unit word, so it can't be tied to this fact."


# ------------------------------------------------------------------------------------------------
# numeric-style facts: dose, frequency, duration, amount, date
# ------------------------------------------------------------------------------------------------
def compare_slot(env: Env, fact: Fact) -> FactResult:
    H = env.slots.heard.get(fact.type, [])
    explicit = [h for h in H if not h.inferred]
    if explicit:
        H = explicit
    noun = {
        FactType.dose: "a dose",
        FactType.frequency: "how often",
        FactType.duration: "how long",
        FactType.amount: "an amount",
        FactType.date: "a date/time",
    }[fact.type]
    want = expected_desc(fact)

    match_active = [h for h in H if h_equals(h, fact) and not h.negated]
    match_neg = [h for h in H if h_equals(h, fact) and h.negated]
    foreign = [h for h in H if not h_equals(h, fact) and not h.negated and not _claimed_by_other(env, h, fact)]
    src = lambda h: f"'{h.surface(env.ctx.text)}'"  # noqa: E731

    # other facts of this type that nothing in the reply matched can "absorb" a stray value:
    # "trip tuesday, money friday" -> tuesday is the (wrong) trip date, not a contradiction of the friday fact
    spare = sum(1 for o in env.facts if o.id != fact.id and o.type == fact.type and not any(h_equals(h, o) for h in H))
    if match_active:
        best = max(match_active, key=lambda h: h.confidence)
        if len(foreign) > spare:
            f0 = foreign[0]
            return _result(
                fact, Status.unclear, describe_heard(env, f0), best.matches + f0.matches, env, 0.5,
                f"Heard both {describe_heard(env, best)} ({src(best)}) and {describe_heard(env, f0)} ({src(f0)}); expected {want}. Conflicting, so not marked understood.",
            )
        suffix = " (inferred from the times of day mentioned)" if best.inferred else ""
        return _result(
            fact, Status.understood, best.value if fact.type != FactType.duration else best.value, best.matches, env, best.confidence,
            f"Heard {src(best)} = {describe_heard(env, best)}; matches expected {want}{suffix}.",
        )
    if match_neg:
        h = match_neg[0]
        neg = h.neg_match.surface if h.neg_match else "a negation"
        return _result(
            fact, Status.negated, describe_heard(env, h), h.matches + ([h.neg_match] if h.neg_match else []), env, h.confidence,
            f"Heard {src(h)} but negated by '{neg}'; the message says {want}.",
        )
    if foreign:
        h = max(foreign, key=lambda x: x.confidence)
        if h.inferred:  # only guessed from times of day: flag it, but never call it "wrong"
            return _result(
                fact, Status.unclear, h.value, h.matches, env, min(h.confidence, 0.55),
                f"No explicit frequency was said; the times of day mentioned ({src(h)}) suggest {describe_heard(env, h)}, expected {want}. Please check.",
            )
        extra = ""
        return _result(
            fact, Status.wrong, h.value, h.matches, env, h.confidence,
            f"Heard {src(h)} = {describe_heard(env, h)}; expected {want}.{extra}",
        )
    if env.slots.bare_numbers and fact.type in (FactType.dose, FactType.frequency, FactType.duration, FactType.amount):
        return _result(fact, Status.unclear, None, list(env.slots.bare_numbers[:2]), env, 0.4, _bare_numbers_reason(env))
    return _result(fact, Status.missing, None, [], env, 0.85, f"Did not hear {noun} (expected {want}).")


# ------------------------------------------------------------------------------------------------
# timing (set comparison)
# ------------------------------------------------------------------------------------------------
def compare_timing(env: Env, fact: Fact) -> FactResult:
    raw = fact.value
    expected = set(raw) if isinstance(raw, list | tuple | set) else {raw}
    H = env.slots.heard[FactType.timing]
    present: dict[str, Heard] = {}
    negated: dict[str, Heard] = {}
    for h in H:
        (negated if h.negated else present).setdefault(h.value, h)
    want = describe_value(FactType.timing, sorted(expected), None)
    missing_tags = expected - present.keys()

    def ev(tags: set[str], pool: dict[str, Heard]) -> list[Match]:
        return [m for t in tags if t in pool for m in pool[t].matches]

    if not missing_tags:
        used = ev(expected, present)
        conflict = (
            ("after_food" in expected and (present.keys() & {"before_food", "empty_stomach"}))
            or ("before_food" in expected and "after_food" in present)
        )
        if conflict:
            other = ev(present.keys() & {"before_food", "after_food", "empty_stomach"}, present)
            return _result(fact, Status.unclear, sorted(present.keys() & FOOD_TAGS), used + other, env, 0.5,
                           f"Heard both before- and after-food wording; expected {want}. Conflicting.")
        conf = min(present[t].confidence for t in expected)
        got = ", ".join(t.replace("_", " ") for t in sorted(expected))
        return _result(fact, Status.understood, sorted(expected), used, env, conf,
                       f"Heard {got}; matches expected {want}.")

    # something expected is missing: is it CONTRADICTED?
    contradicted: list[str] = []
    for e in sorted(missing_tags):
        if e == "after_food" and present.keys() & {"before_food", "empty_stomach"}:
            contradicted.append(e)
        elif e == "before_food" and "after_food" in present:
            contradicted.append(e)
        elif e == "empty_stomach" and "after_food" in present:
            contradicted.append(e)
        elif e in TOD_TAGS and (present.keys() & TOD_TAGS) - expected:
            contradicted.append(e)
    if contradicted:
        heard_tags = set(present.keys()) & (FOOD_TAGS | TOD_TAGS)
        hs = ", ".join(t.replace("_", " ") for t in sorted(heard_tags))
        return _result(fact, Status.wrong, sorted(heard_tags), ev(heard_tags, present), env,
                       min((present[t].confidence for t in heard_tags), default=0.8),
                       f"Heard {hs}; expected {want}.")
    neg_hit = missing_tags & negated.keys()
    if neg_hit:
        t = sorted(neg_hit)[0]
        h = negated[t]
        return _result(fact, Status.negated, t, h.matches + ([h.neg_match] if h.neg_match else []), env, h.confidence,
                       f"Heard '{t.replace('_', ' ')}' but negated; the message says {want}.")
    got = expected & present.keys()
    miss = ", ".join(t.replace("_", " ") for t in sorted(missing_tags))
    if got:
        return _result(fact, Status.missing, sorted(got), ev(got, present), env, 0.8,
                       f"Heard part of it ({', '.join(t.replace('_', ' ') for t in sorted(got))}) but not: {miss}.")
    return _result(fact, Status.missing, None, [], env, 0.85, f"Did not hear the timing (expected {want}).")


# ------------------------------------------------------------------------------------------------
# condition: trigger + action, with negation
# ------------------------------------------------------------------------------------------------
def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def find_trigger(env: Env, trigger_text: str) -> tuple[list[Match], float] | None:
    """Return (evidence matches, confidence) if the reply mentions the trigger."""
    ctx = env.ctx
    tctx = prepare(trigger_text)
    keys = {m.value for m in tctx.matches if m.category in ("symptom", "travel")}
    if keys:
        hits = [m for m in ctx.matches if m.category in ("symptom", "travel") and m.value in keys]
        if hits:
            hit = max(hits, key=lambda m: m.score)
            return [hit], hit.score / 100
        return None
    # not a lexicon symptom: fuzzy match the trigger's significant words against the reply
    sig = []
    for t in tctx.tokens:
        m = tctx.match_at.get(t.idx)
        if t.is_word and len(t.norm) >= 4 and t.norm not in TRIGGER_STOPWORDS and not (m and m.category == "filler"):
            sig.append(_stem(t.norm))
    if not sig:
        return None
    found: list[Match] = []
    for s in sig:
        sk = sound_key(s)
        for t in ctx.tokens:
            if not t.is_word or len(t.norm) < 4:
                continue
            tk = sound_key(_stem(t.norm))
            if tk == sk or (tk[:1] == sk[:1] and len(tk) >= 5 and fuzz.ratio(tk, sk) >= 85):
                found.append(_token_match(t, ctx))
                break
    need = max(1, math.ceil(0.6 * len(sig)))
    if len(found) >= need:
        return found, 0.8
    return None


def _token_match(t, ctx: Ctx) -> Match:
    from .lexicon import Entry

    e = Entry(canonical=t.norm, category="trigger_word", value=t.norm, lang="?")
    return Match(t.idx, t.idx, e, 90, "fuzzy", t.text, t.start, t.end)


def _dist(ctx: Ctx, a: Match, b: Match) -> int:
    if a.j < b.i:
        return ctx.cidx[b.i] - ctx.cidx[a.j]
    if b.j < a.i:
        return ctx.cidx[a.i] - ctx.cidx[b.j]
    return 0


def _is_negated(env: Env, m: Match) -> bool:
    return m.entry.negates or id(m) in env.match_neg


def compare_condition(env: Env, fact: Fact) -> FactResult:
    ctx = env.ctx
    val = fact.value if isinstance(fact.value, dict) else {}
    trigger_text = str(val.get("trigger", "")).strip()
    action = str(val.get("action", "stop"))
    want = str(val.get("text") or fact.label)
    trig = find_trigger(env, trigger_text) if trigger_text else None

    if action == "avoid":
        return _compare_avoid(env, fact, trig, want)

    cat = ACTION_CAT.get(action, "action_stop")
    exp_all = [m for m in ctx.matches if m.category == cat]
    exp_ok = [m for m in exp_all if not _is_negated(env, m)]
    exp_neg = [m for m in exp_all if _is_negated(env, m)]
    opp_cat = ACTION_CAT.get(OPPOSITE.get(action, ""), "")
    opp_ok = [m for m in ctx.matches if opp_cat and m.category == opp_cat and not _is_negated(env, m)]

    tm, tconf = (trig if trig else ([], 0.0))
    trig_present = bool(tm)
    trig_neg = trig_present and any(_is_negated(env, m) for m in tm)
    tname = tm[0].surface if tm else (trigger_text or "the trigger")

    def near(ms: list[Match]) -> list[Match]:
        if not trig_present:
            return ms
        return [m for m in ms if _dist(ctx, tm[0], m) <= CONDITION_WINDOW]

    ok_near = near(exp_ok)
    if exp_ok and exp_neg:
        return _result(fact, Status.unclear, None, exp_ok + exp_neg + tm, env, 0.5,
                       f"Reply both says and denies the action ({exp_ok[0].surface!r} / {exp_neg[0].surface!r}); not marked understood.")
    if ok_near and trig_present:
        a = max(ok_near, key=lambda m: m.score)
        if trig_neg:
            return _result(fact, Status.unclear, None, tm + [a], env, 0.5,
                           f"Reply seems to say '{tname}' does NOT happen; can't confirm the rule: {want}.")
        conf = min(tconf, a.score / 100) * (0.85 if a.alts else 1.0)
        return _result(fact, Status.understood, action, tm + [a], env, conf,
                       f"Heard '{tname}' with '{a.surface}' ({action.replace('_', ' ')}); matches: {want}.")
    if exp_neg:
        a = exp_neg[0]
        negator = env.match_neg.get(id(a))
        ev = [a] + ([negator] if negator else []) + tm
        why = f"'{a.surface}' carries its own 'don't'" if a.entry.negates else f"'{a.surface}' is negated by '{negator.surface}'" if negator else f"'{a.surface}' is negated"
        return _result(fact, Status.negated, f"do not {action.replace('_', ' ')}", ev, env, min(a.score / 100, tconf or 1.0),
                       f"Heard {why}; the message says: {want}. The reply says the opposite.")
    if opp_ok and trig_present:
        o = opp_ok[0]
        return _result(fact, Status.wrong, OPPOSITE[action], tm + [o], env, min(tconf, o.score / 100),
                       f"Heard '{tname}' with '{o.surface}' ({OPPOSITE[action]}); expected {action.replace('_', ' ')}: {want}.")
    if exp_ok and not trig_present:
        a = exp_ok[0]
        return _result(fact, Status.unclear, action, [a], env, 0.45,
                       f"Heard '{a.surface}' ({action.replace('_', ' ')}) but no mention of '{trigger_text}', so it isn't clear when.")
    if exp_ok and trig_present:  # action exists but far from the trigger
        a = exp_ok[0]
        return _result(fact, Status.unclear, action, tm + [a], env, 0.45,
                       f"Heard '{tname}' and '{a.surface}' but far apart; unclear they go together.")
    if trig_present:
        return _result(fact, Status.unclear, None, tm, env, 0.5,
                       f"Heard '{tname}' but not what to do about it ({action.replace('_', ' ')}).")
    return _result(fact, Status.missing, None, [], env, 0.85, f"No mention of '{trigger_text}' or what to do about it.")


def _compare_avoid(env: Env, fact: Fact, trig, want: str) -> FactResult:
    ctx = env.ctx
    tm, tconf = trig if trig else ([], 0.0)
    fused = [m for m in ctx.matches if m.category == "action_avoid" and _is_negated(env, m)]
    if tm:
        t = tm[0]
        if _is_negated(env, t):
            neg = env.match_neg.get(id(t))
            return _result(fact, Status.understood, "avoid", tm + ([neg] if neg else []), env, min(tconf, neg.score / 100 if neg else 1.0),
                           f"Heard '{t.surface}' negated{f' by {neg.surface!r}' if neg else ''}; matches: {want}.")
        if fused:
            return _result(fact, Status.understood, "avoid", tm + fused, env, min(tconf, fused[0].score / 100),
                           f"Heard '{t.surface}' with '{fused[0].surface}' (don't); matches: {want}.")
        return _result(fact, Status.unclear, None, tm, env, 0.5,
                       f"Heard '{t.surface}' but no 'don't' wording, so it isn't clear the rule was understood: {want}.")
    if fused:
        return _result(fact, Status.understood, "avoid", fused, env, fused[0].score / 100,
                       f"Heard '{fused[0].surface}' (don't); matches: {want}.")
    return _result(fact, Status.missing, None, [], env, 0.85, f"No mention of the restriction: {want}.")


# ------------------------------------------------------------------------------------------------
def compare_fact(env: Env, fact: Fact) -> FactResult:
    if fact.type == FactType.timing:
        res = compare_timing(env, fact)
    elif fact.type == FactType.condition:
        res = compare_condition(env, fact)
    else:
        res = compare_slot(env, fact)
    thr = env.cfg.unclear_threshold
    if res.status in (Status.understood, Status.wrong, Status.negated) and res.confidence < thr:
        res = res.model_copy(
            update={
                "status": Status.unclear,
                "reason": f"{res.reason} (match confidence {res.confidence:.2f} is below {thr:.2f}, so we are not sure.)",
            }
        )
    return res


__all__ = ["EngineConfig", "Env", "compare_fact", "Span"]
