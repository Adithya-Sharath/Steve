"""Tests for the STT reality-test tooling. No network, no audio: providers are fakes."""

import csv
import json
from pathlib import Path

import pytest

import providers
import run
from providers import Provider, ProviderError, Sarvam, Transcript, Variant
from report import build_report
from scoring import (
    FIXED,
    GARBLED,
    SURVIVED,
    Pair,
    accent_pairs,
    classify,
    normalize,
    score_file,
    summarise,
    wer,
)

# ---- scoring ---------------------------------------------------------------------------------------------------


def test_normalize_lowercases_and_drops_punctuation_but_keeps_contractions():
    assert normalize("Yalla, HABIBI! Don't come’s-now.") == ["yalla", "habibi", "don't", "come's", "now"]
    assert normalize("") == [] and normalize(None) == []


def test_wer():
    assert wer(["a", "b", "c", "d"], ["a", "x", "c", "d"]) == 0.25
    assert wer(["a"], []) == 1.0 and wer([], []) == 0.0 and wer([], ["x"]) == 1.0
    assert wer(normalize("come to the barking"), normalize("Come to the barking.")) == 0.0


def test_equal_length_replacements_pair_word_by_word():
    pairs = accent_pairs("yalla habibi come to the barking gate tree", "yalla habibi come to the parking gate three")
    assert pairs == [Pair("barking", "parking"), Pair("tree", "three")]


def test_unequal_replacements_become_one_phrase_pair():
    assert accent_pairs("yalla habibi come now", "come on my friend come now") == [Pair("yalla habibi", "come on my friend")]


def test_insertions_and_deletions_are_not_accent_evidence():
    assert accent_pairs("come to parking", "come to the parking") == []
    assert accent_pairs("come to the the parking", "come to the parking") == []


def test_a_correctly_spoken_control_has_no_pairs():
    assert accent_pairs("come to the parking now", "Come to the parking now.") == []


@pytest.mark.parametrize("hyp,expected", [
    ("come to the barking gate", SURVIVED),
    ("come to the parking gate", FIXED),
    ("come to the barkin gate", GARBLED),
    ("come to the barking and parking gate", SURVIVED),  # both present: the spoken form was kept
])
def test_classify_single_word(hyp, expected):
    assert classify(Pair("barking", "parking"), normalize(hyp)) == expected


def test_classify_phrase_needs_every_word():
    p = Pair("yalla habibi", "come on my friend")
    assert classify(p, normalize("yalla habibi come")) == SURVIVED
    assert classify(p, normalize("yalla come")) == GARBLED
    assert classify(p, normalize("come on my friend")) == FIXED


def test_classify_respects_word_counts():
    assert classify(Pair("same same", "the same"), normalize("same")) == GARBLED


def test_score_file_end_to_end():
    r = score_file("01", "ar", "v", "come to the barking gate tree", "come to the parking gate three", "come to the parking gate tree", 1.2)
    assert r.ref_len == 6 and r.edit_count == 1
    assert [(p.heard, k) for p, k in r.pairs] == [("barking", FIXED), ("tree", SURVIVED)]


def test_summary_counts_percentages_and_latency():
    rs = [
        score_file("1", "ar", "v", "come to the barking", "come to the parking", "come to the barking", 1.0),
        score_file("2", "ar", "v", "bring the bebsi", "bring the pepsi", "bring the pepsi", 3.0),
        score_file("3", "hi", "v", "wery good", "very good", "very good", 2.0),
        score_file("4", "hi", "other", "x y", "x y", "x y", 9.0),
    ]
    rs.append(type(rs[0])(file="5", accent="hi", variant="v", error="HTTP 500"))
    s = summarise(rs, "v")
    assert (s.files, s.errors, s.pairs, s.survived, s.fixed, s.garbled) == (3, 1, 3, 1, 2, 0)
    assert s.pct(s.fixed) == pytest.approx(66.666, abs=0.01)
    assert s.wer == pytest.approx(2 / 9)  # bebsi and wery: 2 edits over 4 + 3 + 2 reference words
    assert (s.latency_mean, s.latency_median) == (2.0, 2.0)


# ---- truth.csv -------------------------------------------------------------------------------------------------


def write_truth(tmp_path, rows, header=None):
    header = header or run.COLUMNS
    p = tmp_path / "truth.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return p


def test_load_truth_reports_problems_instead_of_crashing(tmp_path):
    rec = tmp_path / "rec"
    rec.mkdir()
    (rec / "01.mp3").write_bytes(b"x")
    (rec / "02.txt").write_bytes(b"x")
    (rec / "03.mp3").write_bytes(b"x")
    path = write_truth(tmp_path, [
        ["01.mp3", "come to the barking", "come to the parking", "ar", ""],
        ["01.mp3", "dup", "dup", "ar", ""],
        ["02.txt", "a", "b", "ar", ""],
        ["03.mp3", "", "come", "ar", ""],
        ["missing.mp3", "a", "b", "ar", ""],
        ["", "", "", "", ""],
    ])
    rows, problems = run.load_truth(path, rec)
    assert list(rows) == ["01.mp3"] and rows["01.mp3"]["spoken_as_heard"] == "come to the barking"
    text = "\n".join(problems)
    assert "listed twice" in text and "not a supported audio type" in text and "needs both" in text and "not found" in text


def test_load_truth_rejects_missing_columns(tmp_path):
    with pytest.raises(SystemExit, match="missing columns"):
        run.load_truth(write_truth(tmp_path, [], header=["file", "spoken_as_heard"]), tmp_path)


def test_a_blank_accent_becomes_unspecified(tmp_path):
    (tmp_path / "a.wav").write_bytes(b"x")
    rows, _ = run.load_truth(write_truth(tmp_path, [["a.wav", "x", "y", "", ""]]), tmp_path)
    assert rows["a.wav"]["accent"] == "unspecified"


# ---- providers and the CLI -------------------------------------------------------------------------------------


def test_sarvam_variant_specs():
    s = Sarvam(key="k")
    default = s.variants()
    assert len(default) == 6 and all(v.params["model"] in ("saaras:v3", "saaras:v4") for v in default)
    assert {v.params["mode"] for v in default} == {"transcribe", "verbatim", ""}
    quick = s.variants(Sarvam.QUICK_SPEC)
    assert [(v.params["mode"], v.params["language_code"]) for v in quick] == [("transcribe", "en-IN"), ("verbatim", "en-IN")]
    with pytest.raises(ProviderError):
        s.variants("saaras:v3:verbatim:en-IN")


def test_sarvam_sends_the_documented_fields_and_omits_an_empty_mode(monkeypatch):
    sent = {}

    class R:
        status_code = 200
        text = ""

        def json(self):
            return {"transcript": " come to the barking ", "language_code": "en-IN", "language_probability": None}

    def fake_post(url, headers=None, files=None, data=None, timeout=None):
        sent.update(url=url, headers=headers, files=files, data=data)
        return R()

    monkeypatch.setattr(providers.httpx, "post", fake_post)
    s = Sarvam(key="secret-key")
    out = s.transcribe(b"audio", "01.m4a", Variant("sarvam", "l", {"model": "saaras:v4", "mode": "", "language_code": "unknown"}))
    assert out.text == "come to the barking"
    assert sent["url"] == "https://api.sarvam.ai/speech-to-text" and sent["headers"] == {"api-subscription-key": "secret-key"}
    assert sent["data"] == {"model": "saaras:v4", "language_code": "unknown"}  # no `mode` for v4
    assert sent["files"]["file"][2] == "audio/mp4"
    s.transcribe(b"a", "x.mp3", Variant("sarvam", "l", {"model": "saaras:v3", "mode": "verbatim", "language_code": "en-IN"}))
    assert sent["data"]["mode"] == "verbatim"


def test_sarvam_errors_never_contain_the_key(monkeypatch):
    class R:
        status_code = 400
        text = "bad request for key secret-key"

    monkeypatch.setattr(providers.httpx, "post", lambda *a, **k: R())
    monkeypatch.setattr(providers.time, "sleep", lambda s: None)
    with pytest.raises(ProviderError) as e:
        Sarvam(key="secret-key").transcribe(b"a", "a.mp3", Variant("sarvam", "l", {"model": "saaras:v3", "mode": "", "language_code": "en-IN"}))
    assert "secret-key" not in str(e.value) and "HTTP 400" in str(e.value)


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, answers, fail=()):
        self.answers, self.fail, self.calls = answers, set(fail), 0

    def available(self):
        return True

    def variants(self, spec=None):
        return [Variant("fake", "fake / verbatim", {})]

    def transcribe(self, audio, filename, variant):
        self.calls += 1
        if filename in self.fail:
            raise ProviderError("HTTP 500")
        return Transcript(self.answers[filename])


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    rec = tmp_path / "recordings"
    rec.mkdir()
    for n in ("01.mp3", "02.mp3", "03.mp3"):
        (rec / n).write_bytes(n.encode())
    truth = write_truth(tmp_path, [
        ["01.mp3", "come to the barking gate tree", "come to the parking gate three", "ar", ""],
        ["02.mp3", "bring the bebsi", "bring the pepsi", "ar", ""],
        ["03.mp3", "wery good", "very good", "hi", "noisy"],
    ])
    monkeypatch.setattr(run, "HERE", tmp_path)
    return tmp_path, rec, truth


def _patch_provider(monkeypatch, prov):
    monkeypatch.setitem(run.PROVIDERS, "sarvam", lambda: prov)


def test_without_yes_nothing_is_sent(workspace, monkeypatch, capsys):
    tmp, rec, truth = workspace
    prov = FakeProvider({})
    _patch_provider(monkeypatch, prov)
    assert run.main(["--truth", str(truth), "--recordings", str(rec), "--out", str(tmp)]) == 0
    assert prov.calls == 0 and "Plan only" in capsys.readouterr().out
    assert not (tmp / "report.md").exists()


def test_a_provider_without_a_key_is_skipped(workspace, monkeypatch, capsys):
    tmp, rec, truth = workspace
    prov = FakeProvider({})
    prov.available = lambda: False
    _patch_provider(monkeypatch, prov)
    assert run.main(["--truth", str(truth), "--recordings", str(rec), "--yes", "--out", str(tmp)]) == 1
    assert "no API key" in capsys.readouterr().out and prov.calls == 0


def test_full_run_writes_report_and_results_and_caches(workspace, monkeypatch):
    tmp, rec, truth = workspace
    prov = FakeProvider({"01.mp3": "come to the barking gate three", "02.mp3": "bring the pepsi", "03.mp3": "wery good"}, fail=())
    _patch_provider(monkeypatch, prov)
    args = ["--truth", str(truth), "--recordings", str(rec), "--yes", "--out", str(tmp), "--sleep", "0"]
    assert run.main(args) == 0 and prov.calls == 3
    report = (tmp / "report.md").read_text(encoding="utf-8")
    assert "fake / verbatim" in report and "Kept as spoken" in report
    results = json.loads((tmp / "results.json").read_text(encoding="utf-8"))
    assert len(results) == 3 and not any(r["error"] for r in results)
    # kept: barking, wery; fixed: tree->three, bebsi->pepsi
    assert "| 4 |" in report and "50% (2)" in report
    assert run.main(args) == 0 and prov.calls == 3  # second run: every answer came from the cache


def test_one_failing_file_does_not_stop_the_run(workspace, monkeypatch):
    tmp, rec, truth = workspace
    prov = FakeProvider({"01.mp3": "come to the barking gate tree", "03.mp3": "very good"}, fail={"02.mp3"})
    _patch_provider(monkeypatch, prov)
    assert run.main(["--truth", str(truth), "--recordings", str(rec), "--yes", "--out", str(tmp), "--sleep", "0"]) == 0
    report = (tmp / "report.md").read_text(encoding="utf-8")
    assert "_error: HTTP 500_" in report
    assert "| fake / verbatim | 2 | 1 |" in report  # summary row: 2 files ok, 1 error


def test_empty_truth_is_a_friendly_message_not_a_crash(tmp_path, capsys):
    (tmp_path / "recordings").mkdir()
    truth = write_truth(tmp_path, [])
    assert run.main(["--truth", str(truth), "--recordings", str(tmp_path / "recordings"), "--out", str(tmp_path)]) == 1
    assert "No usable rows" in capsys.readouterr().out


def test_report_is_dignified_and_lists_caveats():
    r = score_file("01.mp3", "ar", "v", "come to the barking", "come to the parking", "come to the parking", 1.0)
    text = build_report([r], ["v"], {"01.mp3": {"accent": "ar", "spoken_as_heard": "come to the barking",
                                                "intended_meaning": "come to the parking", "notes": ""}}, ["a note"])
    for phrase in ("Caveats", "Every recording", "a note", "fixed"):
        assert phrase in text.replace('"', "")
    for bad in ("bad english", "incorrect english", "wrong accent", "poor accent"):
        assert bad not in text.lower()


def test_the_gitignore_keeps_audio_and_transcripts_out_of_git():
    root = Path(__file__).resolve().parents[2]
    ignore = (root / ".gitignore").read_text(encoding="utf-8")
    for line in ("tools/**/recordings/", "tools/**/*.mp3", "tools/**/*.m4a", "tools/**/*.wav", "tools/stt_compare/.cache/",
                 "tools/stt_compare/report.md", "tools/stt_compare/results.json"):
        assert line in ignore, line
