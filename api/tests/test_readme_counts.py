"""README test counts must not drift: `eval/update_readme.py` rewrites them from real pytest runs (D12 tooling)."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("update_readme", ROOT / "eval" / "update_readme.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def test_main_writes_counts_into_the_real_readme_source():
    """The wiring, not just the helper: main() must call refresh_counts (it silently didn't once)."""
    src = (ROOT / "eval" / "update_readme.py").read_text(encoding="utf-8")
    assert re.search(r"README\.write_text\(refresh_counts\(new\)", src)
