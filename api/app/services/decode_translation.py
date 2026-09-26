"""Translation of the settled English card (D46). Thin seam between the API routes and `translate.service`."""

from __future__ import annotations

from steve_engine.decode import DecodedCard

from ..schemas import TranslatedCard
from . import translate


def translate_for(card: DecodedCard, language: str | None) -> tuple[TranslatedCard | None, list[str]]:
    return translate.service.translate(card, language)


def availability() -> dict:
    return translate.availability()
