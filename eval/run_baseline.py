"""LLM baseline: ask Gemini for a per-fact status (strict JSON), 5 runs per item to measure consistency.

Fair setup: the baseline is given the message, the gold fact list, and the reply, plus the same five status
definitions we use. Responses are cached on disk (eval/.cache/baseline). Without a key it skips gracefully and
writes {"available": false} so the web page shows "baseline not run" instead of inventing numbers.

    python eval/run_baseline.py [--runs 5] [--synthetic-sample 120] [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, RESULTS, STATUSES, dump, load_messages, load_replies  # noqa: E402

try:  # pick up GEMINI_API_KEY from .env like the API does
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

PROMPT = """You are grading whether a reader understood a message, fact by fact.

MESSAGE the sender wrote:
\"\"\"{message}\"\"\"

KEY FACTS (id: what the message means):
{facts}

The READER replied (may mix languages, romanized, spelled by ear):
\"\"\"{reply}\"\"\"

For EVERY fact id give one status:
- understood: the reply states this fact correctly
- wrong: the reply states a different value
- missing: the reply does not mention it
- negated: the reply says the opposite / negates it (e.g. "don't stop")
- unclear: you cannot tell
Return ONLY a JSON object mapping each fact id to its status."""


def fact_line(f: dict) -> str:
    v = f["value"]
    if isinstance(v, dict):
        v = f"if {v['trigger']}: {v['action']}" if v["action"] != "avoid" else f"do not {v['trigger']}"
    return f"- {f['id']}: {f['label']} ({f['type']} = {v}{' ' + f['unit'] if f.get('unit') else ''})"


def call_gemini(client, model: str, prompt: str) -> dict:
    from google.genai import types

    resp = client.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7),
    )
    return json.loads(resp.text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--synthetic-sample", type=int, default=120, help="how many synthetic replies to include (all hand-written always)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    out = RESULTS / "baseline_predictions.json"

    key = os.getenv("GEMINI_API_KEY", "")
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    if not key:
        dump(out, {"available": False, "reason": "GEMINI_API_KEY not set; baseline skipped"})
        print("baseline: no GEMINI_API_KEY, skipped (results will say 'baseline not run').")
        return
    try:
        from google import genai
    except ImportError:
        dump(out, {"available": False, "reason": "google-genai not installed"})
        print("baseline: google-genai missing, skipped.")
        return

    client = genai.Client(api_key=key)
    messages = load_messages()
    replies = load_replies()
    hand = [r for r in replies if not r["synthetic"]]
    syn = [r for r in replies if r["synthetic"]]
    random.Random(7).shuffle(syn)
    items = hand + syn[: args.synthetic_sample]
    if args.limit:
        items = items[: args.limit]

    CACHE.joinpath("baseline").mkdir(parents=True, exist_ok=True)

    def one(job: tuple[dict, int]) -> tuple[str, int, dict | None]:
        r, run = job
        msg = messages[r["message_id"]]
        prompt = PROMPT.format(message=msg["text"], facts="\n".join(fact_line(f) for f in msg["facts"]), reply=r["reply_text"])
        h = hashlib.sha256(f"{model}|{run}|{prompt}".encode()).hexdigest()[:24]
        path = CACHE / "baseline" / f"{h}.json"
        if path.exists():
            return r["reply_id"], run, json.loads(path.read_text(encoding="utf-8"))
        for attempt in range(4):
            try:
                data = call_gemini(client, model, prompt)
                path.write_text(json.dumps(data), encoding="utf-8")
                return r["reply_id"], run, data
            except Exception as e:  # noqa: BLE001
                time.sleep(2**attempt)
                err = e
        print(f"  failed {r['reply_id']} run {run}: {err}", file=sys.stderr)
        return r["reply_id"], run, None

    jobs = [(r, k) for r in items for k in range(args.runs)]
    print(f"baseline: {len(items)} replies x {args.runs} runs = {len(jobs)} calls to {model} (cached where possible)")
    runs: dict[str, dict[int, dict]] = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for rid, run, data in ex.map(one, jobs):
            if data is not None:
                runs.setdefault(rid, {})[run] = {k: (v if v in STATUSES else "unclear") for k, v in data.items() if isinstance(v, str)}
    dump(out, {"available": True, "model": model, "runs": args.runs, "n_replies": len(runs), "predictions": runs})
    print(f"baseline: wrote {len(runs)} replies -> baseline_predictions.json")


if __name__ == "__main__":
    main()
