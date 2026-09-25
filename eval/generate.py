"""Expand templates into labelled synthetic replies and write data/replies.csv.

* Hand-written rows (synthetic=false) already in data/replies.csv are KEPT untouched (teammates add theirs there).
  If there are none yet, the seed set in eval/handwritten_seed.py is used to bootstrap them.
* Synthetic rows (synthetic=true) are regenerated deterministically (seeded) every run.
Gold labels come from construction, not from running the engine.

    python eval/generate.py [--variants 6]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import templates as T  # noqa: E402
from common import load_messages, load_replies, write_replies  # noqa: E402

WEIGHTS = {"understood": 0.5, "wrong": 0.17, "missing": 0.2, "negated": 0.13}


def supports(fact: dict) -> set[str]:
    t, v = fact["type"], fact["value"]
    ok = {"understood", "missing"}
    if t in ("dose", "amount"):
        ok |= {"wrong", "negated"}
    elif t == "frequency":
        ok |= {"wrong"}
    elif t == "duration":
        ok |= {"wrong", "negated"} if fact.get("unit") == "day" else {"wrong"}
    elif t in ("date", "timing"):
        ok |= {"wrong"}
    elif t == "condition":
        act = v["action"]
        ok |= {"wrong", "negated"} if act == "stop" else {"negated"}
    return ok


def wrap_neg(lang: str, phrase: str) -> str:
    pre, post = T.NEG_AROUND[lang]
    return " ".join(x for x in (pre, phrase, post) if x)


def other_number(n: int, rng: random.Random, kind: str) -> int:
    if kind == "amount":
        cands = [n + 30, max(10, n - 10), n * 2, n + 50]
    elif kind == "duration":
        cands = [n + 2, n * 2, max(1, n - 2), n + 5]
    else:
        cands = [n + 1, n + 2, max(1, n - 1), n * 2]
    cands = [c for c in cands if c != n and c >= 1]
    return cands[rng.randrange(len(cands))]


def render(fact: dict, lang: str, want: str, rng: random.Random, msg: dict) -> str:
    t, v, unit = fact["type"], fact["value"], fact.get("unit")
    if t == "dose":
        n = v if want != "wrong" else other_number(int(v), rng, "dose")
        s = f"{T.num_word(lang, int(n), rng, linker=True)} {T.pick(rng, T.UNIT[unit][lang])}"
        return wrap_neg(lang, s) if want == "negated" else s
    if t == "frequency":
        if v == 24:
            return T.pick(rng, T.FREQ_EVERY_HOUR[lang]) if want != "wrong" else "twice a day"
        n = int(v) if want != "wrong" else rng.choice([x for x in (1, 2, 3) if x != int(v)])
        fixed = T.FREQ_FIXED.get(lang, {}).get(n)
        if fixed and (rng.random() < 0.6 or lang == "arabizi" and n in (1, 2)):
            return T.pick(rng, fixed)
        return T.pick(rng, T.FREQ[lang]).format(n=T.num_word(lang, n, rng, linker=True))
    if t == "timing":
        tags = list(v) if isinstance(v, list) else [v]
        if want == "wrong":
            food = [i for i, x in enumerate(tags) if x in ("after_food", "before_food")]
            i = food[0] if food else 0
            tags[i] = T.TIMING_WRONG[tags[i]]
        return " ".join(T.pick(rng, T.TIMING[x][lang]) for x in tags)
    if t == "duration":
        n = int(v) if want != "wrong" else other_number(int(v), rng, "duration")
        words = T.MINWORD if unit == "minute" else T.DAYWORD
        s = f"{T.num_word(lang, n, rng)} {T.pick(rng, words[lang])}"
        return wrap_neg(lang, s) if want == "negated" else s
    if t == "date":
        if ":" in str(v):
            hh, mm = str(v).split(":")
            h = int(hh) if want != "wrong" else int(hh) + 1
            return f"{h}:{mm}"
        day = str(v)
        if want == "wrong":
            taken = {f["value"] for f in msg["facts"] if f["type"] == "date"}
            day = rng.choice([d for d in T.DAYS if d not in taken])
        bank = T.WEEKDAY["english"] if lang == "taglish" and rng.random() < 0.3 else T.WEEKDAY[lang]
        return T.pick(rng, bank[day])
    if t == "amount":
        n = int(v) if want != "wrong" else other_number(int(v), rng, "amount")
        s = f"{n} {T.pick(rng, T.CURRENCY['AED'])}"
        return wrap_neg(lang, s) if want == "negated" else s
    if t == "condition":
        trig, action = v["trigger"], v["action"]
        pol = "correct" if want == "understood" else want
        if want == "negated" and action == "avoid":
            pol = "wrong"  # "I can travel" = the opposite
        if action == "avoid" and want == "wrong":
            pol = "correct"
        key = (action, pol)
        word = T.pick(rng, T.SYMPTOM[trig][lang]) if trig in T.SYMPTOM else trig
        return T.pick(rng, T.COND[key][lang]).format(t=word)
    raise ValueError(t)


def gold_status(fact: dict, want: str) -> str:
    return want


def make_reply(msg: dict, lang: str, rng: random.Random) -> tuple[str, dict]:
    parts: list[tuple[dict, str]] = []
    gold: dict[str, str] = {}
    for f in msg["facts"]:
        ok = sorted(supports(f))
        w = [WEIGHTS[s] for s in ok]
        want = rng.choices(ok, weights=w)[0]
        gold[f["id"]] = want
        if want == "missing":
            continue
        parts.append((f, render(f, lang, want, rng, msg)))
    rng.shuffle(parts)
    # conditions read most naturally last
    parts.sort(key=lambda p: p[0]["type"] == "condition" and rng.random() < 0.7)
    text = ""
    for i, (_, s) in enumerate(parts):
        text += (T.pick(rng, T.JOINERS) if i else "") + s
    if rng.random() < 0.25:
        text = f"{T.pick(rng, T.CHATTER)} {text}"
    if rng.random() < 0.2:
        text = f"{text} {T.pick(rng, T.CHATTER)}"
    text = T.noisy(text.strip() or T.pick(rng, T.CHATTER), rng)
    return text, gold


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", type=int, default=6, help="synthetic replies per message per language mix")
    args = ap.parse_args()

    messages = load_messages()
    existing = load_replies()
    hand = [r for r in existing if not r["synthetic"]]
    # seed sets are added once per id-prefix (hw- = development set, ho- = blind held-out set); after that the CSV is the source of truth
    from handwritten_seed import seed_rows
    from heldout_seed import heldout_rows

    for prefix, rows in (("hw-", seed_rows(messages)), ("ho-", heldout_rows(messages))):
        if not any(r["reply_id"].startswith(prefix) for r in hand):
            hand += rows
            print(f"bootstrapped {len(rows)} '{prefix}' rows from the seed files")

    rows = [
        {"reply_id": r["reply_id"], "message_id": r["message_id"], "lang_mix": r["lang_mix"], "reply_text": r["reply_text"],
         "gold_labels": r["gold_labels"] if isinstance(r.get("gold_labels"), str) else json.dumps(r["gold"], ensure_ascii=False),
         "author": r["author"], "synthetic": "false"}
        for r in hand
    ]
    n_syn = 0
    seen: set[tuple[str, str]] = set()
    for mid, msg in messages.items():
        for lang in T.LANGS:
            for k in range(args.variants):
                rng = random.Random(f"samjha|{mid}|{lang}|{k}")
                text, gold = make_reply(msg, lang, rng)
                if (mid, text) in seen:
                    continue
                seen.add((mid, text))
                n_syn += 1
                rows.append({"reply_id": f"syn-{mid}-{lang[:2]}-{k}", "message_id": mid, "lang_mix": lang, "reply_text": text,
                             "gold_labels": json.dumps(gold, ensure_ascii=False), "author": "generate.py", "synthetic": "true"})
    write_replies(rows)
    n_checks = sum(len(json.loads(r["gold_labels"])) for r in rows)
    print(f"wrote {len(rows)} replies ({len(hand)} hand-written, {n_syn} synthetic) = {n_checks} labelled fact checks")


if __name__ == "__main__":
    main()
