"""The exact cases required by the build brief (§4.6)."""

from conftest import C, M, N, U, W, cond, mk, statuses


def test_manglish_oru_week_is_wrong_duration(rx_facts, run):
    res = run(rx_facts[:4], "randu gulika, food kazhinju, raavile vaikittu, oru week")
    st = statuses(res)
    assert st == {"dose": U, "timing": U, "freq": U, "dur": W}
    assert res["dur"].heard_value == 7
    assert res["dur"].expected_value == 5
    assert "7 days" in res["dur"].reason and "5 days" in res["dur"].reason
    assert "oru week" in res["dur"].reason


def test_hinglish_all_understood(rx_facts, run):
    res = run(rx_facts[:4], "do goli khane ke baad subah shaam paanch din")
    assert set(statuses(res).values()) == {U}


def test_taglish_linker_ng_all_understood(rx_facts, run):
    res = run(rx_facts[:4], "dalawang tableta pagkatapos kumain, dalawang beses, limang araw")
    assert set(statuses(res).values()) == {U}


def test_arabizi_all_understood(rx_facts, run):
    res = run(rx_facts[:4], "ithnain habba ba3d al akl marratain 5 ayyam")
    assert set(statuses(res).values()) == {U}


def test_condition_understood(run):
    res = run([cond("rash", "rash", "stop")], "rash vannal nirthanam")
    assert res["rash"].status == U


def test_condition_negated_fused_word(run):
    res = run([cond("rash", "rash", "stop")], "rash vannalum nirthanda")
    assert res["rash"].status == N


def test_condition_missing_when_not_mentioned(run):
    res = run([cond("rash", "rash", "stop")], "randu gulika food kazhinju")
    assert res["rash"].status == M


def test_low_evidence_reply_never_understood(rx_facts, run):
    res = run(rx_facts, "ok ok sheri")
    assert all(r.status in (M, C) for r in res.values())


def test_low_evidence_variants_never_understood(rx_facts, run):
    for reply in ["ok", "👍", "okay okay", "theek hai", "sheri sheri", "haan ji", "", "   ", "ok sir noted", "understood"]:
        res = run(rx_facts, reply)
        assert all(r.status in (M, C) for r in res.values()), reply


def test_spelling_variants_two(run):
    for w in ["rendu", "randu", "rndu", "RANDU", "Rendu"]:
        r = run([mk("d", "dose", 2, "tablet")], f"{w} gulika")
        assert r["d"].status == U, w


def test_spelling_variants_five(run):
    for w in ["paanch", "panch", "paach", "PAANCH"]:
        r = run([mk("d", "duration", 5, "day")], f"{w} din")
        assert r["d"].status == U, w


def test_spelling_variants_four_arabizi(run):
    for w in ["arba3a", "arbaa", "arb3a"]:
        r = run([mk("d", "duration", 4, "day")], f"{w} ayyam")
        assert r["d"].status == U, w


def test_evidence_spans_point_at_original_text(rx_facts, run):
    reply = "RanDu gulika 😊 food KAZHINJU, raavile vaikittu, oru week"
    res = run(rx_facts[:4], reply)
    for r in res.values():
        assert r.evidence, r.fact_id
        for s in r.evidence:
            assert reply[s.start : s.end] == s.text
    assert res["dose"].evidence[0].text == "RanDu gulika"
    assert any("KAZHINJU" in s.text for s in res["timing"].evidence)
    assert res["dur"].evidence[0].text == "oru week"
