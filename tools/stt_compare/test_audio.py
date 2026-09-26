"""WhatsApp voice notes (.ogg / .opus) and other formats: accepted as they are or converted. Uses real ffmpeg when it is installed."""

import subprocess
from pathlib import Path

import audio
import pytest

import run
from providers import Provider, ProviderError, Transcript, Variant, mime_for

needs_ffmpeg = pytest.mark.skipif(audio.ffmpeg() is None, reason="ffmpeg not installed")


def make_audio(path: Path, codec_args: list[str], seconds: float = 1.0) -> Path:
    subprocess.run([audio.ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", *codec_args, str(path)],
                   check=True, timeout=60)
    return path


def test_whatsapp_formats_are_accepted_without_conversion():
    for name in ("PTT-20260926-WA0001.ogg", "note.opus", "x.OGG", "clip.m4a", "a.mp3", "b.wav", "c.aac", "d.amr", "e.webm", "f.aiff"):
        assert audio.allowed_extension(name) and not audio.needs_conversion(name), name
    assert mime_for("PTT-1.ogg") == "audio/ogg" and mime_for("note.opus") == "audio/ogg" and mime_for("a.oga") == "audio/ogg"


def test_other_containers_are_accepted_but_converted():
    for name in ("voice.oga", "clip.3gp", "x.caf", "y.mka", "z.mov"):
        assert audio.allowed_extension(name) and audio.needs_conversion(name), name
    assert not audio.allowed_extension("notes.txt") and not audio.allowed_extension("photo.jpg")


@needs_ffmpeg
def test_an_opus_in_ogg_voice_note_is_sent_unchanged(tmp_path):
    src = make_audio(tmp_path / "PTT-20260926-WA0001.ogg", ["-c:a", "libopus", "-b:a", "16k"])
    name, data = audio.prepare(src, tmp_path / "converted")
    assert name == src.name and data == src.read_bytes() and data[:4] == b"OggS"
    assert not (tmp_path / "converted").exists()  # nothing was converted


@needs_ffmpeg
def test_an_unsupported_container_is_converted_to_16k_mono_wav(tmp_path):
    src = make_audio(tmp_path / "voice.oga", ["-c:a", "libopus"])
    name, data = audio.prepare(src, tmp_path / "converted")
    assert name == "voice.wav" and data[:4] == b"RIFF"
    assert src.exists() and src.read_bytes()[:4] == b"OggS"  # the original is untouched
    out = subprocess.run([audio.ffprobe(), "-v", "error", "-show_entries", "stream=sample_rate,channels", "-of", "csv=p=0",
                          str(next((tmp_path / "converted").glob("*.wav")))], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "16000,1"
    assert audio.prepare(src, tmp_path / "converted")[1] == data  # second call reuses the converted file


@needs_ffmpeg
def test_duration_is_measured(tmp_path):
    src = make_audio(tmp_path / "a.ogg", ["-c:a", "libopus"], seconds=2.0)
    assert audio.duration_seconds(src) == pytest.approx(2.0, abs=0.2)
    assert audio.duration_seconds(tmp_path / "missing.ogg") is None


def test_conversion_without_ffmpeg_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "ffmpeg", lambda: None)
    (tmp_path / "v.oga").write_bytes(b"OggS....")
    with pytest.raises(audio.AudioError, match="ffmpeg was not found"):
        audio.prepare(tmp_path / "v.oga", tmp_path / "c")


class Recorder(Provider):
    name = "rec"

    def __init__(self):
        self.sent = []

    def available(self):
        return True

    def variants(self, spec=None):
        return [Variant("rec", "rec / x", {})]

    def transcribe(self, audio_bytes, filename, variant):
        self.sent.append((filename, audio_bytes[:4]))
        if filename.endswith(".wav") and audio_bytes[:4] != b"RIFF":
            raise ProviderError("not wav")
        return Transcript("come to the parking")


@needs_ffmpeg
def test_a_run_over_whatsapp_and_odd_formats_end_to_end(tmp_path, monkeypatch):
    rec = tmp_path / "recordings"
    rec.mkdir()
    make_audio(rec / "PTT-1.ogg", ["-c:a", "libopus"])
    make_audio(rec / "note.opus", ["-c:a", "libopus", "-f", "ogg"])
    make_audio(rec / "old.oga", ["-c:a", "libopus"])
    (tmp_path / "truth.csv").write_text(
        "file,spoken_as_heard,intended_meaning,accent,notes\n"
        + "".join(f"{n},come to the parking,come to the parking,ar,\n" for n in ("PTT-1.ogg", "note.opus", "old.oga")), encoding="utf-8")
    prov = Recorder()
    monkeypatch.setitem(run.PROVIDERS, "sarvam", lambda: prov)
    monkeypatch.setattr(run, "HERE", tmp_path)
    assert run.main(["--truth", str(tmp_path / "truth.csv"), "--recordings", str(rec), "--yes", "--out", str(tmp_path), "--sleep", "0"]) == 0
    sent = dict(prov.sent)
    assert sent["PTT-1.ogg"] == b"OggS" and sent["note.opus"] == b"OggS"  # sent as they are
    assert sent["old.wav"] == b"RIFF"  # the .oga went through ffmpeg
    assert "_error" not in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_a_file_that_cannot_be_converted_is_an_error_row_not_a_crash(tmp_path, monkeypatch):
    rec = tmp_path / "recordings"
    rec.mkdir()
    (rec / "v.oga").write_bytes(b"OggS....")
    (tmp_path / "truth.csv").write_text("file,spoken_as_heard,intended_meaning,accent,notes\nv.oga,a b,a c,ar,\n", encoding="utf-8")
    monkeypatch.setattr(audio, "ffmpeg", lambda: None)
    monkeypatch.setitem(run.PROVIDERS, "sarvam", lambda: Recorder())
    monkeypatch.setattr(run, "HERE", tmp_path)
    assert run.main(["--truth", str(tmp_path / "truth.csv"), "--recordings", str(rec), "--yes", "--out", str(tmp_path), "--sleep", "0"]) == 0
    assert "ffmpeg was not found" in (tmp_path / "report.md").read_text(encoding="utf-8")
