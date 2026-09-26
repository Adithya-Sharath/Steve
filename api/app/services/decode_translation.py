"""Seam for Phase 5 (translation of the settled English card). Until then: English only, with a note when a language was asked for."""

from __future__ import annotations

from steve_engine.decode import DecodedCard

from ..schemas import TranslatedCard


def translate_for(card: DecodedCard, language: str | None) -> tuple[TranslatedCard | None, list[str]]:
    if not language or language == "en":
        return None, []
    return None, ["Translation isn't available right now, showing English."]


def availability() -> dict:
    return {"available": False, "providers": []}
