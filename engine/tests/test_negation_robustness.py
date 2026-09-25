"""SMS / typo negators. A misspelled "don't" must never turn "don't stop if rash" into "stop if rash"."""

import pytest
from conftest import N, U, cond, mk

STOP = [cond("c", "rash", "stop")]


@pytest.mark.parametrize(
    "reply",
    [
        # English SMS / typos
        "dnt stop if rash", "dont stop if rash", "donot stop if rash", "do nt stop if rash", "didnt stop if rash",
        "dontt stop if rash", "doont stop if rash", "don't stop if rash", "dun stop if rash", "nt stop if rash",
        "wont stop if rash", "never stop if rash", "not stop if rash",
        # Hindi / Urdu
        "rash ho to band nhi karo", "rash ho to band nai karo", "rash ho to band mt karo", "rash ho to band na karo",
        "rash ho to band mat karo", "rash aaye to rok mat do",
        # Malayalam
        "rash vannalum nirthanda", "rash vannal nirthanam venda", "rash vannal nirthanam alla",
        # Tagalog
        "kapag may rash, wag itigil", "kapag may rash, huwag itigil", "kapag may rash, hndi itigil",
        "kapag may rash, huwg itigil", "kapag may rash, di itigil", "kapag may rash, hindi itigil",
        # Arabizi
        "rash la waqqif", "rash mo waqqif", "rash mub wagif", "rash ma waqqif",
    ],
)
def test_negated_stop_in_every_spelling(run, reply):
    r = run(STOP, reply)["c"]
    assert r.status == N, (reply, r.status, r.reason)


@pytest.mark.parametrize("reply", ["dnt stop if rash", "dontstop if rash", "dnt sto if rash"])
def test_never_understood_when_a_negator_is_present_or_garbled(run, reply):
    assert run(STOP, reply)["c"].status != U


def test_fuzzy_negators_do_not_swallow_ordinary_words(run):
    for reply in ["note stop if rash", "dot stop if rash", "don stop if rash", "nod stop if rash", "dun stop if rash and"]:
        r = run(STOP, reply)["c"]
        if reply.startswith("dun"):
            continue  # "dun" is an SMS negator when English words surround it (covered above)
        assert r.status == U, (reply, r.status, r.reason)


def test_ambiguous_negators_need_same_language_support(run):
    # Tagalog "na" (already / linker) must NOT negate "tigil na"
    assert run(STOP, "kapag may rash, tigil na")["c"].status == U
    assert run(STOP, "kapag may rash itigil na po")["c"].status == U
    # Tagalog "mo" = "your"; Tagalog "dun" = "there"; Tagalog "di" needs Tagalog neighbours
    assert run(STOP, "yung gamot mo, kapag may rash itigil")["c"].status == U
    assert run(STOP, "kapag may rash dun itigil")["c"].status == U
    assert run([mk("d", "dose", 2, "tablet")], "2 tablets mo")["d"].status == U


def test_negated_numbers_and_timing_with_sms_negators(run):
    assert run([mk("d", "dose", 2, "tablet")], "dnt take 2 tablets")["d"].status == N
    assert run([mk("t", "timing", "after_food")], "dnt take after food")["t"].status == N
    assert run([mk("a", "amount", 150, "AED")], "nhi 150 dirham")["a"].status == N


def test_avoid_fact_with_typo_negator(run):
    f = [mk("c", "condition", {"trigger": "travel", "action": "avoid", "text": "Do not travel"})]
    assert run(f, "dnt travel")["c"].status == U
    assert run(f, "huwg bumiyahe")["c"].status == U
    assert run(f, "travel")["c"].status != U
