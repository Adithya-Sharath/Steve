"""HELD-OUT test of the voice safety net on the L2-ARCTIC scripted run (D41). L2-ARCTIC is a TEST set only: nothing here was used to tune a rule or a
margin (those were tuned on the synthetic domain set, `eval/decode_safety_eval.py`).

    python tools/stt_compare/safety_eval.py            # uses the cached Sarvam transcripts (clean and, if present, whatsapp-snr10); no new calls

Risky words   = the words where Sarvam wrote something other than the intended word at an accent word and it is a different real word that changes
                the word (not a spelling/plural/tense variant), plus the words where it wrote the HEARD word (kept): 50 + 23 = 73 on the clean run.
Correct words = every word Sarvam wrote exactly as intended (the 428 accent words it fixed, and every other correctly transcribed word).
Catch rate       = risky words the net rewrote to the intended word or asked about (options include the intended word).
False-alarm rate = correct words the net rewrote (false rewrites) or asked about (false questions).
Reported per accent and per condition. The report is gitignored (it contains transcripts of licensed audio).
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "importers"))
sys.path.insert(0, str(ROOT / "engine"))

import phone_scoring as ps  # noqa: E402
import scripted_eval as se  # noqa: E402
import word_align as wa  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402
from steve_engine.decode.safety import SafetyConfig, review_transcript  # noqa: E402
from steve_engine.decode.tokens import tokenize  # noqa: E402


def aligned_words(views, transcript: str):
    """[(WordView, transcript Token or None)] by a word-level alignment of the transcript's alphabetic tokens to the intended words."""
    toks = [t for t in tokenize(transcript) if t.norm.isalpha()]
    intended = [v.word for v in views]
    got = [t.norm for t in toks]
    pairs: dict[int, object] = {}
    for tag, i1, i2, j1, j2 in Levenshtein.opcodes(intended, got):
        if tag in ("equal", "replace"):
            for k in range(i2 - i1):
                pairs[i1 + k] = toks[j1 + k] if j1 + k < j2 else None
        elif tag == "delete":
            for k in range(i1, i2):
                pairs[k] = None
    return [(v, pairs.get(i)) for i, v in enumerate(views)]


def judge(review, tok, want: str) -> str:
    for c in review.changes:
        if c.span.start == tok.start:
            return "caught_rewrite" if c.meant == want else "wrong_rewrite"
    for q in review.clarify:
        if q.span.start == tok.start:
            return "caught_clarify" if want in q.options else "clarify_without_answer"
    return "missed"


def evaluate(clips, transcripts: dict[str, str], lex, cfg: SafetyConfig | None = None):
    risky: dict[str, Counter] = defaultdict(Counter)
    clean: dict[str, Counter] = defaultdict(Counter)
    for c in clips:
        got = transcripts.get(c["id"])
        if got is None:
            continue
        acc = c["accent"]
        hint = {"Arabic": "ar", "Hindi": "hi"}.get(acc)
        review = review_transcript(got, hint, cfg)
        for v, tok in aligned_words(c["views"], got):
            if tok is None or not v.exact:
                continue
            is_risky = False
            if tok.norm != v.word:
                kept = bool(v.swap_word) and tok.norm == v.swap_word
                changed = v.accent and se.is_real(tok.norm, lex) and not se.likely_variant(v.word, tok.norm)
                is_risky = kept or changed
            if is_risky:
                verdict = judge(review, tok, v.word)
                for k in (acc, "all"):
                    risky[k]["n"] += 1
                    risky[k][verdict] += 1
                    risky[k]["kept_case" if v.swap_word and tok.norm == v.swap_word else "changed_case"] += 1
            elif tok.norm == v.word:
                rewrote = any(ch.span.start == tok.start for ch in review.changes)
                asked = any(q.span.start == tok.start for q in review.clarify)
                for k in (acc, "all"):
                    for name in ("correct", "fixed_accent") if v.accent else ("correct",):
                        clean[f"{k}|{name}"]["n"] += 1
                        clean[f"{k}|{name}"]["rewrite"] += rewrote
                        clean[f"{k}|{name}"]["question"] += asked
                        clean[f"{k}|{name}"]["any"] += rewrote or asked
    return risky, clean


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "n/a"


def rows_for(condition: str, risky, clean, accents: list[str]) -> list[str]:
    out = []
    for a in accents + ["all"]:
        r = risky[a]
        c, f = clean[f"{a}|correct"], clean[f"{a}|fixed_accent"]
        caught = r["caught_rewrite"] + r["caught_clarify"]
        out.append(f"| {condition} | {a} | {r['n']} | {r['caught_rewrite']} | {r['caught_clarify']} | {pct(caught, r['n'])} | {r['wrong_rewrite']} | "
                   f"{r['missed'] + r['clarify_without_answer']} | {c['n']} | {c['rewrite']} | {c['question']} | {pct(c['any'], c['n'])} | "
                   f"{f['n']} | {f['any']} | {pct(f['any'], f['n'])} |")
    return out


def main() -> int:
    import pyarrow.parquet as pq  # noqa: F401

    lex = ps.pronunciations()
    inv = wa.inverse_lexicon(lex)
    clips = se.select(se.PARQUET, ("Arabic", "Hindi"), lex, inv)
    accents = sorted({c["accent"] for c in clips})
    lines = ["# Voice safety net on L2-ARCTIC (held-out test), Sarvam transcribe transcripts", "",
             f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}. Nothing here tuned the net (D41). Directional only; not committed.", "",
             "| Condition | Accent | Risky words | Caught by rewrite | Caught by question | Catch rate | Wrong rewrite | Missed | Correct words | False rewrites | False questions | "
             "False-alarm rate | Accent words Sarvam fixed | Alarms on them | Their false-alarm rate |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for cond, path in (("clean", HERE / "results_l2arctic_scripted.json"), ("whatsapp-snr10", HERE / "results_l2arctic_scripted_whatsapp_snr10.json")):
        if not path.exists():
            continue
        transcripts = {r["clip"]: r["transcript"] for r in json.loads(path.read_text(encoding="utf-8")) if not r["error"]}
        risky, clean = evaluate(clips, transcripts, lex)
        lines += rows_for(cond, risky, clean, accents)
        print(cond, {k: dict(v) for k, v in risky.items() if k == "all"}, {k: dict(v) for k, v in clean.items() if k.startswith("all|")})
    lines += ["", "Risky = accent words where Sarvam wrote a different real word that changes the word, or wrote the heard word. Correct = every word written exactly as intended."]
    (HERE / "report_safety_l2arctic.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("Wrote", HERE / "report_safety_l2arctic.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
