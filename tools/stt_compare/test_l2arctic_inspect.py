"""Tests for the L2-ARCTIC spontaneous importer's `inspect` step. A tiny synthetic parquet stands in for the gated dataset:
no network, no token, no real audio."""

import io
import struct
import sys
from pathlib import Path

import pytest

pa = pytest.importorskip("pyarrow")
import pyarrow.parquet as pq  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent / "importers"))
import l2arctic_spontaneous as l2  # noqa: E402


def wav(seconds: float, rate: int = 16000, float32: bool = True) -> bytes:
    n = int(seconds * rate)
    fmt, bits = (3, 32) if float32 else (1, 16)
    block = bits // 8
    data = b"\x00" * (n * block)
    fmt_chunk = struct.pack("<HHIIHH", fmt, 1, rate, rate * block, block, bits)
    return (b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt_chunk) + 8 + len(data)) + b"WAVE" + b"fmt " + struct.pack("<I", len(fmt_chunk))
            + fmt_chunk + b"data" + struct.pack("<I", len(data)) + data)


def make_parquet(path: Path, rows: list[dict], extra: dict | None = None) -> Path:
    cols = {
        "audio": [{"bytes": r["wav"], "path": None} for r in rows],
        "ipa": [r.get("ipa", "ðə sˈuːtkeɪs") for r in rows],
        "g2p": [r.get("g2p", "ðə sˈuːtkeɪs") for r in rows],
        "speaker_code": [r["spk"] for r in rows],
        "speaker_gender": [r.get("gender", "F") for r in rows],
        "speaker_native_language": [r["l1"] for r in rows],
    }
    cols.update(extra or {})
    pq.write_table(pa.table(cols), path)
    return path


ROWS = [
    {"wav": wav(10.0), "spk": "A1", "l1": "Arabic"},
    {"wav": wav(12.5), "spk": "A1", "l1": "Arabic"},
    {"wav": wav(11.0), "spk": "A2", "l1": "Arabic"},
    {"wav": wav(10.5), "spk": "H1", "l1": "Hindi"},
    {"wav": wav(12.0), "spk": "V1", "l1": "Vietnamese"},
]


def test_wav_duration_for_float32_and_pcm16():
    assert l2.wav_seconds(wav(10.0)) == pytest.approx(10.0)
    assert l2.wav_seconds(wav(2.5, float32=False)) == pytest.approx(2.5)
    assert l2.wav_seconds(b"not a wav file at all, just bytes" * 5) is None
    assert l2.wav_seconds(b"") is None


def test_inspect_reports_columns_counts_and_usage(tmp_path):
    out = io.StringIO()
    info = l2.inspect(make_parquet(tmp_path / "t.parquet", ROWS), out=out)
    text = out.getvalue()
    assert "audio:" in text and "speaker_native_language:" in text and "Rows: 5" in text
    assert "NONE found" in text  # only ipa / g2p / speaker fields: no English word transcript
    assert "| Arabic | spontaneous | 3 | 2 | 0.6 |" in text  # 33.5 s
    assert "| Hindi | spontaneous | 1 | 1 | 0.2 |" in text  # 10.5 s
    assert "Vietnamese" in text.split("Selected:")[0]  # counted overall ...
    assert "Vietnamese" not in text.split("Selected:")[1]  # ... but not selected
    assert "Total selected: 4 clips" in text
    assert "--quick: 4 x 2 = 8 calls" in text and "default matrix: 4 x 6 = 24 calls" in text
    assert info["clips"] == 4 and info["word_columns"] == []


def test_the_l1_filter_is_case_insensitive_and_configurable(tmp_path):
    out = io.StringIO()
    info = l2.inspect(make_parquet(tmp_path / "t.parquet", ROWS), ("hindi", "vietnamese"), out=out)
    assert info["clips"] == 2


def test_a_word_transcript_column_is_detected(tmp_path):
    extra = {"text": ["he took the suitcase to the station"] * len(ROWS)}
    out = io.StringIO()
    info = l2.inspect(make_parquet(tmp_path / "t.parquet", ROWS, extra), out=out)
    assert info["word_columns"] == ["text"] and "column: text" in out.getvalue()


def test_ipa_strings_are_not_mistaken_for_a_transcript(tmp_path):
    rows = [{**r, "ipa": "ðɪs ɪz ɐ sˈuːtkeɪs stˈoːɹi ɪn aɪpiːeɪ"} for r in ROWS]
    assert l2.inspect(make_parquet(tmp_path / "t.parquet", rows), out=io.StringIO())["word_columns"] == []


def test_a_split_column_is_used_when_the_file_has_one(tmp_path):
    extra = {"split": ["scripted", "spontaneous", "spontaneous", "scripted", "scripted"]}
    out = io.StringIO()
    l2.inspect(make_parquet(tmp_path / "t.parquet", ROWS, extra), out=out)
    text = out.getvalue()
    assert "| Arabic | scripted | 1 |" in text and "| Arabic | spontaneous | 2 |" in text and "| Hindi | scripted | 1 |" in text


def test_without_a_split_column_it_says_so(tmp_path):
    out = io.StringIO()
    l2.inspect(make_parquet(tmp_path / "t.parquet", ROWS), out=out)
    assert "no split/subset column" in out.getvalue()


def test_gated_access_gives_instructions_and_never_the_token(monkeypatch, capsys):
    def gated(*a, **k):
        raise l2.GatedAccess("Access to the dataset is gated and this token has no access yet. Accept the terms.")

    monkeypatch.setattr(l2, "download", gated)
    monkeypatch.setattr(l2, "hf_token", lambda: "hf_SECRETTOKEN123")
    assert l2.main(["inspect"]) == 2
    out = capsys.readouterr()
    assert "gated" in out.out and "hf_SECRETTOKEN123" not in out.out + out.err


def test_missing_token_is_a_clear_message(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    with pytest.raises(SystemExit, match="HF_TOKEN is not set"):
        l2.hf_token()


def test_the_local_file_option_works_without_a_token(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    p = make_parquet(tmp_path / "t.parquet", ROWS)
    assert l2.main(["inspect", "--file", str(p)]) == 0
    assert "Total selected: 4 clips" in capsys.readouterr().out
