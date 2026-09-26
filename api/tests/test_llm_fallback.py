"""The optional LLM must never make "Find key facts" hang or fail (D26/D27): 10 s deadline -> built-in extractor,
then a cooldown so repeated clicks do not each wait. Default model is the lite one."""

import re
import time
from pathlib import Path

import pytest

from app.services import extractor
from app.settings import DEFAULT_GEMINI_MODEL, Settings, settings

PHARMACY = "Take 2 tablets after food, twice a day, for 5 days. Stop taking them and call us if you get a rash."
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def llm_on(monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.3)
    monkeypatch.setattr(settings, "llm_cooldown_seconds", 60.0)
    extractor.reset_breaker()
    yield
    extractor.reset_breaker()


def _builtin_keys():
    return {(f.type.value, f.unit) for f in extractor.regex_extract(PHARMACY)}


def test_a_slow_llm_is_abandoned_after_the_deadline(monkeypatch):
    monkeypatch.setattr(extractor, "llm_extract", lambda text: time.sleep(3) or [])
    t0 = time.monotonic()
    facts, who, note = extractor.suggest_facts(PHARMACY)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.5, f"waited {elapsed:.1f}s for a 0.3 s deadline"
    assert who == "regex" and {(f.type.value, f.unit) for f in facts} == _builtin_keys()
    assert "timed out after 0.3 s" in note and "built-in extractor" in note


def test_after_a_failure_the_llm_is_skipped_so_repeat_clicks_do_not_wait(monkeypatch):
    calls = []
    monkeypatch.setattr(extractor, "llm_extract", lambda text: calls.append(1) or time.sleep(3) or [])
    extractor.suggest_facts(PHARMACY)  # times out, trips the breaker
    t0 = time.monotonic()
    for _ in range(5):
        facts, who, note = extractor.suggest_facts(PHARMACY)
        assert who == "regex" and facts and "paused" in note
    assert time.monotonic() - t0 < 0.5  # five more clicks: instant
    assert len(calls) == 1  # the LLM was not even called again


def test_cooldown_expires_and_the_llm_is_tried_again(monkeypatch):
    monkeypatch.setattr(settings, "llm_cooldown_seconds", 0.0)
    calls = []

    def flaky(text):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return extractor.regex_extract(text)

    monkeypatch.setattr(extractor, "llm_extract", flaky)
    _, who, note = extractor.suggest_facts(PHARMACY)
    assert who == "regex" and "RuntimeError" in note
    _, who, note = extractor.suggest_facts(PHARMACY)
    assert who == "llm" and note is None and len(calls) == 2


def test_rate_limit_falls_back_with_a_readable_note(monkeypatch):
    def rate_limited(text):
        raise RuntimeError("429 RESOURCE_EXHAUSTED. quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier")

    monkeypatch.setattr(extractor, "llm_extract", rate_limited)
    facts, who, note = extractor.suggest_facts(PHARMACY)
    assert who == "regex" and facts and "rate limit hit" in note


def test_daily_quota_pauses_the_llm_for_15_minutes(monkeypatch):
    def daily(text):
        raise RuntimeError("429 RESOURCE_EXHAUSTED. quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier limit: 20")

    monkeypatch.setattr(extractor, "llm_extract", daily)
    _, _, note = extractor.suggest_facts(PHARMACY)
    assert "daily quota used up" in note
    assert 14 * 60 < extractor._paused_for() <= 15 * 60


def test_healthy_llm_path_still_returns_llm_facts(monkeypatch):
    sentinel = extractor.regex_extract(PHARMACY)[:2]
    monkeypatch.setattr(extractor, "llm_extract", lambda text: sentinel)
    facts, who, note = extractor.suggest_facts(PHARMACY)
    assert who == "llm" and note is None and facts == sentinel


def test_llm_off_never_touches_the_llm(monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", False)
    monkeypatch.setattr(extractor, "llm_extract", lambda text: pytest.fail("LLM must not be called when switched off"))
    facts, who, note = extractor.suggest_facts(PHARMACY)
    assert who == "regex" and note is None and facts


def test_the_http_route_never_hangs_and_still_returns_facts(client, monkeypatch):
    monkeypatch.setattr(extractor, "llm_extract", lambda text: time.sleep(3) or [])
    t0 = time.monotonic()
    r = client.post("/messages", json={"text": PHARMACY, "sender_name": "x", "context": "pharmacy"})
    assert time.monotonic() - t0 < 1.5
    body = r.json()
    assert r.status_code == 200 and body["extractor"] == "regex" and body["suggested_facts"] and "timed out" in body["note"]


def test_the_sdk_client_gets_the_same_deadline_in_milliseconds(monkeypatch):
    import google.genai as genai

    seen = {}

    class FakeClient:
        def __init__(self, **kw):
            seen.update(kw)
            raise RuntimeError("stop here: only the constructor arguments matter")

    monkeypatch.setattr(genai, "Client", FakeClient)
    monkeypatch.setattr(settings, "llm_timeout_seconds", 12.0)
    with pytest.raises(RuntimeError):
        extractor.llm_extract(PHARMACY)
    assert seen["http_options"].timeout == 12000 and seen["api_key"] == "fake-key"


@pytest.mark.parametrize("configured", [0.05, 0.3, 1, 5, 9.99, 10, 25])
def test_the_sdk_deadline_is_never_below_ten_seconds(monkeypatch, configured):
    """Gemini answers "400 INVALID_ARGUMENT: Manually set deadline 5s is too short. Minimum allowed deadline is 10s"."""
    import google.genai as genai

    seen = {}

    class FakeClient:
        def __init__(self, **kw):
            seen.update(kw)
            raise RuntimeError("stop")

    monkeypatch.setattr(genai, "Client", FakeClient)
    monkeypatch.setattr(settings, "llm_timeout_seconds", configured)
    with pytest.raises(RuntimeError):
        extractor.llm_extract(PHARMACY)
    assert seen["http_options"].timeout >= 10_000
    assert seen["http_options"].timeout == extractor.sdk_timeout_ms() == int(max(configured, 10) * 1000)


def test_a_503_is_a_short_cooldown_not_a_quota_pause(monkeypatch):
    def unavailable(text):
        raise RuntimeError("503 UNAVAILABLE. {'error': {'code': 503, 'message': 'The model is overloaded.'}}")

    monkeypatch.setattr(extractor, "llm_extract", unavailable)
    facts, who, note = extractor.suggest_facts(PHARMACY)
    assert who == "regex" and facts and "service unavailable (503)" in note
    assert 50 < extractor._paused_for() <= 60  # LLM_COOLDOWN_SECONDS, not the 15-minute daily pause


def test_the_provider_message_is_logged_without_the_key(monkeypatch, caplog):
    def bad(text):
        raise RuntimeError("400 INVALID_ARGUMENT: Manually set deadline 5s is too short. key=fake-key")

    monkeypatch.setattr(extractor, "llm_extract", bad)
    with caplog.at_level("WARNING", logger="steve.extractor"):
        extractor.suggest_facts(PHARMACY)
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "INVALID_ARGUMENT" in logged and "deadline 5s is too short" in logged  # the message, not just the class
    assert "fake-key" not in logged and "key=***" in logged


def test_default_model_is_the_lite_one_everywhere(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert DEFAULT_GEMINI_MODEL == "gemini-3.1-flash-lite" == Settings().gemini_model
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^GEMINI_MODEL=gemini-3\.1-flash-lite\b", example, re.M)
    assert "gemini-3.8-flash" not in example
    assert "gemini-3.1-flash-lite" in (ROOT / "README.md").read_text(encoding="utf-8")
    baseline = (ROOT / "eval" / "run_baseline.py").read_text(encoding="utf-8")
    assert 'os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")' in baseline


def test_timeout_and_cooldown_defaults(monkeypatch):
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_COOLDOWN_SECONDS", raising=False)
    s = Settings()
    assert s.llm_timeout_seconds == 10.0 and s.llm_cooldown_seconds == 60.0
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "2.5")
    assert Settings().llm_timeout_seconds == 2.5
