"""typed_truth.csv: the committed template loads cleanly, real-looking personal data is rejected, bad rows are reported not guessed."""

import csv
from pathlib import Path

import pytest
import typed_truth as tt


def write(tmp_path: Path, rows: list[list[str]], header=None) -> Path:
    p = tmp_path / "t.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header or tt.COLUMNS)
        w.writerows(rows)
    return p


def test_the_committed_file_loads_cleanly_and_its_examples_are_marked_synthetic():
    rows, problems = tt.load()
    assert problems == [] and len(rows) >= 5
    assert all(r.synthetic for r in rows)  # nothing real has been committed
    assert {r.accent for r in rows} <= tt.ACCENTS
    assert any("barking" in r.text_as_typed for r in rows)


def test_a_good_row_round_trips(tmp_path):
    rows, problems = tt.load(write(tmp_path, [["come to the barking", "come to the parking", "ar", "handwritten", ""]]))
    assert problems == [] and rows[0].intended_meaning == "come to the parking" and not rows[0].synthetic


@pytest.mark.parametrize("text", [
    "call me +971 50 123 4567 now", "call 0501234567", "mail me at worker@example.com", "see https://example.com/x", "go to www.site.ae",
])
def test_personal_data_is_rejected(tmp_path, text):
    rows, problems = tt.load(write(tmp_path, [[text, "call me", "ar", "whatsapp-screenshot", ""]]))
    assert rows == [] and any("anonymise" in p for p in problems)


def test_placeholders_and_short_numbers_are_fine(tmp_path):
    rows, problems = tt.load(write(tmp_path, [["come at 5 to gate 3 [NAME] flat 12", "come at 5", "hi", "handwritten", "[PHONE] removed"]]))
    assert problems == [] and len(rows) == 1


def test_bad_rows_are_reported_and_skipped(tmp_path):
    rows, problems = tt.load(write(tmp_path, [
        ["", "meaning", "ar", "handwritten", ""], ["typed", "", "ar", "handwritten", ""], ["typed", "meaning", "xx", "handwritten", ""],
        ["typed", "meaning", "ar", "invented", ""], ["ok", "fine", "ar", "synthetic", ""], ["", "", "", "", ""],
    ]))
    assert [r.text_as_typed for r in rows] == ["ok"]
    text = "\n".join(problems)
    for expected in ("text_as_typed is empty", "intended_meaning is empty", "accent 'xx'", "source 'invented'"):
        assert expected in text


def test_missing_columns_are_an_error(tmp_path):
    with pytest.raises(ValueError, match="missing columns"):
        tt.load(write(tmp_path, [], header=["text_as_typed", "accent"]))
