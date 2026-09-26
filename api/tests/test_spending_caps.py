"""Daily spending caps on the paid services (D33)."""

from datetime import date, timedelta

import httpx
import pytest
from test_api import MANGLISH, PHARMACY, _flow

from app.budget import DailyBudget, llm_budget, stt_budget
from app.services import extractor
from app.settings import Settings, settings

# ---- the counter ------------------------------------------------------------------------------------------------


def test_budget_counts_down_and_stops_at_the_cap():
    b = DailyBudget(lambda: 3)
    assert [b.try_spend() for _ in range(5)] == [True, True, True, False, False]
    assert b.remaining() == 0


def test_a_refused_call_uses_nothing_and_resets_at_midnight_utc():
    day = [date(2026, 9, 26)]
    b = DailyBudget(lambda: 1, today=lambda: day[0])
    assert b.try_spend() and not b.try_spend() and b.remaining() == 0
    day[0] += timedelta(days=1)
    assert b.remaining() == 1 and b.try_spend()


def test_zero_blocks_everything_and_negative_is_unlimited():
    off = DailyBudget(lambda: 0)
    assert off.try_spend() is False and off.remaining() == 0
    free = DailyBudget(lambda: -1)
    assert all(free.try_spend() for _ in range(1000)) and free.remaining() == -1


def test_the_cap_is_read_live_so_it_can_be_changed_without_a_restart(monkeypatch):
    b = DailyBudget(lambda: settings.llm_daily_cap)
    monkeypatch.setattr(settings, "llm_daily_cap", 1)
    assert b.try_spend() and not b.try_spend()
    monkeypatch.setattr(settings, "llm_daily_cap", 2)
    assert b.try_spend() and not b.try_spend()


def test_defaults_are_200_and_300(monkeypatch):
    monkeypatch.delenv("LLM_DAILY_CAP", raising=False)
    monkeypatch.delenv("STT_DAILY_CAP", raising=False)
    s = Settings()
    assert (s.llm_daily_cap, s.stt_daily_cap) == (200, 300)
    monkeypatch.setenv("LLM_DAILY_CAP", "7")
    monkeypatch.setenv("STT_DAILY_CAP", "junk")
    s = Settings()
    assert (s.llm_daily_cap, s.stt_daily_cap) == (7, 300)


# ---- the LLM ----------------------------------------------------------------------------------------------------


@pytest.fixture()
def llm_on(monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "fake-key")
    extractor.reset_breaker()
    yield
    extractor.reset_breaker()


def test_when_the_llm_cap_is_hit_the_built_in_extractor_answers_with_a_note(llm_on, monkeypatch):
    calls = []
    monkeypatch.setattr(extractor, "llm_extract", lambda text: calls.append(1) or extractor.regex_extract(text))
    monkeypatch.setattr(settings, "llm_daily_cap", 2)
    out = [extractor.suggest_facts(PHARMACY) for _ in range(4)]
    assert [o[1] for o in out] == ["llm", "llm", "regex", "regex"]
    assert len(calls) == 2  # the provider was not called once the cap was reached
    facts, who, note = out[2]
    assert facts and "daily AI limit reached" in note and "built-in extractor" in note


def test_a_failed_llm_call_still_counts_toward_the_cap(llm_on, monkeypatch):
    def boom(text):
        raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(extractor, "llm_extract", boom)
    monkeypatch.setattr(settings, "llm_daily_cap", 5)
    extractor.suggest_facts(PHARMACY)
    assert llm_budget.remaining() == 4


def test_paused_or_disabled_llm_does_not_spend_budget(monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", False)
    extractor.suggest_facts(PHARMACY)
    assert llm_budget.remaining() == settings.llm_daily_cap
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(extractor, "llm_extract", lambda text: (_ for _ in ()).throw(RuntimeError("boom")))
    extractor.reset_breaker()
    extractor.suggest_facts(PHARMACY)  # fails, trips the cooldown, spends 1
    before = llm_budget.remaining()
    extractor.suggest_facts(PHARMACY)  # paused: nothing is called, nothing is spent
    assert llm_budget.remaining() == before
    extractor.reset_breaker()


def test_the_route_still_returns_facts_when_the_llm_cap_is_hit(client, llm_on, monkeypatch):
    monkeypatch.setattr(settings, "llm_daily_cap", 0)
    r = client.post("/messages", json={"text": PHARMACY, "sender_name": "x", "context": "pharmacy"})
    body = r.json()
    assert r.status_code == 200 and body["extractor"] == "regex" and body["suggested_facts"]
    assert "daily AI limit reached" in body["note"]


# ---- speech-to-text ---------------------------------------------------------------------------------------------


def _stt_on(monkeypatch):
    calls = []

    def fake_post(url, headers=None, files=None, data=None, timeout=None):
        calls.append(1)
        return httpx.Response(200, json={"transcript": MANGLISH, "language_code": "ml-IN"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "sarvam_api_key", "test-key")
    monkeypatch.setattr(settings, "stt_flag", True)
    monkeypatch.setattr("app.services.stt.httpx.post", fake_post)
    return calls


def test_stt_cap_asks_the_reader_to_type_instead(client, monkeypatch):
    calls = _stt_on(monkeypatch)
    monkeypatch.setattr(settings, "stt_daily_cap", 2)
    _, _, conf = _flow(client)
    url = f"/r/{conf['reader_token']}/reply"
    voice = lambda: client.post(url, files={"audio": ("r.wav", b"RIFFxxxx", "audio/wav")})  # noqa: E731
    assert [voice().status_code for _ in range(2)] == [200, 200]
    r = voice()
    assert r.status_code == 429 and "type your reply" in r.json()["detail"]
    assert len(calls) == 2  # Sarvam was not called for the third
    assert client.post(url, data={"text": MANGLISH}).status_code == 200  # typing always works


def test_typed_replies_never_spend_the_stt_budget(client, monkeypatch):
    _stt_on(monkeypatch)
    _, _, conf = _flow(client)
    client.post(f"/r/{conf['reader_token']}/reply", data={"text": MANGLISH})
    assert stt_budget.remaining() == settings.stt_daily_cap


# ---- /health ----------------------------------------------------------------------------------------------------


def test_health_shows_numbers_only(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_daily_cap", 10)
    monkeypatch.setattr(settings, "stt_daily_cap", -1)
    monkeypatch.setattr(settings, "gemini_api_key", "super-secret-gemini")
    monkeypatch.setattr(settings, "sarvam_api_key", "super-secret-sarvam")
    llm_budget.try_spend()
    r = client.get("/health")
    assert r.json()["budget"] == {"llm_cap": 10, "llm_remaining": 9, "stt_cap": -1, "stt_remaining": -1}
    assert "super-secret" not in r.text
