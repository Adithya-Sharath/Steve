"""Rate limits (D32): in-memory sliding windows behind one reusable dependency."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from test_api import MANGLISH, PHARMACY, _flow

from app.ratelimit import DAY, MINUTE, Rule, SlidingWindowLimiter, limit, limiter
from app.settings import Settings, settings

FACTS = [{"id": "d", "type": "dose", "value": 2, "unit": "tablet", "label": "2 tablets"}]


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture()
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(limiter, "clock", c)
    return c


def msg(c, text=PHARMACY):
    return c.post("/messages", json={"text": text, "sender_name": "x", "context": "pharmacy"})


# ---- the limiter itself ----------------------------------------------------------------------------------------

def test_a_sliding_window_frees_up_as_old_hits_expire():
    clock = Clock()
    lim = SlidingWindowLimiter(clock)
    rule = [Rule(3, MINUTE)]
    assert [lim.check("b", "k", rule) for _ in range(3)] == [None, None, None]
    blocked = lim.check("b", "k", rule)
    assert blocked and 59 < blocked[0] <= 60  # the oldest hit leaves the window in ~60 s
    clock.t += 30
    assert lim.check("b", "k", rule) is not None  # still inside the window
    clock.t += 31
    assert lim.check("b", "k", rule) is None  # first three expired together


def test_blocked_requests_do_not_use_up_the_allowance():
    clock = Clock()
    lim = SlidingWindowLimiter(clock)
    rule = [Rule(1, MINUTE)]
    assert lim.check("b", "k", rule) is None
    for _ in range(50):  # hammering while blocked must not push the release time back
        clock.t += 1
        assert lim.check("b", "k", rule) is not None
    clock.t = 1000.0 + 60.1
    assert lim.check("b", "k", rule) is None


def test_minute_and_day_rules_are_independent_and_atomic():
    clock = Clock()
    lim = SlidingWindowLimiter(clock)
    rules = [Rule(2, MINUTE), Rule(3, DAY)]
    assert lim.check("b", "k", rules) is None and lim.check("b", "k", rules) is None
    assert lim.check("b", "k", rules)[1] == MINUTE  # minute rule blocks first
    clock.t += 61
    assert lim.check("b", "k", rules) is None  # third of the day
    clock.t += 61
    blocked = lim.check("b", "k", rules)
    assert blocked and blocked[1] == DAY and blocked[0] > 80_000  # day rule: come back tomorrow
    clock.t += DAY
    assert lim.check("b", "k", rules) is None


def test_keys_and_buckets_are_separate():
    lim = SlidingWindowLimiter(Clock())
    rule = [Rule(1, MINUTE)]
    assert lim.check("a", "1", rule) is None
    assert lim.check("a", "2", rule) is None and lim.check("b", "1", rule) is None
    assert lim.check("a", "1", rule) is not None


def test_zero_or_negative_limit_switches_a_rule_off():
    lim = SlidingWindowLimiter(Clock())
    assert all(lim.check("b", "k", [Rule(0, MINUTE)]) is None for _ in range(100))
    assert all(lim.check("b", "k", [Rule(-1, MINUTE)]) is None for _ in range(100))


def test_idle_keys_are_swept_so_memory_does_not_grow_forever():
    clock = Clock()
    lim = SlidingWindowLimiter(clock)
    for i in range(400):
        lim.check("b", f"ip{i}", [Rule(5, MINUTE)])
    clock.t += DAY + 1
    for i in range(100):  # crosses the sweep threshold (500 allowed hits)
        lim.check("b", "fresh", [Rule(1000, MINUTE)])
    assert len(lim._hits) == 1


def test_the_dependency_factory_is_reusable_on_any_route():
    app = FastAPI()

    @app.get("/x", dependencies=[Depends(limit("x", per_minute=lambda: 2))])
    def x():
        return {"ok": True}

    with TestClient(app) as c:
        assert [c.get("/x").status_code for _ in range(3)] == [200, 200, 429]
        r = c.get("/x")
        assert int(r.headers["Retry-After"]) >= 1 and "wait" in r.json()["detail"].lower()


# ---- POST /messages --------------------------------------------------------------------------------------------

def test_messages_per_minute_per_ip(client, monkeypatch, clock):
    monkeypatch.setattr(settings, "rl_messages_per_min", 3)
    assert [msg(client).status_code for _ in range(3)] == [200, 200, 200]
    r = msg(client)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0 and "wait" in r.json()["detail"].lower()
    clock.t += 61
    assert msg(client).status_code == 200


def test_messages_per_day_per_ip(client, other, monkeypatch, clock):
    monkeypatch.setattr(settings, "rl_messages_per_min", 1000)
    monkeypatch.setattr(settings, "rl_messages_per_day", 5)
    codes = [msg(client if i % 2 == 0 else other).status_code for i in range(6)]  # two sender keys, one IP
    assert codes == [200] * 5 + [429]
    r = msg(client)
    assert "today" in r.json()["detail"] and int(r.headers["Retry-After"]) > 80_000
    clock.t += DAY + 1
    assert msg(client).status_code == 200


def test_messages_per_sender_key_per_day(client, other, monkeypatch, clock):
    monkeypatch.setattr(settings, "rl_messages_per_min", 1000)
    monkeypatch.setattr(settings, "rl_messages_per_sender_day", 3)
    assert [msg(client).status_code for _ in range(3)] == [200] * 3
    assert msg(client).status_code == 429  # sender A is done for today ...
    assert msg(other).status_code == 200  # ... sender B (same IP) is not affected


def test_a_missing_sender_key_gets_403_not_429_and_uses_no_sender_allowance(anon, client, monkeypatch):
    monkeypatch.setattr(settings, "rl_messages_per_sender_day", 1)
    assert msg(anon).status_code == 403
    assert msg(client).status_code == 200


# ---- replies ---------------------------------------------------------------------------------------------------

def test_reply_limit_is_per_minute_per_token_and_ip(client, monkeypatch, clock):
    monkeypatch.setattr(settings, "reply_rate_limit", 2)
    _, _, a = _flow(client)
    _, _, b = _flow(client)
    post = lambda t: client.post(f"/r/{t}/reply", data={"text": MANGLISH})  # noqa: E731
    assert [post(a["reader_token"]).status_code for _ in range(3)] == [200, 200, 429]
    assert post(b["reader_token"]).status_code == 200  # another link has its own allowance
    r = post(a["reader_token"])
    assert int(r.headers["Retry-After"]) > 0
    clock.t += 61
    assert post(a["reader_token"]).status_code == 200


def test_hard_cap_on_total_replies_per_message(client, monkeypatch):
    monkeypatch.setattr(settings, "reply_cap_per_message", 4)
    monkeypatch.setattr(settings, "reply_rate_limit", 1000)
    mid, _, conf = _flow(client)
    codes = [client.post(f"/r/{conf['reader_token']}/reply", data={"text": MANGLISH}).status_code for _ in range(6)]
    assert codes == [200] * 4 + [429] * 2
    assert "limit of 4 replies" in client.post(f"/r/{conf['reader_token']}/reply", data={"text": "x"}).json()["detail"]
    assert len(client.get(f"/messages/{mid}").json()["replies"]) == 4  # nothing beyond the cap was stored


def test_reply_cap_defaults_to_30_and_other_defaults_are_as_specified(monkeypatch):
    for name in ("RL_MESSAGES_PER_MIN", "RL_MESSAGES_PER_DAY", "RL_MESSAGES_PER_SENDER_DAY", "REPLY_RATE_LIMIT", "REPLY_CAP_PER_MESSAGE",
                 "RL_CHECK_PER_MIN", "RL_SEED_PER_MIN", "RL_DEFAULT_PER_MIN"):
        monkeypatch.delenv(name, raising=False)
    s = Settings()
    assert (s.rl_messages_per_min, s.rl_messages_per_day, s.rl_messages_per_sender_day) == (10, 100, 30)
    assert (s.reply_rate_limit, s.reply_cap_per_message) == (12, 30)
    assert (s.rl_check_per_min, s.rl_seed_per_min, s.rl_default_per_min) == (60, 5, 120)


def test_env_overrides_and_junk_values(monkeypatch):
    monkeypatch.setenv("RL_MESSAGES_PER_MIN", "3")
    monkeypatch.setenv("RL_SEED_PER_MIN", "not-a-number")
    s = Settings()
    assert s.rl_messages_per_min == 3 and s.rl_seed_per_min == 5  # junk falls back to the default, never crashes


# ---- engine + demo + catch-all ---------------------------------------------------------------------------------

@pytest.mark.parametrize("path,body", [("/check", {"facts": FACTS, "reply": "do goli"}), ("/analyze", {"reply": "do goli"})])
def test_check_and_analyze_are_limited_per_ip(anon, monkeypatch, path, body):
    monkeypatch.setattr(settings, "rl_check_per_min", 3)
    assert [anon.post(path, json=body).status_code for _ in range(4)] == [200, 200, 200, 429]


def test_demo_seed_is_limited_to_a_few_per_minute(client, monkeypatch):
    monkeypatch.setattr(settings, "rl_seed_per_min", 2)
    assert [client.post("/demo/seed").status_code for _ in range(3)] == [200, 200, 429]


def test_everything_else_gets_the_catch_all(anon, monkeypatch):
    monkeypatch.setattr(settings, "rl_default_per_min", 4)
    assert [anon.get("/health").status_code for _ in range(5)] == [200] * 4 + [429]
    assert anon.get("/demo/scenarios").status_code == 429  # same bucket, same IP


def test_routes_with_their_own_limit_do_not_also_burn_the_catch_all(anon, monkeypatch):
    monkeypatch.setattr(settings, "rl_default_per_min", 2)
    monkeypatch.setattr(settings, "rl_check_per_min", 50)
    for _ in range(10):
        assert anon.post("/check", json={"facts": FACTS, "reply": "do goli"}).status_code == 200
    assert anon.get("/health").status_code == 200


def test_ips_behind_a_trusted_proxy_get_separate_buckets(anon, monkeypatch):
    monkeypatch.setattr(settings, "rl_default_per_min", 1)
    monkeypatch.setattr(settings, "trust_proxy", True)
    get = lambda ip: anon.get("/health", headers={"CF-Connecting-IP": ip}).status_code  # noqa: E731
    assert get("203.0.113.1") == 200 and get("203.0.113.1") == 429
    assert get("203.0.113.2") == 200  # another visitor
    monkeypatch.setattr(settings, "trust_proxy", False)
    assert get("203.0.113.9") == 200 and get("203.0.113.10") == 429  # header ignored: shared bucket


def test_cors_lets_the_browser_read_retry_after(anon, monkeypatch):
    monkeypatch.setattr(settings, "rl_default_per_min", 1)
    origin = {"Origin": "http://localhost:3000"}
    anon.get("/health", headers=origin)
    r = anon.get("/health", headers=origin)
    assert r.status_code == 429 and r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "retry-after" in r.headers["access-control-expose-headers"].lower()
