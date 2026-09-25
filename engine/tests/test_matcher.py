from samjha_engine.matcher import prepare
from samjha_engine.normalize import sound_key, tokenize


def cats(text, lang=None):
    return [(m.surface, m.category, m.value) for m in prepare(text, lang).matches]


def test_done_does_not_match_one():
    assert not [m for m in prepare("done").matches if m.category == "number"]
    assert not [m for m in prepare("I am done with it").matches if m.category == "number"]


def test_no_does_not_match_do():
    ms = prepare("no").matches
    assert [m.category for m in ms] == ["negation"]
    assert not [m for m in ms if m.category == "number"]


def test_to_is_not_two():
    assert not [m for m in prepare("I went to the shop").matches if m.category == "number"]
    assert not [m for m in prepare("to").matches if m.category == "number"]


def test_do_is_only_two_with_hindi_support():
    assert cats("do goli")[0][1:] == ("number", 2.0)
    assert not [m for m in prepare("do the thing").matches if m.category == "number"]
    assert not [m for m in prepare("do not take").matches if m.category == "number"]
    assert [m for m in prepare("do baar").matches if m.category == "number"]


def test_short_tokens_exact_only():
    # 3-letter near-misses must not fuzzy match
    for w in ["tno", "dno", "thr", "fiv", "sxi", "nne"]:
        assert not [m for m in prepare(w).matches if m.category == "number"], w


def test_sound_key_equivalences():
    assert sound_key("paanch") == sound_key("panch")
    assert sound_key("arba3a") == sound_key("arbaa")
    assert sound_key("vaikittu") == sound_key("vaikeettu")
    assert sound_key("wa7ed") == sound_key("wahed")
    assert sound_key("5amsa") == sound_key("khamsa")


def test_offsets_with_emoji_and_case():
    text = "😊 RaNDu   gulika!"
    toks = tokenize(text)
    assert [text[t.start : t.end] for t in toks] == ["RaNDu", "gulika"]
    assert toks[0].norm == "randu"


def test_arabic_indic_digits():
    ms = prepare("٥ ayyam").matches
    assert ms[0].category == "number" and ms[0].value == 5


def test_glued_number_unit():
    ms = {m.category: m.value for m in prepare("5days 2tabs").matches if m.category in ("duration_unit", "unit")}
    assert ms == {"duration_unit": "day", "unit": "tablet"}


def test_arabizi_digit_words_not_split():
    ms = prepare("3ashra wa7ed").matches
    assert [m.value for m in ms] == [10, 1]


def test_tagalog_linker_suffix_stripping():
    assert prepare("tatlong").matches[0].value == 3
    assert prepare("sampung").matches[0].value == 10


def test_english_plural_stem():
    m = prepare("weeks").matches[0]
    assert m.category == "duration_unit" and m.value == "week"


def test_phrase_match_longest_wins():
    ms = prepare("take it on an empty stomach").matches
    assert any(m.category == "timing" and m.value == "empty_stomach" for m in ms)


def test_compound_numbers_merge():
    ms = [m for m in prepare("one hundred fifty dirham").matches if m.category == "number"]
    assert ms[0].value == 150
    ms = [m for m in prepare("twenty five aed").matches if m.category == "number"]
    assert ms[0].value == 25


def test_clock_token():
    ms = prepare("break at 12:30").matches
    assert any(m.category == "clock" and m.value == "12:30" for m in ms)


def test_decimal_and_thousands():
    ms = [m for m in prepare("2.5 ml and 1,500 aed").matches if m.category == "number"]
    assert [m.value for m in ms] == [2.5, 1500]


def test_article_a_only_before_unit():
    ms = [m for m in prepare("a week").matches if m.category == "number"]
    assert ms and ms[0].value == 1
    assert not [m for m in prepare("a good idea").matches if m.category == "number"]
    assert not [m for m in prepare("twice a day").matches if m.category == "number"]


def test_lang_hint_and_neighbour_break_ties():
    m = prepare("do goli", "hi").matches[0]
    assert m.lang == "hi"
