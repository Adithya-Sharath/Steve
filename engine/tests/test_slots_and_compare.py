import pytest
from conftest import C, M, N, U, W, cond, mk


# ---------------------------------------------------------------- dose
@pytest.mark.parametrize(
    "reply",
    ["randu gulika", "do goli", "dalawang tableta", "ithnain habba", "2 tabs", "two tablets", "2 tablet", "take 2 pills", "moonu gulika illa randu gulika"],
)
def test_dose_two_tablets(run, reply):
    r = run([mk("d", "dose", 2, "tablet")], reply)["d"]
    if reply.startswith("moonu"):
        assert r.status in (C, U)  # contains both 3 and 2 -> must not be a clean 'understood'
    else:
        assert r.status == U, r.reason


def test_dose_wrong_number(run):
    r = run([mk("d", "dose", 2, "tablet")], "moonu gulika")["d"]
    assert r.status == W and r.heard_value == 3


def test_dose_half(run):
    assert run([mk("d", "dose", 0.5, "tablet")], "half tablet")["d"].status == U
    assert run([mk("d", "dose", 0.5, "tablet")], "aadha goli")["d"].status == U
    assert run([mk("d", "dose", 0.5, "tablet")], "nuss habba")["d"].status == U


def test_dose_conflict_is_unclear_not_understood(run):
    r = run([mk("d", "dose", 2, "tablet")], "2 tablets and also 3 tablets")["d"]
    assert r.status == C


def test_dose_unit_class_tablet_capsule_equivalent(run):
    assert run([mk("d", "dose", 1, "tablet")], "1 capsule")["d"].status == U


def test_dose_wrong_unit(run):
    r = run([mk("d", "dose", 2, "tablet")], "2 ml")["d"]
    assert r.status == W


def test_bare_number_is_never_understood(run):
    facts = [mk("d", "dose", 2, "tablet"), mk("dur", "duration", 5, "day")]
    res = run(facts, "2 5")
    assert res["d"].status == C and res["dur"].status == C


def test_dose_negated(run):
    r = run([mk("d", "dose", 2, "tablet")], "don't take 2 tablets")["d"]
    assert r.status == N


# ---------------------------------------------------------------- frequency
@pytest.mark.parametrize(
    "reply,n",
    [
        ("twice a day", 2), ("2 times", 2), ("do baar", 2), ("randu neram", 2), ("marratain", 2), ("dalawang beses", 2),
        ("once", 1), ("thrice", 3), ("three times a day", 3), ("ek baar", 1), ("3x", 3), ("every 8 hours", 3), ("every 12 hours", 2),
        ("every hour", 24), ("daily", 1), ("every day", 1),
    ],
)
def test_frequency_explicit(run, reply, n):
    r = run([mk("f", "frequency", n)], reply)["f"]
    assert r.status == U, (reply, r.reason)


def test_frequency_wrong(run):
    r = run([mk("f", "frequency", 2)], "3 times a day")["f"]
    assert r.status == W and r.heard_value == 3


def test_frequency_inferred_from_times_of_day(run):
    r = run([mk("f", "frequency", 2)], "subah shaam")["f"]
    assert r.status == U and "inferred" in r.reason
    assert r.confidence < 0.9  # lower confidence than an explicit statement


def test_frequency_single_time_of_day_is_only_unclear(run):
    r = run([mk("f", "frequency", 1)], "raavile")["f"]
    assert r.status == C


def test_explicit_frequency_beats_inference(run):
    r = run([mk("f", "frequency", 3)], "morning and night, three times a day")["f"]
    assert r.status == U


def test_marra_implicit_once(run):
    assert run([mk("f", "frequency", 1)], "marra")["f"].status == U


# ---------------------------------------------------------------- timing
def test_timing_before_vs_after_is_wrong(run):
    r = run([mk("t", "timing", "after_food")], "food munpu")["t"]
    assert r.status == W
    r = run([mk("t", "timing", "before_food")], "khane ke baad")["t"]
    assert r.status == W


def test_timing_set_understood(run):
    r = run([mk("t", "timing", ["after_food", "morning", "night"])], "after food, morning and night")["t"]
    assert r.status == U


def test_timing_partial_is_missing(run):
    r = run([mk("t", "timing", ["after_food", "morning", "night"])], "after food in the morning")["t"]
    assert r.status in (M, W)
    assert r.status != U


def test_timing_wrong_time_of_day(run):
    r = run([mk("t", "timing", "morning")], "at night")["t"]
    assert r.status == W


def test_timing_empty_stomach(run):
    assert run([mk("t", "timing", "empty_stomach")], "on an empty stomach")["t"].status == U
    assert run([mk("t", "timing", "empty_stomach")], "khali pet")["t"].status == U
    assert run([mk("t", "timing", "after_food")], "on an empty stomach")["t"].status == W


def test_timing_negated(run):
    r = run([mk("t", "timing", "after_food")], "not after food")["t"]
    assert r.status == N


def test_after_alone_is_not_after_food(run):
    assert run([mk("t", "timing", "after_food")], "after 5 days")["t"].status == M


# ---------------------------------------------------------------- duration
@pytest.mark.parametrize(
    "reply,days",
    [("oru week", 7), ("ek hafta", 7), ("isang linggo", 7), ("5 divasam", 5), ("paanch din", 5), ("2 weeks", 14), ("one month", 30), ("a week", 7), ("for 10 days", 10), ("esbou3 wa7ed", None)],
)
def test_duration(run, reply, days):
    if days is None:
        pytest.skip("number-after-unit form is not supported for Arabizi weeks")
    r = run([mk("d", "duration", days, "day")], reply)["d"]
    assert r.status == U, (reply, r.reason)


def test_twice_a_day_is_not_a_one_day_duration(run):
    r = run([mk("d", "duration", 1, "day")], "twice a day")["d"]
    assert r.status == M


def test_duration_minutes(run):
    f = [mk("d", "duration", 15, "minute")]
    assert run(f, "15 minute break")["d"].status == U
    assert run(f, "15 minuto")["d"].status == U
    assert run(f, "quarter hour")["d"].status in (M, C)
    assert run(f, "20 minutes")["d"].status == W


def test_every_hour_is_not_a_duration(run):
    r = run([mk("d", "duration", 1, "hour")], "every hour")["d"]
    assert r.status == M


# ---------------------------------------------------------------- amount / date
def test_amount(run):
    f = [mk("a", "amount", 150, "AED")]
    assert run(f, "150 AED")["a"].status == U
    assert run(f, "AED 150")["a"].status == U
    assert run(f, "one hundred fifty dirham")["a"].status == U
    assert run(f, "150 dhs")["a"].status == U
    assert run(f, "115 AED")["a"].status == W
    assert run(f, "150 rupees")["a"].status == W


def test_dates_weekday_and_clock(run):
    assert run([mk("d", "date", "thursday")], "by Thursday")["d"].status == U
    assert run([mk("d", "date", "thursday")], "guruvaar")["d"].status == U
    assert run([mk("d", "date", "thursday")], "huwebes")["d"].status == U
    assert run([mk("d", "date", "thursday")], "youm al khamis")["d"].status == U
    assert run([mk("d", "date", "thursday")], "friday")["d"].status == W
    assert run([mk("d", "date", "12:30")], "at 12:30")["d"].status == U
    assert run([mk("d", "date", "12:30")], "at 1:30")["d"].status == W


def test_two_dates_claim_each_other(run):
    facts = [mk("trip", "date", "monday"), mk("due", "date", "friday")]
    res = run(facts, "the fee is due friday")
    assert res["due"].status == U
    assert res["trip"].status == M  # 'friday' belongs to the other fact, so no false 'wrong'
    res = run(facts, "trip monday, money friday")
    assert res["trip"].status == U and res["due"].status == U
    res = run(facts, "trip tuesday, money friday")
    assert res["trip"].status == W and res["due"].status == U


def test_iso_and_month_dates(run):
    assert run([mk("d", "date", "2026-03-15")], "15 march")["d"].status == U
    assert run([mk("d", "date", "2026-03-15")], "march 15")["d"].status == U
    assert run([mk("d", "date", "2026-03-15")], "16 march")["d"].status == W


# ---------------------------------------------------------------- condition & negation
@pytest.mark.parametrize(
    "reply,expected",
    [
        ("rash vannal nirthanam", U),
        ("rash vannalum nirthanda", N),
        ("if rash, stop", U),
        ("if rash don't stop", N),
        ("rash aayaal band karo", U),
        ("rash ho to band mat karo", N),
        ("rash lumabas huwag itigil", N),
        ("rash lumabas itigil", U),
        ("rash ma tiwaqqif", None),
        ("rash sa3at wagif", U),
        ("stop", C),
        ("rash", C),
        ("rash vannal continue", W),
        ("rash vannal nirthanam venda", N),
        ("randu gulika", M),
    ],
)
def test_condition_stop_if_rash(run, reply, expected):
    r = run([cond("c", "rash", "stop")], reply)["c"]
    if expected is None:
        assert r.status != U
    else:
        assert r.status == expected, (reply, r.status, r.reason)


def test_condition_call(run):
    f = [cond("c", "dizzy", "call")]
    assert run(f, "dizzy aayal vilikkanam")["c"].status == U
    assert run(f, "if dizzy call")["c"].status == U
    assert run(f, "chakkar aaye to call karo")["c"].status == U
    assert run(f, "dizzy")["c"].status == C


def test_stop_and_call_facts_claim_their_own_action(run):
    facts = [cond("stop", "rash", "stop"), cond("call", "rash", "call")]
    res = run(facts, "if rash stop taking and call them")
    assert res["stop"].status == U and res["call"].status == U
    res = run(facts, "if rash call them")
    assert res["call"].status == U and res["stop"].status == C


def test_condition_trigger_synonym_other_language(run):
    assert run([cond("c", "fever", "call")], "bukhar ho to call karo")["c"].status == U
    assert run([cond("c", "rash", "stop")], "pantal lumabas itigil")["c"].status == U


def test_condition_free_text_trigger_fuzzy(run):
    f = [cond("c", "visa stamped", "call")]
    assert run(f, "when visa stamped call")["c"].status == U


def test_avoid_travel(run):
    f = [mk("c", "condition", {"trigger": "travel", "action": "avoid", "text": "Do not travel until visa is stamped"})]
    assert run(f, "do not travel")["c"].status == U
    assert run(f, "travel cheyyaruthu")["c"].status in (U, C)
    assert run(f, "safar mat karo")["c"].status == U
    assert run(f, "huwag bumiyahe")["c"].status == U
    assert run(f, "I will travel")["c"].status == C
    assert run(f, "ok")["c"].status == M


def test_negation_does_not_leak_across_sentences(run):
    r = run([mk("d", "dose", 2, "tablet")], "I do not know. 2 tablets")["d"]
    assert r.status == U


# ---------------------------------------------------------------- safety properties
def test_no_false_understood_on_wrong_numbers(run, rx_facts):
    res = run(rx_facts[:4], "teen goli khane ke baad char baar paanch din")
    assert res["dose"].status == W and res["freq"].status == W and res["dur"].status == U


def test_confidence_threshold_makes_weak_matches_unclear():
    from samjha_engine import EngineConfig, check_reply

    facts = [mk("d", "dose", 2, "tablet")]
    strict = check_reply(facts, "rendu gulikka", config=EngineConfig(unclear_threshold=0.99))[0]
    assert strict.status == C


def test_result_shape(run):
    r = run([mk("d", "dose", 2, "tablet")], "randu gulika")["d"]
    assert r.matched_terms and {"token", "lexeme", "lang", "score"} <= set(r.matched_terms[0])
    assert 0 <= r.confidence <= 1 and r.reason


def test_empty_and_nonsense_reply(run, rx_facts):
    for reply in ["", "asdkjh qwe", "😀😀😀"]:
        assert all(r.status == M for r in run(rx_facts, reply).values())


def test_lexicon_loads_and_only_english_is_verified():
    from samjha_engine.lexicon import get_lexicon

    lex = get_lexicon()
    assert len(lex.entries) > 250
    assert all(e.verified == (e.lang == "en") for e in lex.entries)


# ---------------------------------------------------------------- rate phrases ("per day")
def test_daily_marker_does_not_conflict_with_explicit_count(run):
    f = [mk("f", "frequency", 2)]
    assert run(f, "roz do baar")["f"].status == U
    assert run(f, "twice daily")["f"].status == U
    assert run(f, "dinavum randu neram")["f"].status == U
    assert run([mk("f", "frequency", 1)], "roz")["f"].status == U


def test_lone_one_day_after_frequency_is_a_rate_not_a_duration(run):
    d = [mk("d", "duration", 1, "day")]
    assert run(d, "dalawang beses sa isang araw")["d"].status == M
    assert run(d, "twice a day")["d"].status == M
    both = [mk("f", "frequency", 2), mk("d", "duration", 5, "day")]
    res = run(both, "dalawang beses sa isang araw, limang araw")
    assert res["f"].status == U and res["d"].status == U
    assert run(d, "1 day")["d"].status == U


# ---------------------------------------------------------------- found by reading the eval errors
def test_arabizi_digit_words_are_not_split_into_number_plus_word(run):
    # "7ma" (fever) used to be split into 7 + "ma" (negation) and negate the action
    r = run([cond("c", "fever", "call")], "law 7ma ittasil")["c"]
    assert r.status != N


def test_do_before_english_unit_is_two_in_hinglish(run):
    assert run([mk("d", "dose", 2, "bottle")], "do bottle")["d"].status == U
    assert run([mk("d", "dose", 2, "puff")], "do puffs")["d"].status == U
    assert run([mk("d", "dose", 2, "photo")], "do photos")["d"].status == U
    # ...but a verb "do" is still not a number
    assert run([mk("d", "dose", 2, "tablet")], "do not take")["d"].status == M
    assert run([mk("d", "dose", 2, "tablet")], "what do you do")["d"].status == M


def test_typo_in_a_negation_word_still_negates(run):
    assert run([mk("d", "duration", 5, "day")], "hndi lima araw")["d"].status == N
    assert run([mk("c", "condition", {"trigger": "travel", "action": "avoid", "text": ""})], "huwg bumiyahe")["c"].status == U


def test_a_day_is_a_rate_even_if_the_frequency_word_is_misspelled(run):
    both = [mk("b", "duration", 15, "minute"), mk("d", "duration", 1, "day")]
    res = run(both, "twce a day, 15 minute break")
    assert res["b"].status == U and res["d"].status == M
    assert run([mk("d", "duration", 1, "day")], "for a day")["d"].status == U


def test_period_word_is_only_weak_evidence(run):
    r = run([mk("f", "frequency", 2)], "dinavum ranu neram")["f"]  # count unreadable: must not become "wrong"
    assert r.status in (M, C)
    r = run([mk("f", "frequency", 2)], "daily")["f"]
    assert r.status == C  # daily alone != twice a day


def test_bare_countable_object_counts_as_one(run):
    assert run([mk("d", "dose", 1, "form")], "signed form")["d"].status == U
    assert run([mk("d", "dose", 1, "bottle")], "water bottle")["d"].status == U
    assert run([mk("d", "dose", 2, "bottle")], "water bottle")["d"].status == C  # mentioned, but no number to check
    assert run([mk("d", "dose", 1, "tablet")], "tablet leni hai")["d"].status == M  # medication is never guessed
    assert run([mk("d", "dose", 1, "bottle")], "2 bottle")["d"].status == W


def test_clock_and_weekday_facts_do_not_blame_each_other(run):
    facts = [mk("t", "date", "06:00"), mk("d", "date", "sunday")]
    res = run(facts, "friday, 2 photos")
    assert res["d"].status == W and res["t"].status == M


def test_two_unmatched_same_kind_facts_are_unclear_not_wrong(run):
    facts = [mk("trip", "date", "monday"), mk("due", "date", "friday")]
    res = run(facts, "saturday")
    assert res["trip"].status == C and res["due"].status == C


def test_no_sound_key_collisions_between_different_meanings():
    """A misspelling must never be equally close to two different meanings (e.g. sab3a=7 vs sabah=morning)."""
    from samjha_engine.lexicon import get_lexicon
    from samjha_engine.normalize import phrase_key, sound_key

    seen: dict[str, set[tuple]] = {}
    for e in get_lexicon().entries:
        for f in e.forms:
            k = phrase_key(f) if " " in f else sound_key(f)
            if len(k) >= 4:  # 3-letter words are matched exactly, never by sound
                seen.setdefault(k, set()).add((e.category, str(e.value)))
    clashes = {k: v for k, v in seen.items() if len(v) > 1}
    assert not clashes, clashes


# ---------------------------------------------------------------- found by the blind held-out run
def test_short_number_words_never_fuzzy_match_other_words(run):
    # Hindi "aankh" (eye) used to fuzzy-match Malayalam "anchu" (5)
    assert run([mk("d", "duration", 5, "day")], "aankh mein din")["d"].status == M
    assert run([mk("d", "duration", 5, "day")], "ek ek boond dono aankh mein, das din")["d"].status == W


def test_for_a_week_after_daily_is_a_duration(run):
    assert run([mk("d", "duration", 7, "day")], "thrice daily for a week")["d"].status == U
    assert run([mk("d", "duration", 1, "day")], "twice a day")["d"].status == M


def test_plural_marrat_is_a_counter_not_once(run):
    assert run([mk("f", "frequency", 3)], "thalatha marrat")["f"].status == U
    assert run([mk("f", "frequency", 3)], "marrat")["f"].status != W  # no count: never "once"
    assert run([mk("f", "frequency", 1)], "marra")["f"].status == U


def test_hindi_boond_is_a_drop(run):
    assert run([mk("d", "dose", 1, "drop")], "ek boond")["d"].status == U
