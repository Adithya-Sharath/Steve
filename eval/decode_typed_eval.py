"""The typed-text decoder on the synthetic typed set (`data/decode/typed_synthetic.csv`, synthetic=true, D41).

    python eval/decode_typed_eval.py

For rows that were typed by ear (accent swaps applied to a clean sentence):
    exact      the decoded plain English equals the intended sentence (number words and digits are compared as numbers)
    clarified  the decoder asked a question whose options include the intended word instead of guessing
    wrong      the decoded sentence differs from the intended one and no question covers the difference (a silent mistake)
For controls (typed correctly): any change or question is a FALSE ALARM. The false-alarm rate is a headline number.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from steve_engine.decode import decode
from steve_engine.decode.actions import parse_number
from steve_engine.decode.safety import SafetyConfig

_WORDS = re.compile(r"[a-z']+|\d+")


def norm(text: str) -> list[str]:
    words = _WORDS.findall(text.lower().replace("’", "'"))
    out, i = [], 0
    while i < len(words):
        n = parse_number(words, i)
        if n and (words[i].isdigit() or words[i] not in {"one"}):
            out.append(str(n[0]))
            i = n[1]
        else:
            out.append(words[i])
            i += 1
    return out


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def evaluate_typed(rows: list[dict], cfg: SafetyConfig | None = None) -> dict:
    res: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        acc = r["accent"]
        card = decode(r["text_as_typed"], None if acc == "none" else acc, "typed", cfg)
        want, typed, got = norm(r["intended_meaning"]), norm(r["text_as_typed"]), norm(card.plain_english)
        # glossary phrases are rewritten in the plain English; compare on the words that are not glossary spans
        for key in (acc, "all"):
            c = res[key]
            c["n"] += 1
            if r["changes"]:  # typed by ear
                c["typed_by_ear"] += 1
                options = {o for q in card.clarify for o in q.options}
                intended_words = {w for w in want if w not in typed}
                if got == want:
                    c["exact"] += 1
                elif intended_words and intended_words & options:
                    c["clarified"] += 1
                else:
                    c["wrong"] += 1
            else:  # control
                c["control"] += 1
                changed, asked = got != typed, bool(card.clarify)
                c["false_rewrite"] += changed
                c["false_question"] += asked
                c["false_any"] += changed or asked
    return res


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "n/a"


def table(res: dict) -> str:
    lines = ["| Accent | Typed by ear | Exact | Asked (intended word offered) | Wrong | Solved or asked | Controls | False rewrites | False questions | False-alarm rate |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for a in sorted(k for k in res if k != "all") + ["all"]:
        c = res[a]
        lines.append(f"| {a} | {c['typed_by_ear']} | {c['exact']} | {c['clarified']} | {c['wrong']} | {pct(c['exact'] + c['clarified'], c['typed_by_ear'])} | "
                     f"{c['control']} | {c['false_rewrite']} | {c['false_question']} | {pct(c['false_any'], c['control'])} |")
    return "\n".join(lines)


def main() -> None:
    rows = load(ROOT / "data" / "decode" / "typed_synthetic.csv")
    print(f"Synthetic typed set: {len(rows)} rows (synthetic=true; the set the typed margins were tuned on)\n")
    print(table(evaluate_typed(rows)))


if __name__ == "__main__":
    main()
