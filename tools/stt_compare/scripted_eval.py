"""Targeted run on the L2-ARCTIC SCRIPTED utterances (Arabic and Hindi) that contain at least one real-word swap, Sarvam `transcribe` only.

    python tools/stt_compare/scripted_eval.py                 # plan only: utterance count, calls, estimated cost; sends nothing
    python tools/stt_compare/scripted_eval.py --yes           # runs it (uses your Sarvam credits)

Source: the sibling dataset `KoelLabs/L2Arctic` (gated, CC-BY-NC-4.0), `scripted` split, read from the cache. Utterances are selected with the same
rules as the spontaneous analysis (word_align: text segmented over g2p with CMUdict, accent word = heard phones differ, clear real-word swap = the
heard phones spell exactly one COMMON English word). Clips are written to `recordings/l2arctic-scripted/` (gitignored). The report
(`report_l2arctic_scripted.md`) and `results_l2arctic_scripted.json` are gitignored: they contain transcripts of licensed audio.

Guards: never runs without --yes; paced under Sarvam's Starter limit (60 requests/min); stops at once on a credit/quota-looking error, and after
3 errors in a row, instead of burning through the list. DIRECTIONAL SIGNAL ONLY (D39/D40).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "importers"))

import l2arctic_spontaneous as l2  # noqa: E402
import phone_scoring as ps  # noqa: E402
import word_align as wa  # noqa: E402
import word_eval as we  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402

import run  # noqa: E402
from providers import Sarvam  # noqa: E402

PARQUET = HERE / ".cache/l2arctic-full/data/scripted-00000-of-00001.parquet"
CLIPS_DIR = HERE / "recordings" / "l2arctic-scripted"  # looked up at call time in main()
PRICE_INR_PER_HOUR = 30.0  # Sarvam real-time speech-to-text, https://www.sarvam.ai/api-pricing (read 2026-09-26; verify)
STARTER_RPM = 60
STOP_WORDS = ("credit", "insufficient", "balance", "quota", "payment", "402", "403", "401")
VARIANT_SPEC = "saaras:v3|transcribe|en-IN"


def select(parquet: Path, l1s: tuple[str, ...], lex: dict, inv: dict) -> list[dict]:
    import pyarrow.parquet as pq

    want = {x.lower() for x in l1s}
    out = []
    for idx, r in enumerate(pq.read_table(parquet).to_pylist()):
        l1 = str(r["speaker_native_language"])
        if l1.lower() not in want:
            continue
        views = wa.utterance_words(r["text"], r["g2p"], r["ipa"], lex, inv)
        if views and any(v.swap_word for v in views):
            out.append({"id": f"{r['speaker_code'].lower()}_{idx:04d}", "accent": l1, "speaker": r["speaker_code"], "text": r["text"],
                        "g2p": r["g2p"], "ipa": r["ipa"], "wav": r["audio"]["bytes"], "views": views})
    return out


def seconds(clips: list[dict]) -> float:
    return sum(l2.wav_seconds(c["wav"]) or 0.0 for c in clips)


def looks_like_credit_error(err: str | None) -> bool:
    return bool(err) and any(w in err.lower() for w in STOP_WORDS)


def analyse(clips: list[dict], transcripts: dict[str, str], lex: dict):
    """-> rows [(accent, clip, WordView, outcome, transcript word)] for accent words, plus counts for words that are not accent words."""
    rows, plain = [], defaultdict(Counter)
    for c in clips:
        if c["id"] not in transcripts:
            continue
        got = transcripts[c["id"]]
        for wv, kind, w in we.classify_words(c["views"], got):
            rows.append((c["accent"], c["id"], wv, kind, w))
        # words that were NOT heard differently: how often did Sarvam write a different real word anyway (the baseline)?
        wrote = set(wa.words_of(got))
        for v in (v for v in c["views"] if not v.accent and v.exact):
            plain[c["accent"]]["words"] += 1
            if v.word not in wrote:
                plain[c["accent"]]["not written as such"] += 1
    return rows, plain


def is_real(word: str | None, lex: dict) -> bool:
    return bool(word) and word in lex


def likely_variant(intended: str, wrote: str | None) -> bool:
    """Spelling, plural, tense or a digit leftover rather than a different word (gray/grey, shadows/shadow, twentieth/'th')."""
    if not wrote:
        return False
    a, b = intended.lower(), wrote.lower()
    return a.startswith(b) or b.startswith(a) or (len(b) >= 2 and a.endswith(b)) or Levenshtein.distance(a, b) <= 1


def build_report(rows, plain, clips, lex, calls: int, minutes: float, stopped: str | None, spont: dict | None) -> str:
    accents = sorted({c["accent"] for c in clips})
    L = ["# STT reality test: L2-ARCTIC SCRIPTED, targeted subset (utterances with a real-word swap), Sarvam saaras:v3 transcribe / en-IN", "",
         f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}. {len(clips)} utterances, {calls} calls, {minutes:.1f} audio-minutes.", "",
         "> **DIRECTIONAL SIGNAL ONLY.** Read speech (book sentences), 8 speakers, and utterances chosen BECAUSE they contain a swap, so they over-represent "
         "accent words. Source data is CC-BY-NC-4.0; this report is not committed.", ""]
    if stopped:
        L += [f"**RUN STOPPED EARLY: {stopped}**", ""]

    def tally(pred):
        c = Counter()
        for a, _, wv, k, w in rows:
            if pred(a, wv):
                c[k if k in (we.KEPT, we.FIXED, we.NONE) else "other"] += 1
                if k == we.GARBLED and is_real(w, lex):
                    c["other: a different real word"] += 1
        return c

    L += ["## Real-word swaps (the heard form is a different real word)", "",
          "| Source | Accent | Swap words | Kept (heard word written) | Fixed (intended word written) | Other | of which a different real word | Not aligned |",
          "|---|---|---:|---:|---:|---:|---:|---:|"]
    for a in accents + ["all"]:
        c = tally(lambda ac, wv, a=a: wv.swap_word and (a == "all" or ac == a))
        n = c[we.KEPT] + c[we.FIXED] + c["other"] + c[we.NONE]
        L.append(f"| scripted | {a} | {n} | {c[we.KEPT]} | {c[we.FIXED]} | {c['other']} | {c['other: a different real word']} | {c[we.NONE]} |")
    if spont:
        for a in [k for k in sorted(spont) if k != "all"] + (["all"] if "all" in spont else []):
            s = spont[a]
            L.append(f"| spontaneous (earlier run) | {a} | {s['n']} | {s['kept']} | {s['fixed']} | {s['other']} | {s.get('real', 'n/a')} | {s['none']} |")
    L += ["", "## Accent words that are not real-word swaps (the heard form is not a word)", "",
          "| Accent | Distorted words | Recognised as intended | Other | of which a different real word | Not aligned |", "|---|---:|---:|---:|---:|---:|"]
    for a in accents + ["all"]:
        c = Counter()
        for ac, _, wv, k, w in rows:
            if not wv.swap_word and (a == "all" or ac == a):
                c["n"] += 1
                c[k] += 1
                if k == we.OTHER and is_real(w, lex):
                    c["real"] += 1
        L.append(f"| {a} | {c['n']} | {c[we.RECOGNISED]} | {c[we.OTHER]} | {c['real']} | {c[we.NONE]} |")

    L += ["", "## Plausible-but-wrong: Sarvam wrote a DIFFERENT REAL WORD than the intended one at an accent word", "",
          "| Clip | Accent | Intended | Heard (annotators) | Sarvam wrote | Kind | Note |", "|---|---|---|---|---|---|---|"]
    bad = [(a, cl, wv, k, w) for a, cl, wv, k, w in rows if k in (we.GARBLED, we.OTHER) and is_real(w, lex)]
    for a, cl, wv, _k, w in sorted(bad, key=lambda r: (r[2].word, r[1])):
        heard = wv.swap_word or "".join(wv.heard)
        note = "likely spelling / plural / tense / digit variant" if likely_variant(wv.word, w) else ""
        L.append(f"| {cl} | {a} | {wv.word} | {heard}{'' if wv.swap_word else ' (not a word)'} | **{w}** | {'real-word swap' if wv.swap_word else 'non-word distortion'} | {note} |")
    if not bad:
        L.append("| _none_ | | | | | | |")
    variants = sum(likely_variant(wv.word, w) for _, _, wv, _, w in bad)
    L += ["", f"Total: {len(bad)} of {len(rows)} accent words; {variants} of them look like spelling, plural, tense or digit variants, "
              f"{len(bad) - variants} change the word.", ""]
    kept = [(a, cl, wv, w) for a, cl, wv, k, w in rows if k == we.KEPT]
    L += ["## Kept: Sarvam wrote the HEARD word (the accent survived into the text)", "", "| Clip | Accent | Intended | Sarvam wrote (= heard) |", "|---|---|---|---|"]
    L += [f"| {cl} | {a} | {wv.word} | **{w}** |" for a, cl, wv, w in sorted(kept, key=lambda r: (r[2].word, r[1]))] or ["| _none_ | | | |"]
    L.append("")
    if plain:
        L += ["## Baseline: words that were NOT heard differently", "", "How often does the intended word fail to appear anywhere in the transcript, for words the annotators heard as normal?", "",
              "| Accent | Words | Intended word not in the transcript | Share |", "|---|---:|---:|---:|"]
        for a in accents:
            p = plain[a]
            L.append(f"| {a} | {p['words']} | {p['not written as such']} | {100 * p['not written as such'] / p['words']:.1f}% |" if p["words"] else f"| {a} | 0 | 0 | n/a |")
        L.append("")
    L += ["## Caveats", "",
          "- Word-level classification uses a word alignment of the transcript to the intended sentence; numbers, hyphens and compounds can shift it.",
          "- 'Different real word' means the transcript word is in CMUdict; a rare real word or a proper name counts too. Read the list.",
          "- The heard form comes from annotators' perceived phones; a swap is 'clear' only if it spells one common word (wordfreq Zipf >= 3.5).", ""]
    return "\n".join(L)


def spontaneous_summary(lex, inv) -> dict | None:
    """Earlier spontaneous numbers (transcribe only), recomputed from the cached transcripts."""
    import pyarrow.parquet as pq

    res = HERE / "results_l2arctic_spont.json"
    full_p = HERE / ".cache/l2arctic-full/data/spontaneous-00000-of-00001.parquet"
    if not (res.exists() and full_p.exists()):
        return None
    import phone_eval

    full = {r["speaker_code"].lower(): r for r in pq.read_table(full_p, columns=["text", "g2p", "ipa", "speaker_code", "speaker_native_language"]).to_pylist()}
    clips = phone_eval.load_clips(HERE / ".cache/l2arctic/data/train-00000-of-00001.parquet", ("Arabic", "Hindi"))
    results = [r for r in json.loads(res.read_text(encoding="utf-8")) if "transcribe" in r["variant"]]
    rows, _, _ = we.evaluate(clips, full, results, lex, inv)
    out: dict = {}
    for a in ("Arabic", "Hindi", "all"):
        c = Counter()
        for ac, _, _, ws in rows:
            for wv, k, w in ws:
                if wv.swap_word and (a == "all" or ac == a):
                    c["n"] += 1
                    c["kept" if k == we.KEPT else "fixed" if k == we.FIXED else "none" if k == we.NONE else "other"] += 1
                    if k == we.GARBLED and is_real(w, lex):
                        c["real"] += 1
        out[a] = {k: c[k] for k in ("n", "kept", "fixed", "other", "none", "real")}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--l1", default="Arabic,Hindi")
    ap.add_argument("--file", type=Path, default=PARQUET)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--out", type=Path, default=HERE)
    ap.add_argument("--sleep", type=float, default=60.0 / STARTER_RPM + 0.1)
    args = ap.parse_args(argv)

    lex = ps.pronunciations()
    inv = wa.inverse_lexicon(lex)
    clips = select(args.file, tuple(x.strip() for x in args.l1.split(",") if x.strip()), lex, inv)
    if args.limit:
        clips = clips[: args.limit]
    minutes = seconds(clips) / 60
    per = Counter(c["accent"] for c in clips)
    sarvam = Sarvam()
    print(f"{len(clips)} scripted utterances with a real-word swap ({', '.join(f'{k}={v}' for k, v in sorted(per.items()))}), {minutes:.1f} audio-minutes")
    print(f"= {len(clips)} Sarvam calls (saaras:v3 transcribe, en-IN). Estimated cost: INR {minutes / 60 * PRICE_INR_PER_HOUR:.1f} "
          f"at INR {PRICE_INR_PER_HOUR:g}/hour (verify at https://www.sarvam.ai/api-pricing); at {args.sleep:.1f} s per call it takes about {len(clips) * args.sleep / 60:.0f} min.")
    if not sarvam.available():
        print("No SARVAM_API_KEY in the environment / .env.")
        return 1
    if not args.yes:
        print("\nPlan only. Nothing was sent. Add --yes to run it.")
        return 0

    variant = sarvam.variants(VARIANT_SPEC)[0]
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    cache = HERE / ".cache"
    transcripts: dict[str, str] = {}
    raw, errors_in_row, stopped, calls = [], 0, None, 0
    for i, c in enumerate(clips, 1):
        wav_path = CLIPS_DIR / f"{c['id']}.wav"
        if not wav_path.exists():
            wav_path.write_bytes(c["wav"])
        out = run.run_variant(sarvam, variant, f"{c['id']}.wav", c["wav"], cache, True)
        calls += not out["cached"]
        raw.append({"clip": c["id"], "accent": c["accent"], "transcript": out["text"], "error": out["error"], "latency": out["latency"], "cached": out["cached"]})
        if out["error"]:
            errors_in_row += 1
            print(f"  [{i}/{len(clips)}] {c['id']}: ERROR {out['error'][:120]}")
            if looks_like_credit_error(out["error"]):
                stopped = f"credit/quota-looking error on call {i}: {out['error'][:120]}"
                break
            if errors_in_row >= 3:
                stopped = f"3 errors in a row (last: {out['error'][:120]})"
                break
        else:
            errors_in_row = 0
            transcripts[c["id"]] = out["text"]
            if i % 25 == 0:
                print(f"  [{i}/{len(clips)}] ok")
        if not out["cached"]:
            time.sleep(args.sleep)
    rows, plain = analyse(clips, transcripts, lex)
    report = build_report(rows, plain, clips, lex, calls, minutes, stopped, spontaneous_summary(lex, inv))
    (args.out / "report_l2arctic_scripted.md").write_text(report, encoding="utf-8", newline="\n")
    (args.out / "results_l2arctic_scripted.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'STOPPED EARLY: ' + stopped if stopped else 'Done'}: {len(transcripts)} transcripts. Wrote {args.out / 'report_l2arctic_scripted.md'}")
    return 0 if not stopped else 3


if __name__ == "__main__":
    sys.exit(main())
