"""Phone tokenising and canonical-vs-perceived alignment (used by the L2-ARCTIC importers)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "importers"))
import phones  # noqa: E402
from phones import Op  # noqa: E402


def test_tokenize_strips_stress_and_keeps_diphthongs_and_affricates():
    assert phones.tokenize("kˈʌtʃɝ") == ["k", "ʌ", "tʃ", "ɝ"]
    assert phones.tokenize("laɪˈkoʊ dʒaʊ") == ["l", "aɪ", "k", "oʊ", "dʒ", "aʊ"]
    assert phones.tokenize("ˌˈ") == [] and phones.tokenize("") == []


def test_identical_sequences_are_all_matches():
    seq = phones.tokenize("pɑɹkɪŋ")
    assert all(o.kind == "match" for o in phones.align(seq, seq))


def test_a_p_heard_as_b_is_a_substitution():
    ops = phones.align(phones.tokenize("pɑɹkɪŋ"), phones.tokenize("bɑɹkɪŋ"))
    assert phones.substitutions(ops) == [("p", "b")]
    assert [o.kind for o in ops].count("match") == 5


def test_deletions_and_insertions():
    ops = phones.align(phones.tokenize("stɑp"), phones.tokenize("tɑp"))
    assert [(o.kind, o.canonical) for o in ops if o.kind != "match"] == [("del", "s")]
    ops = phones.align(phones.tokenize("tɑp"), phones.tokenize("tɑpə"))
    assert [(o.kind, o.perceived) for o in ops if o.kind != "match"] == [("ins", "ə")]


def test_a_vowel_for_a_vowel_is_preferred_over_delete_plus_insert():
    ops = phones.align(["b", "ʌ", "t"], ["b", "æ", "t"])
    assert ops == [Op("match", "b", "b"), Op("sub", "ʌ", "æ"), Op("match", "t", "t")]


def test_alignment_reconstructs_both_sequences():
    a, b = phones.tokenize("ðɪsɪzɐsɛntəns"), phones.tokenize("dɪsɪzəsɛntɪns")
    ops = phones.align(a, b)
    assert [o.canonical for o in ops if o.canonical] == a and [o.perceived for o in ops if o.perceived] == b


def test_empty_inputs():
    assert phones.align([], []) == []
    assert [o.kind for o in phones.align(["p"], [])] == ["del"] and [o.kind for o in phones.align([], ["p"])] == ["ins"]
