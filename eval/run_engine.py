"""Run the deterministic engine over every reply -> eval/results/engine_predictions.json"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESULTS, dump, load_messages, load_replies
from samjha_engine import check_reply


def main() -> None:
    messages = load_messages()
    replies = load_replies()
    if not replies:
        sys.exit("data/replies.csv is empty. Run: python eval/generate.py")
    preds: dict[str, dict] = {}
    t0 = time.perf_counter()
    for r in replies:
        facts = messages[r["message_id"]]["facts"]
        res1 = check_reply(facts, r["reply_text"])
        res2 = check_reply(facts, r["reply_text"])
        assert [x.model_dump() for x in res1] == [x.model_dump() for x in res2], "engine must be deterministic"
        preds[r["reply_id"]] = {
            x.fact_id: {"status": x.status.value, "reason": x.reason, "confidence": x.confidence} for x in res1
        }
    dt = time.perf_counter() - t0
    dump(RESULTS / "engine_predictions.json", preds)
    print(f"engine: {len(preds)} replies in {dt:.2f}s ({dt / len(preds) * 1000:.2f} ms/reply), deterministic -> engine_predictions.json")


if __name__ == "__main__":
    main()
