"""Copy-paste detection: a pasted message shows nothing about understanding -> every fact `unclear`."""

import json
from pathlib import Path

import pytest

from steve_engine import COPY_REASON, Status, check_reply, copy_similarity, looks_copied

SCENARIOS = json.loads((Path(__file__).resolve().parents[2] / "data" / "scenarios.json").read_text(encoding="utf-8"))
PHARMACY = SCENARIOS[0]
MSG = PHARMACY["text"]
FACTS = PHARMACY["facts"]


def run(reply, message=MSG):
    return check_reply(FACTS, reply, message=message)


@pytest.mark.parametrize(
    "reply",
    [
        MSG,
        MSG.upper(),
        MSG + " ok",
        "ok sir " + MSG,
        MSG.replace(",", "").replace(".", ""),
        "  " + MSG.replace("Take", "take") + " 👍",
        MSG.replace("2 tablets", "3 tablets"),  # near-verbatim: still a paste (documented in D14)
    ],
)
def test_pasted_message_marks_every_fact_unclear(reply):
    res = run(reply)
    assert len(res) == len(FACTS)
    for r in res:
        assert r.status == Status.unclear
        assert r.reason == COPY_REASON == "Reply looks copied from the message; ask them to say it in their own words."
        assert r.flags == ["copied"]
        assert r.evidence == [] and r.matched_terms == []
    assert copy_similarity(MSG, reply) > 0.85


@pytest.mark.parametrize(
    "reply",
    [
        "randu gulika, food kazhinju, raavile vaikittu, oru week",
        "do goli khane ke baad subah shaam paanch din",
        "I take two pills after eating, twice daily for five days and stop if I get a rash",
        "2 tablets after food twice a day 5 days",  # a SUBSET of the message's words must not count as a copy
        "5 days",
        "ok",
        "",
    ],
)
def test_own_words_are_never_flagged(reply):
    assert not looks_copied(MSG, reply)
    assert all("copied" not in r.flags for r in run(reply))


def test_own_words_still_get_real_statuses():
    res = {r.fact_id: r.status for r in run("randu gulika, food kazhinju, raavile vaikittu, oru week")}
    assert res["dose"] == Status.understood and res["dur"] == Status.wrong


def test_short_correct_reply_is_understood_even_though_its_words_are_a_subset():
    res = {r.fact_id: r.status for r in run("2 tablets after food twice a day 5 days")}
    assert res["dose"] == Status.understood and res["dur"] == Status.understood


def test_no_message_means_no_detection():
    assert all("copied" not in r.flags for r in check_reply(FACTS, MSG))
    assert not looks_copied(None, MSG)


def test_unrelated_message_is_not_a_copy():
    assert not looks_copied("Pay 30 AED by Friday and bring a signed form.", MSG)


def test_every_demo_preset_is_not_a_copy_of_its_own_message():
    for sc in SCENARIOS:
        for p in sc["presets"]:
            assert not looks_copied(sc["text"], p["text"]), (sc["id"], p["id"])


@pytest.mark.parametrize(
    "reply",
    [
        # honest restatements that reuse the message's own words: token_set_ratio alone scores ~100 on these
        "5 ml three times a day for 7 days, call if fever",
        "1 drop 3 times a day for 10 days",
        "come back friday, 3 times a day for 5 days, don't travel",
        "drink one bottle of water every hour, 15 minute break at 12:30, if dizzy stop work",
        "Take 2 tablets after food, twice a day, for 5 days. Stop and call if rash.",
    ],
)
def test_honest_restatements_in_english_are_not_copies(reply):
    from steve_engine.copycheck import order_similarity

    msg = {
        "5 ml": "Give the child 5 ml three times a day for 7 days. Call the clinic if there is fever.",
        "1 drop": "Put 1 drop in each eye, 3 times a day, for 10 days.",
        "come back": "Come back on Friday. Take the medicine 3 times a day for 5 days. Do not travel.",
        "drink one": "Drink 1 bottle of water every hour. Take a 15-minute break in the shade at 12:30. If you feel dizzy, stop work and tell the supervisor.",
        "Take 2": MSG,
    }[next(k for k in ("5 ml", "1 drop", "come back", "drink one", "Take 2") if reply.startswith(k))]
    assert not looks_copied(msg, reply), (copy_similarity(msg, reply), order_similarity(msg, reply))
