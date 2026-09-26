"""Demo-friendly examples for `GET /decode/examples` (D47): a few fixed INPUTS, and for each the card the engine returns RIGHT NOW.

The inputs are fixed text; the outputs are computed on every request by `decode()` and never hard-coded, so an engine change shows up here at once.
Nothing is stored and no clarify state is created (`decode_id` is null): to play with a question, send the example's `request` to `POST /decode`.
"""

from __future__ import annotations

from steve_engine.decode import decode

from ..schemas import DecodeExample, DecodeIn, DecodeResponse
from .decode_flow import say_back

# (id, label, text, accent_hint)
EXAMPLES: list[tuple[str, str, str, str | None]] = [
    ("al-quoz-maghrib", "Drop it at Al Quoz before Maghrib", "Yalla, drop it at Al Quoz before Maghrib. No signature, just call the guy.", None),
    ("barking-gate-tree", "Barking gate tree (Arabic speaker)", "yalla habibi come to the barking gate tree", "ar"),
    ("dont-come-khalas", "Don't come, khalas", "don't come to the barking now, khalas", "ar"),
    ("bebsi", "Bring the bebsi", "bring the bebsi from the fridge", "ar"),
    ("parking-or-building", "A question, not a guess", "come to the barking or the building?", "ar"),
    ("wery-good-fife", "Wery good, come at fife (Hindi speaker)", "wery good, come at fife", "hi"),
]


def build_examples() -> list[DecodeExample]:
    out = []
    for id_, label, text, hint in EXAMPLES:
        card = decode(text, hint, "typed")
        out.append(DecodeExample(id=id_, label=label, request=DecodeIn(text=text, accent_hint=hint), response=DecodeResponse(card=card, say_back=say_back(card))))
    return out
