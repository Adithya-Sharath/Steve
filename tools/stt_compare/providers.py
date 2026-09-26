"""Pluggable speech-to-text providers for the reality test.

To add one: subclass `Provider`, implement `available()`, `variants()` and `transcribe()`, and register it in `PROVIDERS`.
Every provider must (a) be silent about keys, (b) raise `ProviderError` with a short message on failure, never a key.

Read the provider's CURRENT docs before changing request parameters (checked 2026-09-26):
  Sarvam  https://docs.sarvam.ai/api-reference-docs/speech-to-text/transcribe  (REST, audio up to 30 s)
  Gemini  https://ai.google.dev/gemini-api/docs/audio
Neither returns word-level confidence or alternatives, so the report cannot use them; it says so.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

SARVAM_URL = "https://api.sarvam.ai/speech-to-text"
MIME = {
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".mp4": "audio/mp4", ".ogg": "audio/ogg", ".opus": "audio/ogg",
    ".webm": "audio/webm", ".flac": "audio/flac", ".aac": "audio/aac", ".amr": "audio/amr", ".wma": "audio/x-ms-wma",
}


class ProviderError(Exception):
    pass


@dataclass(frozen=True)
class Variant:
    provider: str
    label: str  # shown in the report, e.g. "sarvam saaras:v3 / verbatim / en-IN"
    params: dict = field(default_factory=dict, hash=False)


@dataclass
class Transcript:
    text: str
    extra: dict = field(default_factory=dict)


class Provider:
    name = "base"

    def available(self) -> bool:  # key present?
        raise NotImplementedError

    def variants(self, spec: str | None = None) -> list[Variant]:
        raise NotImplementedError

    def transcribe(self, audio: bytes, filename: str, variant: Variant) -> Transcript:
        raise NotImplementedError


def mime_for(filename: str) -> str:
    return MIME.get(Path(filename).suffix.lower(), "audio/mpeg")


class Sarvam(Provider):
    """Sarvam `POST /speech-to-text`: fields file, model (saaras:v3 | saaras:v4), mode (saaras:v3 only: transcribe | translate |
    verbatim | translit | codemix), language_code (en-IN ... or `unknown` = auto-detect). `verbatim` is documented as word for
    word without normalisation; `transcribe` normalises numbers and formatting."""

    name = "sarvam"
    # a spec is a comma list of `model|mode|language`; the model id itself contains a colon, hence the pipes
    DEFAULT_SPEC = ("saaras:v3|transcribe|en-IN,saaras:v3|transcribe|unknown,saaras:v3|verbatim|en-IN,saaras:v3|verbatim|unknown,"
                    "saaras:v4||en-IN,saaras:v4||unknown")
    QUICK_SPEC = "saaras:v3|transcribe|en-IN,saaras:v3|verbatim|en-IN"

    def __init__(self, key: str | None = None):
        self.key = key if key is not None else os.getenv("SARVAM_API_KEY", "")

    def available(self) -> bool:
        return bool(self.key)

    def variants(self, spec: str | None = None) -> list[Variant]:
        """spec = comma list of `model|mode|language`; an empty mode sends no `mode` field (v4 has none documented)."""
        out = []
        for item in (spec or self.DEFAULT_SPEC).split(","):
            parts = item.strip().split("|")
            if len(parts) != 3 or not parts[0] or not parts[2]:
                raise ProviderError(f"bad Sarvam variant {item!r}: use model|mode|language, e.g. saaras:v3|verbatim|en-IN")
            model, mode, lang = parts
            label = f"sarvam {model} / {mode or 'default'} / {lang}"
            out.append(Variant("sarvam", label, {"model": model, "mode": mode, "language_code": lang}))
        return out

    def transcribe(self, audio: bytes, filename: str, variant: Variant) -> Transcript:
        p = variant.params
        data = {"model": p["model"], "language_code": p["language_code"]}
        if p.get("mode"):
            data["mode"] = p["mode"]
        last = "no attempt"
        for attempt in range(3):
            try:
                r = httpx.post(SARVAM_URL, headers={"api-subscription-key": self.key},
                               files={"file": (filename, audio, mime_for(filename))}, data=data, timeout=60.0)
            except httpx.HTTPError as e:
                last = type(e).__name__
            else:
                if r.status_code == 200:
                    body = r.json()
                    return Transcript((body.get("transcript") or "").strip(), {"language_code": body.get("language_code"),
                                                                                "language_probability": body.get("language_probability")})
                last = f"HTTP {r.status_code}: {r.text[:160].replace(self.key, '***') if self.key else r.text[:160]}"
                if r.status_code not in (429, 500, 502, 503, 504):
                    break
            time.sleep(2.0 * (attempt + 1))
        raise ProviderError(last)


class Gemini(Provider):
    """Optional second opinion: Gemini audio understanding asked to transcribe EXACTLY as spoken. Experimental (its behaviour
    on accented speech is part of what we are testing). Uses the classic `generate_content` with an inline audio part."""

    name = "gemini"
    PROMPT = ("Transcribe this audio exactly as spoken, word for word, in Roman letters. Do NOT correct pronunciation, grammar or "
              "word choice, do NOT translate, and do not add anything. If a word sounds like 'barking' write barking even if "
              "'parking' would make more sense. Output only the transcript.")

    def __init__(self, key: str | None = None, model: str | None = None):
        self.key = key if key is not None else os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    def available(self) -> bool:
        return bool(self.key)

    def variants(self, spec: str | None = None) -> list[Variant]:
        return [Variant("gemini", f"gemini {self.model} / verbatim prompt", {"model": self.model})]

    def transcribe(self, audio: bytes, filename: str, variant: Variant) -> Transcript:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.key, http_options=types.HttpOptions(timeout=60_000))
            resp = client.models.generate_content(
                model=variant.params["model"],
                contents=[self.PROMPT, types.Part.from_bytes(data=audio, mime_type=mime_for(filename))],
                config=types.GenerateContentConfig(temperature=0),
            )
            return Transcript((resp.text or "").strip())
        except Exception as e:  # noqa: BLE001 - reported per file, never fatal
            msg = f"{type(e).__name__}: {e}"
            raise ProviderError(msg.replace(self.key, "***")[:200] if self.key else msg[:200]) from e


PROVIDERS: dict[str, type[Provider]] = {"sarvam": Sarvam, "gemini": Gemini}
