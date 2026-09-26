"""Optional speech-to-text behind an interface, so typed replies always work.

Sarvam Saaras (per https://docs.sarvam.ai, REST reference):
  POST https://api.sarvam.ai/speech-to-text      header  api-subscription-key: <key>
  multipart fields: file, model (saaras:v3), mode (transcribe|translate|verbatim|translit|codemix), language_code (optional)
  response: {"request_id", "transcript", "language_code"}
  audio: WAV/MP3/AAC/FLAC/OGG, up to ~30 s per request.
We use mode="translit" (romanised text, NOT translation) so spoken numbers/words stay as the reader said them.
Audio is held in memory only for the request and is never written to disk or the database.
"""

from __future__ import annotations

from typing import Protocol

import httpx

from ..settings import settings

SARVAM_URL = "https://api.sarvam.ai/speech-to-text"  # the default; the call uses settings.sarvam_base_url
LANG_CODES = {"ml": "ml-IN", "hi": "hi-IN", "en": "en-IN"}  # Sarvam covers Indian languages only


class STTUnavailable(Exception):
    pass


class SpeechToText(Protocol):
    enabled: bool

    def transcribe(self, audio: bytes, content_type: str, lang_hint: str | None = None) -> str: ...


class NullSpeechToText:
    enabled = False

    def transcribe(self, audio: bytes, content_type: str, lang_hint: str | None = None) -> str:
        raise STTUnavailable("Voice replies are not enabled on this server; please type your reply.")


class SarvamSTT:
    enabled = True

    def __init__(self, api_key: str, model: str = "saaras:v3", mode: str = "translit", timeout: float = 30.0):
        self.api_key, self.model, self.mode, self.timeout = api_key, model, mode, timeout

    def transcribe(self, audio: bytes, content_type: str, lang_hint: str | None = None) -> str:
        ext = "wav" if "wav" in content_type else "ogg" if "ogg" in content_type else "webm" if "webm" in content_type else "mp3"
        data = {"model": self.model, "mode": self.mode}
        if lang_hint in LANG_CODES:
            data["language_code"] = LANG_CODES[lang_hint]
        try:
            r = httpx.post(
                f"{settings.sarvam_base_url}/speech-to-text",
                headers={"api-subscription-key": self.api_key},
                files={"file": (f"reply.{ext}", audio, content_type or "audio/wav")},
                data=data,
                timeout=self.timeout,
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise STTUnavailable(f"Speech service error: {type(e).__name__}") from e
        return (r.json().get("transcript") or "").strip()


def get_decode_stt() -> SpeechToText:
    """Decode wants what was SAID, in the speaker's own English: Sarvam `saaras:v3`, mode `transcribe`, `en-IN` (D37, D40). Not `translit`."""
    if settings.stt_enabled:
        return SarvamSTT(settings.sarvam_api_key, mode="transcribe")
    return NullSpeechToText()


def get_stt() -> SpeechToText:
    if settings.stt_enabled:
        return SarvamSTT(settings.sarvam_api_key)
    return NullSpeechToText()
