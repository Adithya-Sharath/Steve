"""The Decode API as a public contract for other front ends (D47): openapi.json, docs/API.md, the TypeScript client, /decode/examples and CORS."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from steve_engine.decode import decode

from app.main import app
from app.security import cors_options
from app.services.decode_sessions import store
from app.settings import settings

ROOT = Path(__file__).resolve().parents[2]
WK = "wk_" + "c" * 32
PATHS = ("/decode", "/decode/clarify", "/decode/health", "/decode/examples", "/decode/inspect", "/decode/eval")


def run_script(name: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / name), "--check"], capture_output=True, text=True, timeout=180)


# ---- the files other people rely on stay in step with the code ---------------------------------------------------------------------------------------


def test_openapi_json_is_up_to_date():
    r = run_script("export_openapi.py")
    assert r.returncode == 0, r.stdout + r.stderr


def test_docs_api_md_is_up_to_date_and_its_examples_are_real():
    r = run_script("make_api_docs.py")
    assert r.returncode == 0, r.stdout + r.stderr


def test_openapi_lists_every_decode_endpoint_with_its_error_answers():
    spec = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
    for p in PATHS:
        assert p in spec["paths"]
    assert {"200", "403", "413", "422", "429"} <= set(spec["paths"]["/decode"]["post"]["responses"])
    assert {"404", "403", "422", "429"} <= set(spec["paths"]["/decode/clarify"]["post"]["responses"])
    schemas = spec["components"]["schemas"]
    for name in ("DecodeResponse", "DecodedCard", "TranslatedCard", "DecodeExamples", "DecodeHealthOut", "ClarifyIn", "DecodeIn", "ErrorOut"):
        assert name in schemas
    assert spec["info"]["version"] == "2.0.0"


def test_the_response_shape_is_pinned():
    """Changing any of these needs a decision record (and a regenerated openapi.json): this is the contract."""
    schemas = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))["components"]["schemas"]
    assert set(schemas["DecodeResponse"]["properties"]) == {"card", "translation", "transcript", "decode_id", "notes", "say_back"}
    assert set(schemas["DecodedCard"]["properties"]) == {"original_text", "plain_english", "changes", "phrases", "actions", "clarify", "skipped", "tips", "confidence",
                                                        "accent_used", "path"}
    assert set(schemas["Actions"]["properties"]) == {"where", "when", "what", "how_much"}
    assert set(schemas["TranslatedCard"]["properties"]) == {"language", "provider", "verified_numbers", "plain_english", "where", "when", "what", "how_much", "phrases",
                                                           "questions", "tip"}
    assert set(schemas["ClarifyIn"]["properties"]) == {"decode_id", "question_index", "choice"}
    assert set(schemas["DecodeIn"]["properties"]) == {"text", "accent_hint", "reply_language"}
    assert set(schemas["DecodeHealthOut"]["properties"]) == {"typed", "voice", "translation", "languages", "accent_hints", "budget", "limits"}


def test_the_docs_mention_every_endpoint_the_header_and_the_client():
    doc = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
    for needle in (*PATHS, "X-Worker-Key", "openapi.json", "steve-client.ts", "Retry-After", "CORS_ORIGINS", "403", "404", "413", "422", "429"):
        assert needle in doc, needle


def test_the_typescript_client_offers_the_four_calls_and_matches_the_contract():
    src = (ROOT / "clients" / "ts" / "steve-client.ts").read_text(encoding="utf-8")
    for needle in ("decode(", "decodeAudio(", "clarify(", "health(", "examples(", "X-Worker-Key", "SteveApiError", "newWorkerKey", '"/decode/clarify"', '"/decode/health"'):
        assert needle in src, needle
    schemas = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))["components"]["schemas"]
    for field in schemas["DecodeResponse"]["properties"]:
        assert field in src


# ---- /decode/examples --------------------------------------------------------------------------------------------------------------------------------


@pytest.fixture()
def anon():
    with TestClient(app) as c:
        yield c


def test_examples_need_no_key_and_return_six_cards(anon):
    r = anon.get("/decode/examples")
    assert r.status_code == 200
    j = r.json()
    assert j["computed_live"] is True and 5 <= len(j["examples"]) <= 6
    assert len({e["id"] for e in j["examples"]}) == len(j["examples"])
    for e in j["examples"]:
        assert e["response"]["decode_id"] is None and e["response"]["card"]["plain_english"] and e["request"]["text"]


def test_the_al_quoz_maghrib_sentence_is_in_and_decodes_as_the_engine_says(anon):
    ex = next(e for e in anon.get("/decode/examples").json()["examples"] if e["id"] == "al-quoz-maghrib")
    a = ex["response"]["card"]["actions"]
    assert ex["request"]["text"].startswith("Yalla, drop it at Al Quoz before Maghrib")
    assert (a["where"]["value"], a["when"]["value"], a["what"]["value"]) == ("al quoz", "maghrib", "drop")
    assert [p["phrase"] for p in ex["response"]["card"]["phrases"]] == ["yalla", "maghrib"]


def test_examples_are_computed_live_not_hard_coded(anon, monkeypatch):
    real = decode

    def changed(text, hint=None, path="typed", *a, **k):
        card = real(text, hint, path, *a, **k)
        return card.model_copy(update={"plain_english": "LIVE-" + card.plain_english})

    monkeypatch.setattr("app.services.decode_examples.decode", changed)
    assert all(e["response"]["card"]["plain_english"].startswith("LIVE-") for e in anon.get("/decode/examples").json()["examples"])


def test_an_examples_request_reproduces_its_card_through_post_decode(anon):
    with TestClient(app, headers={"X-Worker-Key": WK}) as c:
        for e in anon.get("/decode/examples").json()["examples"]:
            got = c.post("/decode", json={k: v for k, v in e["request"].items() if v is not None}).json()
            assert got["card"] == e["response"]["card"], e["id"]


def test_examples_store_nothing_and_include_a_question_example(anon):
    store.reset()
    ex = anon.get("/decode/examples").json()["examples"]
    assert store.count() == 0
    assert any(e["response"]["card"]["clarify"] for e in ex)  # the "a question, not a guess" button


def test_examples_never_shame(anon):
    blob = json.dumps(anon.get("/decode/examples").json()["examples"], ensure_ascii=False)
    import re

    strings = re.findall(r'"(?:reason|label|tips|say_back|social_meaning|literal)": ?"([^"]*)"', blob)
    assert strings and not any(re.search(r"\b(wrong|incorrect|bad english|mistake|error)\b", s, re.I) for s in strings)


# ---- CORS: another site can call the API ---------------------------------------------------------------------------------------------------------------


def cors_app() -> TestClient:
    a = FastAPI()
    a.add_middleware(CORSMiddleware, **cors_options())

    @a.post("/decode")
    def _decode():
        return {"ok": True}

    return TestClient(a)


def preflight(c, origin):
    return c.options("/decode", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-worker-key,content-type"})


def test_a_listed_origin_may_call_with_the_worker_key_header(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", ["https://demo.example.com"])
    r = preflight(cors_app(), "https://demo.example.com")
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "https://demo.example.com"
    assert "x-worker-key" in r.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in r.headers


def test_an_unlisted_origin_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", ["https://demo.example.com"])
    monkeypatch.setattr(settings, "cors_allow_localhost", False)
    r = preflight(cors_app(), "https://evil.example.org")
    assert "access-control-allow-origin" not in r.headers and r.status_code == 400
    assert "access-control-allow-origin" not in preflight(cors_app(), "http://localhost:5173").headers  # localhost rule switched off


def test_localhost_on_any_port_is_allowed_by_default(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", ["https://demo.example.com"])
    monkeypatch.setattr(settings, "cors_allow_localhost", True)
    assert preflight(cors_app(), "http://localhost:5173").headers["access-control-allow-origin"] == "http://localhost:5173"


def test_a_star_allows_any_origin_without_credentials(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", ["*"])
    r = preflight(cors_app(), "https://anything.example.net")
    assert r.headers["access-control-allow-origin"] == "*" and "access-control-allow-credentials" not in r.headers


def test_several_origins_can_be_listed(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", ["https://a.example.com", "https://b.example.com"])
    for o in ("https://a.example.com", "https://b.example.com"):
        assert preflight(cors_app(), o).headers["access-control-allow-origin"] == o


def test_a_real_response_carries_retry_after_to_browsers(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", ["https://demo.example.com"])
    assert "retry-after" in cors_options()["expose_headers"][0].lower()


def test_the_running_app_answers_a_preflight_for_the_configured_origin(anon):
    r = anon.options("/decode", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-worker-key"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_settings_are_documented():
    ex = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "CORS_ORIGINS" in ex and "CORS_ALLOW_LOCALHOST" in ex


# ---- /decode/inspect and /decode/eval (D50): additions, no existing shape changed ------------------------------------------------------------------------


def test_the_new_shapes_are_pinned():
    schemas = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))["components"]["schemas"]
    assert set(schemas["InspectOut"]["properties"]) == {"path", "tokens", "glossary", "slots", "examined", "effective_words", "unresolved_tokens", "card"}
    assert set(schemas["InspectExamined"]["properties"]) == {"token", "slot", "decision", "best", "margin", "options", "candidates", "original_score"}
    assert set(schemas["DecodeEvalOut"]["properties"]) == {"available", "message", "generated_from", "caveats", "sections"}
    assert set(schemas["EvalSection"]["properties"]) == {"id", "title", "label", "note", "rows"}


def test_inspect_shows_every_stage_and_matches_the_engine(anon):
    from steve_engine.decode import inspect_decode

    text = "yalla habibi come to the barking gate tree"
    r = anon.post("/decode/inspect", json={"text": text, "accent_hint": "ar"})
    assert r.status_code == 200
    j = r.json()
    assert j["card"] == decode(text, "ar", "typed").model_dump(mode="json")
    assert [g["phrase"] for g in j["glossary"]] == ["yalla", "habibi"] and any(s["kind"] == "where" for s in j["slots"])
    ex = {e["token"]: e for e in j["examined"]}
    assert ex["barking"]["decision"] == "rewrite" and ex["barking"]["best"] == "parking" and ex["barking"]["candidates"][0]["word"] == "parking"
    assert ex["tree"]["decision"] == "rewrite" and ex["barking"]["margin"] > 0
    assert j["effective_words"] == inspect_decode(text, "ar", "typed")["effective_words"] and "parking" in j["effective_words"]


def test_inspect_covers_the_voice_path_and_a_question(anon):
    j = anon.post("/decode/inspect", json={"text": "come to the barking or the building?", "accent_hint": "ar", "path": "voice"}).json()
    assert j["path"] == "voice" and j["unresolved_tokens"] and any(e["decision"] == "clarify" for e in j["examined"])


@pytest.mark.parametrize("body", [{"text": ""}, {"text": "x" * 501}, {"text": "hi", "path": "audio"}, {"text": "hi", "accent_hint": "zz"}, {}])
def test_inspect_rejects_bad_input(anon, body):
    assert anon.post("/decode/inspect", json=body).status_code == 422


def test_inspect_is_rate_limited_and_logs_no_text(anon, monkeypatch, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(settings, "rl_check_per_min", 2)
    codes = [anon.post("/decode/inspect", json={"text": "quokka barking gate"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429] and "quokka" not in caplog.text.lower()


def test_eval_serves_labelled_sections_from_the_committed_file(anon):
    j = anon.get("/decode/eval").json()
    assert j["available"] is True and j["caveats"] and len(j["sections"]) >= 6
    ids = {s["id"] for s in j["sections"]}
    assert {"false_alarm", "typed_ear", "extraction", "voice_net", "stt", "baseline", "missing"} <= ids
    for s in j["sections"]:
        assert s["label"] and s["rows"] and all(r["metric"] and r["value"] for r in s["rows"])
    voice = next(s for s in j["sections"] if s["id"] == "voice_net")
    assert "tuned on it" in voice["label"] and any("0/72" in r["value"] for r in voice["rows"])  # the two labels the owner requires travel with the catch rate
    assert "real-world validation" in json.dumps(j["sections"][-1]).lower() or j["sections"][-1]["id"] == "missing"


def test_eval_says_so_when_there_is_no_file(anon, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "eval_dir", tmp_path)
    j = anon.get("/decode/eval").json()
    assert j["available"] is False and "decode_metrics_export" in j["message"] and j["sections"] == []


def test_the_metrics_file_is_regenerated_from_its_sources():
    """decode_metrics.json must not drift from the reports it is built from."""
    r = subprocess.run([sys.executable, str(ROOT / "eval" / "decode_metrics_export.py")], capture_output=True, text=True, timeout=180, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    committed = subprocess.run(["git", "diff", "--quiet", "--", "eval/results/decode_metrics.json"], cwd=ROOT)
    assert committed.returncode == 0, "eval/results/decode_metrics.json changed when regenerated: commit the new file"


def test_the_readme_example_is_what_the_engine_and_the_whatsapp_reply_really_produce():
    """The README shows the reply for the Al Quoz / Maghrib sentence and says a test compares it with the engine (D50)."""
    from app.schemas import DecodeResponse
    from app.services.decode_flow import say_back
    from app.services.whatsapp import format_card

    c = decode("Yalla, drop it at Al Quoz before Maghrib. No signature, just call the guy.", None, "typed")
    block = format_card(DecodeResponse(card=c, say_back=say_back(c)))
    readme = (ROOT / "README.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert block in readme, block
    assert 'Someone says:  "Yalla, drop it at Al Quoz before Maghrib. No signature, just call the guy."' in readme
