"""Slot fillers: turn matched lexicon hits into typed "heard" facts (dose, frequency, timing, duration, date, amount).

Numbers are only ever attributed through an ANCHOR word (unit / counter / duration unit / currency). A bare "5" is
never guessed into a fact — it is reported as an unclaimed number so compare.py can answer `unclear`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .matcher import Ctx, Match
from .schema import FactType

MINUTES = {"minute": 1.0, "hour": 60.0, "day": 1440.0, "week": 10080.0, "month": 43200.0}
DAYS_PER_UNIT = {"minute": 1 / 1440, "hour": 1 / 24, "day": 1.0, "week": 7.0, "month": 30.0}
TOD_GROUP = {"morning": "morning", "noon": "midday", "afternoon": "midday", "evening": "evening", "night": "night", "bedtime": "night"}
INFERRED_FREQ_CONF = 0.72
IMPLICIT_ONE_UNITS = {"bottle", "form", "copy"}
IMPLICIT_ONE_CONF = 0.65
INFERRED_SINGLE_FREQ_CONF = 0.5  # one time-of-day word alone is too weak to call "once a day"


@dataclass
class Heard:
    type: FactType
    value: Any
    unit: str | None
    matches: list[Match]
    confidence: float
    inferred: bool = False
    negated: bool = False
    neg_match: Match | None = None
    extra: dict = field(default_factory=dict)

    @property
    def first(self) -> int:
        return min(m.i for m in self.matches)

    @property
    def last(self) -> int:
        return max(m.j for m in self.matches)

    def surface(self, text: str) -> str:
        a = min(m.start for m in self.matches)
        b = max(m.end for m in self.matches)
        return text[a:b]


@dataclass
class Slots:
    heard: dict[FactType, list[Heard]]
    bare_numbers: list[Match]

    def all(self) -> list[Heard]:
        return [h for hs in self.heard.values() for h in hs]


def _conf(matches: list[Match], penalty: float = 1.0) -> float:
    c = min((m.score for m in matches), default=100.0) / 100.0
    if any(m.alts for m in matches):
        c *= 0.85
    return round(c * penalty, 3)


def _numbers(ctx: Ctx) -> list[Match]:
    return [m for m in ctx.matches if m.category == "number"]


# ------------------------------------------------------------------------------------------------
def fill_slots(ctx: Ctx) -> Slots:
    heard: dict[FactType, list[Heard]] = {t: [] for t in FactType}
    used: set[int] = set()  # ids of matches consumed by a slot

    def use(*ms: Match) -> None:
        used.update(id(m) for m in ms)

    # -- dates first (they claim day-of-month numbers) -----------------------------------------
    _fill_dates(ctx, heard, use)

    # -- "every N hours/days" -> frequency ---------------------------------------------------------
    _fill_every(ctx, heard, use)

    # -- anchored numbers: dose / duration / amount / N-times frequency ------------------------------
    anchors = [
        m
        for m in ctx.matches
        if id(m) not in used
        and (
            m.category in ("unit", "duration_unit", "currency")
            or (m.category == "frequency_phrase" and m.value == "counter")
        )
    ]
    numbers = [m for m in _numbers(ctx) if id(m) not in used]

    pairs: list[tuple[int, int, Match, Match]] = []
    for a in anchors:
        for n in numbers:
            d = ctx.cdist(n, a)
            if d > 2:
                continue
            if n.j < a.i:  # number BEFORE anchor: "2 tablets"
                pairs.append((d, 0, a, n))
            elif d <= 1:  # number AFTER anchor: "tablets 2", "AED 150"
                pairs.append((d, 1, a, n))
    pairs.sort(key=lambda p: (p[0], p[1]))
    used_anchor: set[int] = set()
    used_num: set[int] = set()
    for _d, _dir, a, n in pairs:
        if id(a) in used_anchor or id(n) in used_num:
            continue
        # "twice a day", "twce a day", "dalawang beses sa isang araw": a lone "a/1 day" is a RATE, not a 1-day duration
        # (only "for a day" is a duration)
        if a.category == "duration_unit" and a.value == "day" and (n.entry.adjacent_only or float(n.value) == 1):
            prev = _prev_content(ctx, n)
            raw_prev = ctx.tokens[n.i - 1].norm if n.i > 0 else ""
            if (prev is not None and prev.category == "frequency_phrase") or (n.entry.adjacent_only and raw_prev != "for"):
                use(n, a)  # part of a rate phrase: consumed, not a stray number
                used_anchor.add(id(a))
                used_num.add(id(n))
                continue
        elif a.category == "duration_unit" and n.entry.adjacent_only:
            prev = _prev_content(ctx, n)
            raw_prev = ctx.tokens[n.i - 1].norm if n.i > 0 else ""
            if prev is not None and prev.category == "frequency_phrase" and raw_prev != "for":
                use(n, a)
                used_anchor.add(id(a))
                used_num.add(id(n))
                continue
        used_anchor.add(id(a))
        used_num.add(id(n))
        _emit_anchored(ctx, heard, a, n)
        use(a, n)

    # anchors without a number: implicit counters ("marra" = once); a bare countable object ("signed form",
    # "water bottle") is weakly heard as ONE of them. Medication units are never guessed.
    unpaired_counter = False
    for a in anchors:
        if id(a) in used_anchor:
            continue
        if a.category == "frequency_phrase" and a.entry.implicit:
            heard[FactType.frequency].append(
                Heard(FactType.frequency, float(a.entry.implicit), None, [a], _conf([a], 0.9))
            )
            use(a)
        elif a.category == "frequency_phrase":
            unpaired_counter = True  # "… neram" with a count we could not read: don't guess the frequency
        elif a.category == "unit" and a.value in IMPLICIT_ONE_UNITS:
            heard[FactType.dose].append(Heard(FactType.dose, 1.0, str(a.value), [a], _conf([a], IMPLICIT_ONE_CONF), inferred=True))
            use(a)

    # -- fixed frequency words: once/twice/thrice/marratain (and "daily"-type markers, only as a last resort) ----
    period: list[Match] = []
    for m in ctx.matches:
        if m.category == "frequency_phrase" and isinstance(m.value, int | float) and not isinstance(m.value, bool) and id(m) not in used:
            if m.entry.period:
                period.append(m)
                continue
            heard[FactType.frequency].append(Heard(FactType.frequency, float(m.value), None, [m], _conf([m])))
            use(m)
    if not heard[FactType.frequency] and not unpaired_counter:
        for m in period[:1]:  # "daily" alone: weak evidence of once a day, never a hard "wrong"
            heard[FactType.frequency].append(Heard(FactType.frequency, float(m.value), None, [m], _conf([m], 0.7), inferred=True))

    # -- timing ---------------------------------------------------------------------------------------
    _fill_timing(ctx, heard, use)

    # -- inferred frequency from distinct times of day (only when nothing explicit was said) -----------
    if not heard[FactType.frequency]:
        tod: dict[str, Heard] = {}
        for h in heard[FactType.timing]:
            grp = TOD_GROUP.get(h.value)
            if grp and grp not in tod:
                tod[grp] = h
        if tod:
            ms = [m for h in tod.values() for m in h.matches]
            count = len(tod)
            conf = _conf(ms, INFERRED_FREQ_CONF if count >= 2 else INFERRED_SINGLE_FREQ_CONF)
            heard[FactType.frequency].append(
                Heard(FactType.frequency, float(count), None, ms, conf, inferred=True, extra={"from": sorted(tod)})
            )

    bare = [m for m in _numbers(ctx) if id(m) not in used and not m.entry.adjacent_only]
    return Slots(heard=heard, bare_numbers=bare)


def _prev_content(ctx: Ctx, m: Match) -> Match | None:
    k = m.i - 1
    while k >= 0:
        pm = ctx.match_at.get(k)
        if pm is not None and pm.category == "filler":
            k -= 1
            continue
        return pm
    return None


def _emit_anchored(ctx: Ctx, heard: dict[FactType, list[Heard]], a: Match, n: Match) -> None:
    val = float(n.value)
    ms = [n, a]
    conf = _conf(ms)
    if a.category == "unit":
        heard[FactType.dose].append(Heard(FactType.dose, val, str(a.value), ms, conf))
    elif a.category == "currency":
        heard[FactType.amount].append(Heard(FactType.amount, val, str(a.value), ms, conf))
    elif a.category == "duration_unit":
        unit = str(a.value)
        if unit in ("week", "month"):
            h = Heard(FactType.duration, val * DAYS_PER_UNIT[unit], "day", ms, conf, extra={"raw": val, "raw_unit": unit})
        else:
            h = Heard(FactType.duration, val, unit, ms, conf, extra={"raw": val, "raw_unit": unit})
        heard[FactType.duration].append(h)
    elif a.category == "frequency_phrase":
        heard[FactType.frequency].append(Heard(FactType.frequency, val, None, ms, conf))


def _fill_every(ctx: Ctx, heard: dict[FactType, list[Heard]], use) -> None:
    for ev in [m for m in ctx.matches if m.category == "frequency_phrase" and m.value == "every"]:
        seq = [m for m in ctx.matches if m.i > ev.j and ctx.cdist(ev, m) <= 3]
        num = None
        unit = None
        for m in seq:
            if m.category == "number" and num is None and unit is None:
                num = m
            elif m.category == "duration_unit":
                unit = m
                break
            elif m.category not in ("filler",):
                break
        if unit is None:
            continue
        n = float(num.value) if num is not None else 1.0
        interval_days = n * DAYS_PER_UNIT[str(unit.value)]
        if interval_days <= 0:
            continue
        ms = [ev] + ([num] if num is not None else []) + [unit]
        heard[FactType.frequency].append(
            Heard(FactType.frequency, round(1.0 / interval_days, 4), None, ms, _conf(ms), extra={"every": True})
        )
        use(*ms)


def _fill_timing(ctx: Ctx, heard: dict[FactType, list[Heard]], use) -> None:
    for m in ctx.matches:
        if m.category == "timing":
            heard[FactType.timing].append(Heard(FactType.timing, str(m.value), None, [m], _conf([m])))
            use(m)
    # relation word + food word: "food kazhinju", "khane ke baad", "ba3d al akl", "pagkatapos kumain"
    rel = [m for m in ctx.matches if m.category == "food_relation" and m.value in ("after", "before")]
    food = [m for m in ctx.matches if m.category == "food_relation" and m.value == "food"]
    cand = sorted(
        ((ctx.cdist(r, f), r.i, r, f) for r in rel for f in food if ctx.cdist(r, f) <= 3),
        key=lambda x: (x[0], x[1]),
    )
    used_r: set[int] = set()
    used_f: set[int] = set()
    for _d, _i, r, f in cand:
        if id(r) in used_r or id(f) in used_f:
            continue
        used_r.add(id(r))
        used_f.add(id(f))
        tag = f"{r.value}_food"
        heard[FactType.timing].append(Heard(FactType.timing, tag, None, [r, f], _conf([r, f])))
        use(r, f)


def _fill_dates(ctx: Ctx, heard: dict[FactType, list[Heard]], use) -> None:
    for m in ctx.matches:
        if m.category == "weekday":
            heard[FactType.date].append(Heard(FactType.date, str(m.value), None, [m], _conf([m])))
            use(m)
        elif m.category == "clock":
            hh, mm = str(m.value).split(":")
            heard[FactType.date].append(Heard(FactType.date, f"{int(hh):02d}:{mm}", None, [m], 1.0))
            use(m)
        elif m.category == "isodate":
            heard[FactType.date].append(Heard(FactType.date, str(m.value), None, [m], 1.0))
            use(m)
    months = [m for m in ctx.matches if m.category == "month"]
    nums = [m for m in _numbers(ctx) if m.kind == "digits" and 1 <= m.value <= 31 and float(m.value).is_integer()]
    for mo in months:
        best = None
        for n in nums:
            if id(n) in {id(x) for h in heard[FactType.date] for x in h.matches}:
                continue
            d = ctx.cdist(n, mo)
            if d <= 1 and (best is None or d < best[0]):
                best = (d, n)
        if best:
            n = best[1]
            heard[FactType.date].append(
                Heard(FactType.date, f"{int(mo.value):02d}-{int(n.value):02d}", None, [n, mo], _conf([n, mo]))
            )
            use(n, mo)
