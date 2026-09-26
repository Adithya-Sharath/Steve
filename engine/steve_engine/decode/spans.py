"""Critical spans: the places in a sentence where a wrongly heard word would change what a worker does (D41): a WHERE (after "to the", "behind"),
a WHEN (after "before", "every"), an ambiguous "at" (a place or a time), a numbered thing ("gate three"), an AMOUNT ("fifty dirhams") or the
OBJECT of a fetching verb ("bring the ___"). Each slot says which kinds of words are EXPECTED there. Words outside every slot are never touched.
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Domain
from .tokens import Token

PLACE_ONLY = {"to", "near", "behind", "from", "inside", "outside", "towards", "toward", "into", "beside", "around", "across", "onto", "opposite"}
AMBIGUOUS_AT = {"at", "in", "by", "on"}
TIME_ONLY = {"before", "after", "until", "till", "every", "next", "last", "within", "since"}
NUMBERED = {"gate", "floor", "flat", "room", "building", "block", "tower", "villa", "number", "level", "apartment", "house", "lane", "exit",
            "bay", "platform", "no", "unit"}
TIME_BEFORE = {"tomorrow", "today", "tonight", "yesterday", "this", "next", "last", "every", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
AMOUNT_BEFORE = {"pay", "paid", "cost", "costs", "fine", "price", "salary", "only", "bonus"}
FETCH_VERBS = {"bring", "take", "get", "carry", "fetch", "send", "give", "drop", "deliver", "collect", "buy", "hand", "pick", "load", "unload"}
SKIP = {"the", "a", "an", "this", "that", "my", "your", "our", "his", "her", "their", "its", "and", "or", "of", "please"}
# function words (pronouns, auxiliaries, conjunctions, wh-words, ...) are never the thing a where / when / amount depends on, so they are never examined:
# "wait for them at the gate", "in it", "before we start" must not trigger a question just because they sit after a preposition
FUNCTION_WORDS = {
    "i", "me", "mine", "we", "us", "you", "he", "him", "she", "it", "they", "them", "these", "those", "who", "whom", "whose", "what", "which", "when",
    "where", "why", "how", "there", "here", "then", "than", "so", "if", "but", "with", "as", "is", "am", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had", "will", "would", "can", "could", "shall", "should", "may", "might", "must", "yes", "ok", "okay", "all",
    "any", "some", "each", "another", "other", "more", "most", "much", "many", "such", "just", "also", "very", "too", "again", "already", "still",
    "yalla", "habibi", "hello", "hi", "listen", "sir", "madam", "myself", "yourself", "himself", "herself", "themselves", "ourselves",
}


@dataclass(frozen=True)
class Slot:
    kind: str  # where | where_or_when | when | number | amount | what
    expects: frozenset[str]  # domain categories a word here would normally belong to
    trigger: str  # the word that created the slot
    label: str  # for reasons shown to a person: "a place", "a time" ...


WHERE = ("where", frozenset({"place"}), "a place")
WHERE_OR_WHEN = ("where_or_when", frozenset({"place", "time", "number"}), "a place or a time")
WHEN = ("when", frozenset({"time", "number"}), "a time")
NUMBER = ("number", frozenset({"number"}), "a number")
AMOUNT = ("amount", frozenset({"number", "amount"}), "an amount")
WHAT = ("what", frozenset({"thing", "place"}), "a thing")
ACTION = ("action", frozenset({"action"}), "a verb")
VERB_LEADS = {"please", "yalla", "habibi", "and", "then", "ok", "okay", "dont", "don't", "not", "never", "just", "kindly", "sir"}


_BREAK = set(",;:.!?()")


def _broken(text: str, a: Token | None, b: Token) -> bool:
    """A comma, full stop or similar between the trigger word and this word ends the span ("only, it is ...")."""
    return bool(a is not None and text and any(ch in _BREAK for ch in text[a.end : b.start]))


def find_slots(tokens: list[Token], dom: Domain, text: str = "", include_action: bool = False) -> dict[int, Slot]:
    """token index -> the slot it sits in (only tokens inside a critical span appear). `text` lets punctuation end a span."""
    slots: dict[int, Slot] = {}
    for t in tokens:
        if t.norm in SKIP or t.norm in dom.place_triggers or t.norm in PLACE_ONLY | AMBIGUOUS_AT | TIME_ONLY or dom.category(t.norm) == "negation":
            continue
        prev = tokens[t.i - 1] if t.i else None
        j = t.i - 1
        had_det = False
        if prev is not None and prev.norm in dom.determiners:
            j, had_det = t.i - 2, True
        lead = tokens[j] if j >= 0 else None
        nxt = tokens[t.i + 1] if t.i + 1 < len(tokens) else None
        kind = None
        if lead is not None and lead.norm in PLACE_ONLY:
            kind = WHERE
        elif prev is not None and not had_det and prev.norm in NUMBERED:
            kind = NUMBER
        elif lead is not None and lead.norm in AMBIGUOUS_AT:
            kind = WHERE_OR_WHEN
        elif lead is not None and lead.norm in TIME_ONLY:
            kind = WHEN
        elif prev is not None and not had_det and prev.norm in TIME_BEFORE:
            kind = WHEN
        elif nxt is not None and dom.in_category(nxt.norm, "amount") and nxt.norm not in {"money", "salary", "cash", "price", "cost", "payment"}:
            kind = AMOUNT
        elif prev is not None and not had_det and prev.norm in AMOUNT_BEFORE:
            kind = AMOUNT
        elif lead is not None and lead.norm in FETCH_VERBS:
            kind = WHAT
        elif include_action and (t.i == 0 or (prev is not None and prev.norm in VERB_LEADS)):
            kind = ACTION  # typed text only: the imperative verb ("bark near the building" for "park")
        trigger = None
        if kind in (WHERE, WHERE_OR_WHEN, WHEN, WHAT) or kind is None:
            trigger = lead if lead is not None else prev
        elif kind is ACTION:
            trigger = None
        elif kind is NUMBER or kind is AMOUNT:
            trigger = prev if kind is NUMBER else (nxt if nxt is not None and dom.in_category(nxt.norm, "amount") else prev)
        if kind and _broken(text, trigger if trigger is not nxt else None, t):
            kind = None
        # a function word (it, we, him, what ...) is never the place, time or thing a worker is told about; numbers and amounts are different: "gate it" is odd
        if kind in (WHERE, WHERE_OR_WHEN, WHEN, WHAT) and t.norm in FUNCTION_WORDS:
            kind = None
        if kind:
            slots[t.i] = Slot(kind[0], kind[1], (lead or prev).norm if (lead or prev) else "", kind[2])
    return slots
