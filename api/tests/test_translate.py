"""Translation of the settled English card, text only (D46): protected tokens, the number check, providers, fallbacks, budgets, cache."""

import os
import re
from pathlib import Path

import httpx
import pytest
from steve_engine.decode import decode

from app.services import translate as tr
from app.services.translate import (
    FakeTranslator,
    GeminiTranslator,
    Protector,
    SarvamTranslator,
    TranslationError,
    TranslationService,
    numbers_match,
    unmask,
    validate_gemini_lines,
)
from app.settings import settings

WK = "wk_" + "t" * 32
TEXT = "yalla habibi come to the barking gate tree"
DIGNITY = re.compile(r"\b(wrong|incorrect|bad english|poor english|broken english|mistake|error|fault)\b", re.I)


@pytest.fixture(autouse=True)
def _clean():
    tr.service.reset()
    tr.translate_budget.reset()
    yield
    tr.service.reset()
    tr.translate_budget.reset()


@pytest.fixture()
def card():
    return decode(TEXT, "ar")


def use(monkeypatch, *providers):
    monkeypatch.setattr(tr, "get_providers", lambda language: [p for p in providers if p.supports(language)])
    return providers


def svc():
    return TranslationService()


# ---- protected tokens -----------------------------------------------------------------------------------------------------------------------------


def test_protect_and_restore_round_trip():
    text = "Come to the parking gate 3 at 5 pm and pay 50 dirhams, or AED 250. It sounds like 'p' /p/."
    masked, held = Protector(["parking gate 3"]).mask(text)
    bare = re.sub(r"\[\[\d+\]\]", "", masked)
    assert "3" not in bare and "50" not in bare and "parking" not in bare and masked.count("[[") == len(held)
    assert unmask(masked, held) == text


def test_times_amounts_and_currency_are_kept_together():
    _, held = Protector([]).mask("at 5 pm, 50 dirhams, 5.30 p.m., AED 250, 8 o'clock")
    assert held == ["5 pm", "50 dirhams", "5.30 p.m.", "AED 250", "8 o'clock"]


def test_unmask_rejects_lost_doubled_and_invented_placeholders():
    held = ["a", "b"]
    assert unmask("x [[2]] y [[1]]", held) == "x b y a"  # reordering is fine
    for bad in ("x [[1]] only", "[[1]] [[1]] [[2]]", "[[1]] [[2]] [[3]]", "nothing"):
        with pytest.raises(TranslationError):
            unmask(bad, held)


def test_unmask_tolerates_spaces_inside_the_brackets():
    assert unmask("[[ 1 ]]", ["3"]) == "3"


@pytest.mark.parametrize("english,translated,ok", [
    ("gate 3 at 5 pm", "gate 3, 5 pm", True), ("gate 3", "gate 8", False), ("pay 50 dirhams", "pay 50", True), ("pay 50", "pay 15", False),
    ("come at 5", "٥", False), ("come at 5", "५ बजे आइए", False), ("no numbers", "none either", True), ("pay 50", "pay 50 and 50", False),
    ("pay 50 dirhams", "pay 50 rupees", False), ("pay 50 dirhams", "50 ₹ അടയ്ക്കുക", False), ("pay 50 rupees", "pay 50 rupees", True),
])
def test_number_check(english, translated, ok):
    assert numbers_match(english, translated) is ok


# ---- the card ---------------------------------------------------------------------------------------------------------------------------------------


def test_a_translation_restores_every_protected_token(card, monkeypatch):
    fake = FakeTranslator()
    use(monkeypatch, fake)
    t, notes = svc().translate(card, "ml")
    assert notes == [] and t.language == "ml" and t.provider == "fake" and t.verified_numbers is True
    assert t.plain_english.startswith("(ml) ") and "parking gate 3" in t.plain_english
    assert t.where == "parking gate 3" and t.what and [p.phrase for p in t.phrases] == ["yalla", "habibi"]
    assert all(p.literal.startswith("(ml)") and p.social_meaning.startswith("(ml)") for p in t.phrases)


def test_only_the_settled_english_card_is_sent_never_the_original_text(card, monkeypatch):
    fake = FakeTranslator()
    use(monkeypatch, fake)
    svc().translate(card, "hi")
    sent = " ".join(" ".join(lines) for lines, _ in fake.calls).lower()
    assert card.original_text.lower() not in sent and "yalla habibi" not in sent
    plain_line = re.sub(r"\[\[\d+\]\]", "", fake.calls[0][0][0].lower())
    assert "barking" not in plain_line and "tree" not in plain_line and "parking" not in plain_line and "3" not in plain_line  # the place is protected
    assert "[[" in fake.calls[0][0][0]


def test_english_needs_no_translation(card, monkeypatch):
    fake = FakeTranslator()
    use(monkeypatch, fake)
    assert svc().translate(card, "en") == (None, []) and svc().translate(card, None) == (None, []) and fake.calls == []


def test_a_clarifying_question_is_translated_with_its_options_protected(monkeypatch):
    fake = FakeTranslator(fn=lambda lines, lang: [ln.replace(" or ", " (or) ") for ln in lines])
    use(monkeypatch, fake)
    c = decode("come to the barking or the building?", "ar")
    t, _ = svc().translate(c, "ur")
    assert t.questions == ["Parking (or) barking?"]
    assert "parking" not in " ".join(" ".join(x) for x, _ in fake.calls).lower()


def test_a_bare_time_and_the_amount_are_kept_as_they_are(monkeypatch):
    fake = FakeTranslator()
    use(monkeypatch, fake)
    c = decode("pay fifty dirhams tomorrow at five")
    t, _ = svc().translate(c, "bn")
    assert t.how_much == "50 dirhams" and t.when.startswith("(bn) ") and "5" in t.when
    assert "50" not in " ".join(" ".join(x) for x, _ in fake.calls)


# ---- the number check rejects ------------------------------------------------------------------------------------------------------------------------


def test_a_translator_that_changes_a_number_is_rejected_and_english_is_shown(card, monkeypatch):
    bad = FakeTranslator(fn=lambda lines, lang: [ln + " 8" if "[[" in ln else ln for ln in lines])  # adds an 8 next to the protected 3
    use(monkeypatch, bad)
    t, notes = svc().translate(card, "ml")
    assert t is None and notes == [tr.NOTE_CHECK]


def test_the_second_layer_catches_a_number_that_was_not_protected(card, monkeypatch):
    class Leaky(Protector):
        def mask(self, text):
            return text, []

    monkeypatch.setattr(tr, "Protector", Leaky)
    bad = FakeTranslator(fn=lambda lines, lang: [ln.replace("3", "8") for ln in lines])  # the classic: "gate 3" comes back as "gate 8"
    use(monkeypatch, bad)
    t, notes = svc().translate(card, "ml")
    assert t is None and notes == [tr.NOTE_CHECK]


@pytest.mark.parametrize("fn", [
    lambda lines, lang: [re.sub(r"\[\[\d+\]\]", "", ln) for ln in lines],  # placeholders dropped
    lambda lines, lang: [ln + " [[9]]" for ln in lines],  # placeholder invented
    lambda lines, lang: [ln.replace("[[1]]", "[[1]] [[1]]") for ln in lines],  # placeholder doubled
    lambda lines, lang: [ln + " ٣" for ln in lines],  # a native-script digit
    lambda lines, lang: [ln + " ₹" for ln in lines],  # a currency added
    lambda lines, lang: lines[:-1],  # a line lost
])
def test_every_kind_of_bad_answer_falls_back_to_english(card, monkeypatch, fn):
    use(monkeypatch, FakeTranslator(fn=fn))
    t, notes = svc().translate(card, "hi")
    assert t is None and len(notes) == 1 and "English" in notes[0]


def test_control_characters_are_stripped_from_an_answer(card, monkeypatch):
    use(monkeypatch, FakeTranslator(fn=lambda lines, lang: [ln + "\x07‮" for ln in lines]))
    t, _ = svc().translate(card, "hi")
    assert "\x07" not in t.plain_english and "‮" not in t.plain_english


# ---- providers, fallbacks, budgets --------------------------------------------------------------------------------------------------------------------


class Boom(FakeTranslator):
    def translate(self, lines, language):
        self.calls.append((lines, language))
        raise TranslationError("down")


def test_a_failing_first_provider_falls_back_to_the_second(card, monkeypatch):
    a, b = Boom("sarvam"), FakeTranslator("gemini")
    use(monkeypatch, a, b)
    t, notes = svc().translate(card, "ml")
    assert t.provider == "gemini" and notes == [] and len(a.calls) == 1 and len(b.calls) == 1


def test_all_providers_failing_gives_english_with_a_note(card, monkeypatch):
    use(monkeypatch, Boom("sarvam"), Boom("gemini"))
    assert svc().translate(card, "ml") == (None, [tr.NOTE_UNAVAILABLE])


def test_no_provider_gives_english_with_a_note(card, monkeypatch):
    use(monkeypatch)
    assert svc().translate(card, "tl") == (None, [tr.NOTE_UNAVAILABLE])


def test_a_provider_that_just_failed_is_skipped_for_a_minute(card, monkeypatch):
    now = [100.0]
    s = TranslationService(clock=lambda: now[0])
    a, b = Boom("sarvam"), FakeTranslator("gemini")
    use(monkeypatch, a, b)
    s.translate(card, "ml")
    s.reset()  # forget the cache but not the pause? reset clears both, so re-pause
    s.translate(decode("come at five"), "ml")
    calls_before = len(a.calls)
    s.translate(decode("come to the lobby"), "ml")
    assert len(a.calls) == calls_before  # paused: not asked again
    now[0] += 61
    s.translate(decode("wait at the gate"), "ml")
    assert len(a.calls) == calls_before + 1  # cooldown over


def test_over_the_daily_cap_english_is_shown_and_the_provider_is_not_called(card, monkeypatch):
    fake = FakeTranslator()
    use(monkeypatch, fake)
    monkeypatch.setattr(settings, "translate_daily_cap", 0)
    assert svc().translate(card, "ml") == (None, [tr.NOTE_BUSY]) and fake.calls == []


def test_the_cap_counts_every_provider_attempt(card, monkeypatch):
    a, b = Boom("sarvam"), FakeTranslator("gemini")
    use(monkeypatch, a, b)
    monkeypatch.setattr(settings, "translate_daily_cap", 1)
    t, notes = svc().translate(card, "ml")
    assert t is None and notes == [tr.NOTE_BUSY] and b.calls == []


def test_a_successful_call_spends_one_budget_unit(card, monkeypatch):
    use(monkeypatch, FakeTranslator())
    before = tr.translate_budget.remaining()
    svc().translate(card, "hi")
    assert tr.translate_budget.remaining() == before - 1


# ---- cache -----------------------------------------------------------------------------------------------------------------------------------------


def test_the_same_card_in_the_same_language_is_translated_once(card, monkeypatch):
    fake = FakeTranslator()
    use(monkeypatch, fake)
    s = svc()
    first, _ = s.translate(card, "ml")
    second, _ = s.translate(decode(TEXT, "ar"), "ml")
    assert first == second and len(fake.calls) == 1
    s.translate(card, "hi")
    assert len(fake.calls) == 2 and s.cache_size() == 2


def test_the_cache_expires_after_a_few_minutes(card, monkeypatch):
    now = [0.0]
    s = TranslationService(clock=lambda: now[0])
    fake = FakeTranslator()
    use(monkeypatch, fake)
    s.translate(card, "ml")
    now[0] += tr.CACHE_TTL_SECONDS + 1
    s.translate(card, "ml")
    assert len(fake.calls) == 2


def test_a_failed_translation_is_not_cached(card, monkeypatch):
    use(monkeypatch, FakeTranslator(fn=lambda lines, lang: lines[:-1]))
    s = svc()
    s.translate(card, "ml")
    assert s.cache_size() == 0


# ---- the real providers, with the network mocked -------------------------------------------------------------------------------------------------------


def test_sarvam_request_and_response_shape(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, json=json)
        return httpx.Response(200, json={"request_id": "r", "translated_text": "[[1]] ലേക്ക്\nരണ്ടാം", "source_language_code": "en-IN"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    out = SarvamTranslator("k" * 20, "https://api.sarvam.ai").translate(["Come to [[1]]", "Second"], "ml")
    assert out == ["[[1]] ലേക്ക്", "രണ്ടാം"]
    assert seen["url"] == "https://api.sarvam.ai/translate" and seen["headers"] == {"api-subscription-key": "k" * 20}
    assert seen["json"] == {"input": "Come to [[1]]\nSecond", "source_language_code": "en-IN", "target_language_code": "ml-IN", "model": "sarvam-translate:v1",
                            "numerals_format": "international"}


def test_sarvam_falls_back_to_line_by_line_when_the_line_count_changes(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json["input"])
        out = json["input"].replace("\n", " ") if "\n" in json["input"] else f"T:{json['input']}"
        return httpx.Response(200, json={"translated_text": out}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    out = SarvamTranslator("k" * 20, "https://x").translate(["one", "two"], "hi")
    assert out == ["T:one", "T:two"] and len(calls) == 3


def test_sarvam_errors_become_translation_errors(monkeypatch):
    def fail(url, headers=None, json=None, timeout=None):
        return httpx.Response(500, json={}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fail)
    with pytest.raises(TranslationError):
        SarvamTranslator("k" * 20, "https://x").translate(["one"], "ur")

    def empty(url, headers=None, json=None, timeout=None):
        return httpx.Response(200, json={"translated_text": "  "}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", empty)
    with pytest.raises(TranslationError):
        SarvamTranslator("k" * 20, "https://x").translate(["one"], "ur")


def test_sarvam_splits_long_input_into_requests_under_its_limit(monkeypatch):
    sizes = []

    def fake_post(url, headers=None, json=None, timeout=None):
        sizes.append(len(json["input"]))
        return httpx.Response(200, json={"translated_text": json["input"]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    lines = ["x" * 600] * 6
    assert SarvamTranslator("k" * 20, "https://x").translate(lines, "bn") == lines
    assert len(sizes) >= 2 and max(sizes) <= tr.SARVAM_MAX_CHARS


def test_only_sarvam_languages_go_to_sarvam():
    s = SarvamTranslator("k" * 20, "https://x")
    assert [lang for lang in ("ml", "hi", "ur", "bn", "tl", "en") if s.supports(lang)] == ["ml", "hi", "ur", "bn"]
    assert GeminiTranslator().supports("tl") and not GeminiTranslator().supports("en")


def test_gemini_answers_are_validated():
    assert validate_gemini_lines(["a1", "b1"], ["a", "b"]) == ["a1", "b1"]
    for raw in ("text", ["only one"], [1, 2], ["ok", ""], ["ok", "x" * 500], {"a": 1}, None):
        with pytest.raises(TranslationError):
            validate_gemini_lines(raw, ["a", "b"])
    assert validate_gemini_lines(["a\x00\x07b", "c"], ["a", "b"]) == ["a b", "c"]


def test_gemini_translation_is_guarded_by_the_daily_llm_cap(monkeypatch):
    monkeypatch.setattr(settings, "llm_daily_cap", 0)
    monkeypatch.setattr(GeminiTranslator, "_generate", lambda self, lines, lang: pytest.fail("must not be called"))
    with pytest.raises(TranslationError):
        GeminiTranslator().translate(["x"], "tl")


def test_gemini_translation_spends_the_llm_budget_and_returns_lines(monkeypatch):
    from app.budget import llm_budget

    llm_budget.reset()
    monkeypatch.setattr(GeminiTranslator, "_generate", lambda self, lines, lang: [f"T {x}" for x in lines])
    before = llm_budget.remaining()
    assert GeminiTranslator().translate(["x"], "tl") == ["T x"]
    assert llm_budget.remaining() == before - 1


def test_gemini_failures_are_translation_errors(monkeypatch):
    def boom(self, lines, lang):
        raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(GeminiTranslator, "_generate", boom)
    with pytest.raises(TranslationError):
        GeminiTranslator().translate(["x"], "tl")


def test_providers_follow_the_keys_and_the_switch(monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "")
    monkeypatch.setattr(settings, "llm_enabled", False)
    assert tr.get_providers("ml") == []
    monkeypatch.setattr(settings, "sarvam_api_key", "k" * 20)
    assert [p.name for p in tr.get_providers("ml")] == ["sarvam"] and tr.get_providers("tl") == []  # Tagalog is not a Sarvam language
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "g" * 20)
    assert [p.name for p in tr.get_providers("ml")] == ["sarvam", "gemini"] and [p.name for p in tr.get_providers("tl")] == ["gemini"]
    assert tr.get_providers("en") == [p for p in tr.get_providers("en")]  # "en" never asks for a provider (checked by the service)


# ---- through the API ------------------------------------------------------------------------------------------------------------------------------


@pytest.fixture()
def wc():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, headers={"X-Worker-Key": WK}) as c:
        yield c


def test_decode_returns_the_translation_next_to_the_english_card(wc, monkeypatch):
    use(monkeypatch, FakeTranslator())
    r = wc.post("/decode", json={"text": TEXT, "accent_hint": "ar", "reply_language": "ml"}).json()
    assert r["translation"]["language"] == "ml" and r["translation"]["verified_numbers"] is True
    assert r["card"]["plain_english"] == decode(TEXT, "ar").plain_english  # the English card is unchanged
    assert "parking gate 3" in r["translation"]["plain_english"] and r["notes"] == []


def test_decode_without_a_working_provider_still_answers_in_english(wc, monkeypatch):
    use(monkeypatch)
    r = wc.post("/decode", json={"text": TEXT, "accent_hint": "ar", "reply_language": "ur"}).json()
    assert r["translation"] is None and r["card"]["plain_english"] and r["notes"] == [tr.NOTE_UNAVAILABLE]


def test_a_bad_translation_never_reaches_the_client(wc, monkeypatch):
    use(monkeypatch, FakeTranslator(fn=lambda lines, lang: [ln.replace("[[1]]", "[[1]] 8") for ln in lines]))
    r = wc.post("/decode", json={"text": TEXT, "accent_hint": "ar", "reply_language": "hi"}).json()
    assert r["translation"] is None and r["notes"] == [tr.NOTE_CHECK]


def test_clarify_returns_the_translation_too(wc, monkeypatch):
    use(monkeypatch, FakeTranslator())
    r = wc.post("/decode", json={"text": "come to the barking or the building?", "accent_hint": "ar", "reply_language": "tl"}).json()
    assert r["translation"]["questions"] and r["decode_id"]
    j = wc.post("/decode/clarify", json={"decode_id": r["decode_id"], "question_index": 0, "choice": "parking"}).json()
    assert j["translation"]["language"] == "tl" and j["translation"]["questions"] == []


def test_health_lists_translation_by_language_without_secrets(wc, monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "SECRET-SARVAM-KEY-123456")
    monkeypatch.setattr(settings, "llm_enabled", False)
    r = wc.get("/decode/health")
    j = r.json()
    assert j["translation"]["available"] is True and set(j["translation"]["languages"]) == {"ml", "hi", "ur", "bn"} and "SECRET" not in r.text


def test_translation_notes_and_strings_never_shame(wc, monkeypatch):
    use(monkeypatch, FakeTranslator())
    for lang in ("ml", "hi", "ur", "tl", "bn"):
        r = wc.post("/decode", json={"text": "don't come to the barking now, khalas", "accent_hint": "ar", "reply_language": lang}).json()
        for s in _strings(r["translation"]) + r["notes"] + r["say_back"]:
            assert not DIGNITY.search(s), s


def test_no_text_reaches_the_logs_through_translation(wc, monkeypatch, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    use(monkeypatch, Boom("sarvam"), FakeTranslator("gemini"))
    wc.post("/decode", json={"text": "quokka yalla come to the barking gate tree", "accent_hint": "ar", "reply_language": "ml"})
    assert "quokka" not in caplog.text.lower() and "barking" not in caplog.text.lower()


def _strings(o):
    if isinstance(o, dict):
        return [s for v in o.values() for s in _strings(v)]
    if isinstance(o, list):
        return [s for v in o for s in _strings(v)]
    return [o] if isinstance(o, str) else []


# ---- live (opt in: STEVE_LIVE_TRANSLATE=1, keys in .env; one real Sarvam call and one real Gemini call) -----------------------------------------------------


def _live_keys():
    from dotenv import dotenv_values

    return dotenv_values(Path(__file__).resolve().parents[2] / ".env")


@pytest.mark.skipif(os.environ.get("STEVE_LIVE_TRANSLATE") != "1", reason="live translation calls are opt-in (set STEVE_LIVE_TRANSLATE=1)")
def test_live_sarvam_and_gemini_translate_and_keep_the_numbers():
    keys = _live_keys()
    if not keys.get("SARVAM_API_KEY") or not keys.get("GEMINI_API_KEY"):
        pytest.skip("no keys in .env")
    c = decode("come to the parking gate three at five, do not pay fifty dirhams", None)
    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(settings, "sarvam_api_key", keys["SARVAM_API_KEY"])
        monkey.setattr(settings, "gemini_api_key", keys["GEMINI_API_KEY"])
        monkey.setattr(settings, "llm_enabled", True)
        got = {}
        for lang, prov in (("ml", SarvamTranslator(keys["SARVAM_API_KEY"], "https://api.sarvam.ai")), ("tl", GeminiTranslator())):
            monkey.setattr(tr, "get_providers", lambda language, p=prov: [p])
            t, notes = TranslationService().translate(c, lang)
            got[lang] = (t.provider if t else None, notes, (t.plain_english if t else ""))
            print("LIVE", lang, got[lang])
        assert got["ml"][0] == "sarvam" and got["tl"][0] == "gemini"
        for _, _, text in got.values():
            assert "3" in text and "5" in text and "50" in text
    finally:
        monkey.undo()
