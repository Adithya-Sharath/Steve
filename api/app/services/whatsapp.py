"""The WhatsApp flow (D48): replies only, text only, nothing stored but a keyed hash of the number, the language choice and anonymous counts.

    webhook (signed, see routes/whatsapp.py) -> handle_incoming -> [onboarding | command | numbered answer | voice note | text | image] -> decode -> translate -> text replies

* The phone number is hashed at once (HMAC-SHA256 with WORKER_HASH_SECRET) and never logged or stored. Message text, transcripts and audio are never stored or
  logged: audio lives in memory for one speech-to-text call; an open question and the last English answer (for "EN") live in memory for 10 minutes.
* We only answer messages we receive (never message first, never join groups). Per-number limits: 20 per hour, 100 per day (env-configurable).
* Reply text is plain, in a fixed order, with emoji as icons (see `format_card`), split cleanly to stay under WhatsApp's 1,600-character limit.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlmodel import Session

from ..db import WorkerPref, get_engine
from ..ratelimit import DAY, Rule, limiter
from ..schemas import DecodeResponse
from ..settings import settings
from . import translate
from .audio import duration_seconds
from .decode_flow import respond, run_decode
from .decode_sessions import Session as ClarifySession
from .decode_sessions import store
from .messaging import Incoming, MediaTooLarge, MediaUnavailable, MessagingProvider

log = logging.getLogger("steve.whatsapp")  # numbers, message text and transcripts are never logged

LANG_ORDER = ["ml", "hi", "ur", "tl", "bn", "en"]  # the numbers 1 to 6 in the picker
LANG_NAMES = {"ml": "മലയാളം", "hi": "हिंदी", "ur": "اردو", "tl": "Tagalog", "bn": "বাংলা", "en": "English"}
ENGLISH_NAMES = {"malayalam": "ml", "hindi": "hi", "urdu": "ur", "tagalog": "tl", "filipino": "tl", "bengali": "bn", "bangla": "bn", "english": "en"}
MAX_PART = 1500  # Twilio allows 1,600 characters per message; leave room for the "(1/2)" marker
SAMPLE_TEXT = "yalla habibi come to the barking gate tree"
SAMPLE_HINT = "ar"
PRIVACY_EN = "I delete your voice notes after listening. Your boss can't see this chat."

PICKER = ("Hello! I'm Steve. I help you understand what people say to you.\n\nChoose your language: reply with a number.\n"
          + "\n".join(f"{i} {LANG_NAMES[c]}" for i, c in enumerate(LANG_ORDER, 1)))
HOWTO = "Now forward me a voice note (up to 30 seconds) or send me a message. Reply HELP any time."
HELP = ("Steve helps you understand what people say.\n"
        "- Forward or send a voice note (up to 30 seconds) or a message.\n"
        "- Reply 1, 2 or 3 to answer a question.\n"
        "- Reply LANGUAGE to change your language.\n"
        "- Reply EN to see the last answer in English.\n"
        "- Reply HELP to see this again.\n"
        "Steve does not save your voice notes or messages.")
IMAGE = "I can read voice notes and text for now."
VOICE_LONG = "That voice note is too long. Please send one up to 30 seconds."
VOICE_FAILED = "I couldn't listen to that voice note. Please try again, or type the message."
NOTHING = "I couldn't find anything to decode. Try again or send the message as text."
EXPIRED = "That question has expired. Please send the message again."
NO_LAST = "Send me a message first, then reply EN to see it in English."
ALREADY_EN = "Your language is English already."
GENERIC_ERROR = "I couldn't finish that. Please try again in a moment."
LIMIT_NOTICE = "You've sent a lot of messages. Please try again in a little while."


def worker_hash(sender: str) -> str:
    """Keyed hash of the digits of a WhatsApp address (`whatsapp:+9715...`). Same number, same hash; the number cannot be read back from it."""
    digits = re.sub(r"\D", "", sender)
    return hmac.new(settings.worker_hash_secret.encode("utf-8"), digits.encode("ascii"), hashlib.sha256).hexdigest()


# ---- small in-memory state (10 minutes, never on disk) ---------------------------------------------------------------------------------------------


@dataclass
class Conv:
    awaiting_language: bool = False
    decode_id: str | None = None  # an open question (its answers are kept by decode_sessions.store)
    options: list[str] = field(default_factory=list)
    last_english: str | None = None
    expires: float = 0.0


class ConvStore:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self._items: OrderedDict[str, Conv] = OrderedDict()
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._notified: dict[str, float] = {}
        self._lock = threading.Lock()

    def get(self, worker: str) -> Conv:
        now = self.clock()
        with self._lock:
            for k in [k for k, c in self._items.items() if c.expires <= now]:
                del self._items[k]
            conv = self._items.get(worker)
            if conv is None:
                conv = self._items[worker] = Conv()
                while len(self._items) > 5000:
                    self._items.popitem(last=False)
            conv.expires = now + settings.clarify_ttl_seconds
            return conv

    def duplicate(self, sid: str) -> bool:
        """The provider may deliver one message twice: answer it once."""
        if not sid:
            return False
        now = self.clock()
        with self._lock:
            for k in [k for k, t in self._seen.items() if now - t > 600]:
                del self._seen[k]
            if sid in self._seen:
                return True
            self._seen[sid] = now
            while len(self._seen) > 5000:
                self._seen.popitem(last=False)
            return False

    def should_notify(self, worker: str) -> bool:
        """One "you've sent a lot" notice per hour, so a flood cannot turn our replies into a flood."""
        now = self.clock()
        with self._lock:
            if now - self._notified.get(worker, -1e9) < 3600:
                return False
            self._notified[worker] = now
            return True

    def reset(self) -> None:
        with self._lock:
            self._items.clear()
            self._seen.clear()
            self._notified.clear()


convs = ConvStore()


# ---- what we keep: hash, language, counts -----------------------------------------------------------------------------------------------------------


def _get_pref(worker: str) -> WorkerPref | None:
    with Session(get_engine()) as s:
        return s.get(WorkerPref, worker)


def _save_pref(worker: str, *, language: str | None = None, decodes: int = 0, voice_notes: int = 0, create: bool = False) -> None:
    with Session(get_engine()) as s:
        row = s.get(WorkerPref, worker)
        if row is None:
            if not create:
                return
            row = WorkerPref(worker_hash=worker)
        if language is not None:
            row.language = language
        row.decodes += decodes
        row.voice_notes += voice_notes
        row.updated_at = datetime.now(UTC)
        s.add(row)
        s.commit()


# ---- text helpers -------------------------------------------------------------------------------------------------------------------------------------


def parse_language(text: str) -> str | None:
    t = text.strip().lower().strip(".!?")
    if t.isdigit() and 1 <= int(t) <= len(LANG_ORDER):
        return LANG_ORDER[int(t) - 1]
    for code, native in LANG_NAMES.items():
        if t == native.lower():
            return code
    return ENGLISH_NAMES.get(t) or ("en" if t == "en" else None)


def split_message(text: str, limit: int = MAX_PART) -> list[str]:
    """Split on line breaks so no message is cut in the middle of a line; a single overlong line is cut at a space. Parts are marked (1/2), (2/2)."""
    if len(text) <= limit:
        return [text]
    room = limit - 10  # the "(12/34)" marker and its line break are added to every part
    parts: list[str] = []
    cur = ""
    for line in text.split("\n"):
        while len(line) > room:
            cut = line.rfind(" ", 0, room)
            cut = room if cut <= 0 else cut
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(line[:cut])
            line = line[cut:].lstrip()
        if cur and len(cur) + 1 + len(line) > room:
            parts.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        parts.append(cur)
    n = len(parts)
    return parts if n == 1 else [f"({i}/{n})\n{p}" for i, p in enumerate(parts, 1)]


def format_card(resp: DecodeResponse, *, translated: bool = True) -> str:
    """The reply, in a fixed order. Empty lines are left out. The translated card comes first when there is one; "Reply EN" brings the English."""
    card = resp.card
    assert card is not None
    tr = resp.translation if translated else None
    a = card.actions
    lines: list[str] = []
    if a.where:
        lines.append(f"📍 Where: {a.where.value}")
    if a.when:
        lines.append(f"⏰ When: {tr.when if tr and tr.when else a.when.value}")
    if a.what:
        lines.append(f"✅ What: {tr.what if tr and tr.what else a.what.value}")
    if a.how_much:
        lines.append(f"💰 How much: {a.how_much.value}")
    if not lines:
        lines.append(f"📝 {tr.plain_english if tr else card.plain_english}")
    lines.append(f'💬 They said: "{card.original_text}"')
    for i, p in enumerate(card.phrases):
        literal = tr.phrases[i].literal if tr and i < len(tr.phrases) else p.literal
        lines.append(f"ℹ️ {p.phrase} = {literal}")
    if card.clarify:
        q = card.clarify[0]  # one question at a time; the next one appears after the answer
        lines.append(f"❓ {tr.questions[0] if tr and tr.questions else q.question}")
        opts = q.options
        lines.append("Reply " + ", ".join(f"{k} for {o.capitalize()}" for k, o in enumerate(opts, 1)) + f", {len(opts) + 1} if not sure")
    lines += [f"ℹ️ {n}" for n in resp.notes]
    if tr:
        lines.append("↩️ Reply EN for English")
    return "\n".join(lines)


def _english_after(resp: DecodeResponse) -> str:
    return format_card(resp, translated=False)


# ---- the flow -----------------------------------------------------------------------------------------------------------------------------------------


def _decode_reply(worker: str, conv: Conv, text: str, path: str, language: str) -> list[str]:
    session = ClarifySession(worker=worker, text=text, accent_hint=None, path=path, reply_language=None if language == "en" else language)
    card = run_decode(session)
    resp = respond(card, session=session, decode_id=None, transcript=text if path == "voice" else None, notes=[])
    conv.decode_id = resp.decode_id
    conv.options = list(card.clarify[0].options) if card.clarify else []
    conv.last_english = _english_after(resp)
    _save_pref(worker, decodes=1)
    return [format_card(resp)]


def _answer(worker: str, conv: Conv, k: int, language: str) -> list[str]:
    session = store.get(conv.decode_id, worker) if conv.decode_id else None
    if session is None:
        conv.decode_id, conv.options = None, []
        return [EXPIRED]
    card = run_decode(session)
    if not card.clarify:
        conv.decode_id, conv.options = None, []
        return [EXPIRED]
    q = card.clarify[0]
    n = len(q.options)
    if not 1 <= k <= n + 1:
        return [f"Please reply with a number from 1 to {n + 1}."]
    not_sure = k == n + 1
    session.resolved[q.span.start] = None if not_sure else q.options[k - 1]
    card = run_decode(session)
    resp = respond(card, session=session, decode_id=conv.decode_id, transcript=session.text if session.path == "voice" else None, notes=[])
    conv.decode_id = resp.decode_id
    conv.options = list(card.clarify[0].options) if card.clarify else []
    conv.last_english = _english_after(resp)
    out = format_card(resp)
    if not_sure:
        out += f"\nYou can show them this: {resp.say_back[0]}" if resp.say_back else ""
    return [out]


def _finish_language(worker: str, conv: Conv, lang: str) -> list[str]:
    """The language was chosen: confirm it, one privacy line in that language, one sample decode, how to use Steve."""
    conv.awaiting_language = False
    _save_pref(worker, language=lang, create=True)
    privacy = (translate.service.translate_lines([PRIVACY_EN], lang) or [PRIVACY_EN])[0]
    first = f"✅ {LANG_NAMES[lang]}\n{privacy}"
    from steve_engine.decode import decode

    card = decode(SAMPLE_TEXT, SAMPLE_HINT, "typed")
    session = ClarifySession(worker=worker, text=SAMPLE_TEXT, accent_hint=SAMPLE_HINT, path="typed", reply_language=None if lang == "en" else lang)
    sample = respond(card, session=session, decode_id=None, transcript=None, notes=[])
    return [first, "Here is an example. Someone says:\n\n" + format_card(sample), HOWTO]


def _voice(inc: Incoming, provider: MessagingProvider, worker: str, conv: Conv, language: str) -> list[str]:
    from ..routes import (
        decode as decode_routes,  # the same speech-to-text step (limits, budget, notes) as the API
    )

    url, ctype = next(m for m in inc.media if m[1].lower().startswith("audio/"))
    try:
        audio = provider.download(url, settings.decode_max_audio_bytes)
    except MediaTooLarge:
        return [VOICE_LONG]
    except MediaUnavailable:
        return [VOICE_FAILED]
    secs = duration_seconds(audio)
    if secs is not None and secs > settings.decode_max_audio_seconds:
        del audio
        return [VOICE_LONG]
    transcript, note = decode_routes._transcribe(audio, ctype)
    del audio  # the voice note is gone from memory as soon as it has been heard
    _save_pref(worker, voice_notes=1)
    if not transcript:
        return [note or NOTHING]
    return _decode_reply(worker, conv, transcript, "voice", language)


def build_replies(inc: Incoming, provider: MessagingProvider, worker: str) -> list[str]:
    pref = _get_pref(worker)
    conv = convs.get(worker)
    text = inc.body.strip()
    low = re.sub(r"[^\w\s]", "", text.lower()).strip()

    if pref is None:  # the first message from a new hashed number
        _save_pref(worker, create=True)
        conv.awaiting_language = True
        return [PICKER]
    if conv.awaiting_language or pref.language is None:
        lang = parse_language(text)
        if lang is None:
            conv.awaiting_language = True
            return [PICKER]
        return _finish_language(worker, conv, lang)
    language = pref.language

    if low in {"help", "hi", "hello", "start", "menu"}:
        return [HELP]
    if low in {"language", "change language", "lang", "languages"}:
        conv.awaiting_language = True
        return [PICKER]
    if low in {"en", "english"}:
        return [conv.last_english] if conv.last_english else [ALREADY_EN if language == "en" else NO_LAST]
    if conv.decode_id and low.isdigit():
        return _answer(worker, conv, int(low), language)

    if any(m[1].lower().startswith("audio/") for m in inc.media):
        return _voice(inc, provider, worker, conv, language)
    if inc.media:
        return [IMAGE]
    if not text:
        return [HELP]
    return _decode_reply(worker, conv, text, "typed", language)


def handle_incoming(inc: Incoming, provider: MessagingProvider) -> None:
    """Process one signed inbound message and send the replies. Never raises (it runs after the webhook has answered) and never logs the number or the text."""
    try:
        if convs.duplicate(inc.sid):
            return
        worker = worker_hash(inc.sender)
        if limiter.check("whatsapp", worker, [Rule(settings.wa_per_number_hour, 3600.0), Rule(settings.wa_per_number_day, DAY)]):
            replies = [LIMIT_NOTICE] if convs.should_notify(worker) else []
        else:
            replies = build_replies(inc, provider, worker)
    except Exception as e:  # noqa: BLE001 - a background task must not die silently or leak text in a traceback
        log.error("whatsapp handling failed: %s", type(e).__name__)
        replies = [GENERIC_ERROR]
    for reply in replies:
        for part in split_message(reply, MAX_PART):
            try:
                provider.send(inc.sender, inc.to, part)
            except Exception as e:  # noqa: BLE001
                log.warning("whatsapp reply not sent: %s", type(e).__name__)
                return
