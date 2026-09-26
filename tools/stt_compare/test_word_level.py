"""Word-level analysis of L2-ARCTIC utterances: segmentation, accent words, clear real-word swaps, transcript classification, clip location."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "importers"))
import phone_scoring as ps  # noqa: E402
import phones  # noqa: E402
import word_align as wa  # noqa: E402
import word_eval as we  # noqa: E402

LEX = {
    "the": [["DH", "AH0"]], "pit": [["P", "IH1", "T"]], "bit": [["B", "IH1", "T"]], "was": [["W", "AH1", "Z"]], "in": [["IH0", "N"]],
    "this": [["DH", "IH1", "S"]], "bag": [["B", "AE1", "G"]], "zehr": [["Z", "EH1", "R"]], "gate": [["G", "EY1", "T"]],
    "ferrous": [["F", "EH1", "R", "AH0", "S"]], "big": [["B", "IH1", "G"]], "pig": [["P", "IH1", "G"]], "dis": [["D", "IH1", "S"]],
}


def g2p(text):
    return "".join(ps.transcript_phones(text, LEX)[0])


def inv():
    return wa.inverse_lexicon(LEX)


def test_words_and_variants():
    assert wa.words_of("It's the Pit, isn't it?") == ["it's", "the", "pit", "isn't", "it"]
    assert wa.variants("pit", LEX) == [["p", "ɪ", "t"]] and wa.variants("unknownword", LEX) == []


def test_segment_tiles_the_phones_exactly():
    words = ["the", "pit", "was", "big"]
    spans = wa.segment(words, phones.tokenize(g2p("the pit was big")), LEX)
    assert [(s, e, x) for s, e, _, x in spans] == [(0, 2, True), (2, 5, True), (5, 8, True), (8, 11, True)]
    assert wa.segment(["the", "pit"], phones.tokenize(g2p("the pit was")), LEX) is None  # leftover phones


def test_an_unknown_word_takes_the_phones_between_its_exact_neighbours():
    canon = phones.tokenize(g2p("the pit") + "flʌgɪdʒɪz" + g2p("was big"))
    words = ["the", "pit", "luggages", "was", "big"]
    assert wa.segment(words, canon, LEX) is None  # not allowed by default
    spans = wa.segment(words, canon, LEX, max_unknown=1)
    assert [x for *_, x in spans] == [True, True, False, True, True]
    assert phones.tokenize("flʌgɪdʒɪz") == canon[spans[2][0] : spans[2][1]]


def test_the_frequency_floor_removes_obscure_dictionary_words():
    table = inv()
    assert "pit" in table[("p", "ɪ", "t")] and "bit" in table[("b", "ɪ", "t")]
    assert ("z", "ɛ", "ɹ") not in table  # 'zehr' is in the dictionary but nobody says it


def views(text, heard_g2p, intended_g2p=None):
    return wa.utterance_words(text, intended_g2p or g2p(text), heard_g2p, LEX, inv())


def test_a_p_heard_as_b_is_a_clear_real_word_swap():
    v = views("the pit was big", g2p("the bit was big"))
    assert [w.word for w in v if w.accent] == ["pit"]
    swap = next(w for w in v if w.accent)
    assert swap.swap_word == "bit" and swap.substitutions == [("p", "b")]


def test_a_distortion_that_is_not_a_word_is_an_accent_word_without_a_swap():
    v = views("the gate", g2p("the gate").replace("ɡ", "ɡʰ"))  # an aspirated stop: not a word in the dictionary
    assert [(w.word, bool(w.swap_word)) for w in v if w.accent] == [("gate", False)]


def test_a_th_to_d_word_that_happens_to_spell_a_word_is_a_swap_only_when_common():
    v = views("this", g2p("dis"))
    assert v[0].accent and v[0].swap_word == "dis"


def test_identical_or_alternative_pronunciations_are_not_accents():
    assert not any(w.accent for w in views("the pit", g2p("the pit")))
    assert not any(w.accent for w in wa.utterance_words("the", g2p("the"), "ðiː".replace("ː", ""), {"the": [["DH", "AH0"], ["DH", "IY0"]]}, inv()))


def test_unsegmentable_utterances_are_skipped_not_guessed():
    assert wa.utterance_words("the pit", "zzz", "zzz", LEX, inv(), 0) is None


def test_two_homophones_are_not_a_clear_mapping():
    lex = {"shoe": [["SH", "UW1"]], "to": [["T", "UW1"]], "too": [["T", "UW1"]], "two": [["T", "UW1"]]}
    v = wa.utterance_words("shoe", g2p_for(lex, "shoe"), "tu", lex, wa.inverse_lexicon(lex))
    assert v[0].accent and v[0].swap_word is None  # to / too / two: which one? not clear, so not written


def g2p_for(lex, text):
    return "".join(ps.transcript_phones(text, lex)[0])


# ---- transcript classification ----------------------------------------------------------------------------------


def test_classify_words_for_swaps_and_nonwords():
    v = views("the pit was big", g2p("the bit was big"))
    out = we.classify_words(v, "the pit was big")
    assert [(w.word, k, got) for w, k, got in out] == [("pit", we.FIXED, "pit")]
    assert [k for _, k, _ in we.classify_words(v, "the bit was big")] == [we.KEPT]
    assert [k for _, k, _ in we.classify_words(v, "the pat was big")] == [we.GARBLED]
    assert [k for _, k, _ in we.classify_words(v, "the was big")] == [we.NONE]
    d = views("the gate", g2p("the gate").replace("ɡ", "ɡʰ"))
    assert [k for _, k, _ in we.classify_words(d, "the gate")] == [we.RECOGNISED]
    assert [k for _, k, _ in we.classify_words(d, "the date")] == [we.OTHER]


# ---- locating a clip inside its full recording -------------------------------------------------------------------


def full_and_clip():
    text = "the pit was big the gate was in the bag"
    canonical = g2p(text)
    perceived = canonical.replace("p", "b", 1)  # the first /p/ (in "pit") is heard as /b/
    full = {"text": text, "g2p": canonical, "ipa": perceived}
    clip_words = "the gate was in the bag"
    start = canonical.index(g2p(clip_words))
    clip = {"g2p": g2p(clip_words), "ipa": perceived[start : start + len(g2p(clip_words))]}
    return full, clip


def test_a_clip_is_located_by_its_phones_and_its_words_are_recovered():
    full, clip = full_and_clip()
    assert we.clip_words(full, clip, LEX) == ["the", "gate", "was", "in", "the", "bag"]


def test_an_ambiguous_or_missing_clip_is_not_guessed():
    full, clip = full_and_clip()
    assert we.clip_words(full, {"g2p": "zzz", "ipa": "zzz"}, LEX) is None
    twice = {"text": full["text"] + " " + full["text"], "g2p": full["g2p"] * 2, "ipa": full["ipa"] * 2}
    assert we.clip_words(twice, clip, LEX) is None  # occurs twice: ambiguous


def test_find():
    assert we.find(list("abcabc"), list("bc")) == [1, 4] and we.find(list("abc"), []) == []
