"""Decode: critical spans and the voice safety net (D40, D41): only critical words are examined, only a clear win rewrites, close calls ask."""

import pytest

from steve_engine.decode.domain import get_domain
from steve_engine.decode.safety import SafetyConfig, apply_changes, review_transcript
from steve_engine.decode.spans import find_slots
from steve_engine.decode.tokens import tokenize

DOM = get_domain()


def slots(text):
    toks = tokenize(text)
    return {toks[i].norm: s.kind for i, s in find_slots(toks, DOM, text).items()}


# ---- spans ---------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text,word,kind", [
    ("come to the barking", "barking", "where"), ("wait behind the gate", "gate", "where"), ("meet me at the lobby", "lobby", "where_or_when"),
    ("come at five", "five", "where_or_when"), ("call me before noon", "noon", "when"), ("gate three", "three", "number"),
    ("pay fifty dirhams", "fifty", "amount"), ("bring the bags", "bags", "what"), ("come tomorrow night", "night", "when"),
    ("it costs ten", "ten", "amount"),
])
def test_slots_are_found(text, word, kind):
    assert slots(text)[word] == kind


@pytest.mark.parametrize("text,word", [
    ("the barking dog is at the gate", "barking"), ("stop barking please", "barking"), ("wait for them at the gate", "them"), ("before we start", "we"),
    ("what is in it", "it"), ("only, it is so", "it"), ("i saw him at work", "him"),
])
def test_words_outside_critical_spans_or_function_words_are_not_slots(text, word):
    assert word not in slots(text)


def test_punctuation_ends_a_span():
    assert "it" not in slots("Only, it is wonderful")
    assert slots("pay only five dirhams")["five"] == "amount"


# ---- policy: rewrite, ask, keep --------------------------------------------------------------------------------------------------------


def test_a_place_that_does_not_fit_is_rewritten_when_a_sound_alike_clearly_wins():
    r = review_transcript("come to the barking gate", "ar")
    assert [(c.heard, c.meant) for c in r.changes] == [("barking", "parking")] and r.corrected == "come to the parking gate"
    assert "Arabic has no /p/" in r.changes[0].reason and r.tips


def test_the_same_word_outside_a_place_is_left_alone():
    r = review_transcript("the barking dog is at the gate", "ar")
    assert r.changes == [] and r.clarify == [] and r.corrected == "the barking dog is at the gate"


def test_a_word_that_already_belongs_is_never_touched():
    r = review_transcript("come to the parking gate three", "ar")
    assert r.changes == [] and r.clarify == [] and {e.decision for e in r.examined} == {"fits"}


def test_choices_on_offer_are_asked_about_not_rewritten():
    r = review_transcript("come to the barking or the building", "ar")
    assert r.changes == [] and r.clarify and r.clarify[0].options[:2] == ["parking", "barking"] and r.clarify[0].question == "Parking or barking?"


def test_a_number_is_never_silently_rewritten_a_question_is_asked():
    r = review_transcript("come to the gate free", None)
    assert r.changes == [] and r.clarify[0].options[:2] == ["three", "free"]


def test_the_dont_touch_original_is_only_ever_questioned():
    r = review_transcript("gate five", "ar")
    assert r.changes == []  # "five" fits a number slot


@pytest.mark.parametrize("text", ["wait at the corner", "the truck is behind the yard", "meet me at the desk", "park near the cabin", "i will be at work until five",
                                  "wait for them at the gate", "call me before we start", "what is in it", "give it to him at the office"])
def test_generic_correct_sentences_raise_no_alarm(text):
    r = review_transcript(text, "ar")
    assert r.changes == [] and r.clarify == []


@pytest.mark.parametrize("text", ["don't come to the parking now", "do not bring the bags", "never park near the gate", "he is not at the office"])
def test_negations_survive(text):
    r = review_transcript(text, "ar")
    assert r.corrected == text


def test_homophone_slips_are_caught():
    r = review_transcript("park near the gait", None)
    assert [(c.heard, c.meant) for c in r.changes] == [("gait", "gate")]


def test_a_time_after_a_time_word_is_examined():
    r = review_transcript("come tomorrow knight", None)
    assert r.changes or r.clarify


def test_two_close_candidates_make_a_question_even_if_one_wins():
    r = review_transcript("go to the marking", None)
    assert r.changes == [] and r.clarify and len(r.clarify[0].options) >= 3


def test_unexpected_kinds_of_words_are_not_offered():
    r = review_transcript("wait at the corner", "ar")
    assert all(e.decision in ("no_alternative", "keep", "fits") for e in r.examined)


def test_apply_changes_keeps_case_and_offsets():
    text = "Come to the Barking gate"
    r = review_transcript(text, "ar")
    assert apply_changes(text, r.changes) == "Come to the Parking gate"
    assert all(text[c.span.start : c.span.end] == c.heard for c in r.changes)


def test_workplace_vocabulary_of_another_kind_needs_a_bigger_win():
    assert review_transcript("i will be at work until five", None).clarify == []


def test_margins_are_config_not_constants():
    text = "come to the barking gate"
    too_small_to_rewrite = review_transcript(text, "ar", SafetyConfig(rewrite_margin=99.0))
    assert too_small_to_rewrite.changes == [] and too_small_to_rewrite.clarify  # a win that is not big enough becomes a question
    silent = review_transcript(text, "ar", SafetyConfig(rewrite_margin=99.0, clarify_margin=99.0))
    assert silent.changes == [] and silent.clarify == []  # and with both raised the transcript is kept as it is


def test_the_net_is_deterministic():
    a = review_transcript("come to the barking gate three", "ar")
    b = review_transcript("come to the barking gate three", "ar")
    assert [c.model_dump() for c in a.changes] == [c.model_dump() for c in b.changes]


def test_an_empty_or_numeric_transcript_is_fine():
    for text in ("", "   ", "12345", "!!!"):
        r = review_transcript(text, None)
        assert r.changes == [] and r.clarify == []
