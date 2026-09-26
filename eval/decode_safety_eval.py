"""Catch rate and FALSE-ALARM rate of the voice safety net on the synthetic domain set (the set the margins are tuned on, D41).

    python eval/decode_safety_eval.py

catch rate         risky rows: the transcript has a different real word at a critical word. Caught = the net rewrote it to the intended word, or asked a
                   clarifying question whose options include the intended word. A rewrite to some OTHER word is counted separately (harmful).
false-alarm rate   control and benign rows (already correct): any rewrite or any question at all. Reported as rewrites (the worse kind) and questions.
Both are reported per accent. The false-alarm rate is a headline number.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from steve_engine.decode.safety import SafetyConfig, review_transcript
from steve_engine.decode.tokens import tokenize


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def intended_word(row: dict) -> str | None:
    """The word that should stand where the risky transcript has a different one."""
    a, b = [t.norm for t in tokenize(row["transcript"])], [t.norm for t in tokenize(row["intended"])]
    if len(a) != len(b):
        return None
    diff = [y for x, y in zip(a, b, strict=True) if x != y]
    return diff[0] if len(diff) == 1 else None


def judge_risky(row: dict, review) -> str:
    want = intended_word(row)
    if want is None:
        return "unjudged"
    spans_target = lambda s: s.text.lower() == row["target"].lower()
    for c in review.changes:
        if spans_target(c.span):
            return "caught_rewrite" if c.meant == want else "wrong_rewrite"
    for q in review.clarify:
        if spans_target(q.span):
            return "caught_clarify" if want in q.options else "clarify_without_answer"
    return "missed"


def evaluate_voice(rows: list[dict], cfg: SafetyConfig | None = None) -> dict:
    out = {"risky": defaultdict(Counter), "clean": defaultdict(Counter)}
    for r in rows:
        acc = r["accent"]
        review = review_transcript(r["transcript"], None if acc == "none" else acc, cfg)
        if r["kind"] == "risky":
            v = judge_risky(r, review)
            for key in (acc, "all"):
                out["risky"][key][v] += 1
                out["risky"][key]["n"] += 1
        else:
            for key in (acc, "all"):
                c = out["clean"][key]
                c["n"] += 1
                c["rewrite"] += bool(review.changes)
                c["question"] += bool(review.clarify)
                c["any"] += bool(review.changes or review.clarify)
    return out


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "n/a"


def table(result: dict) -> str:
    lines = ["| Accent | Risky words | Caught by rewrite | Caught by question | Catch rate | Wrong rewrite | Missed | Clean sentences | False rewrites | False questions | False-alarm rate |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for a in sorted(k for k in result["risky"] if k != "all") + ["all"]:
        r, c = result["risky"][a], result["clean"][a]
        caught = r["caught_rewrite"] + r["caught_clarify"]
        lines.append(f"| {a} | {r['n']} | {r['caught_rewrite']} | {r['caught_clarify']} | {pct(caught, r['n'])} | {r['wrong_rewrite']} | {r['missed'] + r['clarify_without_answer']} | "
                     f"{c['n']} | {c['rewrite']} | {c['question']} | {pct(c['any'], c['n'])} |")
    return "\n".join(lines)


def main() -> None:
    rows = load(ROOT / "data" / "decode" / "voice_synthetic.csv")
    result = evaluate_voice(rows)
    print(f"Synthetic voice set: {len(rows)} rows (synthetic=true; the set the margins were tuned on)\n")
    print(table(result))


if __name__ == "__main__":
    main()
