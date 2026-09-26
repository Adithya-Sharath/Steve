"""Evaluation set v2 for Decode (D44): a SECOND, fresh set written AFTER the extraction fixes that followed the first scoring of v1.

    python eval/decode_eval_set_v2.py       # writes data/decode/workplace_instructions_v2.csv and data/decode/eval_v2.csv
    python eval/decode_eval.py --set v2 --write --tag first_run

Why it exists: the v1 set was used to find and fix gaps (D44), so v1 numbers after the fixes are contaminated. These sentences were written after those fixes,
without looking at how the decoder handles them, and are scored once. Same author, same conventions, same generator (decode_eval_set.py), different sentences
and a different random seed. Still synthetic (D42).
"""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

import decode_eval_set as base  # noqa: E402

# (sentence, where, when, what, how_much, phrases)
I2 = [
    ("come to the service lift", "service lift", "", "come", "", ""),
    ("wait at the fire exit", "fire exit", "", "wait", "", ""),
    ("go to the staff room", "staff room", "", "go", "", ""),
    ("meet me at the swimming pool", "swimming pool", "", "meet", "", ""),
    ("park behind the generator room", "generator room", "", "park", "", ""),
    ("come to the school gate", "school gate", "", "come", "", ""),
    ("take the files to the bank", "bank", "", "take files", "", ""),
    ("bring the tools to level two", "level 2", "", "bring tools", "", ""),
    ("go to block c", "block c", "", "go", "", ""),
    ("come to room eleven", "room 11", "", "come", "", ""),
    ("wait near the hospital entrance", "hospital entrance", "", "wait", "", ""),
    ("leave the bags outside the office", "office", "", "leave bags", "", ""),
    ("come to the back gate", "back gate", "", "come", "", ""),
    ("go to the city center", "city center", "", "go", "", ""),
    ("meet at the gym", "gym", "", "meet", "", ""),
    ("park in the visitor parking", "visitor parking", "", "park", "", ""),
    ("take the boxes to the garage", "garage", "", "take boxes", "", ""),
    ("come to gate ten", "gate 10", "", "come", "", ""),
    ("wait at the bakery", "bakery", "", "wait", "", ""),
    ("send the driver to the hotel", "hotel", "", "send driver", "", ""),
    ("come at four", "", "4", "come", "", ""),
    ("come tomorrow morning", "", "tomorrow morning", "come", "", ""),
    ("call me before nine", "", "9", "call", "", ""),
    ("come after isha", "", "isha", "come", "", ""),
    ("the bus leaves at seven", "", "7", "", "", ""),
    ("wait until evening", "", "evening", "wait", "", ""),
    ("come on sunday", "", "sunday", "come", "", ""),
    ("finish by friday", "", "friday", "finish", "", ""),
    ("start at six thirty", "", "6 30", "start", "", ""),
    ("call me tomorrow", "", "tomorrow", "call", "", ""),
    ("come at three pm", "", "3 pm", "come", "", ""),
    ("come at noon tomorrow", "", "noon tomorrow", "come", "", ""),
    ("pay one hundred and twenty dirhams", "", "", "pay", "120 dirhams", ""),
    ("the bill is 75 dirhams", "", "", "", "75 dirhams", ""),
    ("send forty dirhams", "", "", "send", "40 dirhams", ""),
    ("the salary is two thousand dirhams", "", "", "", "2000 dirhams", ""),
    ("pay 90 aed today", "", "today", "pay", "90 aed", ""),
    ("give me fifteen dirhams", "", "", "give", "15 dirhams", ""),
    ("it costs eighty dirhams", "", "", "", "80 dirhams", ""),
    ("transfer 500 dirhams tomorrow", "", "tomorrow", "transfer", "500 dirhams", ""),
    ("don't come tomorrow", "", "tomorrow", "don't come", "", ""),
    ("do not park at the gate", "gate", "", "don't park", "", ""),
    ("never open the door", "", "", "never open door", "", ""),
    ("i cannot come today", "", "today", "cannot come", "", ""),
    ("don't wait at the lobby", "lobby", "", "don't wait", "", ""),
    ("do not send the bags", "", "", "don't send bags", "", ""),
    ("please don't call before eight", "", "8", "don't call", "", ""),
    ("do not bring the truck to the yard", "yard", "", "don't bring truck", "", ""),
    ("never come to the site at night", "site", "night", "never come", "", ""),
    ("don't take the keys home", "", "", "don't take keys", "", ""),
    ("do not pay sixty dirhams", "", "", "don't pay", "60 dirhams", ""),
    ("come to the parking at six", "parking", "6", "come", "", ""),
    ("meet me at the reception tomorrow at eight", "reception", "tomorrow 8", "meet", "", ""),
    ("bring the files to floor five today", "floor 5", "today", "bring files", "", ""),
    ("wait at gate four until nine", "gate 4", "9", "wait", "", ""),
    ("pay thirty dirhams at the counter", "counter", "", "pay", "30 dirhams", ""),
    ("send the boxes to the warehouse on monday", "warehouse", "monday", "send boxes", "", ""),
    ("come to the clinic at five pm", "clinic", "5 pm", "come", "", ""),
    ("park the van behind the mall tonight", "mall", "tonight", "park van", "", ""),
    ("take the parcel to building two tomorrow", "building 2", "tomorrow", "take parcel", "", ""),
    ("don't come to the office on friday", "office", "friday", "don't come", "", ""),
    ("call me at seven pm", "", "7 pm", "call", "", ""),
    ("yalla come to the parking", "parking", "", "come", "", "yalla"),
    ("khalas don't pay today", "", "today", "don't pay", "", "khalas"),
    ("habibi bring the box to the lobby", "lobby", "", "bring box", "", "habibi"),
    ("mafi mushkila come at five", "", "5", "come", "", "mafi mushkila"),
    ("inshallah the truck comes tomorrow", "", "tomorrow", "", "", "inshallah"),
    ("the lift is on the second floor", "", "", "", "", ""),
    ("good evening sir", "", "", "", "", ""),
    ("the water is cold", "", "", "", "", ""),
    ("we are very busy", "", "", "", "", ""),
    ("the office is closed today", "", "today", "", "", ""),
    ("my friend is in the hospital", "hospital", "", "", "", ""),
    ("thank you for the help", "", "", "", "", ""),
]


def build() -> tuple[list[dict], list[dict], int]:
    tuning = base._load_tuning_sentences() | {r[0] for r in base.I}
    kept = [r for r in I2 if r[0] not in tuning]
    dropped = len(I2) - len(kept)
    inst = [{"id": f"wj{n:03d}", "sentence": s, "where": w, "when": t, "what": a, "how_much": h, "phrases": p, "tags": ""} for n, (s, w, t, a, h, p) in enumerate(kept, 1)]
    rng = random.Random(45)
    rows: list[dict] = []
    n = 0

    def add(view, text, accent, intended, base_id, swaps, in_pack):
        nonlocal n
        n += 1
        rows.append({"id": f"ew{n:04d}", "view": view, "text": text, "accent": accent or "none", "intended": intended, "base_id": base_id,
                     "swaps": "; ".join(f"{a}>{b}" for a, b in swaps), "in_pack": in_pack, "synthetic": "true"})

    for k, r in enumerate(inst):
        add("typed_clean", r["sentence"], base.CLEAN_HINTS[k % 5], r["sentence"], r["id"], [], "")
    for k, r in enumerate(inst):
        s = r["sentence"]
        add("voice_clean", s[0].upper() + s[1:] + ".", base.CLEAN_HINTS[(k + 2) % 5], s, r["id"], [], "")
    for in_pack in (True, False):
        for r in inst:
            v = base._ear_variant(rng, r["sentence"], in_pack)
            if v:
                text, _acc, swaps, hint = v
                add("typed_ear", text, hint, r["sentence"], r["id"], swaps, "true" if in_pack else "false")
    return inst, rows, dropped


if __name__ == "__main__":
    inst, rows, dropped = build()
    for name, data in (("workplace_instructions_v2.csv", inst), ("eval_v2.csv", rows)):
        with (base.OUT / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    print(f"{len(inst)} instructions ({dropped} dropped as already used), {len(rows)} scored rows")
