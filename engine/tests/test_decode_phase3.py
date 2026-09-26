"""Decode: the fixes that followed the first scoring of the Phase 3 evaluation set (D44), and the evaluation harness itself."""

import importlib.util
import sys
from pathlib import Path

import pytest

from steve_engine.decode import decode
from steve_engine.decode.actions import Eff, extract
from steve_engine.decode.domain import get_domain
from steve_engine.decode.tokens import tokenize

ROOT = Path(__file__).resolve().parents[2]
DOM = get_domain()


def acts(text):
    return extract([Eff(t, t.norm) for t in tokenize(text)], text, DOM, set())


def val(v):
    return v.value if v else None


# ---- where: introduced places, with modifiers --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text,where", [
    ("come to the main gate", "main gate"), ("park near the petrol station", "petrol station"), ("come to the labour camp", "labour camp"),
    ("go to the bus stop", "bus stop"), ("wait at the loading bay", None), ("leave the keys at the desk", "desk"), ("park the truck in the yard", "yard"),
    ("take the lift to floor twelve", "floor 12"), ("go home", None), ("come to the parking gate three at five", "parking gate 3"),
])
def test_a_place_needs_an_introducer_and_keeps_its_modifiers(text, where):
    assert val(acts(text).where) == where


@pytest.mark.parametrize("text", ["the lift is not working", "do not open the door", "stop the bus", "the desk is dirty", "he fixed the gate"])
def test_a_place_word_that_nothing_introduces_is_not_a_where(text):
    assert acts(text).where is None


# ---- what: the object of the verb ----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text,what", [
    ("bring the trolley to the warehouse", "bring trolley"), ("park the truck near tower three", "park truck"), ("start work at seven", "start work"),
    ("send the driver to the airport", "send driver"), ("don't send the money today", "don't send money"), ("don't take the keys home", "don't take keys"),
    ("send 100 dirhams", "send"), ("give me sixty dirhams", "give"), ("deliver this to flat 204", "deliver"), ("call me tonight", "call"),
    ("pick up the bags", "pick bags"), ("park near the gate", "park"),
])
def test_the_object_is_the_noun_after_the_verb_and_stops_at_a_pronoun_number_or_preposition(text, what):
    assert val(acts(text).what) == what


# ---- when: greetings and clock times ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["good morning sir", "good evening", "good night"])
def test_a_greeting_is_not_a_time(text):
    assert acts(text).when is None


@pytest.mark.parametrize("text,when", [
    ("start at six thirty", "6:30"), ("come at half past four", "4:30"), ("come at quarter to seven", "6:45"), ("come at ten fifteen pm", "10:15 pm"),
    ("come at five", "5"), ("come at 5 pm", "5 pm"), ("come at eight o'clock", "8 o'clock"), ("pay it at five fifty dirhams", "5"),
])
def test_clock_times_keep_their_minutes(text, when):
    assert val(acts(text).when) == when


# ---- a negation typed by ear becomes a question -------------------------------------------------------------------------------------------------


def test_a_real_word_that_could_be_a_respelled_negation_is_asked_about_not_read_as_an_instruction():
    c = decode("newer come to de site alone", "hi")
    assert c.clarify and c.clarify[0].options[:2] == ["never", "newer"] and c.clarify[0].slot == "negation"
    assert c.actions.what is None  # instruction or its opposite: nothing is claimed


def test_a_typed_never_is_untouched():
    c = decode("never come to the site alone", "hi")
    assert c.clarify == [] and val(c.actions.what) == "never come"


@pytest.mark.parametrize("text", ["the newer building is open", "i have a new phone", "come to the note desk", "we are near the gate"])
def test_ordinary_sentences_do_not_trigger_the_negation_question(text):
    assert decode(text, "hi").clarify == []


# ---- the evaluation harness -------------------------------------------------------------------------------------------------------------------


def _load(name):
    sys.path.insert(0, str(ROOT / "eval"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "eval" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_frozen_evaluation_sets_are_what_their_generators_write():
    for module, inst_name, ev_name in (("decode_eval_set", "workplace_instructions.csv", "eval_v1.csv"), ("decode_eval_set_v2", "workplace_instructions_v2.csv", "eval_v2.csv")):
        mod = _load(module)
        inst, rows, _ = mod.build()
        for name, data in ((inst_name, inst), (ev_name, rows)):
            text = (ROOT / "data" / "decode" / name).read_text(encoding="utf-8")
            assert text.count("\n") == len(data) + 1, name
            assert all(r.get("synthetic", "true") == "true" for r in data)


def test_evaluation_sets_share_no_sentence_with_the_tuning_sets_or_each_other():
    mod = _load("decode_eval_set")
    v1 = {r["sentence"] for r in mod.build()[0]}
    v2 = {r["sentence"] for r in _load("decode_eval_set_v2").build()[0]}
    assert not (v1 & v2) and not ((v1 | v2) & mod._load_tuning_sentences())


def test_gold_values_only_use_words_that_are_in_the_sentence_or_numbers():
    ev = _load("decode_eval")
    mod = _load("decode_eval_set")
    for r in mod.build()[0]:
        words = set(ev.norm_words(r["sentence"]))
        for slot in ("where", "when", "what", "how_much"):
            for w in ev.norm_words(r[slot]):
                assert w in words or w.isdigit() or w in {"don't", "aed"}, (r["sentence"], slot, w)


def test_scorer_helpers():
    ev = _load("decode_eval")
    assert ev.norm_value("the Gate three") == ("gate", "3") and ev.norm_value("at 8 o'clock") == ("8",) and ev.norm_value(None) == ()
    lo, hi = ev.wilson(0, 100)
    assert lo == 0 and 0.02 < hi < 0.05
    assert ev.wilson(0, 0) == (0.0, 0.0)
    assert ev.rate(0, 0) == "n/a" and "3/10" in ev.rate(3, 10)


def test_a_lost_negation_is_wrong_never_partial():
    ev = _load("decode_eval")
    card = decode("come to the site", None)
    row = {"view": "typed_clean", "text": "come to the site", "accent": "none", "intended": "never come to the site", "in_pack": ""}
    gold = {"where": "", "when": "", "what": "never come", "how_much": ""}
    assert ev.score_row(row, gold, card)["slots"]["what"][0] == "wrong"
