import asyncio
import json

from app.routes import reader as reader_routes
from app.services.broker import Broker
from app.services.extractor import regex_extract
from app.settings import settings

PHARMACY = "Take 2 tablets after food, twice a day, for 5 days. Stop taking them and call us if you get a rash."
MANGLISH = "randu gulika, food kazhinju, raavile vaikittu, oru week"


def _flow(client, text=PHARMACY):
    r = client.post("/messages", json={"text": text, "sender_name": "Priya", "context": "pharmacy"})
    assert r.status_code == 200
    body = r.json()
    facts = body["suggested_facts"]
    c = client.post(f"/messages/{body['message_id']}/confirm", json={"facts": facts})
    assert c.status_code == 200
    return body["message_id"], facts, c.json()


def test_health_reports_flags_and_works_without_keys(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["llm_enabled"] is False and h["stt_enabled"] is False
    assert h["lexicon"]["entries"] > 250


def test_regex_extractor_finds_pharmacy_facts_without_llm():
    facts = regex_extract(PHARMACY)
    keys = {(f.type.value, json.dumps(f.value, sort_keys=True), f.unit) for f in facts}
    assert ("dose", "2", "tablet") in keys
    assert ("timing", '"after_food"', None) in keys
    assert ("frequency", "2", None) in keys
    assert ("duration", "5", "day") in keys
    conds = [f for f in facts if f.type.value == "condition"]
    assert len(conds) == 1 and conds[0].value["trigger"] == "rash" and conds[0].value["action"] == "stop"
    assert len(facts) == 5


def test_regex_extractor_other_scenarios():
    site = regex_extract(
        "Drink 1 bottle of water every hour. Take a 15-minute break in the shade at 12:30. "
        "If you feel dizzy, stop work and tell the supervisor."
    )
    got = {(f.type.value, f.unit) for f in site}
    assert {("dose", "bottle"), ("frequency", None), ("duration", "minute"), ("date", None), ("condition", None)} <= got
    visa = regex_extract(
        "Submit your passport copy and 2 photos by Thursday. The fee is 150 AED. Do not travel until your visa is stamped."
    )
    kinds = {(f.type.value, str(f.value if not isinstance(f.value, dict) else f.value["action"])) for f in visa}
    assert ("amount", "150") in kinds and ("date", "thursday") in kinds and ("condition", "avoid") in kinds


def test_full_flow_reader_never_sees_scores(client):
    mid, facts, conf = _flow(client)
    token = conf["reader_token"]
    assert conf["reader_url"].endswith(f"/r/{token}")

    view = client.get(f"/r/{token}").json()
    assert view["text"] == PHARMACY
    assert set(view) == {"text", "sender_name", "context", "stt_enabled", "prompt"}

    r = client.post(f"/r/{token}/reply", data={"text": MANGLISH})
    assert r.status_code == 200 and r.json() == {"received": True}

    m = client.get(f"/messages/{mid}").json()
    assert len(m["replies"]) == 1
    by = {x["fact_id"]: x["status"] for x in m["latest"]}
    assert by["dose_1"] == "understood" and by["duration_1"] == "wrong"
    assert m["aggregate"]["understood"] >= 3 and m["aggregate"]["total"] == len(facts)
    dur = next(x for x in m["replies"][0]["results"] if x["fact_id"] == "duration_1")
    assert "7 days" in dur["reason"] and dur["evidence"][0]["text"] == "oru week"

    lst = client.get("/messages").json()
    assert any(x["id"] == mid and x["reply_count"] == 1 for x in lst)


def test_followup_covers_only_failed_facts(client):
    mid, _, conf = _flow(client)
    client.post(f"/r/{conf['reader_token']}/reply", data={"text": MANGLISH})
    f = client.post(f"/messages/{mid}/followup").json()
    labels = {x["label"] for x in f["failed"]}
    assert "5 days" in labels and "2 tablets" not in labels
    assert "5 days" in f["draft"] and "2 tablets" not in f["draft"]


def test_later_reply_fixes_only_what_it_mentions(client):
    mid, _, conf = _flow(client)
    t = conf["reader_token"]
    client.post(f"/r/{t}/reply", data={"text": MANGLISH})
    client.post(f"/r/{t}/reply", data={"text": "anju divasam"})
    by = {x["fact_id"]: x["status"] for x in client.get(f"/messages/{mid}").json()["latest"]}
    assert by["duration_1"] == "understood" and by["dose_1"] == "understood"


def test_confirm_validation(client):
    r = client.post("/messages", json={"text": "hi"}).json()
    assert client.post(f"/messages/{r['message_id']}/confirm", json={"facts": []}).status_code == 422
    dup = [{"id": "a", "type": "dose", "value": 1, "unit": "tablet", "label": "x"}] * 2
    assert client.post(f"/messages/{r['message_id']}/confirm", json={"facts": dup}).status_code == 422
    assert client.get("/messages/nope").status_code == 404
    assert client.get("/r/nope").status_code == 404


def test_reply_validation_and_audio_without_stt(client):
    _, _, conf = _flow(client)
    t = conf["reader_token"]
    assert client.post(f"/r/{t}/reply", data={"text": "   "}).status_code == 422
    r = client.post(f"/r/{t}/reply", files={"audio": ("a.webm", b"123", "audio/webm")})
    assert r.status_code == 400 and "type" in r.json()["detail"].lower()


def test_stateless_check_and_analyze(client):
    facts = [{"id": "d", "type": "dose", "value": 2, "unit": "tablet", "label": "2 tablets"}]
    r = client.post("/check", json={"facts": facts, "reply": "do goli"}).json()
    assert r[0]["status"] == "understood"
    a = client.post("/analyze", json={"reply": "do goli", "facts": facts}).json()
    assert a["tokens"] and a["matches"] and a["slots"][0]["type"] == "dose" and a["results"][0]["status"] == "understood"


def test_llm_toggle_and_wrapper_test(client):
    assert client.post("/settings/llm", json={"enabled": True}).json()["llm_enabled"] is False  # no key => still off
    client.post("/settings/llm", json={"enabled": False})
    _, facts, conf = _flow(client)  # full flow works with the LLM off
    assert facts and conf["reader_token"]


def test_llm_failure_degrades_to_regex(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "fake")
    monkeypatch.setattr("app.services.extractor.llm_extract", lambda t: (_ for _ in ()).throw(RuntimeError("boom")))
    r = client.post("/messages", json={"text": PHARMACY}).json()
    assert r["extractor"] == "regex" and r["suggested_facts"] and r["note"]


def test_demo_seed_and_eval_empty_state(client):
    s = client.post("/demo/seed").json()
    assert len(s["seeded"]) >= 4
    assert client.post("/demo/seed").status_code == 200  # idempotent
    demo = [m for m in client.get("/messages").json() if m["demo"]]
    assert len(demo) >= 4
    ph = next(m for m in demo if m["id"] == "demo-pharmacy")
    assert ph["reply_count"] == 1
    assert client.get("/demo/scenarios").json()[0]["id"] == "pharmacy"
    assert "available" in client.get("/eval/results").json()


def test_rate_limit(client, monkeypatch):
    _, _, conf = _flow(client)
    t = conf["reader_token"]
    reader_routes._hits.clear()
    monkeypatch.setattr(settings, "reply_rate_limit", 2)
    codes = [client.post(f"/r/{t}/reply", data={"text": "ok"}).status_code for _ in range(4)]
    assert codes[:2] == [200, 200] and codes[2:] == [429, 429]


def test_broker_pubsub():
    async def go():
        b = Broker()
        q = b.subscribe("m1")
        assert b.publish("m1", {"x": 1}) == 1
        assert await q.get() == {"x": 1}
        b.unsubscribe("m1", q)
        assert b.publish("m1", {"x": 2}) == 0

    asyncio.run(go())


def test_voice_reply_via_stt_interface(client, monkeypatch):
    """Sarvam call is mocked: the transcript (romanised, verbatim) goes through the engine like typed text."""
    import httpx

    seen = {}

    def fake_post(url, headers=None, files=None, data=None, timeout=None):
        seen.update(url=url, key=headers["api-subscription-key"], data=data, fname=files["file"][0])
        return httpx.Response(200, json={"request_id": "x", "transcript": "randu gulika food kazhinju oru week", "language_code": "ml-IN"},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "sarvam_api_key", "test-key")
    monkeypatch.setattr(settings, "stt_flag", True)
    monkeypatch.setattr("app.services.stt.httpx.post", fake_post)
    _, _, conf = _flow(client)
    t = conf["reader_token"]
    assert client.get(f"/r/{t}").json()["stt_enabled"] is True
    r = client.post(f"/r/{t}/reply", files={"audio": ("reply.wav", b"RIFFxxxx", "audio/wav")}, data={"lang_hint": "ml"})
    assert r.status_code == 200 and r.json() == {"received": True}
    assert seen["url"] == "https://api.sarvam.ai/speech-to-text" and seen["key"] == "test-key"
    assert seen["data"]["model"] == "saaras:v3" and seen["data"]["mode"] == "translit" and seen["data"]["language_code"] == "ml-IN"
    msg = client.get("/messages").json()[0]
    detail = client.get(f"/messages/{msg['id']}").json()
    assert detail["replies"][-1]["source"] == "voice" and "oru week" in detail["replies"][-1]["text"]
