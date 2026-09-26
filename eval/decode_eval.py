"""Phase 3 scoring of the Decode engine on the frozen evaluation set (D44).

    python eval/decode_eval.py            # print the report
    python eval/decode_eval.py --write    # also write eval/results/decode_eval_v1.md

Headline metrics (owner, Checkpoint 2 review): (1) false-alarm rate, (2) typed-text decode accuracy, (3) where / when / what / how-much extraction accuracy.
The voice safety net's catch rate is reported ONLY as "synthetic, author-written, tuned on it", next to the held-out L2-ARCTIC result (0 of 72).

Definitions (all counted per sentence unless said otherwise):
  false alarm        a correctly written sentence (typed_clean, voice_clean) for which the card has any change or any clarifying question
                       false rewrite = at least one change (a silent wrong edit: the worst case), false question = a question only
  typed-ear exact    applying the card's changes to the typed text gives the intended sentence (numbers compared as numbers)
  typed-ear asked    not exact, but a clarifying question offers a word that was meant (no silent guess)
  typed-ear wrong    not exact, and no question covers it: wrong-but-confident
  extraction         for each slot with a gold value: correct / empty (nothing extracted) / wrong (a different value). For a slot whose gold is empty:
                       spurious = something was extracted anyway. Values are compared after dropping articles, prepositions and "o'clock", with numbers as digits.
Intervals are 95% Wilson intervals: with ~130-450 rows they are wide, and the sets are synthetic, so read them as ranges, not promises.
"""

from __future__ import annotations

import csv
import hashlib
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "eval"))

from steve_engine.decode import decode  # noqa: E402
from steve_engine.decode.actions import parse_number  # noqa: E402
from steve_engine.decode.safety import apply_changes  # noqa: E402

DATA = ROOT / "data" / "decode"
SLOTS = ("where", "when", "what", "how_much")
STOP = {"the", "a", "an", "at", "in", "on", "to", "by", "near", "from", "for", "until", "before", "after", "o'clock", "please", "of", "me", "this", "it"}
NEGATIONS = {"don't", "never", "cannot", "not", "no", "can't", "won't"}
_WORDS = re.compile(r"[a-z']+|\d+")


def norm_words(text: str) -> list[str]:
    """Lowercase words with number words turned into digits (as in decode_typed_eval.norm, but keeping 'one' as a word)."""
    words = _WORDS.findall(text.lower().replace("’", "'"))
    out, i = [], 0
    while i < len(words):
        n = parse_number(words, i) if words[i] != "one" else None
        if n:
            out.append(str(n[0]))
            i = n[1]
        else:
            out.append(words[i])
            i += 1
    return out


def norm_value(text: str | None) -> tuple[str, ...]:
    return tuple(w for w in norm_words(text or "") if w not in STOP)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def rate(k: int, n: int) -> str:
    if n == 0:
        return "n/a"
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f}% ({k}/{n}; 95% {100 * lo:.0f}-{100 * hi:.0f}%)"


def load(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def file_hash(name: str) -> str:
    return hashlib.sha256((DATA / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


def score_row(row: dict, gold: dict, card) -> dict:
    """Everything the report needs about one row."""
    path = "voice" if row["view"] == "voice_clean" else "typed"
    hint = None if row["accent"] == "none" else row["accent"]
    text = row["text"]
    res: dict = {"row": row, "card": card, "path": path, "hint": hint}
    res["changed"] = bool(card.changes)
    res["asked"] = bool(card.clarify)
    effective = apply_changes(text, card.changes)
    res["effective"] = effective
    res["exact"] = norm_words(effective) == norm_words(row["intended"])
    options = {o for q in card.clarify for o in q.options}
    typed = set(norm_words(text))
    missing = {w for w in norm_words(row["intended"]) if w not in typed and not w.isdigit()}
    res["offered"] = bool(missing & options) or any(norm_words(o) and set(norm_words(o)) & set(norm_words(row["intended"])) - typed for o in options)
    slots = {}
    for s in SLOTS:
        v = getattr(card.actions, s)
        pred = v.value if v else ""
        g = gold[s]
        if g:
            pv, gv = norm_value(pred), norm_value(g)
            state = "correct" if pv == gv else "empty" if not pred else "partial" if pv and set(pv) < set(gv) else "wrong"
            if state == "partial" and (set(gv) & NEGATIONS) and not (set(pv) & NEGATIONS):
                state = "wrong"  # an incomplete value that lost the negation reverses the instruction: never merely "partial"
        else:
            state = "spurious" if pred else "none"
        slots[s] = (state, pred, g)
    res["slots"] = slots
    return res


def run() -> tuple[list[dict], dict]:
    inst = {r["id"]: r for r in load("workplace_instructions.csv")}
    rows = load("eval_v1.csv")
    results = []
    for r in rows:
        path = "voice" if r["view"] == "voice_clean" else "typed"
        card = decode(r["text"], None if r["accent"] == "none" else r["accent"], path)
        results.append(score_row(r, inst[r["base_id"]], card))
    return results, inst


def summarise(results: list[dict]) -> dict:
    out: dict = {}
    clean = [x for x in results if x["row"]["view"] in ("typed_clean", "voice_clean")]
    out["false_alarm"] = {
        "all": Counter(n=len(clean), any=sum(x["changed"] or x["asked"] for x in clean), rewrite=sum(x["changed"] for x in clean), question=sum(x["asked"] and not x["changed"] for x in clean)),
    }
    for view in ("typed_clean", "voice_clean"):
        v = [x for x in clean if x["row"]["view"] == view]
        out["false_alarm"][view] = Counter(n=len(v), any=sum(x["changed"] or x["asked"] for x in v), rewrite=sum(x["changed"] for x in v), question=sum(x["asked"] and not x["changed"] for x in v))
    by_hint: dict = defaultdict(Counter)
    for x in clean:
        h = x["row"]["accent"]
        by_hint[h]["n"] += 1
        by_hint[h]["any"] += x["changed"] or x["asked"]
        by_hint[h]["rewrite"] += x["changed"]
    out["false_alarm_by_hint"] = by_hint
    ear = [x for x in results if x["row"]["view"] == "typed_ear"]
    for name, sel in (("in_pack", [x for x in ear if x["row"]["in_pack"] == "true"]), ("out_of_pack", [x for x in ear if x["row"]["in_pack"] == "false"]), ("all", ear)):
        c = Counter(n=len(sel))
        for x in sel:
            if x["exact"]:
                c["exact"] += 1
            elif x["offered"]:
                c["asked"] += 1
            elif not x["changed"]:
                c["left"] += 1  # nothing was decoded and nothing was asked: the typed text passes through as it is
            else:
                c["wrong"] += 1  # the card rewrote something and the result is not the intended sentence
        out.setdefault("typed_ear", {})[name] = c
    ear_acc: dict = defaultdict(Counter)
    for x in ear:
        a = x["row"]["accent"]
        ear_acc[a]["n"] += 1
        ear_acc[a]["exact"] += x["exact"]
        ear_acc[a]["asked"] += (not x["exact"]) and x["offered"]
    out["typed_ear_by_hint"] = ear_acc
    ext: dict = {}
    for view in ("typed_clean", "voice_clean", "typed_ear_in_pack", "typed_ear_out_of_pack"):
        if view.startswith("typed_ear"):
            want = "true" if view.endswith("in_pack") else "false"
            sel = [x for x in ear if x["row"]["in_pack"] == want]
        else:
            sel = [x for x in results if x["row"]["view"] == view]
        per = {}
        for s in SLOTS:
            c = Counter()
            for x in sel:
                c[x["slots"][s][0]] += 1
            per[s] = c
        ext[view] = per
    out["extraction"] = ext
    neg = [x for x in results if any(w in norm_words(x["row"]["intended"]) for w in ("don't", "do", "never", "cannot")) and re.search(r"\b(don't|do not|never|cannot)\b", x["row"]["intended"])]
    out["negation"] = Counter(n=len(neg), kept=sum(bool(re.search(r"\b(don't|do not|never|cannot|not)\b", x["effective"].lower())) and bool(re.search(r"\b(don't|do not|never|cannot|not)\b", x["card"].plain_english.lower())) for x in neg))
    return out


def failures(results: list[dict]) -> list[str]:
    lines = []
    for x in results:
        r, c = x["row"], x["card"]
        why = []
        if r["view"] in ("typed_clean", "voice_clean") and (x["changed"] or x["asked"]):
            why.append("FALSE ALARM: " + ("; ".join(f"{h.heard}->{h.meant}" for h in c.changes) or "") + (" | asked: " + " / ".join(q.question for q in c.clarify) if c.clarify else ""))
        if r["view"] == "typed_ear" and not x["exact"]:
            if x["offered"]:
                why.append("asked: " + " / ".join(q.question for q in c.clarify))
            elif not x["changed"]:
                why.append("LEFT AS TYPED (nothing decoded, nothing asked)")
            else:
                why.append(f"WRONG REWRITE: decoded as '{x['effective']}' (changes: {'; '.join(f'{h.heard}->{h.meant}' for h in c.changes)})")
        for s, (state, pred, gold) in x["slots"].items():
            if state in ("wrong", "spurious", "partial"):
                why.append(f"{s} {state}: got '{pred}', gold '{gold}'")
        if why:
            lines.append(f"* `{r['id']}` [{r['view']}{' in-pack' if r['in_pack'] == 'true' else ' out-of-pack' if r['in_pack'] == 'false' else ''}, {r['accent']}] `{r['text']}` -> " + " ; ".join(why))
    return lines


def empties(results: list[dict]) -> Counter:
    c = Counter()
    for x in results:
        for s, (state, _p, _g) in x["slots"].items():
            if state == "empty":
                c[s] += 1
    return c


def report(results: list[dict], summ: dict) -> str:
    L: list[str] = []
    a = L.append
    inst_hash, ev_hash = file_hash("workplace_instructions.csv"), file_hash("eval_v1.csv")
    a("# Decode Phase 3 evaluation (D44)\n")
    a(f"Frozen evaluation set `data/decode/eval_v1.csv` (sha256 {ev_hash}), built from `workplace_instructions.csv` (sha256 {inst_hash}): {len(results)} scored rows from "
      f"{len(load('workplace_instructions.csv'))} hand-written UAE workplace instructions. **Synthetic, one author: sentences, gold labels and by-ear respellings.** "
      "It was committed before its first scoring run and nothing was tuned on it. It measures whether the decoder does what its author intended on a fresh sample; it says nothing about "
      "how real workers write or speak (real-world validation is missing, D42). Every rule, phrase and word list is `verified: false`.\n")
    fa = summ["false_alarm"]
    a("## 1. False-alarm rate (headline)\n")
    a("A correctly written sentence for which the card shows any change or any clarifying question.\n")
    a("| Rows | Sentences | False alarm (any) | False rewrite (silent edit) | Question only |\n|---|---:|---|---|---|")
    for k, label in (("all", "All correct sentences"), ("typed_clean", "Typed correctly"), ("voice_clean", "Voice transcript, correct")):
        c = fa[k]
        a(f"| {label} | {c['n']} | {rate(c['any'], c['n'])} | {rate(c['rewrite'], c['n'])} | {rate(c['question'], c['n'])} |")
    a("\nBy the accent hint given with the sentence (typed and voice together):\n")
    a("| Hint | Sentences | Any false alarm | False rewrites |\n|---|---:|---:|---:|")
    for h in sorted(summ["false_alarm_by_hint"]):
        c = summ["false_alarm_by_hint"][h]
        a(f"| {h} | {c['n']} | {c['any']} | {c['rewrite']} |")
    a("\n## 2. Typed-text decode accuracy (headline)\n")
    a("Sentences typed by ear (respelled). *Exact* = the card's changes give the intended sentence; *asked* = a clarifying question offers the meant word (no silent guess); "
      "*left as typed* = nothing decoded and nothing asked (a miss; the misspelling stays visible in the text); *wrong rewrite* = the card changed something and the result is not the "
      "intended sentence (wrong-but-confident). (Left-as-typed was split from wrong rewrite after the first scoring run, because the first version lumped them.) "
      "**In-pack** = the respelling is one the accent packs are meant to cover; **out-of-pack** = a pattern they do not model (th->f, ee->i, h-dropping, ...), so this row is the honest limit.\n")
    a("| Respellings | Sentences | Exact | Asked | Exact or asked | Left as typed | Wrong rewrite (wrong-but-confident) |\n|---|---:|---|---|---|---|---|")
    for k, label in (("in_pack", "In-pack"), ("out_of_pack", "Out-of-pack"), ("all", "All")):
        c = summ["typed_ear"][k]
        a(f"| {label} | {c['n']} | {rate(c['exact'], c['n'])} | {rate(c['asked'], c['n'])} | {rate(c['exact'] + c['asked'], c['n'])} | {rate(c['left'], c['n'])} | {rate(c['wrong'], c['n'])} |")
    a("\nBy accent hint (in-pack and out-of-pack together):\n")
    a("| Hint | Sentences | Exact | Asked |\n|---|---:|---:|---:|")
    for h in sorted(summ["typed_ear_by_hint"]):
        c = summ["typed_ear_by_hint"][h]
        a(f"| {h} | {c['n']} | {c['exact']} | {c['asked']} |")
    a("\n## 3. Where / when / what / how-much extraction accuracy (headline)\n")
    a("For every slot that has a gold value: *correct*, *partial* (right but incomplete: \"gate\" for \"main gate\", \"bring\" for \"bring trolley\"), *empty* (nothing extracted: the safe "
      "failure) or *wrong* (a value that is not part of the gold: the dangerous one). (Partial was split from wrong after the first scoring run, because the first version counted every "
      "incomplete value as wrong.) *Spurious* = the slot had no gold value but the card filled it anyway (of all rows whose gold is empty).\n")
    a("| Rows | Slot | Gold present | Correct | Partial | Empty | Wrong | Spurious fills |\n|---|---|---:|---|---:|---:|---|---|")
    labels = {"typed_clean": "Typed correctly", "voice_clean": "Voice transcript, correct", "typed_ear_in_pack": "Typed by ear, in-pack", "typed_ear_out_of_pack": "Typed by ear, out-of-pack"}
    for view, per in summ["extraction"].items():
        for s in SLOTS:
            c = per[s]
            g = c["correct"] + c["empty"] + c["wrong"] + c["partial"]
            none_ = c["none"] + c["spurious"]
            a(f"| {labels[view]} | {s} | {g} | {rate(c['correct'], g)} | {c['partial']} | {c['empty']} | {rate(c['wrong'], g)} | {rate(c['spurious'], none_)} |")
    neg = summ["negation"]
    a(f"\nNegation kept: {neg['kept']} of {neg['n']} negated sentences still contain the negation in the plain English (a negation must never be lost).\n")
    a("## 4. Voice safety net catch rate (secondary; read the labels)\n")
    import decode_safety_eval as dse

    res = dse.evaluate_voice(dse.load(DATA / "voice_synthetic.csv"))
    r, c = res["risky"]["all"], res["clean"]["all"]
    caught = r["caught_rewrite"] + r["caught_clarify"]
    a(f"* **Synthetic, author-written, tuned on it:** {caught} of {r['n']} risky words caught ({100 * caught / r['n']:.1f}%: {r['caught_rewrite']} rewritten, "
      f"{r['caught_clarify']} asked), {r['wrong_rewrite']} wrong rewrites; false alarm {c['any']} of {c['n']} clean sentences. This set was used to set the margins, so it is an upper bound.")
    a("* **Held-out L2-ARCTIC (test only, Sarvam transcripts, D43): catch 0 of 72 risky words** (0 of 105 on the whatsapp-snr10 run). The errors in that data (coal -> cold, boat -> board) fall "
      "outside the where / when / what / amount / negation slots the net watches, so the net correctly does not look at them: the number says the net is not a general "
      "speech-to-text error fixer, and nothing about how it would do on workplace instructions.")
    a("* Whether real voice notes break critical-slot words at all is untested. The only real-audio evidence is D42: on clean and whatsapp-snr10 audio, numbers, times, places and negations "
      "came back right 48/57 and 47/57 times with 0 wrong real words (the rest not aligned or kept).")
    a("\n## 5. Every miss, listed\n")
    f = failures(results)
    a(f"{len(f)} rows with a false alarm, a wrong-but-confident decode, or a wrong / spurious slot value (empty slots are counted above, not listed):\n")
    L.extend(f)
    e = empties(results)
    a(f"\nEmpty slots (nothing extracted although gold had a value): {dict(e)}.\n")
    a("## 6. What this evaluation cannot show\n")
    a("* No real voice notes, no real typed messages (D42). All text is author-written; the by-ear respellings are generated by letter rules, real people vary far more.\n"
      "* One author wrote the sentences and the gold, so the results reflect the author's own idea of the task. A different author would find different gaps.\n"
      "* The in-pack rows use the same kinds of sound swaps the packs were built from, so the in-pack accuracy is optimistic; the out-of-pack rows show what happens outside them.\n"
      "* No baseline comparison yet (a Gemini baseline on the same set is planned but not run: it costs API calls).\n")
    return "\n".join(L)


def main() -> None:
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "latest"
    results, _ = run()
    summ = summarise(results)
    text = report(results, summ).replace("# Decode Phase 3 evaluation (D44)", f"# Decode Phase 3 evaluation (D44), run: {tag}", 1)
    print(text)
    if "--write" in sys.argv:
        out = ROOT / "eval" / "results" / f"decode_eval_v1_{tag}.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print("\nWrote", out)


if __name__ == "__main__":
    main()
