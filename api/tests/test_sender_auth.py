"""Sender endpoints need the sender key (403 otherwise); reader endpoints stay open by token (D16)."""

import pytest
from conftest import KEY_A, KEY_B

from app.auth import hash_key

PHARMACY = "Take 2 tablets after food, twice a day, for 5 days. Stop taking them and call us if you get a rash."


def _make(client):
    r = client.post("/messages", json={"text": PHARMACY, "sender_name": "Priya", "context": "pharmacy"}).json()
    c = client.post(f"/messages/{r['message_id']}/confirm", json={"facts": r["suggested_facts"]}).json()
    return r["message_id"], r["suggested_facts"], c["reader_token"]


def test_every_sender_endpoint_rejects_a_missing_key(client, anon):
    mid, facts, _ = _make(client)
    calls = [
        anon.post("/messages", json={"text": "hi"}),
        anon.get("/messages"),
        anon.get(f"/messages/{mid}"),
        anon.post(f"/messages/{mid}/confirm", json={"facts": facts}),
        anon.post(f"/messages/{mid}/followup"),
        anon.get(f"/messages/{mid}/stream"),
        anon.post("/demo/seed"),
        anon.post("/settings/llm", json={"enabled": False}),
    ]
    assert [c.status_code for c in calls] == [403] * len(calls)
    assert "Sender key" in calls[0].json()["detail"]


@pytest.mark.parametrize("bad", ["", "abc", "sk_short", "sk_" + "!" * 30, "AAAA" * 10, "sk_" + "A" * 200])
def test_malformed_keys_are_rejected(anon, bad):
    assert anon.get("/messages", headers={"X-Sender-Key": bad}).status_code == 403
    assert anon.get("/messages", params={"key": bad}).status_code == 403  # the query key is only for the SSE stream anyway


def test_someone_elses_message_is_403_everywhere(client, other):
    mid, facts, _ = _make(client)
    assert other.get(f"/messages/{mid}").status_code == 403
    assert other.post(f"/messages/{mid}/followup").status_code == 403
    assert other.post(f"/messages/{mid}/confirm", json={"facts": facts}).status_code == 403
    assert other.get(f"/messages/{mid}/stream").status_code == 403
    assert other.get(f"/messages/{mid}/stream", params={"key": KEY_B}).status_code == 403
    assert mid not in [m["id"] for m in other.get("/messages").json()]
    assert mid in [m["id"] for m in client.get("/messages").json()]
    assert client.get(f"/messages/{mid}").status_code == 200
    assert client.get("/messages/does-not-exist").status_code == 404  # unknown id is still just 404


def test_reader_endpoints_stay_open_by_token(client, anon):
    mid, _, token = _make(client)
    view = anon.get(f"/r/{token}")
    assert view.status_code == 200 and view.json()["text"] == PHARMACY
    assert anon.post(f"/r/{token}/reply", data={"text": "randu gulika, food kazhinju"}).json() == {"received": True}
    assert len(client.get(f"/messages/{mid}").json()["replies"]) == 1  # the owner sees it


def test_public_endpoints_need_no_key(anon):
    assert anon.get("/health").status_code == 200
    assert anon.get("/demo/scenarios").status_code == 200
    assert anon.get("/eval/results").status_code == 200
    facts = [{"id": "d", "type": "dose", "value": 2, "unit": "tablet", "label": "2 tablets"}]
    assert anon.post("/check", json={"facts": facts, "reply": "do goli"}).status_code == 200
    assert anon.post("/analyze", json={"reply": "do goli"}).status_code == 200


def test_demo_is_per_sender(client, other):
    a = client.post("/demo/seed").json()["seeded"]
    b = other.post("/demo/seed").json()["seeded"]
    assert len(a) >= 4 and len(b) >= 4
    ids_a, ids_b = {s["message_id"] for s in a}, {s["message_id"] for s in b}
    assert not ids_a & ids_b
    assert other.get(f"/messages/{a[0]['message_id']}").status_code == 403
    assert client.get(f"/messages/{a[0]['message_id']}").status_code == 200
    assert {m["id"] for m in other.get("/messages").json() if m["demo"]} == ids_b
    client.post("/demo/seed")  # re-seeding one sender never touches the other's demo data
    assert other.get(f"/messages/{b[0]['message_id']}").status_code == 200


def test_key_is_stored_only_as_a_hash(client):
    from sqlmodel import Session, select

    from app.db import Message, get_engine

    mid, _, _ = _make(client)
    with Session(get_engine()) as s:
        m = s.get(Message, mid)
        assert m.owner_hash == hash_key(KEY_A) and KEY_A not in m.owner_hash
        assert len(s.exec(select(Message).where(Message.owner_hash == KEY_A)).all()) == 0


def test_llm_toggle_is_not_available_to_sender_keys(client, anon, other):
    """D30: a self-issued sender key must not flip a switch that affects everyone (details in test_admin_toggle.py)."""
    assert anon.post("/settings/llm", json={"enabled": False}).status_code == 403
    assert client.post("/settings/llm", json={"enabled": False}).status_code == 403
    assert other.post("/settings/llm", json={"enabled": False}).status_code == 403


def test_legacy_rows_without_owner_are_not_readable(client):
    from sqlmodel import Session

    from app.db import Message, get_engine

    with Session(get_engine()) as s:
        s.add(Message(id="legacy01", text="old", confirmed=True))
        s.commit()
    assert client.get("/messages/legacy01").status_code == 403


def test_old_message_table_gets_owner_hash_column(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text

    import app.db as db

    eng = create_engine(f"sqlite:///{(tmp_path / 'old2.db').as_posix()}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE message (id VARCHAR PRIMARY KEY, text VARCHAR)"))
    monkeypatch.setattr(db, "_engine", eng)
    db._ensure_columns()
    assert "owner_hash" in {c["name"] for c in inspect(eng).get_columns("message")}
