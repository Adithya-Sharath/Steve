"""WhatsApp (D48): signed webhook, text and voice notes, images, onboarding, numbered questions, language change, splitting, limits, privacy. All mocked: no live message."""

import itertools
import logging
import re

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text as sql
from test_decode_api import FakeSTT, OffSTT, wav

from app.db import get_engine
from app.main import app
from app.services import translate as tr
from app.services import whatsapp as wa
from app.services.decode_sessions import store
from app.services.messaging import FakeProvider, MediaUnavailable, TwilioProvider, compute_signature
from app.services.messaging.base import MediaTooLarge
from app.settings import settings

SECRET = "s" * 40
_n = itertools.count(5_000_000)
DIGNITY = re.compile(r"\b(wrong|incorrect|bad english|poor english|broken english|mistake|error|fault)\b", re.I)


@pytest.fixture(autouse=True)
def _wa(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_enabled", True)
    monkeypatch.setattr(settings, "worker_hash_secret", SECRET)
    monkeypatch.setattr(settings, "twilio_account_sid", "")
    monkeypatch.setattr(settings, "whatsapp_webhook_url", "")
    wa.convs.reset()
    store.reset()
    tr.service.reset()
    tr.translate_budget.reset()
    yield
    wa.convs.reset()
    store.reset()


@pytest.fixture()
def provider(monkeypatch):
    p = FakeProvider()
    monkeypatch.setattr("app.routes.whatsapp.get_provider", lambda: p)
    return p


@pytest.fixture()
def http():
    with TestClient(app) as c:
        yield c


class Phone:
    """One made-up number; `say` posts a webhook like Twilio would."""

    def __init__(self, http, provider):
        self.http, self.provider = http, provider
        self.number = f"+9715{next(_n)}"
        self.addr = f"whatsapp:{self.number}"
        self.sid = 0

    def post(self, body="", media=(), sid=None, sender=None, **extra):
        self.sid += 1
        form = {"From": sender or self.addr, "To": "whatsapp:+14155238886", "Body": body, "MessageSid": sid or f"SM{next(_n)}", "NumMedia": str(len(media)), **extra}
        for i, (url, ctype) in enumerate(media):
            form[f"MediaUrl{i}"], form[f"MediaContentType{i}"] = url, ctype
        return self.http.post("/whatsapp/webhook", data=form, headers={"X-Twilio-Signature": "x"})

    def say(self, body="", **kw):
        before = len(self.provider.sent)
        r = self.post(body, **kw)
        assert r.status_code == 200, r.text
        return [b for to, _f, b in self.provider.sent[before:] if to == self.addr]

    def onboard(self, choice="6"):
        self.say("hello")
        return self.say(choice)


@pytest.fixture()
def phone(http, provider):
    return Phone(http, provider)


def use_translator(monkeypatch, fn=None):
    fake = tr.FakeTranslator(fn=fn)
    monkeypatch.setattr(tr, "get_providers", lambda language: [fake] if fake.supports(language) else [])
    return fake


# ---- the provider and the signature -----------------------------------------------------------------------------------------------------------------


def test_the_signature_matches_twilios_worked_example():
    params = {"CallSid": ["CA1234567890ABCDE"], "Caller": ["+14158675310"], "Digits": ["1234"], "From": ["+14158675310"], "To": ["+18005551212"]}
    assert compute_signature("12345", "https://example.com/myapp.php?foo=1&bar=2", params) == "L/OH5YylLD5NRKLltdqwSvS0BnU="
    p = TwilioProvider("AC1", "12345")
    assert p.validate("https://example.com/myapp.php?foo=1&bar=2", params, "L/OH5YylLD5NRKLltdqwSvS0BnU=")
    assert not p.validate("https://example.com/myapp.php?foo=1&bar=2", params, "L/OH5YylLD5NRKLltdqwSvS0BnU")  # one character short
    assert not p.validate("https://example.com/other", params, "L/OH5YylLD5NRKLltdqwSvS0BnU=")  # another URL
    assert not p.validate("https://example.com/myapp.php?foo=1&bar=2", {**params, "Digits": ["9999"]}, "L/OH5YylLD5NRKLltdqwSvS0BnU=")  # a changed parameter
    assert not p.validate("https://example.com/myapp.php?foo=1&bar=2", params, "") and not TwilioProvider("AC1", "").validate("u", params, "x")


def test_a_repeated_parameter_is_signed_value_by_value():
    a = compute_signature("t", "https://x", {"K": ["b", "a"]})
    assert a == compute_signature("t", "https://x", {"K": ["a", "b"]}) == compute_signature("t", "https://x", {"K": ["a", "b"]})


def real_provider(monkeypatch, url="https://tunnel.example/whatsapp/webhook", token="secret-token-123"):
    p = TwilioProvider("ACtest", token)
    monkeypatch.setattr("app.routes.whatsapp.get_provider", lambda: p)
    monkeypatch.setattr(settings, "whatsapp_webhook_url", url)
    sent = []
    monkeypatch.setattr(p, "send", lambda to, from_, body: sent.append((to, from_, body)))
    return p, sent, url, token


def signed(http, url, token, form, tamper=False):
    sig = compute_signature(token, url, {k: [v] for k, v in form.items()})
    if tamper:
        form = {**form, "Body": form["Body"] + " and more"}
    return http.post("/whatsapp/webhook", data=form, headers={"X-Twilio-Signature": sig})


FORM = {"From": "whatsapp:+971501110000", "To": "whatsapp:+14155238886", "Body": "hello", "MessageSid": "SMsig1", "NumMedia": "0", "AccountSid": "ACtest"}


def test_a_correctly_signed_webhook_is_accepted_and_answered(http, monkeypatch):
    _p, sent, url, token = real_provider(monkeypatch)
    r = signed(http, url, token, {**FORM, "MessageSid": "SMsig-ok"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/xml") and "<Response" in r.text and sent and sent[0][0] == FORM["From"]


def test_unsigned_wrongly_signed_and_tampered_webhooks_do_nothing(http, monkeypatch):
    _p, sent, url, token = real_provider(monkeypatch)
    assert http.post("/whatsapp/webhook", data=FORM).status_code == 403  # no signature at all
    assert http.post("/whatsapp/webhook", data=FORM, headers={"X-Twilio-Signature": "AAAA"}).status_code == 403
    assert signed(http, url, token, FORM, tamper=True).status_code == 403  # body changed after signing
    assert signed(http, "https://other.example/whatsapp/webhook", token, FORM).status_code == 403  # signed for another URL
    assert signed(http, url, "another-token", FORM).status_code == 403  # signed with another token
    assert sent == []


def test_a_message_from_another_twilio_account_is_refused(http, monkeypatch):
    _p, sent, url, token = real_provider(monkeypatch)
    monkeypatch.setattr(settings, "twilio_account_sid", "ACmine")
    assert signed(http, url, token, {**FORM, "AccountSid": "ACsomeoneelse"}).status_code == 403 and sent == []


def test_it_is_off_unless_enabled_and_configured(http, provider, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_enabled", False)
    assert http.post("/whatsapp/webhook", data=FORM).status_code == 404
    monkeypatch.setattr(settings, "whatsapp_enabled", True)
    monkeypatch.setattr(settings, "worker_hash_secret", "short")
    assert http.post("/whatsapp/webhook", data=FORM).status_code == 503
    assert provider.sent == []


def test_a_message_that_is_not_from_whatsapp_is_ignored(phone):
    assert phone.say("hello", sender="+971501110000") == [] and phone.provider.sent == []


def test_nothing_is_ever_sent_unless_a_message_arrived(provider):
    assert provider.sent == []


# ---- onboarding -----------------------------------------------------------------------------------------------------------------------------------------


def test_the_first_message_gets_a_numbered_language_picker(phone):
    out = phone.say("hello")
    assert len(out) == 1
    for line in ("1 മലയാളം", "2 हिंदी", "3 اردو", "4 Tagalog", "5 বাংলা", "6 English"):
        assert line in out[0]


def test_choosing_a_language_gives_a_privacy_line_a_sample_decode_and_how_to_use_it(phone, monkeypatch):
    use_translator(monkeypatch)
    phone.say("hello")
    out = phone.say("1")
    assert len(out) == 3
    assert out[0].startswith("✅ മലയാളം") and "(ml) I delete your voice notes after listening. Your boss can't see this chat." in out[0]
    assert "📍 Where: parking gate 3" in out[1] and "yalla" in out[1] and "Reply EN for English" in out[1]
    assert "voice note" in out[2] and "HELP" in out[2]


def test_the_privacy_line_falls_back_to_english_when_translation_is_unavailable(phone, monkeypatch):
    monkeypatch.setattr(tr, "get_providers", lambda language: [])
    phone.say("hello")
    out = phone.say("2")
    assert "I delete your voice notes after listening. Your boss can't see this chat." in out[0] and out[0].startswith("✅ हिंदी")


@pytest.mark.parametrize("reply,lang", [("3", "ur"), ("Malayalam", "ml"), ("english", "en"), ("6", "en"), ("Bangla", "bn"), ("tagalog", "tl")])
def test_a_language_can_be_picked_by_number_or_name(phone, monkeypatch, reply, lang):
    use_translator(monkeypatch)
    phone.say("hello")
    phone.say(reply)
    assert wa._get_pref(wa.worker_hash(phone.addr)).language == lang


def test_anything_else_while_choosing_shows_the_picker_again(phone):
    phone.say("hello")
    assert "Choose your language" in phone.say("what?")[0]
    assert "Choose your language" in phone.say("9")[0]


# ---- text ---------------------------------------------------------------------------------------------------------------------------------------------


def test_a_text_message_gets_the_fixed_format(phone):
    phone.onboard("6")
    out = phone.say("yalla habibi come to the barking gate tree")
    assert len(out) == 1
    msg = out[0]
    order = [msg.index(x) for x in ("📍 Where: parking gate 3", "✅ What: come", '💬 They said: "yalla habibi come to the barking gate tree"', "ℹ️ yalla = come on / let's go", "ℹ️ habibi = ")]
    assert order == sorted(order)
    assert "Reply EN" not in msg and "⏰" not in msg and "💰" not in msg  # empty lines are left out; English needs no EN


def test_when_and_how_much_have_their_own_lines(phone):
    phone.onboard("6")
    msg = phone.say("pay fifty dirhams tomorrow at five")[0]
    assert "⏰ When: tomorrow, 5" in msg and "💰 How much: 50 dirhams" in msg and msg.index("⏰") < msg.index("✅") < msg.index("💰") < msg.index("💬")


def test_a_message_without_actions_shows_the_plain_english(phone):
    phone.onboard("6")
    assert "📝 Good morning sir" in phone.say("good morning sir")[0]


def test_the_translated_card_comes_first_and_en_shows_the_english(phone, monkeypatch):
    use_translator(monkeypatch)
    phone.onboard("1")
    msg = phone.say("don't come to the barking now, khalas")[0]
    assert "✅ What: (ml) don't come" in msg and "📍 Where: parking" in msg and "↩️ Reply EN for English" in msg
    english = phone.say("EN")
    assert len(english) == 1 and "✅ What: don't come" in english[0] and "(ml)" not in english[0] and "Reply EN" not in english[0]


def test_en_before_any_message_asks_for_one(phone):
    phone.onboard("1")
    assert "Send me a message first" in phone.say("EN")[0]


def test_en_for_an_english_speaker_says_so(phone):
    phone.onboard("6")
    assert "English already" in phone.say("EN")[0]


def test_a_failed_translation_shows_english_with_a_note(phone, monkeypatch):
    monkeypatch.setattr(tr, "get_providers", lambda language: [])
    phone.onboard("1")
    msg = phone.say("come to the parking gate three")[0]
    assert "📍 Where: parking gate 3" in msg and "Translation isn't available right now, showing English." in msg and "Reply EN" not in msg


# ---- clarifying questions with numbers -----------------------------------------------------------------------------------------------------------------


def question(phone):
    phone.onboard("6")
    msg = phone.say("come to the barking or the building?")[0]
    assert "❓ Parking or barking?" in msg and "Reply 1 for Parking, 2 for Barking, 3 if not sure" in msg
    return msg


def test_a_question_is_asked_with_numbers_and_no_guess(phone):
    msg = question(phone)
    assert "📍" not in msg  # where stays empty while the question is open


def test_replying_with_a_number_answers_the_question(phone):
    question(phone)
    out = phone.say("1")
    assert len(out) == 1 and "📍 Where: parking" in out[0] and "❓" not in out[0] and store.count() == 0


def test_the_second_option_is_a_number_too(phone):
    question(phone)
    out = phone.say("2")[0]
    assert "❓" not in out and "📍" not in out  # "barking" is not a place: still no invented where


def test_not_sure_gives_a_phrase_to_send_back(phone):
    question(phone)
    out = phone.say("3")[0]
    assert "📍" not in out and "You can show them this: Sorry, parking or barking?" in out


def test_a_number_out_of_range_is_asked_again_and_keeps_the_question(phone):
    question(phone)
    assert "Please reply with a number from 1 to 3." in phone.say("9")[0]
    assert "📍 Where: parking" in phone.say("1")[0]


def test_an_answer_after_the_question_expired_says_so(phone):
    question(phone)
    store.reset()
    assert "expired" in phone.say("1")[0]


def test_a_number_without_an_open_question_is_just_a_message(phone):
    phone.onboard("6")
    assert "💬 They said: \"7\"" in phone.say("7")[0]


def test_another_number_cannot_answer_my_question(http, provider):
    a, b = Phone(http, provider), Phone(http, provider)
    question(a)
    b.onboard("6")
    assert "They said: \"1\"" in b.say("1")[0]  # for b, "1" is just text
    assert "📍 Where: parking" in a.say("1")[0]  # a's question is still a's


# ---- commands and language change -----------------------------------------------------------------------------------------------------------------------


def test_help_lists_the_commands(phone):
    phone.onboard("6")
    for word in ("help", "HELP", "Hello"):
        out = phone.say(word)[0]
        assert "LANGUAGE" in out and "EN" in out and "voice note" in out


def test_change_language_shows_the_picker_and_applies_the_choice(phone, monkeypatch):
    use_translator(monkeypatch)
    phone.onboard("6")
    assert "Choose your language" in phone.say("change language")[0]
    out = phone.say("2")
    assert out[0].startswith("✅ हिंदी") and wa._get_pref(wa.worker_hash(phone.addr)).language == "hi"
    assert "(hi)" in phone.say("come at five")[0]


def test_language_alone_also_works(phone):
    phone.onboard("6")
    assert "Choose your language" in phone.say("Language")[0]


# ---- voice notes and images -----------------------------------------------------------------------------------------------------------------------------


OGG = ("https://api.twilio.com/2010-04-01/Accounts/AC1/Messages/MM1/Media/ME1", "audio/ogg")


def test_a_voice_note_is_downloaded_heard_decoded_and_answered(phone, monkeypatch):
    phone.onboard("6")
    phone.provider.media[OGG[0]] = wav(3)
    stt = FakeSTT("yalla come to the barking gate three")
    monkeypatch.setattr("app.routes.decode.get_decode_stt", lambda: stt)
    out = phone.say("", media=[OGG])
    assert len(out) == 1 and "📍 Where: parking gate 3" in out[0] and '💬 They said: "yalla come to the barking gate three"' in out[0]
    assert stt.calls == [(len(wav(3)), "audio/ogg", "en")]


def test_a_voice_note_spends_the_stt_budget_and_is_counted_anonymously(phone, monkeypatch):
    from app.budget import stt_budget

    phone.onboard("6")
    phone.provider.media[OGG[0]] = wav(2)
    monkeypatch.setattr("app.routes.decode.get_decode_stt", lambda: FakeSTT())
    before = stt_budget.remaining()
    phone.say("", media=[OGG])
    assert stt_budget.remaining() == before - 1 and wa._get_pref(wa.worker_hash(phone.addr)).voice_notes == 1


def test_a_voice_note_can_leave_a_question_to_answer_with_a_number(phone, monkeypatch):
    phone.onboard("6")
    phone.provider.media[OGG[0]] = wav(2)
    monkeypatch.setattr("app.routes.decode.get_decode_stt", lambda: FakeSTT("come to the gate free"))
    assert "Reply 1 for Three, 2 for Free, 3 if not sure" in phone.say("", media=[OGG])[0]
    assert "📍 Where: gate 3" in phone.say("1")[0]


def test_voice_that_is_switched_off_gets_a_friendly_note(phone, monkeypatch):
    phone.onboard("6")
    phone.provider.media[OGG[0]] = wav(2)
    monkeypatch.setattr("app.routes.decode.get_decode_stt", lambda: OffSTT())
    assert "Voice isn't available right now" in phone.say("", media=[OGG])[0]


def test_a_voice_note_that_says_nothing(phone, monkeypatch):
    phone.onboard("6")
    phone.provider.media[OGG[0]] = wav(2)
    monkeypatch.setattr("app.routes.decode.get_decode_stt", lambda: FakeSTT(""))
    assert "couldn't find anything" in phone.say("", media=[OGG])[0]


def test_a_voice_note_over_the_length_or_size_cap_is_refused_before_speech_to_text(phone, monkeypatch):
    phone.onboard("6")
    stt = FakeSTT()
    monkeypatch.setattr("app.routes.decode.get_decode_stt", lambda: stt)
    phone.provider.media[OGG[0]] = wav(31)
    assert "too long" in phone.say("", media=[OGG])[0]
    phone.provider.media[OGG[0]] = b"\x00" * (4 * 1024 * 1024 + 5)
    assert "too long" in phone.say("", media=[OGG])[0]
    assert stt.calls == []


def test_a_voice_note_that_cannot_be_downloaded_is_a_note(phone):
    phone.onboard("6")
    assert "couldn't listen" in phone.say("", media=[OGG])[0]  # not in the fake's media dict


def test_an_image_gets_a_polite_reply(phone):
    phone.onboard("6")
    assert phone.say("", media=[("https://x/img", "image/jpeg")]) == ["I can read voice notes and text for now."]


def test_an_empty_message_shows_help(phone):
    phone.onboard("6")
    assert "LANGUAGE" in phone.say("")[0]


# ---- splitting ------------------------------------------------------------------------------------------------------------------------------------------


def test_short_messages_are_not_split():
    assert wa.split_message("hello") == ["hello"]


def test_long_messages_split_on_line_breaks_and_are_numbered():
    text = "\n".join(f"line {i} " + "x" * 90 for i in range(40))
    parts = wa.split_message(text, limit=1000)
    assert len(parts) > 1 and all(len(p) <= 1000 for p in parts)
    assert parts[0].startswith(f"(1/{len(parts)})\n") and parts[-1].startswith(f"({len(parts)}/{len(parts)})\n")
    body = "\n".join(p.split("\n", 1)[1] for p in parts)
    assert body == text  # nothing lost, nothing cut inside a line


def test_a_single_overlong_line_is_cut_at_a_space():
    parts = wa.split_message(" ".join(["word"] * 500), limit=300)
    assert len(parts) > 1 and all(len(p) <= 300 for p in parts)
    assert " ".join(p.split("\n", 1)[1] for p in parts).split() == ["word"] * 500


def test_the_real_limit_keeps_every_part_under_twilios_1600_characters():
    assert all(len(p) <= 1600 for p in wa.split_message("y" * 20000))


def test_a_long_reply_is_sent_as_several_numbered_messages(phone, monkeypatch):
    phone.onboard("6")
    monkeypatch.setattr(wa, "MAX_PART", 160)
    out = phone.say("yalla habibi come to the barking gate tree, kindly revert by tomorrow, pay fifty dirhams")
    assert len(out) >= 2 and all(len(p) <= 160 for p in out)
    assert out[0].startswith(f"(1/{len(out)})\n") and out[-1].startswith(f"({len(out)}/{len(out)})\n")


# ---- limits and duplicates -----------------------------------------------------------------------------------------------------------------------------


def test_per_hour_limit_gives_one_notice_then_silence(phone, monkeypatch):
    monkeypatch.setattr(settings, "wa_per_number_hour", 3)
    phone.onboard("6")  # 2 messages
    phone.say("come at five")  # 3rd
    assert phone.say("come at six") == [wa.LIMIT_NOTICE]
    assert phone.say("come at seven") == [] and phone.say("come at eight") == []


def test_another_number_is_not_limited_by_mine(http, provider, monkeypatch):
    monkeypatch.setattr(settings, "wa_per_number_hour", 1)
    a, b = Phone(http, provider), Phone(http, provider)
    a.say("hello")
    assert a.say("hello again") == [wa.LIMIT_NOTICE]
    assert "Choose your language" in b.say("hello")[0]


def test_per_day_limit(phone, monkeypatch):
    monkeypatch.setattr(settings, "wa_per_number_hour", 0)  # off
    monkeypatch.setattr(settings, "wa_per_number_day", 2)
    phone.say("hello")
    phone.say("6")
    assert phone.say("come at five") == [wa.LIMIT_NOTICE]


def test_the_same_message_delivered_twice_is_answered_once(phone):
    phone.onboard("6")
    assert len(phone.say("come at five", sid="SMdup1")) == 1
    assert phone.say("come at five", sid="SMdup1") == []


# ---- privacy ----------------------------------------------------------------------------------------------------------------------------------------------


def dump_db() -> str:
    out = []
    with get_engine().connect() as c:
        for (name,) in c.execute(sql("select name from sqlite_master where type='table'")).fetchall():
            for row in c.execute(sql(f'select * from "{name}"')).fetchall():
                out.append(f"{name}: {row}")
    return "\n".join(out)


def test_the_database_holds_only_a_hash_a_language_and_counts(phone, monkeypatch):
    use_translator(monkeypatch)
    phone.onboard("1")
    phone.say("quokka yalla come to the barking gate tree")
    phone.provider.media[OGG[0]] = wav(2)
    monkeypatch.setattr("app.routes.decode.get_decode_stt", lambda: FakeSTT("okapi voice words"))
    phone.say("", media=[OGG])
    dump = dump_db()
    digits = phone.number.lstrip("+")
    assert digits not in dump and phone.number not in dump and phone.addr not in dump
    assert "quokka" not in dump and "okapi" not in dump and "barking" not in dump
    row = wa._get_pref(wa.worker_hash(phone.addr))
    assert row and len(row.worker_hash) == 64 and row.language == "ml" and row.decodes == 2 and row.voice_notes == 1
    with get_engine().connect() as c:
        cols = {r[1] for r in c.execute(sql("pragma table_info(workerpref)")).fetchall()}
    assert cols == {"worker_hash", "language", "decodes", "voice_notes", "created_at", "updated_at"}


def test_the_hash_is_keyed_stable_and_hides_the_number(monkeypatch):
    a = wa.worker_hash("whatsapp:+971501234567")
    assert a == wa.worker_hash("whatsapp:+971 50 123 4567") == wa.worker_hash("whatsapp:+971501234567") and len(a) == 64
    assert a != wa.worker_hash("whatsapp:+971501234568") and "971501234567" not in a
    monkeypatch.setattr(settings, "worker_hash_secret", "another-secret-value-0123456789abcdef")
    assert wa.worker_hash("whatsapp:+971501234567") != a  # keyed: without the secret the number cannot be recomputed


def test_no_number_and_no_text_in_any_log(phone, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    use_translator(monkeypatch, fn=lambda lines, lang: lines[:-1])  # a failing translation logs a warning
    phone.onboard("1")
    phone.say("quokka yalla come to the barking gate tree")
    phone.say("come to the barking or the building?")
    phone.say("3")
    phone.say("EN")
    phone.provider.fail_send = True
    phone.say("zebra message while sending fails")
    monkeypatch.setattr(wa, "run_decode", lambda s: (_ for _ in ()).throw(RuntimeError("engine exploded on zebra")))
    phone.provider.fail_send = False
    assert wa.GENERIC_ERROR in phone.say("zebra breaks the engine")
    text = caplog.text.lower()
    assert phone.number not in text and phone.number.lstrip("+") not in text
    for w in ("quokka", "barking", "zebra", "building"):
        assert w not in text


def test_a_failing_provider_or_engine_never_breaks_the_webhook(phone):
    phone.provider.fail_send = True
    assert phone.post("hello").status_code == 200


def test_the_provider_is_only_asked_to_send_replies_to_the_sender(phone):
    phone.onboard("6")
    phone.say("come at five")
    assert phone.provider.sent and all(to == phone.addr and frm == "whatsapp:+14155238886" for to, frm, _b in phone.provider.sent)


def test_replies_never_shame_the_speaker(phone, monkeypatch):
    use_translator(monkeypatch)
    phone.onboard("1")
    bodies = []
    for t in ("yalla habibi come to the barking gate tree", "come to the barking or the building?", "3", "wery good come at fife", "EN", "help", "language", "2", "good morning"):
        bodies += phone.say(t)
    bodies += [wa.PICKER, wa.HOWTO, wa.HELP, wa.IMAGE, wa.VOICE_LONG, wa.VOICE_FAILED, wa.NOTHING, wa.EXPIRED, wa.NO_LAST, wa.LIMIT_NOTICE, wa.GENERIC_ERROR]
    for b in bodies:
        assert not DIGNITY.search(re.sub(r'💬 They said: ".*"', "", b)), b
        assert not re.search(r"\b(score|accuracy|percent)\b", b, re.I)


# ---- the real Twilio calls, with the network mocked -----------------------------------------------------------------------------------------------------


def test_twilio_send_uses_the_messages_endpoint_with_basic_auth(monkeypatch):
    seen = {}

    def fake_post(url, auth=None, data=None, timeout=None):
        seen.update(url=url, auth=auth, data=data)
        return httpx.Response(201, json={"sid": "SM1", "status": "queued"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    TwilioProvider("ACabc", "tok").send("whatsapp:+971501110000", "whatsapp:+14155238886", "hello")
    assert seen["url"] == "https://api.twilio.com/2010-04-01/Accounts/ACabc/Messages.json" and seen["auth"] == ("ACabc", "tok")
    assert seen["data"] == {"From": "whatsapp:+14155238886", "To": "whatsapp:+971501110000", "Body": "hello"}


def test_twilio_send_errors_are_raised_without_leaking_the_body(monkeypatch, caplog):
    def fail(url, auth=None, data=None, timeout=None):
        return httpx.Response(400, json={"message": "bad number +971501110000"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fail)
    with pytest.raises(httpx.HTTPError):
        TwilioProvider("ACabc", "tok").send("whatsapp:+971501110000", "whatsapp:+1", "secret text")
    assert "971501110000" not in caplog.text and "secret text" not in caplog.text


def test_twilio_download_uses_basic_auth_and_enforces_the_size_cap(monkeypatch):
    class Stream:
        def __init__(self, data, headers=None):
            self.data, self.headers = data, headers or {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield from (self.data[i : i + 1000] for i in range(0, len(self.data), 1000))

    calls = {}

    def fake_stream(method, url, auth=None, follow_redirects=None, timeout=None):
        calls.update(method=method, url=url, auth=auth, redirects=follow_redirects)
        return Stream(b"a" * 3000)

    monkeypatch.setattr(httpx, "stream", fake_stream)
    p = TwilioProvider("ACabc", "tok")
    assert p.download("https://api.twilio.com/media/1", 5000) == b"a" * 3000
    assert calls == {"method": "GET", "url": "https://api.twilio.com/media/1", "auth": ("ACabc", "tok"), "redirects": True}
    with pytest.raises(MediaTooLarge):
        p.download("https://api.twilio.com/media/1", 2000)
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    with pytest.raises(MediaUnavailable):
        p.download("https://x", 100)
