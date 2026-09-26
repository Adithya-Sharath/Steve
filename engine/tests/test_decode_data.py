"""Decode data files: the domain vocabulary and the accent packs load, validate, and stay honest (everything verified: false, D36)."""

from pathlib import Path

import pytest
import yaml

from steve_engine.decode import accents
from steve_engine.decode.domain import CATEGORIES, get_domain, load_domain

ROOT = Path(__file__).resolve().parents[2]


# ---- domain ----------------------------------------------------------------------------------------------------


def test_the_domain_lists_are_populated_and_unverified():
    d = get_domain()
    assert set(d.words) == set(CATEGORIES) and d.verified is False
    assert all(len(d.words[c]) >= 15 for c in CATEGORIES)
    assert {"parking", "gate", "building", "floor", "villa", "flat", "reception", "lobby", "metro", "station", "masjid", "mall", "basement", "lift", "stairs"} <= d.words["place"]
    assert {"now", "today", "tomorrow", "morning", "evening"} <= d.words["time"] and {"come", "go", "wait", "bring", "call", "drop", "deliver", "clean", "fix"} <= d.words["action"]


@pytest.mark.parametrize("word,cat", [("parking", "place"), ("Tomorrow", "time"), ("five", "number"), ("17", "number"), ("5pm", "number"), ("3rd", "number"),
                                      ("never", "negation"), ("don't", "negation"), ("dirhams", "amount"), ("come", "action"), ("barking", None), ("dog", None)])
def test_categories(word, cat):
    assert get_domain().category(word) == cat


def test_in_category_handles_digits_and_case():
    d = get_domain()
    assert d.in_category("12", "number") and d.in_category("Gate", "place") and not d.in_category("gate", "time")


def test_dont_touch_covers_negations_numbers_amounts_and_named_times():
    d = get_domain()
    for w in ("not", "no", "never", "don't", "five", "hundred", "20", "5pm", "dirham", "monday", "tomorrow", "fajr", "am"):
        assert d.is_dont_touch(w), w
    for w in ("parking", "gate", "come", "hours", "days", "dog", "the"):
        assert not d.is_dont_touch(w), w


def test_a_domain_file_must_stay_unverified_and_use_known_categories(tmp_path):
    good = yaml.safe_load((ROOT / "engine/steve_engine/decode/domain.yaml").read_text(encoding="utf-8"))
    p = tmp_path / "d.yaml"
    p.write_text(yaml.safe_dump({**good, "verified": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="verified: false"):
        load_domain(p)
    p.write_text(yaml.safe_dump({**good, "categories": {**good["categories"], "colours": ["red"]}}), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown domain categories"):
        load_domain(p)


# ---- accent packs -----------------------------------------------------------------------------------------------


def test_every_pack_loads_and_every_rule_is_unverified_with_a_reason():
    for pid in accents.PACK_IDS:
        pack = accents.load_pack(pid)
        assert pack.id == pid and pack.verified is False
        for s in pack.swaps:
            assert 0 < s.weight <= 1 and s.note and s.heard != s.meant
            assert s.phones is None or set(s.phones) <= accents.ARPABET


def test_the_arabic_pack_is_conservative_and_matches_the_briefing():
    swaps = {(s.heard, s.meant): s for s in accents.load_pack("ar").swaps}
    assert set(swaps) == {("b", "p"), ("f", "v")}  # only what was specified as a solid Arabic-English pattern; vowel guesses were left out
    assert swaps[("b", "p")].weight == 0.9 and swaps[("b", "p")].phones == ("B", "P") and "no /p/" in swaps[("b", "p")].note


def test_the_other_packs_have_two_to_four_conservative_swaps_at_most():
    assert {(s.heard, s.meant) for s in accents.load_pack("hi").swaps} == {("w", "v"), ("v", "w")}
    assert {(s.heard, s.meant) for s in accents.load_pack("common").swaps} == {("t", "th"), ("d", "th")}
    assert 1 <= len(accents.load_pack("ml").swaps) <= 4 and 1 <= len(accents.load_pack("tl").swaps) <= 4


def test_active_swaps_use_the_hint_or_fall_back_to_all_packs_at_half_weight():
    hinted = accents.active_swaps("ar")
    assert {s.pack for s in hinted} == set(accents.PACK_IDS)  # the hinted pack at full weight, every other pack at half weight
    hi_w = next(s.weight for s in hinted if s.pack == "hi" and s.heard == "w")
    assert hi_w == pytest.approx(accents.load_pack("hi").swaps[0].weight / 2)
    unknown = accents.active_swaps(None)
    assert {s.pack for s in unknown} == set(accents.PACK_IDS)
    ar_full = next(s.weight for s in hinted if s.pack == "ar" and s.heard == "b")
    ar_half = next(s.weight for s in unknown if s.pack == "ar" and s.heard == "b")
    assert ar_half == pytest.approx(ar_full / 2)
    with pytest.raises(KeyError, match="no accent pack"):
        accents.active_swaps("xx")


@pytest.mark.parametrize("swap", [
    {"heard": "b", "meant": "p", "weight": 0.9, "note": "x", "verified": True},
    {"heard": "b", "meant": "p", "weight": 1.5, "note": "x", "verified": False},
    {"heard": "b", "meant": "b", "weight": 0.5, "note": "x", "verified": False},
    {"heard": "b", "meant": "p", "weight": 0.5, "note": "", "verified": False},
    {"heard": "b", "meant": "p", "weight": 0.5, "phones": ["B", "QQ"], "note": "x", "verified": False},
    {"heard": "b1", "meant": "p", "weight": 0.5, "note": "x", "verified": False},
])
def test_a_bad_rule_is_rejected(tmp_path, swap):
    p = tmp_path / "xx.yaml"
    p.write_text(yaml.safe_dump({"id": "xx", "name": "x", "verified": False, "swaps": [swap]}), encoding="utf-8")
    with pytest.raises(ValueError):
        accents._pack(p)


def test_a_pack_must_be_unverified_and_match_its_file_name(tmp_path):
    (tmp_path / "xx.yaml").write_text(yaml.safe_dump({"id": "yy", "name": "x", "verified": False, "swaps": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        accents._pack(tmp_path / "xx.yaml")
    (tmp_path / "zz.yaml").write_text(yaml.safe_dump({"id": "zz", "name": "x", "verified": True, "swaps": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="verified: false"):
        accents._pack(tmp_path / "zz.yaml")


def test_the_review_sheet_lists_every_rule():
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_accent_review", ROOT / "engine/tools/make_accent_review.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = mod.build()
    assert text.count("| [ ] |") == sum(len(accents.load_pack(p).swaps) for p in accents.PACK_IDS)
    assert "Arabic has no /p/ sound" in text
    # the committed sheet is the generated one
    assert (ROOT / "ACCENT_REVIEW.md").read_text(encoding="utf-8").strip() == text.strip()


def test_a_bare_yaml_boolean_word_is_rejected_not_silently_turned_into_false(tmp_path):
    good = yaml.safe_load((ROOT / "engine/steve_engine/decode/domain.yaml").read_text(encoding="utf-8"))
    good["categories"]["negation"] = [False if w == "no" else w for w in good["categories"]["negation"]]  # what an unquoted no becomes
    p = tmp_path / "d.yaml"
    p.write_text(yaml.safe_dump(good), encoding="utf-8")
    with pytest.raises(ValueError, match="non-string"):
        load_domain(p)
