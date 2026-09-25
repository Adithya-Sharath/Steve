"""README test counts must not drift, and the updater must never damage the README (D19)."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKELETON = "# T\n<!-- EVAL:START -->\nSTALE-TABLE\n<!-- EVAL:END -->\nengine 1 + API 2\n"


def _load():
    spec = importlib.util.spec_from_file_location("update_readme", ROOT / "eval" / "update_readme.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _point_at(mod, monkeypatch, readme: Path):
    monkeypatch.setattr(mod, "README", readme)
    monkeypatch.setattr(mod, "LATEST", ROOT / "eval" / "results" / "latest.json")


def test_refresh_counts_rewrites_every_place_the_readme_mentions_counts(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "count_tests", lambda folder: {"engine": 111, "api": 22}[folder])
    text = (
        "![t](https://img.shields.io/badge/engine%20tests-1%20passing-x) ![a](https://img.shields.io/badge/api%20tests-2%20passing-x)\n"
        "(9 engine tests)\n`make test` (engine 3 + API 4)\nengine/ x   (+5 tests)\napi/ y   (+6 tests)\n"
    )
    out = mod.refresh_counts(text)
    assert "engine%20tests-111%20passing" in out and "api%20tests-22%20passing" in out
    assert "(111 engine tests)" in out and "engine 111 + API 22" in out
    assert "(+111 tests)" in out and "(+22 tests)" in out


def test_a_red_suite_never_truncates_or_edits_the_readme(tmp_path, monkeypatch):
    """Regression: main() once opened the README for writing BEFORE the test-count guard could abort, wiping the file."""
    mod = _load()
    readme = tmp_path / "README.md"
    readme.write_text(SKELETON, encoding="utf-8")
    _point_at(mod, monkeypatch, readme)
    monkeypatch.setattr(mod, "count_tests", lambda folder: (_ for _ in ()).throw(SystemExit("suite is red")))
    with pytest.raises(SystemExit):
        mod.main()
    assert readme.read_text(encoding="utf-8") == SKELETON


def test_missing_markers_leave_the_readme_untouched(tmp_path, monkeypatch):
    mod = _load()
    readme = tmp_path / "README.md"
    readme.write_text("# no markers here\n", encoding="utf-8")
    _point_at(mod, monkeypatch, readme)
    with pytest.raises(SystemExit):
        mod.main()
    assert readme.read_text(encoding="utf-8") == "# no markers here\n"


def test_main_updates_table_and_counts_when_green_and_writes_lf(tmp_path, monkeypatch):
    mod = _load()
    readme = tmp_path / "README.md"
    readme.write_text(SKELETON, encoding="utf-8")
    _point_at(mod, monkeypatch, readme)
    monkeypatch.setattr(mod, "count_tests", lambda folder: {"engine": 7, "api": 8}[folder])
    mod.main()
    out = readme.read_bytes().decode("utf-8")
    assert "engine 7 + API 8" in out and "STALE-TABLE" not in out and "Our engine" in out
    assert "\r\n" not in out
