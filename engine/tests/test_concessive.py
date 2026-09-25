"""Concessive clauses ("even if rash") undermine or flip a rule. They can never be `understood`."""

import pytest
from conftest import C, N, U, cond

STOP = [cond("c", "rash", "stop")]


@pytest.mark.parametrize(
    "reply",
    [
        "stop only after 5 days even if rash",
        "stop even with rash", "despite rash, stop", "rash still stop", "rash anyway stop taking it",
        "rash regardless stop", "even though rash i stop",
        "rash bhi ho to band karo", "kahit may rash itigil", "kahit na may rash, itigil",
        "rash vannalum nirthanam", "rash aayalum nirthu",
    ],
)
def test_concessive_is_never_understood(run, reply):
    r = run(STOP, reply)["c"]
    assert r.status == C, (reply, r.status, r.reason)
    assert "undermines" in r.reason


@pytest.mark.parametrize(
    "reply",
    [
        "even if rash continue", "even if rash, keep taking them", "despite rash i continue",
        "rash vannalum continue", "kahit may rash, ituloy", "rash bhi ho to continue karo", "rash still continue",
    ],
)
def test_concessive_with_continue_is_negated(run, reply):
    r = run(STOP, reply)["c"]
    assert r.status == N, (reply, r.status, r.reason)


def test_concessive_far_from_the_trigger_is_ignored(run):
    assert run(STOP, "main bhi do goli lunga, rash aaye to band karo")["c"].status == U
    assert run(STOP, "still 5 days. if rash, stop")["c"].status == U
    assert run(STOP, "stop if rash")["c"].status == U


def test_concessive_in_another_sentence_is_ignored(run):
    assert run(STOP, "I will take it anyway. If rash, stop.")["c"].status == U


def test_expected_continue_fact_may_use_even_if(run):
    assert run([cond("c", "rash", "continue")], "even if rash continue")["c"].status == U


def test_call_fact_with_concessive_is_unclear(run):
    assert run([cond("c", "fever", "call")], "even if fever call")["c"].status == C


def test_existing_negation_still_wins_over_concessive(run):
    assert run(STOP, "rash vannalum nirthanda")["c"].status == N
    assert run(STOP, "even if rash don't stop")["c"].status == N
