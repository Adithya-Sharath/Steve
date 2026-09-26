"""Suggest facts from the SENDER's message. The sender always confirms/edits them.

* Default path: a deterministic extractor that reuses the engine's own matcher + slot fillers (no LLM, no keys).
* Optional path: Gemini suggests facts (strict JSON). If it fails for any reason we fall back to the regex path.
The LLM never decides whether a reply was understood; it only proposes what to check.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from steve_engine import Fact, FactType
from steve_engine.compare import describe_value
from steve_engine.matcher import Match, prepare
from steve_engine.negation import assign
from steve_engine.slots import fill_slots

from ..budget import llm_budget
from ..settings import settings

log = logging.getLogger("steve.extractor")

ACTION_PRIORITY = ["action_stop", "action_avoid", "action_call", "action_continue", "action_return"]
ACTION_NAME = {
    "action_stop": "stop", "action_call": "call", "action_return": "come_back",
    "action_continue": "continue", "action_avoid": "avoid",
}
WEEKDAY_LABEL = {d: d.capitalize() for d in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}


def _sentence_text(text: str, ctx, m: Match) -> str:
    sent = ctx.tokens[m.i].sent
    idxs = [t for t in ctx.tokens if t.sent == sent]
    return text[idxs[0].start : idxs[-1].end].strip()


def _freq_label(h) -> str:
    v = float(h.value)
    if h.extra.get("every") and v >= 1:
        interval_h = 24 / v
        if v == 24:
            return "every hour"
        if float(interval_h).is_integer():
            return f"every {int(interval_h)} hours"
    if v == 1:
        return "once a day"
    if v == 2:
        return "twice a day"
    return f"{v:g} times a day"


def regex_extract(text: str) -> list[Fact]:
    ctx = prepare(text)
    slots = fill_slots(ctx)
    facts: list[Fact] = []
    seen: set[tuple] = set()
    counter: dict[str, int] = {}

    def add(type_: FactType, value, unit, label: str, critical: bool = True) -> None:
        key = (type_.value, json.dumps(value, sort_keys=True, default=str), unit)
        if key in seen:
            return
        seen.add(key)
        counter[type_.value] = counter.get(type_.value, 0) + 1
        n = counter[type_.value]
        facts.append(Fact(id=f"{type_.value}_{n}", type=type_, value=value, unit=unit, critical=critical, label=label))

    for h in slots.heard[FactType.dose]:
        if not h.negated:
            add(FactType.dose, h.value if not float(h.value).is_integer() else int(h.value), h.unit,
                describe_value(FactType.dose, h.value, h.unit))
    for h in slots.heard[FactType.frequency]:
        if not h.inferred and not h.negated:
            add(FactType.frequency, h.value if not float(h.value).is_integer() else int(h.value), None, _freq_label(h))
    tags = [h.value for h in slots.heard[FactType.timing] if not h.negated]
    tags = list(dict.fromkeys(tags))
    if tags:
        add(FactType.timing, tags[0] if len(tags) == 1 else tags, None, ", ".join(t.replace("_", " ") for t in tags))
    for h in slots.heard[FactType.duration]:
        if not h.negated:
            v = h.value if not float(h.value).is_integer() else int(h.value)
            unit = h.unit or "day"
            label = describe_value(FactType.duration, h.value, unit)
            add(FactType.duration, v, unit, label)
    for h in slots.heard[FactType.amount]:
        if not h.negated:
            add(FactType.amount, h.value if not float(h.value).is_integer() else int(h.value), h.unit,
                describe_value(FactType.amount, h.value, h.unit))
    for h in slots.heard[FactType.date]:
        if h.negated:
            continue
        v = str(h.value)
        label = f"by {WEEKDAY_LABEL[v]}" if v in WEEKDAY_LABEL else f"at {v}" if ":" in v else v
        add(FactType.date, v, None, label)

    # conditions: one per symptom (best action wins), plus "do not <travel>" restrictions
    symptoms = [m for m in ctx.matches if m.category == "symptom"]
    actions = [m for m in ctx.matches if m.category in ACTION_PRIORITY]
    for sym in symptoms:
        near = [a for a in actions if ctx.cdist(sym, a) <= 8 and not a.entry.negates]
        if not near:
            continue
        best = min(near, key=lambda a: (ACTION_PRIORITY.index(a.category), ctx.cdist(sym, a)))
        action = ACTION_NAME[best.category]
        sent = _sentence_text(text, ctx, sym)
        add(FactType.condition, {"trigger": str(sym.value), "action": action, "text": sent}, None,
            f"{action.replace('_', ' ').capitalize()} if {sym.value}")
    travel = [m for m in ctx.matches if m.category == "travel"]
    if travel:
        neg = assign(ctx, [(m.i, m.j) for m in travel])
        for ti, m in enumerate(travel):
            if ti in neg:
                add(FactType.condition, {"trigger": str(m.value), "action": "avoid", "text": _sentence_text(text, ctx, m)}, None,
                    f"Do not {m.value}")
    return facts


# ------------------------------------------------------------------------------------------------
_PROMPT = """You help a sender check that a reader understood an important message.
Extract the KEY FACTS a reader must get exactly right from the message below. The message may mix languages or
scripts (Manglish, Hinglish, Arabizi, Taglish): do NOT translate or rewrite it.

Fact types and value formats:
- dose: value number, unit one of tablet|capsule|ml|puff|drop|spoon|bottle|photo|form|copy
- frequency: value = times per day (number)
- timing: value = one tag or a list of tags from before_food, after_food, morning, noon, afternoon, evening, night, bedtime, empty_stomach
- duration: value number, unit day|hour|minute
- date: value = lowercase weekday name, or "HH:MM" clock time, or ISO date
- amount: value number, unit = currency code (AED, INR, PHP ...)
- condition: value = {{"trigger": short word for the symptom/thing, "action": stop|call|come_back|continue|avoid, "text": the sentence}}
Give each fact a short human label (e.g. "2 tablets"), a unique id, and critical=true unless truly minor.
Return JSON: a list of facts. Message:
\"\"\"{text}\"\"\""""


# Gemini rejects a request deadline under 10 s ("400 INVALID_ARGUMENT: Manually set deadline 5s is too short"), so the
# SDK is never given less, however small our own wrapper deadline is (D27).
MIN_SDK_TIMEOUT_SECONDS = 10.0


def sdk_timeout_ms() -> int:
    return int(max(settings.llm_timeout_seconds, MIN_SDK_TIMEOUT_SECONDS) * 1000)


def _safe_error(e: Exception) -> str:
    """The provider's message for the log, with the API key removed and length capped."""
    msg = f"{type(e).__name__}: {e}"
    if settings.gemini_api_key:
        msg = msg.replace(settings.gemini_api_key, "***")
    return " ".join(msg.split())[:400]


def llm_extract(text: str) -> list[Fact]:
    from google import genai  # imported lazily: optional dependency path
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key, http_options=types.HttpOptions(timeout=sdk_timeout_ms()))
    resp = client.models.generate_content(
        model=settings.gemini_model,
        contents=_PROMPT.format(text=text),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=list[Fact],
            temperature=0,
        ),
    )
    raw = resp.parsed if getattr(resp, "parsed", None) else json.loads(resp.text)
    facts = [f if isinstance(f, Fact) else Fact.model_validate(f) for f in raw]
    if not facts:
        raise ValueError("LLM returned no facts")
    return facts


# ------------------------------------------------------------------------------------------------------------
# Deadline + circuit breaker. The LLM is an optional helper: it must never make the sender wait or fail.
#  * every call has a hard wall-clock deadline (default 10 s) -> built-in extractor
#  * after a timeout/503/rate limit/other failure the LLM is skipped for a cooldown (default 60 s; 15 min only for a DAILY quota),
#    so a judge clicking "Find key facts" repeatedly waits at most once, not on every click
# ------------------------------------------------------------------------------------------------------------
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm-extract")
_breaker_lock = threading.Lock()
_paused_until = 0.0
DAILY_QUOTA_COOLDOWN = 15 * 60


def reset_breaker() -> None:
    global _paused_until
    with _breaker_lock:
        _paused_until = 0.0


def _trip(seconds: float) -> None:
    global _paused_until
    with _breaker_lock:
        _paused_until = max(_paused_until, time.monotonic() + seconds)


def _paused_for() -> float:
    with _breaker_lock:
        return max(0.0, _paused_until - time.monotonic())


def _extract_with_deadline(text: str) -> list[Fact]:
    future = _pool.submit(llm_extract, text)
    return future.result(timeout=settings.llm_timeout_seconds)  # raises concurrent.futures.TimeoutError


def suggest_facts(text: str) -> tuple[list[Fact], str, str | None]:
    """-> (facts, extractor name, note). Never raises and never waits longer than `llm_timeout_seconds` for the LLM."""
    if not settings.llm_available:
        return regex_extract(text), "regex", None
    wait = _paused_for()
    if wait > 0:
        return regex_extract(text), "regex", f"LLM paused for another {wait:.0f} s after a recent failure; used the built-in extractor."
    if not llm_budget.try_spend():  # global daily cap (D33): no Gemini call, the built-in extractor answers
        log.warning("LLM_DAILY_CAP reached; using the built-in extractor until 00:00 UTC")
        return regex_extract(text), "regex", "LLM unavailable (daily AI limit reached); used the built-in extractor."
    try:
        return _extract_with_deadline(text), "llm", None
    except FutureTimeout:
        _trip(settings.llm_cooldown_seconds)
        reason = f"timed out after {settings.llm_timeout_seconds:g} s"
        detail = reason
    except Exception as e:  # noqa: BLE001 - any failure must degrade to the deterministic path
        msg = str(e)
        daily = "PerDay" in msg
        # only a DAILY quota earns the long pause; 503 UNAVAILABLE / per-minute 429 / anything else is the short cooldown
        _trip(DAILY_QUOTA_COOLDOWN if daily else settings.llm_cooldown_seconds)
        if daily:
            reason = "daily quota used up"
        elif "503" in msg or "UNAVAILABLE" in msg:
            reason = "service unavailable (503)"
        elif "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            reason = "rate limit hit"
        else:
            reason = type(e).__name__
        detail = _safe_error(e)
    log.warning("LLM extraction unavailable (%s); using the built-in extractor. Provider said: %s", reason, detail)
    return regex_extract(text), "regex", f"LLM unavailable ({reason}); used the built-in extractor."
