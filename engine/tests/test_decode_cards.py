"""Decode: the DecodedCard for the exact cases in the Phase 2 brief, plus dignity, offsets and determinism (D36, D40, D41)."""

import json
import re
from pathlib import Path

import pytest

from steve_engine.decode import DecodedCard, decode, inspect_decode

ROOT = Path(__file__).resolve().parents[2]


def v(x):
    return x.value if x else None


# ---- the brief's exact cases -----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["typed", "voice"])
def test_yalla_habibi_barking_gate_tree(path):
    text = "yalla habibi come to the barking gate tree" if path == "typed" else "yalla habibi come to the barking gate three"
    c = decode(text, "ar", path)
    assert "parking" in c.plain_english and "gate 3" in c.plain_english
    assert v(c.actions.where) == "parking gate 3"
    by = {x.heard: x for x in c.changes}
    assert by["barking"].meant == "parking" and "no /p/" in by["barking"].reason
    if path == "typed":
        assert by["tree"].meant == "three"
    assert {p.phrase for p in c.phrases} == {"yalla", "habibi"}


def test_a_barking_dog_keeps_its_barking():
    c = decode("the barking dog is at the gate", "ar")
    assert c.changes == [] and c.clarify == [] and "barking" in c.plain_english


def test_bebsi_is_pepsi():
    c = decode("bring the bebsi from the fridge", "ar")
    assert "pepsi" in c.plain_english and [(x.heard, x.meant) for x in c.changes] == [("bebsi", "pepsi")] and v(c.actions.what) == "bring pepsi"


def test_barking_or_building_is_a_question_not_a_guess():
    c = decode("come to the barking or the building?", "ar")
    assert c.clarify and set(c.clarify[0].options) >= {"parking", "barking"} and c.changes == []
    assert c.actions.where is None  # where is ambiguous: no silent guess
    assert "barking" in c.plain_english


def test_dont_come_to_the_barking_now_khalas():
    c = decode("don't come to the barking now, khalas", "ar")
    assert v(c.actions.what) == "don't come" and v(c.actions.when) == "now" and v(c.actions.where) == "parking"
    assert [p.phrase for p in c.phrases] == ["khalas"] and "finished" in c.phrases[0].literal and c.phrases[0].social_meaning


def test_wait_one_minute_inshallah_send_the_money_tomorrow():
    c = decode("wait one minute, inshallah I send the money tomorrow")
    assert [p.phrase for p in c.phrases] == ["one minute", "inshallah"] and v(c.actions.when) == "tomorrow"
    insh = c.phrases[1]
    assert insh.social_meaning and "not always a firm promise" in insh.social_meaning
    for bad in ("lie", "excuse", "unreliable", "cannot be trusted"):
        assert bad not in insh.social_meaning.lower()


@pytest.mark.parametrize("hint", ["hi", None, "ar"])
def test_wery_good_come_at_fife(hint):
    c = decode("wery good, come at fife", hint)
    assert {(x.heard, x.meant) for x in c.changes} >= {("wery", "very"), ("fife", "five")} and v(c.actions.when) == "5" and c.plain_english.startswith("Very good")


def test_the_hindi_pack_explains_wery():
    c = decode("wery good", "hi")
    assert "v and w are often not told apart" in c.changes[0].reason


# ---- offsets, dignity, structure, determinism -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["😀 yalla habibi come to the barking gate tree 👍", "come to the barking 😀 gate", "🚚🚚 don't come to the barking now, khalas 🙏"])
def test_every_span_is_a_correct_code_point_offset_even_with_emoji(text):
    c = decode(text, "ar")
    assert c.original_text == text
    spans = [x.span for x in c.changes] + [p.span for p in c.phrases] + [q.span for q in c.clarify]
    spans += [a.evidence for a in (c.actions.where, c.actions.when, c.actions.what, c.actions.how_much) if a and a.evidence]
    assert spans
    for s in spans:
        assert text[s.start : s.end] == s.text and s.start < s.end


CORPUS = [
    "yalla habibi come to the barking gate tree", "the barking dog is at the gate", "bring the bebsi from the fridge", "come to the barking or the building?",
    "don't come to the barking now, khalas", "wait one minute, inshallah I send the money tomorrow", "wery good, come at fife", "wait at te basement near te lift",
    "pay fifty dirhams tomorrow", "kindly revert by tomorrow", "mafi mushkila, same same", "come to the gate free", "salam alaikum, sabah al khair",
    "call me before maghrib", "shway shway, the floor is wet", "please do the needful",
]


@pytest.mark.parametrize("text", CORPUS)
@pytest.mark.parametrize("path", ["typed", "voice"])
def test_no_output_ever_shames_the_speaker(text, path):
    c = decode(text, "ar", path)
    blob = json.dumps(c.model_dump(exclude={"original_text"}), ensure_ascii=False).lower()
    assert not re.search(r"\b(wrong|incorrect|bad english|poor english|broken english|mistake|error|fault)\b", blob), blob
    assert not re.search(r"\b(score|accuracy|percent)\b", blob)


def test_the_card_has_every_field_of_the_brief():
    c = decode("yalla habibi come to the barking gate tree", "ar")
    assert isinstance(c, DecodedCard)
    for field in ("original_text", "plain_english", "changes", "phrases", "actions", "clarify", "tips", "confidence", "accent_used"):
        assert hasattr(c, field)
    assert c.accent_used == "ar" and 0 <= c.confidence <= 1 and len(c.tips) <= 1
    assert set(c.actions.model_dump()) == {"where", "when", "what", "how_much"}
    assert DecodedCard.model_validate(json.loads(c.model_dump_json())) == c


def test_a_tip_is_one_short_neutral_pattern_explanation():
    c = decode("come to the barking gate", "ar")
    assert len(c.tips) == 1 and c.tips[0].startswith("It often sounds like this") and len(c.tips[0]) < 120


def test_decode_is_deterministic():
    a = decode("yalla habibi come to the barking gate tree", "ar")
    assert all(decode("yalla habibi come to the barking gate tree", "ar") == a for _ in range(3))


def test_confidence_drops_when_a_question_is_open():
    assert decode("come to the barking or the building?", "ar").confidence <= 0.5 < decode("come to the parking", "ar").confidence


def test_a_glossary_word_is_not_treated_as_a_misspelling():
    c = decode("yalla habibi khalas wallah", "ar")
    assert c.changes == [] and len(c.phrases) == 4


def test_plain_correct_english_is_returned_unchanged_apart_from_capitals():
    for text in ("come to the parking gate three at five", "the flat number is nine on the third floor"):
        c = decode(text)
        assert c.changes == [] and c.clarify == []
        assert c.plain_english.lower().replace("3", "three").replace("5", "five") == text


def test_empty_and_odd_input_do_not_crash():
    for text in ("", "   ", "😀", "12345", "!!! ???", "a", "x" * 5000):
        c = decode(text, "ar")
        assert isinstance(c, DecodedCard)


def test_paths_and_hints_are_validated():
    with pytest.raises(ValueError, match="path"):
        decode("hello", None, "audio")
    with pytest.raises(KeyError, match="no accent pack"):
        decode("hello", "xx")


def test_inspect_decode_shows_every_stage():
    info = inspect_decode("yalla habibi come to the barking gate tree", "ar")
    assert set(info) >= {"tokens", "glossary", "slots", "examined", "effective_words", "unresolved_tokens", "card", "path"}
    assert {g["phrase"] for g in info["glossary"]} == {"yalla", "habibi"} and "parking" in info["effective_words"] and info["card"]["actions"]["where"]["value"] == "parking gate 3"
    assert any(s["kind"] == "where" for s in info["slots"])


def test_the_voice_path_trusts_a_transcript_unless_a_critical_word_fits_badly():
    c = decode("we were wondering about the weather in the meeting", "ar", "voice")
    assert c.changes == [] and c.clarify == []


def test_the_typed_path_decodes_respelled_function_words():
    c = decode("wait at te basement near te lift", "ar")
    assert c.plain_english == "Wait at the basement near the lift"


def test_the_synthetic_sets_on_disk_are_what_the_generator_writes():
    import importlib.util

    spec = importlib.util.spec_from_file_location("decode_synth", ROOT / "eval" / "decode_synth.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name, rows in (("voice_synthetic.csv", mod.build_voice()), ("typed_synthetic.csv", mod.build_typed())):
        text = (ROOT / "data" / "decode" / name).read_text(encoding="utf-8")
        assert text.count("\n") == len(rows) + 1, name
        assert all(r["synthetic"] == "true" for r in rows)
