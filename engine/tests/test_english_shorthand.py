"""SMS shorthand and squashed number+unit tokens: 5dys, 2tab, 2wice, aftr fud, b4 fud, stp."""

import pytest
from conftest import M, U, W, cond, mk

TABLET2 = mk("d", "dose", 2, "tablet")
DAYS5 = mk("d", "duration", 5, "day")


@pytest.mark.parametrize("reply", ["2tab", "2tabs", "2 tabs", "2tabl", "2 tblt", "2Tab", "take 2tab", "two tabz"])
def test_squashed_and_shorthand_dose(run, reply):
    assert run([TABLET2], reply)["d"].status == U, reply


@pytest.mark.parametrize("reply", ["5dys", "5 dys", "5dy", "5days", "5 dayz", "for 5dys", "5DYS"])
def test_squashed_and_shorthand_days(run, reply):
    assert run([DAYS5], reply)["d"].status == U, reply


@pytest.mark.parametrize("reply,days", [("1wk", 7), ("2wks", 14), ("2 wk", 14), ("3wek", 21), ("1 week", 7)])
def test_shorthand_weeks(run, reply, days):
    assert run([mk("d", "duration", days, "day")], reply)["d"].status == U, reply


@pytest.mark.parametrize("reply,n", [("2wice a day", 2), ("2wice", 2), ("twise a day", 2), ("3rice a day", 3), ("1ce a day", 1), ("2x", 2), ("3x a day", 3), ("2tmes a day", 2), ("2 tmes", 2)])
def test_shorthand_frequency(run, reply, n):
    assert run([mk("f", "frequency", n)], reply)["f"].status == U, reply


@pytest.mark.parametrize("reply", ["aftr fud", "aftr food", "after fud", "aftar fud", "AFTR FUD", "aftr meals"])
def test_after_food_shorthand(run, reply):
    assert run([mk("t", "timing", "after_food")], reply)["t"].status == U, reply


@pytest.mark.parametrize("reply", ["b4 fud", "b4 food", "bfr food", "befor fud", "b4 meals"])
def test_before_food_shorthand_and_wrong_direction(run, reply):
    assert run([mk("t", "timing", "before_food")], reply)["t"].status == U, reply
    assert run([mk("t", "timing", "after_food")], reply)["t"].status == W, reply


def test_stop_shorthand(run):
    assert run([cond("c", "rash", "stop")], "stp if rash")["c"].status == U
    assert run([cond("c", "rash", "stop")], "rash stp")["c"].status == U
    assert run([cond("c", "rash", "stop")], "dnt stp if rash")["c"].status != U  # SMS negation + SMS stop


def test_a_full_sms_reply(run):
    facts = [
        mk("dose", "dose", 2, "tablet"), mk("timing", "timing", "after_food"), mk("freq", "frequency", 2),
        mk("dur", "duration", 5, "day"), cond("rash", "rash", "stop"),
    ]
    res = run(facts, "2tab aftr fud 2wice a day 5dys stp if rash")
    assert {k: v.status for k, v in res.items()} == {k: U for k in ("dose", "timing", "freq", "dur", "rash")}
    res = run(facts, "3tab b4 fud 3x a day 7dys")
    assert res["dose"].status == W and res["timing"].status == W and res["freq"].status == W and res["dur"].status == W and res["rash"].status == M


def test_shorthand_does_not_invent_numbers_or_units(run):
    # "b4" contains a digit but is a word; "dy"/"wk" alone carry no number
    assert run([mk("d", "duration", 4, "day")], "b4 food")["d"].status == M
    assert run([mk("d", "duration", 5, "day")], "wk")["d"].status == M
    assert run([mk("d", "duration", 5, "day")], "dys")["d"].status == M
