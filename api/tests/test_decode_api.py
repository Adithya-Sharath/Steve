"""Decode API (D45): /decode, /decode/clarify, /decode/health. Written against the Phase 4 spec."""

import io
import logging
import re
import struct
import tempfile

import pytest
from fastapi.testclient import TestClient
from steve_engine.decode import decode

from app.main import app
from app.services.decode_sessions import store
from app.services.stt import STTUnavailable
from app.settings import settings

WK_A = "wk_" + "a" * 32
WK_B = "wk_" + "b" * 32
BARKING = "come to the barking or the building?"
DIGNITY = re.compile(r"\b(wrong|incorrect|bad english|poor english|broken english|mistake|error|fault)\b", re.I)


@pytest.fixture()
def wc():
    """A worker's browser (device key A)."""
    with TestClient(app, headers={"X-Worker-Key": WK_A}) as c:
        yield c


@pytest.fixture()
def wb():
    with TestClient(app, headers={"X-Worker-Key": WK_B}) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_store():
    store.reset()
    yield
    store.reset()


class FakeSTT:
    enabled = True

    def __init__(self, transcript="come to the barking gate three", fail=False):
        self.transcript, self.fail, self.calls = transcript, fail, []

    def transcribe(self, audio, content_type, lang_hint=None):
        self.calls.append((len(audio), content_type, lang_hint))
        if self.fail:
            raise STTUnavailable("down")
        return self.transcript


class OffSTT:
    enabled = False

    def transcribe(self, *a, **k):  # pragma: no cover - must not be called
        raise AssertionError("STT must not be called when it is off")


def use_stt(monkeypatch, stt):
    monkeypatch.setattr("app.routes.decode.get_decode_stt", lambda: stt)
    return stt


def wav(seconds: float, rate: int = 8000) -> bytes:
    n = int(seconds * rate)
    data = b"\x00\x00" * n
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", len(data))
    return header + data


def audio_post(c, data, ctype="audio/wav", **fields):
    return c.post("/decode", files={"audio": ("note.wav", io.BytesIO(data), ctype)}, data=fields)


def strings(obj, skip=("original_text", "transcript", "heard", "text")):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in skip:
                yield from strings(v, skip)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v, skip)
    elif isinstance(obj, str):
        yield obj


# ---- identity and validation ----------------------------------------------------------------------------------------------------------------------


def test_a_worker_key_is_required(anon):
    assert anon.post("/decode", json={"text": "come to the gate"}).status_code == 403
    assert anon.post("/decode", json={"text": "hi"}, headers={"X-Worker-Key": "wk_short"}).status_code == 403
    assert anon.post("/decode", json={"text": "hi"}, headers={"X-Worker-Key": "sk_" + "a" * 32}).status_code == 403  # a sender key is not a worker key
    assert anon.post("/decode/clarify", json={"decode_id": "x" * 10, "question_index": 0, "choice": "a"}).status_code == 403


@pytest.mark.parametrize("body", [{"text": ""}, {"text": "   "}, {"text": "x" * 2001}, {}, {"text": "hi", "accent_hint": "xx"}, {"text": "hi", "reply_language": "fr"}])
def test_bad_input_is_422(wc, body):
    assert wc.post("/decode", json=body).status_code == 422


def test_not_json_and_not_multipart_is_422(wc):
    assert wc.post("/decode", content=b"hello", headers={"content-type": "text/plain"}).status_code == 422


# ---- text ------------------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text,hint", [("yalla habibi come to the barking gate tree", "ar"), ("wery good, come at fife", "hi"), ("pay fifty dirhams tomorrow", None),
                                       ("don't come to the barking now, khalas", "ar")])
def test_the_text_card_is_exactly_what_decode_returns(wc, text, hint):
    body = {"text": text, **({"accent_hint": hint} if hint else {})}
    r = wc.post("/decode", json=body)
    assert r.status_code == 200
    assert r.json()["card"] == decode(text, hint, "typed").model_dump(mode="json")
    assert r.json()["transcript"] is None and r.json()["notes"] == []


def test_multipart_text_works_too(wc):
    r = wc.post("/decode", data={"text": "come at fife", "accent_hint": "ar"})
    assert r.status_code == 200 and r.json()["card"]["path"] == "typed" and "5" in r.json()["card"]["plain_english"]


def test_a_reply_language_is_accepted_and_falls_back_to_english_with_a_note_until_translation_is_on(wc):
    r = wc.post("/decode", json={"text": "come at five", "reply_language": "ml"}).json()
    assert r["card"]["plain_english"] and (r["translation"] is not None or any("English" in n for n in r["notes"]))


def test_a_clean_message_has_no_decode_id_and_nothing_is_stored(wc):
    r = wc.post("/decode", json={"text": "come to the parking gate three"}).json()
    assert r["decode_id"] is None and store.count() == 0


def test_say_back_phrases_are_short_plain_text(wc):
    r = wc.post("/decode", json={"text": BARKING, "accent_hint": "ar"}).json()
    assert r["say_back"][0] == "Sorry, parking or barking?" and all(len(s) < 80 for s in r["say_back"]) and len(r["say_back"]) <= 3


# ---- voice ------------------------------------------------------------------------------------------------------------------------------------------


def test_audio_goes_through_stt_then_the_voice_decoder(wc, monkeypatch):
    stt = use_stt(monkeypatch, FakeSTT("yalla come to the barking gate three"))
    r = audio_post(wc, wav(3), accent_hint="ar")
    assert r.status_code == 200
    j = r.json()
    assert j["transcript"] == "yalla come to the barking gate three"
    assert j["card"] == decode("yalla come to the barking gate three", "ar", "voice").model_dump(mode="json")
    assert j["card"]["path"] == "voice" and stt.calls == [(len(wav(3)), "audio/wav", "en")]


def test_a_voice_decode_spends_the_stt_budget(wc, monkeypatch):
    from app.budget import stt_budget

    use_stt(monkeypatch, FakeSTT())
    before = stt_budget.remaining()
    audio_post(wc, wav(2))
    assert stt_budget.remaining() == before - 1


def test_voice_unavailable_gives_a_typing_note_not_an_error(wc, monkeypatch):
    use_stt(monkeypatch, OffSTT())
    r = audio_post(wc, wav(2))
    assert r.status_code == 200 and r.json()["card"] is None and "type" in " ".join(r.json()["notes"])


def test_voice_unavailable_but_text_sent_too_still_decodes_the_text(wc, monkeypatch):
    use_stt(monkeypatch, OffSTT())
    r = audio_post(wc, wav(2), text="come at fife", accent_hint="ar").json()
    assert r["card"]["path"] == "typed" and any("type" in n for n in r["notes"])


def test_a_failing_stt_service_is_a_note(wc, monkeypatch):
    use_stt(monkeypatch, FakeSTT(fail=True))
    j = audio_post(wc, wav(2)).json()
    assert j["card"] is None and j["notes"]


def test_nothing_heard_says_so(wc, monkeypatch):
    use_stt(monkeypatch, FakeSTT(""))
    j = audio_post(wc, wav(2)).json()
    assert j["card"] is None and "couldn't find anything" in j["notes"][0]


def test_over_the_daily_stt_cap_falls_back_to_typing(wc, monkeypatch):
    use_stt(monkeypatch, FakeSTT())
    monkeypatch.setattr(settings, "stt_daily_cap", 0)
    j = audio_post(wc, wav(2)).json()
    assert j["card"] is None and any("busy" in n for n in j["notes"])


def test_audio_over_the_size_cap_is_413(wc, monkeypatch):
    use_stt(monkeypatch, FakeSTT())
    assert audio_post(wc, b"\x00" * (4 * 1024 * 1024 + 1000), "audio/webm").status_code == 413


def test_audio_over_the_body_cap_is_413(wc, monkeypatch):
    use_stt(monkeypatch, FakeSTT())
    assert audio_post(wc, b"\x00" * (5 * 1024 * 1024 + 10), "audio/webm").status_code == 413


def test_a_wav_longer_than_30_seconds_is_413_and_never_reaches_stt(wc, monkeypatch):
    stt = use_stt(monkeypatch, FakeSTT())
    assert audio_post(wc, wav(31)).status_code == 413 and stt.calls == []
    assert audio_post(wc, wav(29)).status_code == 200


def test_an_ogg_opus_upload_is_measured_from_its_last_page(wc, monkeypatch):
    from app.services.audio import ogg_seconds

    def page(granule):
        return b"OggS" + b"\x00\x04" + struct.pack("<q", granule) + b"\x00" * 15

    ogg = b"OggS\x00\x02" + b"\x00" * 8 + b"OpusHead" + b"\x00" * 40 + page(48_000 * 41)
    assert 40.9 < ogg_seconds(ogg) < 41.1
    stt = use_stt(monkeypatch, FakeSTT())
    assert audio_post(wc, ogg, "audio/ogg").status_code == 413 and stt.calls == []


def test_uploads_are_kept_in_memory_never_spooled_to_disk(wc, monkeypatch):
    use_stt(monkeypatch, FakeSTT())

    def boom(self, *a, **k):
        raise AssertionError("an upload was spooled to disk")

    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", boom)
    assert audio_post(wc, wav(20, 16000)).status_code == 200  # 640 KB
    assert audio_post(wc, b"\x01" * (3 * 1024 * 1024), "audio/webm").status_code == 200  # 3 MB, well over the 1 MB default spool size


# ---- clarify ----------------------------------------------------------------------------------------------------------------------------------------


def open_question(c, hint="ar"):
    r = c.post("/decode", json={"text": BARKING, "accent_hint": hint}).json()
    assert r["decode_id"] and r["card"]["clarify"]
    return r


def test_clarify_resolves_a_question_and_recomputes_the_actions(wc):
    r = open_question(wc)
    assert r["card"]["actions"]["where"] is None  # no silent guess
    r2 = wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "parking"})
    assert r2.status_code == 200
    j = r2.json()
    assert j["card"]["clarify"] == [] and j["card"]["actions"]["where"]["value"] == "parking" and j["decode_id"] is None
    assert store.count() == 0  # deleted once every question is answered
    assert wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "parking"}).status_code == 404


def test_clarify_is_case_insensitive_and_can_keep_the_heard_word(wc):
    r = open_question(wc)
    j = wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "BARKING"}).json()
    assert j["card"]["clarify"] == [] and j["card"]["changes"] == [] and j["card"]["actions"]["where"] is None and "barking" in j["card"]["plain_english"]


def test_not_sure_keeps_the_slot_empty_and_offers_a_phrase_to_say_back(wc):
    r = open_question(wc)
    j = wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "not_sure"}).json()
    assert j["card"]["clarify"] == [] and j["card"]["actions"]["where"] is None and len(j["card"]["skipped"]) == 1
    assert j["say_back"][0] == "Sorry, parking or barking?" and j["notes"]


def test_clarify_rejects_a_choice_that_is_not_offered_or_a_missing_question(wc):
    r = open_question(wc)
    assert wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "mosque"}).status_code == 422
    assert wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 3, "choice": "parking"}).status_code == 422
    assert store.count() == 1  # a bad answer changes nothing


def test_clarify_for_an_unknown_id_is_404(wc):
    assert wc.post("/decode/clarify", json={"decode_id": "nope-nope-nope", "question_index": 0, "choice": "x"}).status_code == 404


def test_another_workers_key_cannot_answer_my_question(wc, wb):
    r = open_question(wc)
    assert wb.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "parking"}).status_code == 404
    assert wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "parking"}).status_code == 200  # still mine


def test_clarify_state_expires_after_ten_minutes(wc, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(store, "clock", lambda: now[0])
    r = open_question(wc)
    now[0] += 601
    assert wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "parking"}).status_code == 404
    assert store.count() == 0


def test_an_answer_renews_the_ten_minutes(wc, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(store, "clock", lambda: now[0])
    text = "come to the barking or the building or the gate free?"
    r = wc.post("/decode", json={"text": text, "accent_hint": "ar"}).json()
    assert r["decode_id"]
    now[0] += 500
    r2 = wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "barking"})
    assert r2.status_code == 200
    now[0] += 500  # 1000 s after the start but only 500 s after the last answer
    if r2.json()["decode_id"]:
        assert wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "free"}).status_code in (200, 422)


def test_clarify_state_is_bounded_per_worker(wc):
    ids = [open_question(wc)["decode_id"] for _ in range(14)]
    assert store.count() <= 10
    assert wc.post("/decode/clarify", json={"decode_id": ids[0], "question_index": 0, "choice": "parking"}).status_code == 404  # oldest evicted
    assert wc.post("/decode/clarify", json={"decode_id": ids[-1], "question_index": 0, "choice": "parking"}).status_code == 200


def test_a_voice_question_keeps_the_transcript_in_memory_only_and_returns_it(wc, monkeypatch):
    use_stt(monkeypatch, FakeSTT("come to the gate free"))
    r = audio_post(wc, wav(2)).json()
    assert r["decode_id"] and r["card"]["clarify"][0]["question"] == "Three or free?"
    j = wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "three"}).json()
    assert j["card"]["actions"]["where"]["value"] == "gate 3" and j["transcript"] == "come to the gate free"


# ---- limits -----------------------------------------------------------------------------------------------------------------------------------------


def test_decode_is_limited_per_minute_per_ip(wc, monkeypatch):
    monkeypatch.setattr(settings, "rl_decode_per_min", 2)
    assert [wc.post("/decode", json={"text": "come at five"}).status_code for _ in range(3)] == [200, 200, 429]
    assert wc.post("/decode", json={"text": "come at five"}).headers["Retry-After"]


def test_decode_is_limited_per_day_per_ip(wc, monkeypatch):
    monkeypatch.setattr(settings, "rl_decode_per_day", 2)
    assert [wc.post("/decode", json={"text": "come at five"}).status_code for _ in range(3)] == [200, 200, 429]


def test_decode_is_limited_per_worker_per_day(wc, wb, monkeypatch):
    monkeypatch.setattr(settings, "decode_per_worker_day", 2)
    assert [wc.post("/decode", json={"text": "come at five"}).status_code for _ in range(3)] == [200, 200, 429]
    assert wb.post("/decode", json={"text": "come at five"}).status_code == 200  # another worker is unaffected


def test_clarify_has_the_default_ip_limit_not_the_decode_one(wc, monkeypatch):
    monkeypatch.setattr(settings, "rl_decode_per_min", 1)
    r = open_question(wc)  # uses the one allowed /decode call
    assert wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "parking"}).status_code == 200


# ---- privacy: nothing is logged or leaked -----------------------------------------------------------------------------------------------------------


def test_no_text_or_transcript_reaches_any_log(wc, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    use_stt(monkeypatch, FakeSTT("zanzibar gate free banana"))
    secret = "quokka yalla come to the barking gate tree"
    wc.post("/decode", json={"text": secret, "accent_hint": "ar"})
    r = audio_post(wc, wav(2)).json()
    if r["decode_id"]:
        wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "not_sure"})
    wc.post("/decode", json={"text": ""})  # even the validation error path
    out = caplog.text.lower()
    assert "quokka" not in out and "zanzibar" not in out and "banana" not in out and "barking" not in out


def test_a_server_error_does_not_log_the_text(wc, monkeypatch, caplog):
    def boom(session):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr("app.routes.decode.run_decode", boom)
    with TestClient(app, headers={"X-Worker-Key": WK_A}, raise_server_exceptions=False) as c:
        r = c.post("/decode", json={"text": "okapi text that must stay private"})
    assert r.status_code == 500 and "okapi" not in r.text and "okapi" not in caplog.text


def test_responses_never_shame_the_speaker(wc, monkeypatch):
    use_stt(monkeypatch, FakeSTT())
    bodies = []
    for text, hint in [("yalla habibi come to the barking gate tree", "ar"), (BARKING, "ar"), ("wery good, come at fife", "hi"), ("pay fifty dirhams tomorrow", None)]:
        bodies.append(wc.post("/decode", json={"text": text, "accent_hint": hint} if hint else {"text": text}).json())
    r = open_question(wc)
    for choice in ("parking", "not_sure"):
        rr = wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": choice})
        bodies.append(rr.json())
        if choice == "parking":
            r = open_question(wc)
    bodies.append(audio_post(wc, wav(2)).json())
    bodies.append(wc.get("/decode/health").json())
    for b in bodies:
        for s in strings(b):
            assert not DIGNITY.search(s), s
            assert not re.search(r"\b(score|accuracy|percent)\b", s, re.I), s


# ---- health -----------------------------------------------------------------------------------------------------------------------------------------


def test_health_is_a_feature_matrix_without_secrets(anon, monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "SECRET-SARVAM-VALUE-123")
    monkeypatch.setattr(settings, "gemini_api_key", "SECRET-GEMINI-VALUE-456")
    monkeypatch.setattr(settings, "admin_key", "SECRET-ADMIN-VALUE-789" * 2)
    r = anon.get("/decode/health")  # no worker key needed
    assert r.status_code == 200
    j = r.json()
    assert j["typed"] is True and j["voice"] is True and set(j["languages"]) == {"en", "ml", "hi", "ur", "tl", "bn"}
    assert set(j["budget"]) == {"stt_remaining", "stt_cap"} and "translation" in j
    assert "SECRET" not in r.text


def test_health_says_voice_is_off_without_a_key(anon, monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "")
    assert anon.get("/decode/health").json()["voice"] is False


def test_health_says_voice_is_off_when_the_daily_cap_is_used_up(anon, monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "k" * 20)
    monkeypatch.setattr(settings, "stt_daily_cap", 0)
    assert anon.get("/decode/health").json()["voice"] is False


def test_the_real_stt_is_sarvam_transcribe_in_english(monkeypatch):
    from app.services import stt

    monkeypatch.setattr(settings, "sarvam_api_key", "k" * 20)
    s = stt.get_decode_stt()
    assert isinstance(s, stt.SarvamSTT) and s.mode == "transcribe" and s.model == "saaras:v3" and stt.LANG_CODES["en"] == "en-IN"
    monkeypatch.setattr(settings, "sarvam_api_key", "")
    assert stt.get_decode_stt().enabled is False


def test_the_real_stt_call_sends_transcribe_and_en_in(monkeypatch):
    import httpx

    from app.services import stt

    seen = {}

    def fake_post(url, headers=None, files=None, data=None, timeout=None):
        seen.update(url=url, headers=headers, data=data, file=files["file"][0])
        return httpx.Response(200, json={"request_id": "r", "transcript": " come to the parking ", "language_code": "en-IN"},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    out = stt.SarvamSTT("k" * 20, mode="transcribe").transcribe(b"abc", "audio/wav", "en")
    assert out == "come to the parking"
    assert seen["url"] == "https://api.sarvam.ai/speech-to-text" and seen["data"] == {"model": "saaras:v3", "mode": "transcribe", "language_code": "en-IN"}
    assert seen["headers"] == {"api-subscription-key": "k" * 20}
