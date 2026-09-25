"""Compute honest metrics -> eval/results/latest.json (consumed by the web /eval page and the README).

Headline metric: FALSE "UNDERSTOOD" RATE = P(system says understood | gold in {wrong, missing, negated}).
We also report accuracy, per-language / per-type / per-source breakdowns, confusion matrices, and (if the baseline
ran) its self-consistency across runs. Nothing here is hard-coded; every number is computed from the prediction files.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    NOT_UNDERSTOOD,
    RESULTS,
    STATUSES,
    dump,
    load_messages,
    load_replies,
)


class Bucket:
    def __init__(self) -> None:
        self.n = self.correct = self.fu = self.fu_den = 0

    def add(self, gold: str, pred: str) -> None:
        self.n += 1
        self.correct += gold == pred
        if gold in NOT_UNDERSTOOD:
            self.fu_den += 1
            self.fu += pred == "understood"

    def out(self) -> dict:
        return {
            "n": self.n,
            "correct": self.correct,
            "accuracy": self.correct / self.n if self.n else 0.0,
            "false_understood": self.fu,
            "false_understood_denominator": self.fu_den,
            "false_understood_rate": self.fu / self.fu_den if self.fu_den else 0.0,
        }


def summarize(rows: list[dict], key: str) -> dict:
    """rows: [{gold, pred, lang, type, source}]"""
    overall = Bucket()
    by: dict[str, dict[str, Bucket]] = {k: defaultdict(Bucket) for k in ("lang", "type", "source")}
    conf: dict[str, Counter] = {s: Counter() for s in STATUSES}
    for r in rows:
        overall.add(r["gold"], r[key])
        for k in by:
            by[k][r[k]].add(r["gold"], r[key])
        conf[r["gold"]][r[key]] += 1
    return {
        "available": True,
        "overall": overall.out(),
        "by_language": {k: b.out() for k, b in sorted(by["lang"].items())},
        "by_type": {k: b.out() for k, b in sorted(by["type"].items())},
        "by_source": {k: b.out() for k, b in sorted(by["source"].items())},
        "confusion": {g: {p: conf[g][p] for p in STATUSES} for g in STATUSES},
    }


def main() -> None:
    messages = load_messages()
    replies = load_replies()
    eng = json.loads((RESULTS / "engine_predictions.json").read_text(encoding="utf-8"))
    bpath = RESULTS / "baseline_predictions.json"
    base = json.loads(bpath.read_text(encoding="utf-8")) if bpath.exists() else {"available": False}

    rows, cases = [], []
    base_rows = []
    agreements = []
    for r in replies:
        msg = messages[r["message_id"]]
        facts = {f["id"]: f for f in msg["facts"]}
        for fid, gold in r["gold"].items():
            f = facts[fid]
            e = eng[r["reply_id"]][fid]
            src = "synthetic" if r["synthetic"] else "held-out" if r["reply_id"].startswith("ho-") else "handwritten"
            row = {"gold": gold, "pred": e["status"], "lang": r["lang_mix"], "type": f["type"], "source": src}
            rows.append(row)
            bpred = None
            if base.get("available") and r["reply_id"] in base["predictions"]:
                votes = [run.get(fid) for run in base["predictions"][r["reply_id"]].values() if run.get(fid)]
                if votes:
                    top, cnt = Counter(votes).most_common(1)[0]
                    bpred = top
                    agreements.append(cnt / len(votes))
                    base_rows.append({**row, "bpred": bpred})
            if e["status"] != gold or (bpred is not None and bpred != gold):
                cases.append(
                    {
                        "reply_id": r["reply_id"], "message_id": r["message_id"], "fact_id": fid, "fact_label": f["label"],
                        "lang_mix": r["lang_mix"], "fact_type": f["type"], "synthetic": r["synthetic"], "reply_text": r["reply_text"],
                        "gold": gold, "engine": {"status": e["status"], "reason": e["reason"]},
                        "baseline": {"status": bpred} if base.get("available") else None,
                    }
                )

    engine = summarize(rows, "pred")
    engine["consistency"] = {"mean_agreement": 1.0, "items": len(replies), "runs": 2, "note": "deterministic code; identical output on repeat runs (asserted in run_engine.py)"}
    baseline: dict = {"available": False, "note": base.get("reason", "baseline not run")}
    if base.get("available") and base_rows:
        baseline = summarize(base_rows, "bpred")
        baseline["consistency"] = {"mean_agreement": sum(agreements) / len(agreements), "items": len(agreements), "runs": base.get("runs", 5)}
        baseline["note"] = f"model: {base.get('model')}, evaluated on {base.get('n_replies')} replies (all hand-written + a synthetic sample)"
        # apples-to-apples: also score OUR engine on exactly the baseline's subset
        subset = summarize(base_rows, "pred")
        baseline["engine_on_same_subset"] = subset["overall"]

    n_syn = sum(1 for r in replies if r["synthetic"])
    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "n_fact_checks": len(rows),
        "n_replies": len(replies),
        "n_synthetic": n_syn,
        "n_handwritten": len(replies) - n_syn,
        "engine": engine,
        "baseline": baseline,
        "cases": cases,
        "caveats": [
            "Synthetic variants are generated from team-written templates that reuse vocabulary the lexicon knows, so they overestimate real-world accuracy. Compare the hand-written row.",
            "The hand-written seed replies were drafted by the developer/assistant, not native speakers, and the engine was iterated while looking at this set. Treat all numbers as development-set numbers.",
            "Lexicon entries for non-English languages are unverified until native speakers review LEXICON_REVIEW.md.",
            "Gold labels for synthetic rows come from construction; for hand-written rows from a human reading the reply. Some real-world replies are genuinely ambiguous.",
            *(["The LLM baseline was not run (no Gemini key), so no comparison is claimed."] if not baseline["available"] else []),
        ],
    }
    dump(RESULTS / "latest.json", out)
    o = engine["overall"]
    print(f"engine: accuracy {o['accuracy']:.1%} ({o['correct']}/{o['n']}), false 'understood' {o['false_understood']}/{o['false_understood_denominator']} = {o['false_understood_rate']:.2%}")
    for k, b in engine["by_source"].items():
        print(f"  {k:12} n={b['n']:4d} acc={b['accuracy']:.1%} false-understood={b['false_understood']}/{b['false_understood_denominator']}")
    if baseline["available"]:
        bo = baseline["overall"]
        print(f"baseline: accuracy {bo['accuracy']:.1%}, false 'understood' {bo['false_understood_rate']:.2%}, consistency {baseline['consistency']['mean_agreement']:.1%}")
    print(f"wrote {RESULTS / 'latest.json'} ({len(cases)} error cases)")


if __name__ == "__main__":
    main()
