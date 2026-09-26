"""Decode: an interpreter for the English a worker actually hears or types (D36, D40, D41)."""

from .decoder import decode, inspect_decode
from .schema import DecodedCard

__all__ = ["DecodedCard", "decode", "inspect_decode"]
