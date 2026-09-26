"""The targeted scripted run: selection, guards (plan only, credit-error stop), and the report's plausible-but-wrong list. Fake provider, tiny lexicon."""

import struct
import sys
from pathlib import Path

import pytest

pa = pytest.importorskip("pyarrow")
import pyarrow.parquet as pq  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent / "importers"))
import phone_scoring as ps  # noqa: E402
import scripted_eval as se  # noqa: E402
import word_align as wa  # noqa: E402
import word_eval as we  # noqa: E402

from providers import Provider, ProviderError, Transcript, Variant  # noqa: E402

LEX = {
    "the": [["DH", "AH0"]], "pit": [["P", "IH1", "T"]], "bit": [["B", "IH1", "T"]], "was": [["W", "AH1", "Z"]], "big": [["B", "IH1", "G"]],
    "bat": [["B", "AE1", "T"]], "pat": [["P", "AE1", "T"]], "gate": [["G", "EY1", "T"]],
}


def g2p(text):
    return "".join(ps.transcript_phones(text, LEX)[0])


def wav(seconds=1.0, rate=16000):
    data = b"\x00\x00" * int(seconds * rate)
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    return b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(data)) + data


ROWS = [  # (speaker, L1, text, heard g2p)
    ("aba", "Arabic", "the pit was big", g2p("the bit was big")),   # swap: pit -> bit
    ("aba", "Arabic", "the gate was big", g2p("the gate was big")),  # no accent word at all: not selected
    ("rrbi", "Hindi", "the pat was big", g2p("the bat was big")),   # swap: pat -> bat
    ("kk", "Korean", "the pit was big", g2p("the bit was big")),    # wrong L1: not selected
]


@pytest.fixture()
def parquet(tmp_path):
    pq.write_table(pa.table({
        "audio": [{"bytes": wav(1.0 + i / 10), "path": None} for i in range(len(ROWS))],
        "text": [r[2] for r in ROWS], "g2p": [g2p(r[2]) for r in ROWS], "ipa": [r[3] for r in ROWS],
        "speaker_code": [r[0] for r in ROWS], "speaker_gender": ["F"] * len(ROWS), "speaker_native_language": [r[1] for r in ROWS],
    }), tmp_path / "s.parquet")
    return tmp_path / "s.parquet"


@pytest.fixture()
def inv():
    return wa.inverse_lexicon(LEX)


def test_selection_keeps_only_arabic_hindi_utterances_with_a_real_word_swap(parquet, inv):
    clips = se.select(parquet, ("Arabic", "Hindi"), LEX, inv)
    assert [(c["id"], c["accent"]) for c in clips] == [("aba_0000", "Arabic"), ("rrbi_0002", "Hindi")]
    assert [v.swap_word for v in clips[0]["views"] if v.swap_word] == ["bit"]


class FakeSarvam(Provider):
    name = "sarvam"
    calls = 0
    answers: dict = {}
    fail_on: str | None = None

    def __init__(self, key=None):
        pass

    def available(self):
        return True

    def variants(self, spec=None):
        return [Variant("sarvam", "sarvam saaras:v3 / transcribe / en-IN", {})]

    def transcribe(self, audio, filename, variant):
        FakeSarvam.calls += 1
        stem = filename.removesuffix(".wav")
        if FakeSarvam.fail_on and stem in FakeSarvam.fail_on.split(","):
            raise ProviderError("HTTP 402: insufficient credits")
        return Transcript(FakeSarvam.answers[stem])


@pytest.fixture()
def env(tmp_path, monkeypatch, parquet):
    monkeypatch.setattr(se, "HERE", tmp_path)
    monkeypatch.setattr(se, "CLIPS_DIR", tmp_path / "recordings" / "l2arctic-scripted")
    monkeypatch.setattr(se, "Sarvam", FakeSarvam)
    monkeypatch.setattr(ps, "_dict", LEX)
    FakeSarvam.calls, FakeSarvam.fail_on = 0, None
    FakeSarvam.answers = {"aba_0000": "the pit was big", "rrbi_0002": "the bit was big"}
    return tmp_path


def test_plan_only_prints_the_cost_and_sends_nothing(env, parquet, capsys):
    assert se.main(["--file", str(parquet), "--out", str(env)]) == 0
    out = capsys.readouterr().out
    assert "2 scripted utterances with a real-word swap (Arabic=1, Hindi=1)" in out and "Estimated cost: INR" in out and "Plan only" in out
    assert FakeSarvam.calls == 0 and not (env / "recordings").exists() and not (env / "report_l2arctic_scripted.md").exists()


def test_a_full_run_classifies_and_lists_plausible_but_wrong_words(env, parquet):
    assert se.main(["--file", str(parquet), "--out", str(env), "--yes", "--sleep", "0"]) == 0
    report = (env / "report_l2arctic_scripted.md").read_text(encoding="utf-8")
    assert "DIRECTIONAL SIGNAL ONLY" in report
    assert "| scripted | Arabic | 1 | 0 | 1 | 0 | 0 | 0 |" in report  # pit: written as the intended word
    assert "| scripted | Hindi | 1 | 0 | 0 | 1 | 1 | 0 |" in report  # pat heard as bat; Sarvam wrote "bit": neither, but a real word
    assert "| rrbi_0002 | Hindi | pat | bat | **bit** | real-word swap |" in report
    assert "## Kept: Sarvam wrote the HEARD word" in report
    assert "Total: 1 of 2 accent words; 0 of them look like" in report
    assert (env / "results_l2arctic_scripted.json").exists()


def test_a_credit_looking_error_stops_the_run_at_once(env, parquet, capsys):
    FakeSarvam.fail_on = "aba_0000"
    assert se.main(["--file", str(parquet), "--out", str(env), "--yes", "--sleep", "0"]) == 3
    assert FakeSarvam.calls == 1  # the second utterance was never sent
    assert "RUN STOPPED EARLY" in (env / "report_l2arctic_scripted.md").read_text(encoding="utf-8")
    assert "STOPPED EARLY" in capsys.readouterr().out


def test_credit_error_detection():
    assert se.looks_like_credit_error("HTTP 402: insufficient credits") and se.looks_like_credit_error("Quota exceeded")
    assert not se.looks_like_credit_error("HTTP 429: Rate limit exceeded") and not se.looks_like_credit_error(None)


def test_classify_words_is_reused_for_the_outcomes(inv):
    v = wa.utterance_words("the pit was big", g2p("the pit was big"), g2p("the bit was big"), LEX, inv)
    assert [k for _, k, _ in we.classify_words(v, "the bit was big")] == [we.KEPT]
    assert se.is_real("pit", LEX) and not se.is_real("zzz", LEX) and not se.is_real(None, LEX)


def test_likely_variants_are_marked_but_different_words_are_not():
    for intended, wrote in (("gray", "grey"), ("shadows", "shadow"), ("picked", "pick"), ("twentieth", "th"), ("faces", "face")):
        assert se.likely_variant(intended, wrote), (intended, wrote)
    for intended, wrote in (("coal", "cold"), ("boat", "board"), ("the", "evidence"), ("river", "for")):
        assert not se.likely_variant(intended, wrote), (intended, wrote)
    assert not se.likely_variant("river", None)


def test_the_spontaneous_rows_are_not_duplicated(env, parquet, monkeypatch):
    monkeypatch.setattr(se, "spontaneous_summary", lambda lex, inv: {"Arabic": dict(n=1, kept=0, fixed=1, other=0, none=0, real=0),
                                                                     "all": dict(n=1, kept=0, fixed=1, other=0, none=0, real=0)})
    assert se.main(["--file", str(parquet), "--out", str(env), "--yes", "--sleep", "0"]) == 0
    report = (env / "report_l2arctic_scripted.md").read_text(encoding="utf-8")
    assert report.count("| spontaneous (earlier run) | all |") == 1
