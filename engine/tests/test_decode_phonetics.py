"""Decode: pronunciations, frequencies, sound-alike words and spelling candidates (D36, D41)."""

import pytest

from steve_engine.decode import phonetics as ph
from steve_engine.decode.accents import active_swaps
from steve_engine.decode.tokens import tokenize
from steve_engine.decode.typed import spelling_candidates

AR = active_swaps("ar")


@pytest.mark.parametrize("word,real", [("parking", True), ("barking", True), ("gate", True), ("three", True), ("pepsi", True), ("bebsi", False),
                                       ("wery", False), ("zzzz", False), ("Parking", True), ("xyzzy", False)])
def test_is_word(word, real):
    assert ph.is_word(word) is real


def test_pronunciations_have_no_stress_digits_and_several_variants():
    assert ph.pronunciations("parking") == [("P", "AA", "R", "K", "IH", "NG")]
    assert len(ph.pronunciations("the")) >= 2 and all(not any(ch.isdigit() for p in v for ch in p) for v in ph.pronunciations("the"))
    assert ph.pronunciations("qqqqzzz") == []


def test_zipf_orders_common_before_rare():
    assert ph.zipf("the") > ph.zipf("parking") > ph.zipf("fife") > 0


def test_a_barking_word_sounds_like_parking_and_the_arabic_rule_makes_it_cheap():
    plain = {c.word: c.cost for c in ph.sound_alikes("barking")}
    with_rule = {c.word: c for c in ph.sound_alikes("barking", AR)}
    assert plain["parking"] == pytest.approx(0.6) or plain["parking"] == pytest.approx(1.0)
    assert with_rule["parking"].cost < plain["parking"] * 0.5 and with_rule["parking"].pack_rule == "ar: b -> p"


def test_sound_alikes_never_return_the_word_itself_and_are_sorted():
    out = ph.sound_alikes("gate", AR)
    assert "gate" not in {c.word for c in out}
    assert [c.cost for c in out] == sorted(c.cost for c in out)


@pytest.mark.parametrize("heard,meant", [("free", "three"), ("coal", "call"), ("tree", "three")])
def test_sound_alikes_find_the_neighbour(heard, meant):
    assert meant in {c.word for c in ph.sound_alikes(heard, active_swaps(None))}


def test_vocab_alikes_finds_a_word_two_edits_away_only_within_the_vocabulary():
    places = ["parking", "gate", "building", "floor", "lobby"]
    assert ph.vocab_alikes("packing", places)[0].word == "parking"
    assert ph.vocab_alikes("barking", places, AR)[0].cost < ph.vocab_alikes("barking", places)[0].cost


def test_homophones_are_cheap_candidates():
    gait = ph.vocab_alikes("gait", ["gate", "floor"])
    assert gait[0].word == "gate" and gait[0].cost == ph.HOMOPHONE_COST


def test_vocab_alikes_respects_max_cost_and_unknown_words():
    assert ph.vocab_alikes("desk", ["mosque", "kitchen"], max_cost=1.0) == []
    assert ph.vocab_alikes("qqqqzzz", ["gate"]) == []


def test_accent_rules_only_discount_the_matching_direction():
    ar = {c.word: c.cost for c in ph.vocab_alikes("parking", ["barking"], AR)}
    assert ar["barking"] > 0.5  # p heard, b meant is NOT an Arabic swap (the rule is b heard, p meant)


@pytest.mark.parametrize("typed,intended,hint", [("barking", "parking", "ar"), ("fife", "five", "ar"), ("wery", "very", "hi"), ("tree", "three", None),
                                                 ("dis", "this", None), ("bebsi", "pepsi", "ar"), ("bery", "very", "tl")])
def test_spelling_candidates_undo_accent_swaps(typed, intended, hint):
    assert intended in {c.word for c in spelling_candidates(typed, active_swaps(hint))}


def test_spelling_candidates_prefer_the_hinted_packs_swap():
    ar = {c.word: c.cost for c in spelling_candidates("fife", active_swaps("ar"))}
    unknown = {c.word: c.cost for c in spelling_candidates("fife", active_swaps(None))}
    assert ar["five"] < unknown["five"]


def test_spelling_candidates_only_return_real_words_and_never_the_input():
    out = spelling_candidates("bebsi", AR)
    assert all(ph.is_word(c.word) for c in out) and "bebsi" not in {c.word for c in out}
    assert spelling_candidates("zzzq", AR) == []


def test_tokenizer_offsets_are_code_points_even_with_emoji():
    text = "come 😀 to the 👍barking gate 3rd 5pm don't"
    toks = tokenize(text)
    assert [t.text for t in toks] == ["come", "to", "the", "barking", "gate", "3rd", "5pm", "don't"]
    for t in toks:
        assert text[t.start : t.end] == t.text


def test_tokenizer_straightens_curly_apostrophes():
    assert [t.norm for t in tokenize("Don’t come")] == ["don't", "come"]
