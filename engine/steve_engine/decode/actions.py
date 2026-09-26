"""Actions: WHERE / WHEN / WHAT / HOW MUCH extracted from the decoded words (D36), each with the evidence span in the ORIGINAL text.

Rules first, no model. The words are the EFFECTIVE words (what the speaker probably meant after any change), so "barking gate tree" is read as
"parking gate three". A slot the decoder could not settle (a clarifying question is open on it) is left empty rather than guessed. Negation is kept:
"don't come to the parking" gives what = "don't come", never "come".
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schema import Span
from .domain import Domain
from .schema import Actions, ActionValue
from .spans import AMBIGUOUS_AT, FUNCTION_WORDS, NUMBERED, PLACE_ONLY, TIME_ONLY
from .tokens import Token

UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
         "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
NEGATORS = {"not", "never", "dont", "don't", "cannot", "cant", "can't", "won't", "wont", "shouldn't", "shouldnt", "mustn't", "no", "without"}
DAY_WORDS = {"today", "tomorrow", "tonight", "yesterday", "now", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
PART_OF_DAY = {"morning", "afternoon", "evening", "night", "noon", "midnight", "fajr", "zuhr", "dhuhr", "asr", "maghrib", "isha"}
CURRENCY = {"dirham", "dirhams", "aed", "riyal", "riyals", "rupee", "rupees", "dollar", "dollars"}
PREP_ANCHORS = PLACE_ONLY | AMBIGUOUS_AT | {"of"}  # a place phrase follows one of these (D44)
MOTION = {"come", "go", "reach", "enter", "visit", "arrive", "leave"}  # ...or one of these ("go home", "come gate 3")
DET = {"the", "a", "an", "this", "that", "my", "your", "our", "his", "her", "their"}
PARTICLES = {"up", "down", "out", "off", "away", "back"}
ADVERBS = {"home", "here", "there", "inside", "outside", "upstairs", "downstairs", "together", "alone", "again", "early", "late", "fast", "slowly", "quickly", "carefully"}
OBJECT_VERBS_EXTRA = {"park", "leave", "start", "finish"}
FETCH = {"bring", "take", "get", "carry", "send", "give", "drop", "deliver", "collect", "buy", "hand", "pick", "load", "unload", "clean", "fix", "wash", "open", "close"}
OPENERS = {"please", "ok", "okay", "yalla", "listen", "hello", "now", "then", "and", "so", "you", "we", "i", "will", "should", "must", "can", "could"}


@dataclass(frozen=True)
class Eff:
    """An effective word: the token as written and the word we take it to be (after any change)."""

    token: Token
    word: str


def parse_number(words: list[str], i: int) -> tuple[int, int] | None:
    """A number starting at words[i] ("five", "twenty five", "two hundred and fifty", "17") -> (value, next index)."""
    def one(w: str) -> int | None:
        if w.isdigit():
            return int(w)
        return UNITS.get(w)

    if i >= len(words):
        return None
    w = words[i]
    if w in TENS:
        v, j = TENS[w], i + 1
        if j < len(words) and (u := UNITS.get(words[j])) is not None and 1 <= u <= 9:
            v, j = v + u, j + 1
        return v, j
    v = one(w)
    if v is None:
        return None
    j = i + 1
    if j < len(words) and words[j] in {"hundred", "thousand"} and v < 1000:
        v, j = v * (100 if words[j] == "hundred" else 1000), j + 1
        if j < len(words) and words[j] == "and":
            j += 1
        rest = parse_number(words, j)
        if rest and rest[0] < 100 and not (words[j - 1] == "and" and rest[0] == 0):
            v, j = v + rest[0], rest[1]
    return v, j


def _span(effs: list[Eff], a: int, b: int, text: str) -> Span:
    s, e = effs[a].token.start, effs[b].token.end
    return Span(start=s, end=e, text=text[s:e])


def extract(effs: list[Eff], text: str, dom: Domain, unresolved: set[int]) -> Actions:
    words = [e.word for e in effs]
    actions = Actions()
    used_numbers: set[int] = set()

    # ---- how much: a number next to a currency word
    for i, w in enumerate(words):
        if w in CURRENCY:
            before = None
            for k in range(max(0, i - 4), i):
                n = parse_number(words, k)
                if n and n[1] == i:
                    before = (k, n[0])
                    break
            if before:
                actions.how_much = ActionValue(value=f"{before[1]} {w}", evidence=_span(effs, before[0], i, text))
                used_numbers.update(range(before[0], i))
                break
            if i + 1 < len(words) and (n := parse_number(words, i + 1)):
                actions.how_much = ActionValue(value=f"{n[0]} {w}", evidence=_span(effs, i, n[1] - 1, text))
                used_numbers.update(range(i + 1, n[1]))
                break

    # ---- where: place words around a place trigger, with a number after a numbered thing ("gate 3")
    place_idx = [i for i, w in enumerate(words) if dom.in_category(w, "place")]
    where_run = _where(effs, words, place_idx, dom)
    if where_run:
        a, b, label = where_run
        if not any(k in unresolved for k in range(a, b + 1)):
            actions.where = ActionValue(value=label, evidence=_span(effs, a, b, text))
            used_numbers.update(range(a, b + 1))

    # ---- when
    when = _when(effs, words, used_numbers)
    if when and not any(k in unresolved for k in range(when[0], when[1] + 1)):
        actions.when = ActionValue(value=when[2], evidence=_span(effs, when[0], when[1], text))

    # ---- what: the first action verb, with its negation and (for fetching verbs) its object
    what = _what(effs, words, dom)
    if what:
        actions.what = ActionValue(value=what[2], evidence=_span(effs, what[0], what[1], text))
    return actions


def _is_modifier(w: str) -> bool:
    """A word that can sit between the article and a place word ("main gate", "labour camp", "petrol station")."""
    return ((w not in FUNCTION_WORDS or w in {"al", "el"}) and w not in PREP_ANCHORS and w not in DAY_WORDS and w not in PART_OF_DAY and w not in CURRENCY and w not in NEGATORS
            and w not in OPENERS and w not in MOTION and w not in TIME_ONLY and not w.isdigit() and w.isalpha() and (len(w) > 2 or w in {"al", "el"}))


def _anchor(words: list[str], p: int) -> int | None:
    """Index where the phrase around the place word at p begins, if a preposition or a motion verb introduces it; otherwise None.

    Only an introduced place counts: "the lift is not working" and "do not open the door" name no place to go to (D44)."""
    k, mods = p - 1, 0
    while k >= 0 and mods < 2 and _is_modifier(words[k]) and words[k] not in DET:
        k -= 1
        mods += 1
    first = k + 1
    if k >= 0 and words[k] in DET:
        k -= 1
    if k >= 0 and (words[k] in PREP_ANCHORS or words[k] in MOTION):
        return first
    return None


def _where(effs, words, place_idx, dom) -> tuple[int, int, str] | None:
    for p in place_idx:
        first = _anchor(words, p)
        if first is None:
            continue
        parts: list[str] = list(words[first:p])
        a = first
        b = p
        i = p
        while i < len(words):
            if dom.in_category(words[i], "place") and (words[i] != "stop" or (parts and dom.in_category(words[i - 1], "place"))) and words[i] != "time":
                parts.append(words[i])
                b = i
                i += 1
                continue
            n = parse_number(words, i)
            if parts and n and words[i - 1] == parts[-1] and words[i - 1] in NUMBERED:
                parts.append(str(n[0]))
                b = n[1] - 1
                i = n[1]
                continue
            break
        return a, b, " ".join(parts)
    return None


def _clock(words: list[str], i: int) -> tuple[int, int, str] | None:
    """A clock time at words[i]: "five", "six thirty" (6:30), "half past six" (6:30), "quarter to seven" (6:45). Returns (hour, next index, label).

    Reading only "six" out of "six thirty" would give the wrong time on a critical slot (D44), so the minutes are taken with it."""
    if words[i] in {"half", "quarter"} and i + 2 < len(words) and words[i + 1] in {"past", "to"} and (h := parse_number(words, i + 2)):
        minutes = 30 if words[i] == "half" else 15
        hour, mm = (h[0], minutes) if words[i + 1] == "past" else (h[0] - 1, 60 - minutes)
        return hour, h[1], f"{hour}:{mm:02d}"
    n = parse_number(words, i)
    if not n:
        return None
    m = parse_number(words, n[1]) if n[1] < len(words) else None
    if m and m[0] in {5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55} and n[0] <= 24 and not (m[1] < len(words) and words[m[1]] in CURRENCY):
        return n[0], m[1], f"{n[0]}:{m[0]:02d}"
    return n[0], n[1], str(n[0])


def _when(effs, words, used: set[int]) -> tuple[int, int, str] | None:
    hits: list[tuple[int, int, str]] = []
    i = 0
    while i < len(words):
        w = words[i]
        if (w in DAY_WORDS or w in PART_OF_DAY) and not (w in PART_OF_DAY and i > 0 and words[i - 1] == "good"):  # "good morning" is a greeting
            j = i
            label = w
            if i > 0 and words[i - 1] == "this" and w in PART_OF_DAY:
                label = "this " + w
            hits.append((i, j, label))
        elif w == "at" and i + 1 < len(words) and (n := _clock(words, i + 1)) and i + 1 not in used:
            end = n[1] - 1
            label = n[2]
            if n[1] < len(words) and words[n[1]] in {"am", "pm"}:
                label += " " + words[n[1]]
                end = n[1]
            elif n[1] < len(words) and words[n[1]] in {"o'clock", "oclock"}:
                label += " o'clock"
                end = n[1]
            hits.append((i, end, label))
            i = end
        i += 1
    if not hits:
        return None
    hits.sort()
    return hits[0][0], hits[-1][1], ", ".join(dict.fromkeys(h[2] for h in hits))


def _what(effs, words, dom) -> tuple[int, int, str] | None:
    for i, w in enumerate(words):
        if not dom.in_category(w, "action"):
            continue
        if i > 0 and words[i - 1] in {"the", "a", "an", "this", "that", "my", "your"}:
            continue  # "the park", "a call": a noun, not an instruction
        neg = None
        for k in range(max(0, i - 3), i):
            if words[k] in NEGATORS or (words[k] == "not" and k > 0 and words[k - 1] == "do"):
                neg = k
        start = neg if neg is not None else i
        label = w
        end = i
        if w in FETCH or w in OBJECT_VERBS_EXTRA:
            obj, j = [], i + 1
            while j < len(words) and (words[j] in DET or words[j] in PARTICLES):
                j += 1
            while j < len(words) and len(obj) < 2 and _is_object_word(words, j):
                obj.append(words[j])
                end = j
                j += 1
            if obj:
                label = " ".join([w, *obj])
        if neg is not None:
            n = words[neg]
            label = ("don't " if n in {"not", "dont", "don't"} else "never " if n == "never" else "cannot " if n in {"cannot", "cant", "can't"} else n + " ") + label
        return start, end, label
    return None


def _is_object_word(words: list[str], j: int) -> bool:
    w = words[j]
    return _is_modifier(w) and w not in DET and w not in PARTICLES and w not in ADVERBS and w != "and" and w != "or" and parse_number(words, j) is None
