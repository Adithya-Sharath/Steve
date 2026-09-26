"""LLM baseline: ask Gemini for a per-fact status (strict JSON), several runs per item to measure consistency.

Fair setup: the baseline is given the message, the gold fact list, and the reply, plus the same five status
definitions we use. Responses are cached on disk (eval/.cache/baseline), so an interrupted run resumes where it stopped.
Without a key it skips gracefully and writes {"available": false} so the web page shows "baseline not run" instead of
inventing numbers.

Free-tier friendly: calls are sequential and paced (`--rpm`), the server's "retry in Ns" is honoured, and a DAILY quota
stops the run cleanly. Whatever finished is written out (partial coverage is reported by metrics.py, never hidden).

    python eval/run_baseline.py [--runs 5] [--synthetic-sample 120] [--limit N] [--rpm 4]
    GEMINI_MODEL=gemini-3.5-flash python eval/run_baseline.py --runs 3 --synthetic-sample 40
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    CACHE,
    RESULTS,
    STATUSES,
    dump,
    load_messages,
    load_replies,
)

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


class DailyQuotaExhausted(Exception):
    pass


def fact_line(f: dict) -> str:
    v = f["value"]
    if isinstance(v, dict):
        v = f"if {v['trigger']}: {v['action']}" if v["action"] != "avoid" else f"do not {v['trigger']}"
    return f"- {f['id']}: {f['label']} ({f['type']} = {v}{' ' + f['unit'] if f.get('unit') else ''})"


def call_gemini(client, model: str, prompt: str) -> dict:
    from google.genai import types

    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7),
    )
    return json.loads(resp.text)


def retry_delay_seconds(message: str, default: float = 15.0) -> float:
    m = re.search(r"retry(?:Delay)?[^0-9]{0,12}([0-9]+(?:[.][0-9]+)?)\s*s", message)
    return float(m.group(1)) + 1.0 if m else default


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--synthetic-sample", type=int, default=120, help="how many synthetic replies to include (all hand-written always)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rpm", type=float, default=4.0, help="max requests per minute (free tier is often 5)")
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

    cache_dir = CACHE / "baseline"
    cache_dir.mkdir(parents=True, exist_ok=True)
    spacing = 60.0 / args.rpm
    state = {"last_call": 0.0, "calls": 0, "failed": 0}

    def fetch(r: dict, run: int) -> dict | None:
        msg = messages[r["message_id"]]
        prompt = PROMPT.format(message=msg["text"], facts="\n".join(fact_line(f) for f in msg["facts"]), reply=r["reply_text"])
        h = hashlib.sha256(f"{model}|{run}|{prompt}".encode()).hexdigest()[:24]
        path = cache_dir / f"{h}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        for _attempt in range(6):
            wait = spacing - (time.monotonic() - state["last_call"])
            if wait > 0:
                time.sleep(wait)
            state["last_call"] = time.monotonic()
            try:
                data = call_gemini(client, model, prompt)
                state["calls"] += 1
                path.write_text(json.dumps(data), encoding="utf-8")
                return data
            except Exception as e:  # noqa: BLE001
                text = str(e)
                if "PerDay" in text:
                    raise DailyQuotaExhausted(text[:300]) from e
                if "429" in text or "RESOURCE_EXHAUSTED" in text or "503" in text:
                    time.sleep(retry_delay_seconds(text))
                    continue
                print(f"  {r['reply_id']} run {run}: {type(e).__name__}: {text[:160]}", file=sys.stderr)
                break
        state["failed"] += 1
        return None

    jobs = [(r, k) for r in items for k in range(args.runs)]
    print(f"baseline: {len(items)} replies x {args.runs} runs = {len(jobs)} calls to {model} at <= {args.rpm:g}/min (cached where possible)", flush=True)
    runs: dict[str, dict[int, dict]] = {}
    stopped = None
    try:
        for i, (r, run) in enumerate(jobs, 1):
            data = fetch(r, run)
            if data is not None:
                runs.setdefault(r["reply_id"], {})[run] = {k: (v if v in STATUSES else "unclear") for k, v in data.items() if isinstance(v, str)}
            if i % 20 == 0:
                print(f"  {i}/{len(jobs)} done ({state['calls']} new calls, {state['failed']} failed)", flush=True)
    except DailyQuotaExhausted as e:
        stopped = "daily quota exhausted"
        print(f"baseline: STOPPED, daily free-tier quota exhausted for {model}. Rerun later; cached calls are kept.\n  {e}", file=sys.stderr)
    except KeyboardInterrupt:
        stopped = "interrupted"
    complete = sum(1 for r in items if len(runs.get(r["reply_id"], {})) == args.runs)
    dump(
        out,
        {
            "available": bool(runs),
            "model": model,
            "runs": args.runs,
            "n_replies": len(runs),
            "n_replies_complete": complete,
            "n_replies_planned": len(items),
            "stopped": stopped,
            "predictions": runs,
        },
    )
    print(f"baseline: wrote {len(runs)} replies ({complete} with all {args.runs} runs, {len(items)} planned) -> baseline_predictions.json", flush=True)


if __name__ == "__main__":
    main()
