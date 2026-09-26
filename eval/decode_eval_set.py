"""The Phase 3 evaluation set for Decode (D44): hand-written UAE workplace instructions with gold where / when / what / how-much labels.

    python eval/decode_eval_set.py      # writes data/decode/workplace_instructions.csv and data/decode/eval_v1.csv (deterministic)

This set was written AFTER Phase 2 was tuned and FROZEN (committed) before the first scoring run; nothing in the engine was tuned on it. It is still
`synthetic=true`: one author wrote the sentences, the gold labels and the by-ear respellings, so it measures whether the decoder does what its author
intended on a fresh sample, NOT how real workers write or speak (D42: real-world validation is missing).

workplace_instructions.csv   the base sentences with gold labels (also the script for the optional TTS test, D44)
    id, sentence, where, when, what, how_much, phrases, tags
    gold conventions: `what` = the requested verb plus its noun object (pronouns dropped, negation kept: "don't bring bags"); `where` = the place phrase;
    `when` = the time phrase; `how_much` = number + currency. Articles, prepositions and "o'clock" are ignored by the scorer.
eval_v1.csv                  the rows that are scored
    id, view, text, accent, intended, base_id, swaps, in_pack, synthetic
    view = typed_clean   the sentence typed correctly (any change or question is a false alarm)
           typed_ear     the sentence typed by ear (respelled) with `swaps` = "typed>meant" pairs. in_pack=true when every swap is one the accent packs
                         are meant to cover, false when the respelling is a pattern the packs do NOT model (the honest limit test)
           voice_clean   what a good speech-to-text transcript of the sentence looks like (capital, full stop)
"""

from __future__ import annotations

import csv
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "decode"

# (sentence, where, when, what, how_much, phrases)  "" = nothing to extract
I = [
    # places, including many the domain list does not contain: an honest coverage test
    ("come to the main gate", "main gate", "", "come", "", ""),
    ("wait at the loading bay", "loading bay", "", "wait", "", ""),
    ("meet me in the lobby", "lobby", "", "meet", "", ""),
    ("go to the security cabin", "security cabin", "", "go", "", ""),
    ("park near the petrol station", "petrol station", "", "park", "", ""),
    ("bring the trolley to the warehouse", "warehouse", "", "bring trolley", "", ""),
    ("wait outside the supermarket", "supermarket", "", "wait", "", ""),
    ("come to the labour camp", "labour camp", "", "come", "", ""),
    ("go to the bus stop", "bus stop", "", "go", "", ""),
    ("meet at the metro station", "metro station", "", "meet", "", ""),
    ("take the boxes to the store room", "store room", "", "take boxes", "", ""),
    ("come to gate three", "gate 3", "", "come", "", ""),
    ("wait at gate seven", "gate 7", "", "wait", "", ""),
    ("go to floor twelve", "floor 12", "", "go", "", ""),
    ("come to building five", "building 5", "", "come", "", ""),
    ("deliver this to flat 204", "flat 204", "", "deliver", "", ""),
    ("come to the parking gate four", "parking gate 4", "", "come", "", ""),
    ("wait in the reception", "reception", "", "wait", "", ""),
    ("go to the basement", "basement", "", "go", "", ""),
    ("come to the clinic", "clinic", "", "come", "", ""),
    ("go to the pharmacy", "pharmacy", "", "go", "", ""),
    ("wait behind the villa", "villa", "", "wait", "", ""),
    ("come to the kitchen", "kitchen", "", "come", "", ""),
    ("leave the keys at the desk", "desk", "", "leave keys", "", ""),
    ("park the truck in the yard", "yard", "", "park truck", "", ""),
    ("take the parcel to the mosque", "mosque", "", "take parcel", "", ""),
    ("send the driver to the airport", "airport", "", "send driver", "", ""),
    ("come to the rooftop", "rooftop", "", "come", "", ""),
    ("wait near the exit", "exit", "", "wait", "", ""),
    ("go to the canteen", "canteen", "", "go", "", ""),
    ("come to the site office", "site office", "", "come", "", ""),
    ("meet me at the car wash", "car wash", "", "meet", "", ""),
    ("come to the mall", "mall", "", "come", "", ""),
    ("bring the ladder to tower two", "tower 2", "", "bring ladder", "", ""),
    ("wait at the bank", "bank", "", "wait", "", ""),
    # times
    ("come tomorrow", "", "tomorrow", "come", "", ""),
    ("come at five", "", "5", "come", "", ""),
    ("call me at 5 pm", "", "5 pm", "call", "", ""),
    ("start work at seven in the morning", "", "7 morning", "start work", "", ""),
    ("come before noon", "", "noon", "come", "", ""),
    ("wait until morning", "", "morning", "wait", "", ""),
    ("come after maghrib", "", "maghrib", "come", "", ""),
    ("call me tonight", "", "tonight", "call", "", ""),
    ("meet me on friday", "", "friday", "meet", "", ""),
    ("come on monday at eight", "", "monday 8", "come", "", ""),
    ("come by evening", "", "evening", "come", "", ""),
    ("the shift starts at six", "", "6", "", "", ""),
    ("the meeting is at three pm", "", "3 pm", "", "", ""),
    ("come today", "", "today", "come", "", ""),
    ("come now", "", "now", "come", "", ""),
    ("wait ten minutes", "", "10 minutes", "wait", "", ""),
    ("come after lunch", "", "lunch", "come", "", ""),
    ("come next week", "", "next week", "come", "", ""),
    ("send it by tomorrow", "", "tomorrow", "send", "", ""),
    ("come at 8 o'clock", "", "8", "come", "", ""),
    ("start at nine", "", "9", "start", "", ""),
    ("finish before midnight", "", "midnight", "finish", "", ""),
    ("come this evening", "", "evening", "come", "", ""),
    ("come at noon", "", "noon", "come", "", ""),
    # amounts
    ("pay fifty dirhams", "", "", "pay", "50 dirhams", ""),
    ("it costs twenty five dirhams", "", "", "", "25 dirhams", ""),
    ("send 100 dirhams", "", "", "send", "100 dirhams", ""),
    ("the fine is two hundred dirhams", "", "", "", "200 dirhams", ""),
    ("pay 30 aed at the counter", "counter", "", "pay", "30 aed", ""),
    ("the taxi is fifteen dirhams", "", "", "", "15 dirhams", ""),
    ("you will get 1500 dirhams", "", "", "", "1500 dirhams", ""),
    ("the rent is 800 dirhams", "", "", "", "800 dirhams", ""),
    ("pay five hundred dirhams tomorrow", "", "tomorrow", "pay", "500 dirhams", ""),
    ("transfer three thousand dirhams", "", "", "transfer", "3000 dirhams", ""),
    ("the ticket costs 45 dirhams", "", "", "", "45 dirhams", ""),
    ("pay 20 dirhams to the driver", "", "", "pay", "20 dirhams", ""),
    ("give me sixty dirhams", "", "", "give", "60 dirhams", ""),
    ("the charge is 12 dirhams", "", "", "", "12 dirhams", ""),
    ("send two hundred aed today", "", "today", "send", "200 aed", ""),
    # negations
    ("don't come today", "", "today", "don't come", "", ""),
    ("do not come to the gate", "gate", "", "don't come", "", ""),
    ("never park here", "", "", "never park", "", ""),
    ("don't bring the bags", "", "", "don't bring bags", "", ""),
    ("do not wait at the lobby", "lobby", "", "don't wait", "", ""),
    ("i cannot come tomorrow", "", "tomorrow", "cannot come", "", ""),
    ("don't pay fifty dirhams", "", "", "don't pay", "50 dirhams", ""),
    ("do not go to the basement", "basement", "", "don't go", "", ""),
    ("don't call me before eight", "", "8", "don't call", "", ""),
    ("please don't come at five", "", "5", "don't come", "", ""),
    ("do not open the door", "", "", "don't open door", "", ""),
    ("don't send the money today", "", "today", "don't send money", "", ""),
    ("never come to the site alone", "site", "", "never come", "", ""),
    ("do not bring food to the office", "office", "", "don't bring food", "", ""),
    ("don't take the keys", "", "", "don't take keys", "", ""),
    ("i cannot pay fifty dirhams", "", "", "cannot pay", "50 dirhams", ""),
    ("do not come at night", "", "night", "don't come", "", ""),
    ("don't leave the truck at the entrance", "entrance", "", "don't leave truck", "", ""),
    ("do not park in front of the gate", "gate", "", "don't park", "", ""),
    ("don't wait for me", "", "", "don't wait", "", ""),
    ("please do not come tomorrow", "", "tomorrow", "don't come", "", ""),
    # combined
    ("come to the parking gate three at five", "parking gate 3", "5", "come", "", ""),
    ("meet me at the lobby tomorrow at nine", "lobby", "tomorrow 9", "meet", "", ""),
    ("bring the keys to the reception before noon", "reception", "noon", "bring keys", "", ""),
    ("pay fifty dirhams at the counter tomorrow", "counter", "tomorrow", "pay", "50 dirhams", ""),
    ("wait at the loading bay until six", "loading bay", "6", "wait", "", ""),
    ("take the parcel to building nine on friday", "building 9", "friday", "take parcel", "", ""),
    ("send the driver to the airport at seven", "airport", "7", "send driver", "", ""),
    ("come to gate two tomorrow morning", "gate 2", "tomorrow morning", "come", "", ""),
    ("deliver the files to floor eight today", "floor 8", "today", "deliver files", "", ""),
    ("pay twenty dirhams at the office tomorrow", "office", "tomorrow", "pay", "20 dirhams", ""),
    ("don't come to the warehouse before eight", "warehouse", "8", "don't come", "", ""),
    ("park the truck near tower three at noon", "tower 3", "noon", "park truck", "", ""),
    ("wait at the bus stop until seven", "bus stop", "7", "wait", "", ""),
    ("collect the bags from the store room at four", "store room", "4", "collect bags", "", ""),
    ("call me tomorrow at ten", "", "tomorrow 10", "call", "", ""),
    ("come to flat 305 at eight pm", "flat 305", "8 pm", "come", "", ""),
    ("bring the box to the site office today", "site office", "today", "bring box", "", ""),
    ("pay two hundred dirhams at the reception on monday", "reception", "monday", "pay", "200 dirhams", ""),
    ("do not pay at the gate today", "gate", "today", "don't pay", "", ""),
    ("meet me at the metro station at six pm", "metro station", "6 pm", "meet", "", ""),
    # local phrases mixed in
    ("yalla come to the gate", "gate", "", "come", "", "yalla"),
    ("habibi wait at the lobby", "lobby", "", "wait", "", "habibi"),
    ("khalas don't come tomorrow", "", "tomorrow", "don't come", "", "khalas"),
    ("inshallah i come at five", "", "5", "", "", "inshallah"),
    ("yalla bring the bags to the villa", "villa", "", "bring bags", "", "yalla"),
    ("mafi mushkila come tomorrow", "", "tomorrow", "come", "", "mafi mushkila"),
    ("kindly revert by tomorrow", "", "tomorrow", "revert", "", "kindly revert"),
    ("yalla pay fifty dirhams", "", "", "pay", "50 dirhams", "yalla"),
    ("shway shway come to the gate", "gate", "", "come", "", "shway shway"),
    ("wallah i cannot come today", "", "today", "cannot come", "", "wallah"),
    # nothing to extract, or only a single slot: a spurious fill is a mistake
    ("the lift is not working", "", "", "", "", ""),
    ("good morning sir", "", "", "", "", ""),
    ("thank you very much", "", "", "", "", ""),
    ("how are you", "", "", "", "", ""),
    ("the food is very good", "", "", "", "", ""),
    ("my phone is not working", "", "", "", "", ""),
    ("i am happy today", "", "today", "", "", ""),
    ("the boss is angry", "", "", "", "", ""),
    ("we are very tired", "", "", "", "", ""),
    ("it is very hot outside", "", "", "", "", ""),
    ("i like this job", "", "", "", "", ""),
    ("the weather is nice tomorrow", "", "tomorrow", "", "", ""),
]

# ---- by-ear respelling ------------------------------------------------------------------------------------------------------------------------
# Written independently of the decoder's accent packs. IN_PACK rules are ones the packs are meant to cover; OUT_OF_PACK are ones they are not.
IN_PACK = {
    "ar": [("p", "b"), ("v", "f"), ("th", "t")],
    "hi": [("v", "w"), ("w", "v"), ("th", "d")],
    "ml": [("z", "s"), ("th", "t")],
    "tl": [("f", "p"), ("v", "b"), ("th", "t")],
}
OUT_OF_PACK = [("ing", "in"), ("th", "f"), ("ee", "i"), ("oo", "u"), ("sh", "ch"), ("ch", "sh")]  # plus initial h-drop and s-cluster i- (below)
HINTS = ["ar", "hi", "ml", "tl", None]
CLEAN_HINTS = ["ar", "hi", "ml", "tl", None]


def _apply(word: str, rule: tuple[str, str]) -> str | None:
    a, b = rule
    i = word.find(a)
    if i < 0 or len(word) < 3:
        return None
    return word[:i] + b + word[i + len(a):]


def _special(word: str) -> str | None:
    if word[0] == "h" and len(word) > 3:
        return word[1:]  # hotel -> otel
    if re.match(r"s[ptk]", word) and len(word) > 4:
        return "i" + word  # station -> istation
    return None


def _ear_variant(rng: random.Random, sentence: str, in_pack: bool) -> tuple[str, str, list[tuple[str, str]], str | None] | None:
    accents = list(IN_PACK)
    rng.shuffle(accents)
    for accent in accents:
        v = _ear_for(rng, sentence, accent, in_pack)
        if v:
            return v
    return None


def _ear_for(rng: random.Random, sentence: str, accent: str, in_pack: bool):
    words = sentence.split()
    rules = IN_PACK[accent] if in_pack else OUT_OF_PACK
    order = list(range(len(words)))
    rng.shuffle(order)
    swaps: list[tuple[str, str]] = []
    out = list(words)
    for i in order:
        w = words[i]
        if w.isdigit() or "'" in w:
            continue
        cands = []
        for r in rules:
            if r == ("th", "f") and w in ("the", "this", "that", "then"):
                continue  # th-fronting is real for think/three, not for the article
            new = _apply(w, r)
            if new and new != w:
                cands.append(new)
        if not in_pack:
            sp = _special(w)
            if sp:
                cands.append(sp)
        if cands:
            new = rng.choice(cands)
            out[i] = new
            swaps.append((new, w))
        if len(swaps) == 2:
            break
    if not swaps:
        return None
    hint = accent if rng.random() < 0.8 else None
    return " ".join(out), accent, swaps, hint


def _load_tuning_sentences() -> set[str]:
    seen: set[str] = set()
    for name, cols in (("voice_synthetic.csv", ("transcript", "intended")), ("typed_synthetic.csv", ("text_as_typed", "intended_meaning"))):
        p = OUT / name
        if p.exists():
            with p.open(encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    seen.update(r[c].strip().lower() for c in cols)
    return seen


def build() -> tuple[list[dict], list[dict], int]:
    tuning = _load_tuning_sentences()
    base = []
    dropped = 0
    for s, where, when, what, how, phrases in I:
        if s in tuning:
            dropped += 1  # an exact sentence the decoder was tuned on is not a fresh test
            continue
        base.append((s, where, when, what, how, phrases))
    inst = [{"id": f"wi{n:03d}", "sentence": s, "where": w, "when": t, "what": a, "how_much": h, "phrases": p, "tags": ""} for n, (s, w, t, a, h, p) in enumerate(base, 1)]
    rng = random.Random(44)
    rows: list[dict] = []
    n = 0

    def add(view, text, accent, intended, base_id, swaps, in_pack):
        nonlocal n
        n += 1
        rows.append({"id": f"ev{n:04d}", "view": view, "text": text, "accent": accent or "none", "intended": intended, "base_id": base_id,
                     "swaps": "; ".join(f"{a}>{b}" for a, b in swaps), "in_pack": in_pack, "synthetic": "true"})

    for k, r in enumerate(inst):
        add("typed_clean", r["sentence"], CLEAN_HINTS[k % 5], r["sentence"], r["id"], [], "")
    for k, r in enumerate(inst):
        s = r["sentence"]
        add("voice_clean", s[0].upper() + s[1:] + ".", CLEAN_HINTS[(k + 2) % 5], s, r["id"], [], "")
    for in_pack in (True, False):
        for r in inst:
            v = _ear_variant(rng, r["sentence"], in_pack)
            if v:
                text, acc, swaps, hint = v
                add("typed_ear", text, hint, r["sentence"], r["id"], swaps, "true" if in_pack else "false")
    return inst, rows, dropped


def write() -> tuple[list[dict], list[dict], int]:
    inst, rows, dropped = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in (("workplace_instructions.csv", inst), ("eval_v1.csv", rows)):
        with (OUT / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    return inst, rows, dropped


if __name__ == "__main__":
    inst, rows, dropped = write()
    views = {}
    for r in rows:
        key = r["view"] + (":in_pack" if r["in_pack"] == "true" else ":out_of_pack" if r["in_pack"] == "false" else "")
        views[key] = views.get(key, 0) + 1
    print(f"{len(inst)} instructions ({dropped} dropped: already in a tuning set), {len(rows)} scored rows: {views}")
