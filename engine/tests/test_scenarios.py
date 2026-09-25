"""The demo scenarios in data/scenarios.json double as regression tests: every preset reply must produce its
hand-declared gold statuses. (If you edit a preset, you must edit its `expected` too — that is the point.)"""

import json
from pathlib import Path

import pytest

from samjha_engine import check_reply

DATA = Path(__file__).resolve().parents[2] / "data" / "scenarios.json"
SCENARIOS = json.loads(DATA.read_text(encoding="utf-8"))
CASES = [(s["id"], p["id"]) for s in SCENARIOS for p in s["presets"]]


def _get(sid, pid):
    s = next(x for x in SCENARIOS if x["id"] == sid)
    return s, next(p for p in s["presets"] if p["id"] == pid)


def test_at_least_four_scenarios_with_three_presets():
    assert len(SCENARIOS) >= 4
    for s in SCENARIOS:
        kinds = {p["kind"] for p in s["presets"]}
        assert kinds == {"correct", "subtle_mistake", "negation_flip"}, s["id"]


@pytest.mark.parametrize("sid,pid", CASES)
def test_preset_matches_gold(sid, pid):
    s, p = _get(sid, pid)
    got = {r.fact_id: r.status.value for r in check_reply(s["facts"], p["text"])}
    assert got == p["expected"], {k: (got[k], p["expected"][k]) for k in got if got[k] != p["expected"][k]}
