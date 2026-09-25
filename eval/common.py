from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "eval" / "results"
CACHE = ROOT / "eval" / ".cache"
MESSAGES = DATA / "messages.json"
REPLIES = DATA / "replies.csv"
COLUMNS = ["reply_id", "message_id", "lang_mix", "reply_text", "gold_labels", "author", "synthetic"]
STATUSES = ["understood", "wrong", "missing", "negated", "unclear"]
NOT_UNDERSTOOD = {"wrong", "missing", "negated"}


def load_messages() -> dict[str, dict]:
    return {m["id"]: m for m in json.loads(MESSAGES.read_text(encoding="utf-8"))}


def load_replies() -> list[dict]:
    if not REPLIES.exists():
        return []
    with REPLIES.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["gold"] = json.loads(r["gold_labels"])
        r["synthetic"] = str(r.get("synthetic", "")).strip().lower() in ("true", "1", "yes")
    return rows


def write_replies(rows: list[dict]) -> None:
    REPLIES.parent.mkdir(parents=True, exist_ok=True)
    with REPLIES.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: (json.dumps(r[c], ensure_ascii=False) if c == "gold_labels" and not isinstance(r[c], str) else r[c]) for c in COLUMNS})


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
