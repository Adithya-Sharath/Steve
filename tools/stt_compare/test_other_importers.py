"""Svarah and Speech Accent Archive importers (inspect only): synthetic data, no network, no token."""

import io
import sys
from pathlib import Path

import pytest

pa = pytest.importorskip("pyarrow")
import pyarrow.parquet as pq  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent / "importers"))
import speech_accent_archive as saa  # noqa: E402
import svarah  # noqa: E402

# ---- Svarah ----------------------------------------------------------------------------------------------------


def svarah_file(path: Path, rows: list[tuple]) -> Path:
    pq.write_table(pa.table({
        "audio_filepath": [b"x" for _ in rows], "duration": [r[0] for r in rows], "text": ["a b c"] * len(rows),
        "gender": ["female"] * len(rows), "age-group": ["18-30"] * len(rows), "primary_language": [r[1] for r in rows],
        "native_place_state": [r[2] for r in rows],
    }), path)
    return path


SV_ROWS = [(4.0, "Hindi", "Bihar"), (6.0, "Hindi", "Delhi"), (35.0, "Hindi", "Delhi"), (5.0, "Malayalam", "Kerala"), (7.0, "Tamil", "Tamil Nadu")]


def test_svarah_inspect_counts_hours_and_estimates(tmp_path):
    out = io.StringIO()
    info = svarah.inspect(pq.ParquetFile(svarah_file(tmp_path / "s.parquet", SV_ROWS)), ("Hindi", "Malayalam"), out)
    text = out.getvalue()
    assert "Rows: 5" in text and "`text`: present" in text and "Phone-level annotation: none" in text
    assert "| Hindi | 3 | 0.8 | 1 |" in text  # 45 s, one clip over 30 s
    assert "| Malayalam | 1 |" in text and "Tamil" not in text.split("Selected languages")[1]
    assert "--quick: 4 x 2 = 8 calls" in text and "default matrix: 4 x 6 = 24 calls" in text
    assert info["clips"] == 4


def test_svarah_without_a_language_filter_keeps_everything(tmp_path):
    out = io.StringIO()
    assert svarah.inspect(pq.ParquetFile(svarah_file(tmp_path / "s.parquet", SV_ROWS)), (), out)["clips"] == 5


def test_svarah_local_file_needs_no_token(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    assert svarah.main(["inspect", "--file", str(svarah_file(tmp_path / "s.parquet", SV_ROWS)), "--languages", "hindi"]) == 0
    assert "Total selected: 3 clips" in capsys.readouterr().out


def test_svarah_gated_gives_instructions_and_no_token(monkeypatch, capsys):
    def gated(token):
        raise svarah.GatedAccess("Access to ai4bharat/Svarah is gated. Agree to share your contact information.")

    monkeypatch.setattr(svarah, "open_remote_parquet", gated)
    monkeypatch.setattr(svarah, "hf_token", lambda: "hf_SECRETTOKEN")
    assert svarah.main(["inspect"]) == 2
    out = capsys.readouterr()
    assert "gated" in out.out and "hf_SECRETTOKEN" not in out.out + out.err


# ---- Speech Accent Archive -------------------------------------------------------------------------------------


def saa_folder(tmp_path: Path, header="filename,native_language,country,sex,age") -> Path:
    (tmp_path / "recordings").mkdir()
    rows = ["arabic1,arabic,egypt,male,30", "arabic2,arabic,saudi arabia,female,25", "hindi1,hindi,india,female,40",
            "english1,english,usa,male,50", "arabic3,arabic,iraq,male,22"]
    (tmp_path / "speakers_all.csv").write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    for stem in ("arabic1", "arabic2", "hindi1", "english1"):  # arabic3 has no audio file
        (tmp_path / "recordings" / f"{stem}.mp3").write_bytes(b"ID3fake")
    return tmp_path


def test_saa_inspect_counts_missing_audio_and_estimates(tmp_path):
    out = io.StringIO()
    info = saa.inspect(saa_folder(tmp_path), ("arabic", "hindi"), out)
    text = out.getvalue()
    assert "| arabic | 3 | 2 |" in text  # 3 rows, only 2 recordings present
    assert "| hindi | 1 | 1 |" in text and "english" not in text.split("Selected:")[1].split("Total")[0]
    assert "Total selected with audio: 3 recordings" in text
    assert "--quick: 3 x 2 = 6 calls" in text and "default matrix: 3 x 6 = 18 calls" in text
    assert info["recordings"] == 3


def test_saa_tolerates_alternative_column_names(tmp_path):
    out = io.StringIO()
    info = saa.inspect(saa_folder(tmp_path, "file,language,country,gender,age"), ("hindi",), out)
    assert info["recordings"] == 1


def test_saa_explains_a_missing_folder_or_columns(tmp_path):
    out = io.StringIO()
    assert saa.inspect(tmp_path, out=out)["error"] == "no metadata" and "Download the Speech Accent Archive yourself" in out.getvalue()
    (tmp_path / "speakers_all.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    out = io.StringIO()
    assert saa.inspect(tmp_path, out=out)["error"] == "columns" and "Cannot find" in out.getvalue()


def test_the_paragraph_is_the_known_69_word_text():
    words = saa.PARAGRAPH.split()
    assert words[:3] == ["Please", "call", "Stella."] and words[-2:] == ["train", "station."] and len(words) == 69
