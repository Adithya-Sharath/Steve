"""The global LLM switch is admin-only (D30): a self-issued sender key must not be able to flip it for everyone."""

import hmac

import pytest

from app.settings import settings

ADMIN = "admin-key-for-tests-0123456789"


@pytest.fixture(autouse=True)
def restore(monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", False)
    monkeypatch.setattr(settings, "gemini_api_key", "fake")
    yield


def test_without_admin_key_configured_the_endpoint_is_closed_to_everyone(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "")
    for headers in ({}, {"X-Admin-Key": ""}, {"X-Admin-Key": "anything"}, {"X-Admin-Key": ADMIN}):
        r = client.post("/settings/llm", json={"enabled": True}, headers=headers)
        assert r.status_code == 403, headers
    assert settings.llm_enabled is False  # the switch follows LLM_ENABLED only
    assert client.get("/health").json()["admin_toggle_available"] is False


def test_a_sender_key_alone_cannot_flip_it(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_key", ADMIN)
    r = client.post("/settings/llm", json={"enabled": True})  # the client fixture carries a valid X-Sender-Key
    assert r.status_code == 403 and settings.llm_enabled is False
    assert r.json()["detail"] == "Admin key required."


@pytest.mark.parametrize("bad", ["", "wrong", ADMIN[:-1], ADMIN + "x", ADMIN.upper()])
def test_wrong_admin_keys_are_rejected(client, monkeypatch, bad):
    monkeypatch.setattr(settings, "admin_key", ADMIN)
    r = client.post("/settings/llm", json={"enabled": True}, headers={"X-Admin-Key": bad})
    assert r.status_code == 403 and settings.llm_enabled is False


def test_the_right_admin_key_flips_it_both_ways(anon, monkeypatch):
    monkeypatch.setattr(settings, "admin_key", ADMIN)  # no sender key needed: this is an operator action
    h = {"X-Admin-Key": ADMIN}
    on = anon.post("/settings/llm", json={"enabled": True}, headers=h)
    assert on.status_code == 200 and on.json() == {"llm_switch": True, "llm_enabled": True}
    off = anon.post("/settings/llm", json={"enabled": False}, headers=h)
    assert off.json() == {"llm_switch": False, "llm_enabled": False}


def test_health_advertises_the_toggle_without_leaking_the_key(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_key", ADMIN)
    r = client.get("/health")
    assert r.json()["admin_toggle_available"] is True
    assert ADMIN not in r.text and "fake" not in r.text


def test_the_comparison_is_constant_time(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_key", ADMIN)
    calls = []
    real = hmac.compare_digest
    monkeypatch.setattr(hmac, "compare_digest", lambda a, b: calls.append((type(a), type(b))) or real(a, b))
    client.post("/settings/llm", json={"enabled": False}, headers={"X-Admin-Key": ADMIN})
    assert calls == [(bytes, bytes)]
