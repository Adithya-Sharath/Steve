"""Loader and validator for `typed_truth.csv`: messages TYPED by ear (WhatsApp-style), with what they meant. This is the truth file for the typed-text
path of the decoder (full sound-swap decoding); the voice path is evaluated with `truth.csv` and the L2-ARCTIC runs.

Columns: text_as_typed, intended_meaning, accent, source, notes
  text_as_typed     the message exactly as the person typed it (spelling by ear, slang and all)
  intended_meaning  what they meant, in plain English
  accent            ar, hi, ml, tl, bn, ur or other (the writer's background)
  source            handwritten | whatsapp-screenshot | synthetic | synthetic-example (rows whose source starts with "synthetic" are synthetic=true)
  notes             optional

PRIVACY: real messages must be anonymised before they go in this file. Names, phone numbers, e-mail addresses, links and building/flat numbers that
identify a person are replaced with placeholders (for example [NAME], [PHONE]). `validate()` rejects rows that look like they still contain a phone
number, e-mail address or link. Nothing here is ever sent to a service by this module.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

COLUMNS = ["text_as_typed", "intended_meaning", "accent", "source", "notes"]
ACCENTS = {"ar", "hi", "ml", "tl", "bn", "ur", "other"}
SOURCES = {"handwritten", "whatsapp-screenshot", "synthetic", "synthetic-example"}
_PHONE = re.compile(r"(?<![\w.])(?:\+?\d[\d\s().-]{8,}\d)(?!\w)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_LINK = re.compile(r"(?:https?://|www\.)\S+", re.I)
DEFAULT = Path(__file__).resolve().parent / "typed_truth.csv"


@dataclass(frozen=True)
class TypedRow:
    text_as_typed: str
    intended_meaning: str
    accent: str
    source: str
    notes: str

    @property
    def synthetic(self) -> bool:
        return self.source.startswith("synthetic")


def validate(row: dict, line: int) -> list[str]:
    problems = []
    for col in ("text_as_typed", "intended_meaning"):
        if not (row.get(col) or "").strip():
            problems.append(f"line {line}: {col} is empty")
    if (row.get("accent") or "").strip() not in ACCENTS:
        problems.append(f"line {line}: accent {row.get('accent')!r} is not one of {sorted(ACCENTS)}")
    if (row.get("source") or "").strip() not in SOURCES:
        problems.append(f"line {line}: source {row.get('source')!r} is not one of {sorted(SOURCES)}")
    blob = " ".join(str(row.get(c) or "") for c in COLUMNS)
    for label, rx in (("phone number", _PHONE), ("e-mail address", _EMAIL), ("link", _LINK)):
        if rx.search(blob):
            problems.append(f"line {line}: looks like it contains a {label}; anonymise it (for example [PHONE])")
    return problems


def load(path: Path = DEFAULT) -> tuple[list[TypedRow], list[str]]:
    """-> (valid rows, problems). Bad rows are reported and skipped, never guessed at."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path.name} is missing columns {missing}; expected {COLUMNS}")
        rows, problems = [], []
        for i, raw in enumerate(reader, start=2):
            if not any((v or "").strip() for v in raw.values()):
                continue
            bad = validate(raw, i)
            if bad:
                problems += bad
                continue
            rows.append(TypedRow(*[(raw.get(c) or "").strip() for c in COLUMNS]))
    return rows, problems
