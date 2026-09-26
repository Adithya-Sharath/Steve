"""WhatsApp-like degradation (noise at a set SNR, phone-quality Opus) and the noisy scripted run. Real ffmpeg, synthetic noise, fake provider."""

import struct
import sys
import zipfile
from pathlib import Path

import audio
import numpy as np
import pytest
import whatsapp_sim as ws

needs_ffmpeg = pytest.mark.skipif(audio.ffmpeg() is None, reason="ffmpeg not installed")
RNG = np.random.default_rng(7)


def tone(seconds=2.0, freq=300.0, amp=0.3):
    t = np.arange(int(seconds * ws.SAMPLE_RATE)) / ws.SAMPLE_RATE
    return (amp * np.sin(2 * np.pi * freq * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))).astype("float32")  # speech-like envelope


def wav_bytes(x: np.ndarray) -> bytes:
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    fmt = struct.pack("<HHIIHH", 1, 1, ws.SAMPLE_RATE, ws.SAMPLE_RATE * 2, 2, 16)
    return b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(pcm)) + pcm


def snr(speech, mixed):
    return 20 * np.log10(ws.rms(speech) / ws.rms(mixed - speech))


@pytest.mark.parametrize("target", [15.0, 10.0, 5.0, 0.0])
def test_the_mix_has_exactly_the_requested_snr(target):
    speech, noise = tone(), RNG.normal(0, 0.05, 5 * ws.SAMPLE_RATE).astype("float32")
    assert snr(speech, ws.mix_at_snr(speech, noise, target, 123)) == pytest.approx(target, abs=0.05)


def test_a_loud_mix_is_limited_not_clipped():
    speech, noise = tone(amp=0.95), RNG.normal(0, 0.9, 3 * ws.SAMPLE_RATE).astype("float32")
    assert float(np.max(np.abs(ws.mix_at_snr(speech, noise, 0.0)))) <= 0.971


def test_a_short_noise_is_tiled_and_silence_is_left_alone():
    speech = tone(3.0)
    assert len(ws.mix_at_snr(speech, RNG.normal(0, 0.05, 1000).astype("float32"), 10.0)) == len(speech)
    assert np.array_equal(ws.mix_at_snr(speech, np.zeros(50_000, "float32"), 10.0), speech)
    assert np.array_equal(ws.mix_at_snr(np.zeros(1000, "float32"), tone(), 10.0), np.zeros(1000, "float32"))


def test_the_offset_is_stable_per_key_and_differs_between_keys():
    assert ws.stable_int("p", "aba_0001") == ws.stable_int("p", "aba_0001") != ws.stable_int("p", "aba_0002")


@needs_ffmpeg
def test_a_degraded_clip_is_a_small_opus_in_ogg_file_of_the_same_length():
    speech, noise = tone(2.0), RNG.normal(0, 0.05, 5 * ws.SAMPLE_RATE).astype("float32")
    data = ws.degrade(wav_bytes(speech), noise, ws.PROFILES["whatsapp-snr10"], "clip1")
    assert data[:4] == b"OggS" and b"OpusHead" in data[:100]
    assert 1500 < len(data) < 8000  # about 16 kbps: roughly 2 KB per second, not the 64 KB of the WAV
    assert len(ws.decode(data)) / ws.SAMPLE_RATE == pytest.approx(2.0, abs=0.3)


@needs_ffmpeg
def test_phone_quality_removes_the_high_frequencies():
    t = np.arange(2 * ws.SAMPLE_RATE) / ws.SAMPLE_RATE
    high = (0.3 * np.sin(2 * np.pi * 6000 * t)).astype("float32")  # above the 4 kHz limit of 8 kHz sampling
    out = ws.decode(ws.encode_opus(high, 8000, "16k"))
    assert ws.rms(out) < 0.15 * ws.rms(high)


@needs_ffmpeg
def test_noise_loads_from_a_demand_style_zip(tmp_path):
    x = RNG.normal(0, 0.1, 2 * ws.SAMPLE_RATE).astype("float32")
    with zipfile.ZipFile(tmp_path / "STRAFFIC_16k.zip", "w") as z:
        z.writestr("STRAFFIC/ch02.wav", wav_bytes(x * 0))
        z.writestr("STRAFFIC/ch01.wav", wav_bytes(x))
    got = ws.load_noise("STRAFFIC", tmp_path)
    assert len(got) == len(x) and ws.rms(got) == pytest.approx(ws.rms(x), rel=0.05)  # channel 1, not channel 2
    with pytest.raises(ws.SimError, match="not found"):
        ws.load_noise("TBUS", tmp_path)


def test_noise_types_rotate_across_clips():
    p = ws.PROFILES["whatsapp-snr10"]
    noises = {n: np.zeros(10, "float32") for n in p.noises}
    assert [ws.noise_for(p, i, noises)[0] for i in range(4)] == ["STRAFFIC", "PSTATION", "TBUS", "STRAFFIC"]


def test_profiles_and_licence_are_recorded():
    assert {"whatsapp-snr15", "whatsapp-snr10", "whatsapp-snr5"} <= set(ws.PROFILES)
    assert ws.PROFILES["whatsapp-snr10"].bitrate == "16k" and ws.PROFILES["whatsapp-snr10"].phone_rate == 8000
    assert "CC BY 4.0" in ws.__doc__ and "1227121" in ws.__doc__
    assert "tools/stt_compare/.cache/" in (Path(__file__).resolve().parents[2] / ".gitignore").read_text(encoding="utf-8")


def test_fetch_skips_files_that_are_already_there(tmp_path, monkeypatch, capsys):
    for n in ws.NOISE_SETS:
        (tmp_path / f"{n}_16k.zip").write_bytes(b"x" * 10_000_001)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: pytest.fail("must not download"))
    ws.fetch(tmp_path)
    assert capsys.readouterr().out.count("have ") == 3


# ---- the noisy scripted run ----------------------------------------------------------------------------------------

pa = pytest.importorskip("pyarrow")
import pyarrow.parquet as pq  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent / "importers"))
import phone_scoring as ps  # noqa: E402
import scripted_eval as se  # noqa: E402

from providers import Provider, Transcript, Variant  # noqa: E402

LEX = {"the": [["DH", "AH0"]], "pit": [["P", "IH1", "T"]], "bit": [["B", "IH1", "T"]], "was": [["W", "AH1", "Z"]], "big": [["B", "IH1", "G"]]}


def g2p(text):
    return "".join(ps.transcript_phones(text, LEX)[0])


class Sarvam(Provider):
    name = "sarvam"
    sent: list = []

    def __init__(self, key=None):
        pass

    def available(self):
        return True

    def variants(self, spec=None):
        return [Variant("sarvam", "sarvam saaras:v3 / transcribe / en-IN", {})]

    def transcribe(self, audio_bytes, filename, variant):
        Sarvam.sent.append((filename, audio_bytes[:4]))
        return Transcript("the bit was big" if filename.startswith("aba") else "")


@needs_ffmpeg
def test_a_noisy_run_sends_ogg_files_reuses_them_and_compares_with_the_clean_run(tmp_path, monkeypatch):
    rows = [("aba", "Arabic", "the pit was big", g2p("the bit was big")), ("rrbi", "Hindi", "the pit was big", g2p("the bit was big"))]
    pq.write_table(pa.table({
        "audio": [{"bytes": wav_bytes(tone(1.0 + i / 10)), "path": None} for i in range(2)], "text": [r[2] for r in rows],
        "g2p": [g2p(r[2]) for r in rows], "ipa": [r[3] for r in rows], "speaker_code": [r[0] for r in rows],
        "speaker_gender": ["F", "F"], "speaker_native_language": [r[1] for r in rows],
    }), tmp_path / "s.parquet")
    monkeypatch.setattr(se, "HERE", tmp_path)
    monkeypatch.setattr(se, "CLIPS_DIR", tmp_path / "recordings" / "l2arctic-scripted")
    monkeypatch.setattr(se, "Sarvam", Sarvam)
    monkeypatch.setattr(ps, "_dict", LEX)
    monkeypatch.setattr(ws, "load_noise", lambda name, cache=None: RNG.normal(0, 0.05, 3 * ws.SAMPLE_RATE).astype("float32"))
    Sarvam.sent = []
    base = ["--file", str(tmp_path / "s.parquet"), "--out", str(tmp_path), "--sleep", "0", "--yes"]
    assert se.main(base) == 0  # the clean run first, as the comparison needs it
    assert se.main([*base, "--profile", "whatsapp-snr10"]) == 0
    noisy = [(n, magic) for n, magic in Sarvam.sent if n.endswith(".ogg")]
    assert [n for n, _ in noisy] == ["aba_0000.ogg", "rrbi_0001.ogg"] and all(m == b"OggS" for _, m in noisy)
    folder = tmp_path / "recordings" / "l2arctic-scripted-whatsapp-snr10"
    assert sorted(p.name for p in folder.glob("*.ogg")) == ["aba_0000.ogg", "rrbi_0001.ogg"]
    report = (tmp_path / "report_l2arctic_scripted_whatsapp_snr10.md").read_text(encoding="utf-8")
    assert "(whatsapp-snr10)" in report and "## Clean vs WhatsApp-like" in report
    assert "| clean | Arabic | 1 | 1 (100.0%) | 0 (0.0%) |" in report  # the fake wrote the heard word "bit"
    assert "| whatsapp-snr10 | Hindi | 1 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 | 1 |" in report  # the fake answers nothing for Hindi: not aligned
    assert "Empty transcripts" in report
    before = len(Sarvam.sent)
    assert se.main([*base, "--profile", "whatsapp-snr10"]) == 0 and len(Sarvam.sent) == before  # files and answers reused: no new calls


def test_plan_only_for_a_profile_needs_no_noise_and_sends_nothing(tmp_path, monkeypatch, capsys):
    rows = [("aba", "Arabic", "the pit was big", g2p("the bit was big"))]
    pq.write_table(pa.table({
        "audio": [{"bytes": wav_bytes(tone(1.0)), "path": None}], "text": [rows[0][2]], "g2p": [g2p(rows[0][2])], "ipa": [rows[0][3]],
        "speaker_code": ["aba"], "speaker_gender": ["F"], "speaker_native_language": ["Arabic"],
    }), tmp_path / "s.parquet")
    monkeypatch.setattr(se, "Sarvam", Sarvam)
    monkeypatch.setattr(ps, "_dict", LEX)
    monkeypatch.setattr(ws, "load_noise", lambda *a, **k: pytest.fail("plan only must not load noise"))
    Sarvam.sent = []
    assert se.main(["--file", str(tmp_path / "s.parquet"), "--out", str(tmp_path), "--profile", "whatsapp-snr5"]) == 0
    out = capsys.readouterr().out
    assert "Condition: whatsapp-snr5" in out and "5 dB SNR" in out and "Plan only" in out and Sarvam.sent == []

