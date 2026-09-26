"""Decode: the UAE glossary and the where / when / what / how much extraction (D36)."""

import pytest
import yaml

from steve_engine.decode import glossary
from steve_engine.decode.actions import Eff, extract, parse_number
from steve_engine.decode.domain import get_domain
from steve_engine.decode.tokens import tokenize

DOM = get_domain()


def hits(text):
    return [h.entry.phrase for h in glossary.find_phrases(tokenize(text), text)]


# ---- glossary ------------------------------------------------------------------------------------------------------------------------


def test_the_glossary_is_big_enough_unverified_and_complete():
    entries = glossary.load_glossary()
    assert 60 <= len(entries) <= 100
    for e in entries:
        assert e.phrase and e.plain and e.literal and e.social_meaning and e.example and e.category in glossary.CATEGORIES
    assert {"yalla", "khalas", "inshallah", "mashallah", "wallah", "habibi", "mafi mushkila", "shway shway", "tamam", "zain", "same same", "kindly revert",
            "do the needful", "one minute"} <= {e.phrase for e in entries}


def test_meanings_stay_neutral():
    banned = ("wrong", "bad english", "primitive", "backward", "uneducated", "lazy", "stupid")
    for e in glossary.load_glossary():
        text = f"{e.plain} {e.literal} {e.social_meaning}".lower()
        assert not any(b in text for b in banned), e.phrase


@pytest.mark.parametrize("spelling,phrase", [
    ("yalla", "yalla"), ("yala", "yalla"), ("yallah", "yalla"), ("Yalla!", "yalla"), ("khalas", "khalas"), ("khalass", "khalas"), ("kalas", "khalas"),
    ("inshallah", "inshallah"), ("insha allah", "inshallah"), ("in sha allah", "inshallah"), ("inshaallah", "inshallah"), ("habibi", "habibi"),
    ("habibee", "habibi"), ("mafi mushkil", "mafi mushkila"), ("mafi mushkila", "mafi mushkila"), ("shway shway", "shway shway"), ("tamam", "tamam"),
    ("wallah", "wallah"), ("mashallah", "mashallah"), ("same same", "same same"), ("kindly revert", "kindly revert"), ("do the needful", "do the needful"),
    ("one minute", "one minute"), ("1 minute", "one minute"),
])
def test_phrases_are_matched_by_ear(spelling, phrase):
    assert phrase in hits(f"ok {spelling} now")


@pytest.mark.parametrize("text", ["the same day", "come to the parking", "bass guitar", "each day", "this is the gate", "my friend is here", "it is good", "again please", "sir"])
def test_plain_english_is_not_mistaken_for_a_phrase(text):
    assert hits(text) == []


def test_longer_phrases_win_and_spans_do_not_overlap():
    text = "mafi mushkila habibi"
    hs = glossary.find_phrases(tokenize(text), text)
    assert [h.entry.phrase for h in hs] == ["mafi mushkila", "habibi"] and hs[0].span.end <= hs[1].span.start


def test_phrase_spans_are_code_point_offsets():
    text = "😀 yalla 👍 habibi"
    for h in glossary.find_phrases(tokenize(text), text):
        assert text[h.span.start : h.span.end].lower() == h.span.text.lower()


def test_time_and_workplace_entries_are_explained_not_substituted():
    e = {x.phrase: x for x in glossary.load_glossary()}
    assert not e["one minute"].substitute and not e["kindly revert"].substitute and e["yalla"].substitute


def _entries(**over):
    base = {"phrase": "x", "variants": [], "plain": "p", "literal": "l", "social_meaning": "s", "example": "e", "category": "greeting", "verified": False}
    return {**base, **over}


@pytest.mark.parametrize("entry,message", [
    (_entries(verified=True), "must be verified: false"), (_entries(category="nonsense"), "unknown category"), (_entries(plain=""), "missing plain"),
    (_entries(social_meaning=" "), "missing social_meaning"),
])
def test_bad_glossary_entries_are_rejected(tmp_path, entry, message):
    p = tmp_path / "g.yaml"
    p.write_text(yaml.safe_dump({"version": 1, "verified": False, "entries": [entry]}), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        glossary.load_glossary.__wrapped__(str(p))


def test_duplicates_and_verified_files_are_rejected(tmp_path):
    p = tmp_path / "g.yaml"
    p.write_text(yaml.safe_dump({"version": 1, "verified": False, "entries": [_entries(), _entries()]}), encoding="utf-8")
    with pytest.raises(ValueError, match="twice"):
        glossary.load_glossary.__wrapped__(str(p))
    p.write_text(yaml.safe_dump({"version": 1, "verified": True, "entries": [_entries()]}), encoding="utf-8")
    with pytest.raises(ValueError, match="verified: false"):
        glossary.load_glossary.__wrapped__(str(p))


# ---- numbers and actions -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("words,value,nxt", [
    (["five"], 5, 1), (["17"], 17, 1), (["twenty", "five"], 25, 2), (["fifty"], 50, 1), (["two", "hundred", "and", "fifty"], 250, 4),
    (["one", "hundred"], 100, 2), (["three", "thousand"], 3000, 2), (["twelve", "days"], 12, 1),
])
def test_parse_number(words, value, nxt):
    assert parse_number(words, 0) == (value, nxt)


@pytest.mark.parametrize("words", [["come"], [], ["hundred"]])
def test_parse_number_rejects_non_numbers(words):
    assert parse_number(words, 0) is None


def acts(text, unresolved=()):
    toks = tokenize(text)
    return extract([Eff(t, t.norm) for t in toks], text, DOM, set(unresolved))


def val(v):
    return v.value if v else None


@pytest.mark.parametrize("text,where", [
    ("come to the parking gate three", "parking gate 3"), ("wait at the lobby", "lobby"), ("meet me near the metro station", "metro station"),
    ("go to the basement floor two", "basement floor 2"), ("bring it to building twelve", "building 12"),
])
def test_where(text, where):
    assert val(acts(text).where) == where


@pytest.mark.parametrize("text,when", [
    ("come at five", "5"), ("come tomorrow", "tomorrow"), ("call me at 5 pm", "5 pm"), ("come at six o'clock", "6 o'clock"), ("wait until morning", "morning"),
    ("come today at five", "today, 5"), ("we meet after maghrib", "maghrib"), ("come now", "now"),
])
def test_when(text, when):
    assert val(acts(text).when) == when


@pytest.mark.parametrize("text,how", [("pay fifty dirhams", "50 dirhams"), ("it costs twenty five aed", "25 aed"), ("send 100 dirhams", "100 dirhams"),
                                      ("aed 250 only", "250 aed")])
def test_how_much(text, how):
    assert val(acts(text).how_much) == how


@pytest.mark.parametrize("text,what", [
    ("come to the parking", "come"), ("don't come now", "don't come"), ("do not bring the bags", "don't bring bags"), ("never park here", "never park"),
    ("bring the keys", "bring keys"), ("please wait", "wait"), ("i cannot come", "cannot come"),
])
def test_what_keeps_negation(text, what):
    assert val(acts(text).what) == what


def test_evidence_spans_point_at_the_original_words():
    text = "come to the parking gate three at five"
    a = acts(text)
    assert a.where.evidence.text == "parking gate three" and a.when.evidence.text == "at five" and text[a.where.evidence.start : a.where.evidence.end] == "parking gate three"


def test_an_unresolved_word_leaves_the_slot_empty_rather_than_guessing():
    text = "come to the parking gate three"
    toks = tokenize(text)
    assert acts(text, unresolved={3}).where is None and toks[3].norm == "parking"


def test_the_gate_number_is_not_also_the_time():
    assert val(acts("gate three").when) is None


def test_nothing_to_extract_gives_empty_actions():
    a = acts("hello there")
    assert (a.where, a.when, a.what, a.how_much) == (None, None, None, None)
