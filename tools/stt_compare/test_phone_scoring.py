"""Phone-level kept / fixed / garbled scoring and the L2-ARCTIC phone evaluation runner (fake provider, tiny dictionary, synthetic parquet)."""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "importers"))
import phone_eval  # noqa: E402
import phone_scoring as ps  # noqa: E402

from providers import Provider, ProviderError, Transcript, Variant  # noqa: E402

LEX = {
    "come": [["K", "AH1", "M"]], "to": [["T", "UW1"]], "the": [["DH", "AH0"]],
    "parking": [["P", "AA1", "R", "K", "IH0", "NG"]], "barking": [["B", "AA1", "R", "K", "IH0", "NG"]],
    "marking": [["M", "AA1", "R", "K", "IH0", "NG"]], "gate": [["G", "EY1", "T"]],
}
SENTENCE = "come to the parking gate"


def canonical() -> str:
    return "".join(ps.transcript_phones(SENTENCE, LEX)[0])


def perceived(replace=("p", "b")) -> str:
    return canonical().replace(*replace)


def test_words_become_phones_with_dictionary_coverage():
    t, found, total = ps.transcript_phones("Come to the PARKING, zzzz gate!", LEX)
    assert (found, total) == (5, 6)
    assert t[:3] == ["k", "ʌ", "m"] and "eɪ" in t and t.count("p") == 1


def test_a_phone_the_transcript_kept_is_kept():
    s = ps.score_clip("Arabic", "v", canonical(), perceived(), "come to the barking gate", LEX)
    assert [(c, p, got, k) for c, p, got, k in s.accent_positions] == [("p", "b", "b", ps.KEPT)]
    assert s.per_vs_perceived == 0.0 and s.per_vs_canonical > 0


def test_a_phone_the_transcript_corrected_is_fixed():
    s = ps.score_clip("Arabic", "v", canonical(), perceived(), "come to the parking gate", LEX)
    assert [k for *_, k in s.accent_positions] == [ps.FIXED]
    assert s.per_vs_canonical == 0.0


def test_something_else_is_garbled():
    s = ps.score_clip("Arabic", "v", canonical(), perceived(), "come to the marking gate", LEX)
    assert [(got, k) for *_, got, k in s.accent_positions] == [("m", ps.GARBLED)]


def test_a_dropped_word_has_no_counterpart():
    s = ps.score_clip("Arabic", "v", canonical(), perceived(), "come to the gate", LEX)
    assert [k for *_, k in s.accent_positions] in ([ps.NONE], [ps.GARBLED])  # the aligner may line "p" up with a neighbour


def test_an_empty_or_unknown_transcript_scores_nothing():
    for text in ("", "zzz qqq"):
        s = ps.score_clip("Arabic", "v", canonical(), perceived(), text, LEX)
        assert s.accent_positions == [] and s.per_vs_canonical is None


def test_tally_percentages_use_classified_positions_only():
    scores = [ps.score_clip("Arabic", "v", canonical(), perceived(), t, LEX)
              for t in ("come to the barking gate", "come to the parking gate", "come to the barking gate", "come to the gate")]
    t = ps.tally(scores)
    assert t.clips == 4 and t.kinds[ps.KEPT] == 2 and t.kinds[ps.FIXED] == 1
    assert t.pct(ps.KEPT) == pytest.approx(100 * 2 / t.classified())
    assert ps.by_pair(scores)[("p", "b")][ps.KEPT] == 2


def test_the_arpabet_table_covers_every_cmudict_phone():
    import cmudict

    used = {p.rstrip("012") for prons in cmudict.dict().values() for pron in prons for p in pron}
    assert used <= set(ps.ARPA_TO_IPA), used - set(ps.ARPA_TO_IPA)


# ---- the runner ------------------------------------------------------------------------------------------------


def wav_bytes(seconds=1.0, rate=16000):
    data = b"\x00\x00" * int(seconds * rate)
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    return b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(data)) + data


@pytest.fixture()
def parquet(tmp_path):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    rows = [("aba", "Arabic"), ("aba", "Arabic"), ("rrbi", "Hindi"), ("kk", "Korean")]
    pq.write_table(pa.table({
        "audio": [{"bytes": wav_bytes(1.0 + i / 10), "path": None} for i, _ in enumerate(rows)],  # distinct bytes: the cache keys on audio
        "ipa": [perceived()] * 4, "g2p": [canonical()] * 4,
        "speaker_code": [r[0] for r in rows], "speaker_gender": ["F"] * 4, "speaker_native_language": [r[1] for r in rows],
    }), tmp_path / "t.parquet")
    return tmp_path / "t.parquet"


class FakeSarvam(Provider):
    name = "sarvam"
    calls = 0

    def __init__(self, key=None):
        pass

    def available(self):
        return True

    def variants(self, spec=None):
        return [Variant("sarvam", "sarvam v3 / transcribe / en-IN", {}), Variant("sarvam", "sarvam v3 / verbatim / en-IN", {})]

    def transcribe(self, audio, filename, variant):
        FakeSarvam.calls += 1
        if filename.startswith("rrbi") and "verbatim" in variant.label:
            raise ProviderError("HTTP 500")
        return Transcript("come to the barking gate" if "verbatim" in variant.label else "come to the parking gate")


@pytest.fixture()
def env(tmp_path, monkeypatch, parquet):
    monkeypatch.setattr(phone_eval, "HERE", tmp_path)
    monkeypatch.setattr(phone_eval, "CLIPS_DIR", tmp_path / "recordings" / "l2arctic-spont")
    monkeypatch.setattr(phone_eval, "Sarvam", FakeSarvam)
    monkeypatch.setattr(ps, "_dict", LEX)
    FakeSarvam.calls = 0
    return tmp_path


def test_load_clips_keeps_only_the_chosen_accents_and_names_them(parquet):
    clips = phone_eval.load_clips(parquet, ("Arabic", "Hindi"))
    assert [c["id"] for c in clips] == ["aba_01", "aba_02", "rrbi_01"] and {c["accent"] for c in clips} == {"Arabic", "Hindi"}


def test_plan_only_sends_nothing_and_writes_nothing(env, parquet, capsys):
    assert phone_eval.main(["--file", str(parquet), "--out", str(env)]) == 0
    out = capsys.readouterr().out
    assert "3 clips (Arabic=2, Hindi=1) x 2 variants = 6 Sarvam calls" in out and "Plan only" in out
    assert FakeSarvam.calls == 0 and not (env / "recordings").exists() and not (env / "report_l2arctic_spont.md").exists()


def test_full_run_writes_wavs_report_and_reuses_the_cache(env, parquet):
    args = ["--file", str(parquet), "--out", str(env), "--yes", "--sleep", "0"]
    assert phone_eval.main(args) == 0
    assert sorted(p.name for p in (env / "recordings" / "l2arctic-spont").glob("*.wav")) == ["aba_01.wav", "aba_02.wav", "rrbi_01.wav"]
    report = (env / "report_l2arctic_spont.md").read_text(encoding="utf-8")
    assert "DIRECTIONAL SIGNAL ONLY" in report and "Arabic" in report and "p -> b" in report
    row = next(r for r in report.splitlines() if r.startswith("| Arabic | sarvam v3 / verbatim"))
    assert "| 2 | 2 | 100% (2) | 0% (0) |" in row  # 2 clips, 2 accent positions, both kept
    row = next(r for r in report.splitlines() if r.startswith("| Arabic | sarvam v3 / transcribe"))
    assert "0% (0) | 100% (2) |" in row  # both fixed
    assert "1 failed calls" in report  # the Hindi verbatim call errored
    first = FakeSarvam.calls
    assert phone_eval.main(args) == 0 and FakeSarvam.calls == first + 1  # only the failed one was retried; the rest came from the cache
    assert (env / "results_l2arctic_spont.json").exists()


def test_gitignore_keeps_the_derived_files_out_of_git():
    ignore = (Path(__file__).resolve().parents[2] / ".gitignore").read_text(encoding="utf-8")
    for line in ("tools/stt_compare/report_*.md", "tools/stt_compare/results_*.json"):
        assert line in ignore
