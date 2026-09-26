"""Targeted run on the L2-ARCTIC SCRIPTED utterances (Arabic and Hindi) that contain at least one real-word swap, Sarvam `transcribe` only.

    python tools/stt_compare/scripted_eval.py                 # plan only: utterance count, calls, estimated cost; sends nothing
    python tools/stt_compare/scripted_eval.py --yes           # runs it (uses your Sarvam credits)

Source: the sibling dataset `KoelLabs/L2Arctic` (gated, CC-BY-NC-4.0), `scripted` split, read from the cache. Utterances are selected with the same
rules as the spontaneous analysis (word_align: text segmented over g2p with CMUdict, accent word = heard phones differ, clear real-word swap = the
heard phones spell exactly one COMMON English word). Clips are written to `recordings/l2arctic-scripted/` (gitignored). The report
(`report_l2arctic_scripted.md`) and `results_l2arctic_scripted.json` are gitignored: they contain transcripts of licensed audio.

WhatsApp-like conditions (D42): `--profile whatsapp-snr10` (or -snr15 / -snr5) mixes DEMAND noise (CC BY 4.0) into each clip at that signal-to-noise
ratio, downsamples to 8 kHz and encodes Opus at 16 kbps in Ogg (see whatsapp_sim.py), then reports next to the clean run. The degraded files are
written once to `recordings/l2arctic-scripted-<profile>/` (gitignored) and reused, so a re-run costs no new calls.

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
import whatsapp_sim as wsim  # noqa: E402
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


def prepare_clip(c: dict, index: int, profile, noises: dict, folder: Path) -> tuple[str, bytes]:
    """(file name, bytes) to send: the clean wav, or a WhatsApp-like Opus file made once and then reused (Ogg output is not byte-stable)."""
    if profile is None:
        path = folder / f"{c['id']}.wav"
        if not path.exists():
            path.write_bytes(c["wav"])
        return path.name, c["wav"]
    path = folder / f"{c['id']}.ogg"
    if not path.exists():
        _, noise = wsim.noise_for(profile, index, noises)
        path.write_bytes(wsim.degrade(c["wav"], noise, profile, c["id"]))
    return path.name, path.read_bytes()


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


CRITICAL_CATEGORIES = ("number", "time", "place", "negation")  # D41: the words a wrong transcription would hurt most


def outcome(kind: str, wrote: str | None, lex: dict) -> str:
    if kind == we.KEPT:
        return "kept"
    if kind in (we.FIXED, we.RECOGNISED):
        return "intended"
    if kind == we.NONE:
        return "not aligned"
    return "wrong real word" if is_real(wrote, lex) else "other (not a word)"


def category_section(rows, lex: dict) -> list[str]:
    """Numbers, times, places and negations only (owner request, D41): how the accent words in those categories came out."""
    from steve_engine.decode.domain import get_domain

    dom = get_domain()
    order = ["kept", "intended", "wrong real word", "other (not a word)", "not aligned"]
    counts: dict[str, Counter] = {c: Counter() for c in CRITICAL_CATEGORIES}
    detail: list[tuple] = []
    for accent, clip, wv, kind, wrote in rows:
        cat = dom.category(wv.word)
        if cat not in counts:
            continue
        o = outcome(kind, wrote, lex)
        counts[cat]["words"] += 1
        counts[cat]["swaps"] += bool(wv.swap_word)
        counts[cat][o] += 1
        if o in ("kept", "wrong real word"):
            detail.append((cat, accent, clip, wv.word, wv.swap_word or "".join(wv.heard), wrote, o))
    L = ["", "## Numbers, times, places and negations only (D41)", "",
         "Accent words (heard differently) whose INTENDED word is in the domain lists (`steve_engine/decode/domain.yaml`, unverified working lists). "
         "Literary text has few of them, so the counts are small.", "",
         "| Category | Accent words | of which real-word swaps | " + " | ".join(o.capitalize() for o in order) + " |", "|---|---:|---:|" + "---:|" * len(order)]
    for cat in CRITICAL_CATEGORIES:
        c = counts[cat]
        L.append(f"| {cat} | {c['words']} | {c['swaps']} | " + " | ".join(str(c[o]) for o in order) + " |")
    tot = Counter()
    for c in counts.values():
        tot.update(c)
    L.append(f"| **all four** | {tot['words']} | {tot['swaps']} | " + " | ".join(str(tot[o]) for o in order) + " |")
    if detail:
        L += ["", "Cases where the accent survived or another real word was written:", "", "| Category | Accent | Clip | Intended | Heard | Sarvam wrote | Outcome |", "|---|---|---|---|---|---|---|"]
        L += [f"| {cat} | {a} | {clip} | {w} | {heard} | **{wrote}** | {o} |" for cat, a, clip, w, heard, wrote, o in sorted(detail)]
    return L + [""]


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

    L += category_section(rows, lex)
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


def condition_row(rows, plain, accent: str, lex: dict) -> dict:
    swaps = [r for r in rows if r[2].swap_word and (accent == "all" or r[0] == accent)]
    kinds = Counter(r[3] for r in swaps)
    real_other = sum(1 for r in swaps if r[3] == we.GARBLED and is_real(r[4], lex))
    acc_words = [r for r in rows if accent == "all" or r[0] == accent]
    wrong_real = sum(1 for r in acc_words if r[3] in (we.GARBLED, we.OTHER) and is_real(r[4], lex))
    words = sum(v["words"] for a, v in plain.items() if accent == "all" or a == accent)
    missing = sum(v["not written as such"] for a, v in plain.items() if accent == "all" or a == accent)
    return {"swaps": len(swaps), "kept": kinds[we.KEPT], "fixed": kinds[we.FIXED], "other": kinds[we.GARBLED], "other_real": real_other,
            "none": kinds[we.NONE], "accent_words": len(acc_words), "wrong_real": wrong_real, "plain_words": words, "plain_missing": missing}


def build_comparison(conditions: dict[str, dict[str, dict]], accents: list[str], empty: dict[str, int]) -> list[str]:
    """conditions: {condition name: {accent: condition_row}}."""
    L = ["## Clean vs WhatsApp-like (same 389 utterances, Sarvam transcribe)", "",
         "| Condition | Accent | Swap words | Kept | Fixed | Other | of which a real word | Not aligned | Wrong real word, all accent words | Intended word missing, normal words | Empty transcripts |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for a in accents + ["all"]:
        for name, by in conditions.items():
            r = by[a]
            s = max(r["swaps"], 1)
            L.append(f"| {name} | {a} | {r['swaps']} | {r['kept']} ({100 * r['kept'] / s:.1f}%) | {r['fixed']} ({100 * r['fixed'] / s:.1f}%) | {r['other']} ({100 * r['other'] / s:.1f}%) | "
                     f"{r['other_real']} | {r['none']} | {r['wrong_real']} of {r['accent_words']} ({100 * r['wrong_real'] / max(r['accent_words'], 1):.1f}%) | "
                     f"{r['plain_missing']} of {r['plain_words']} ({100 * r['plain_missing'] / max(r['plain_words'], 1):.1f}%) | {empty.get(name, 0) if a == 'all' else ''} |")
    return L + [""]


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
    ap.add_argument("--profile", default="clean", choices=["clean", *sorted(wsim.PROFILES)], help="clean audio, or a WhatsApp-like degradation")
    args = ap.parse_args(argv)
    profile = None if args.profile == "clean" else wsim.PROFILES[args.profile]
    tag = "" if profile is None else f"_{profile.name.replace('whatsapp-', 'whatsapp_')}"

    lex = ps.pronunciations()
    inv = wa.inverse_lexicon(lex)
    clips = select(args.file, tuple(x.strip() for x in args.l1.split(",") if x.strip()), lex, inv)
    if args.limit:
        clips = clips[: args.limit]
    minutes = seconds(clips) / 60
    per = Counter(c["accent"] for c in clips)
    sarvam = Sarvam()
    print(f"{len(clips)} scripted utterances with a real-word swap ({', '.join(f'{k}={v}' for k, v in sorted(per.items()))}), {minutes:.1f} audio-minutes")
    if profile:
        print(f"Condition: {profile.name}: noise {', '.join(profile.noises)} (DEMAND, CC BY 4.0) at {profile.snr_db:g} dB SNR, {profile.phone_rate} Hz, Opus {profile.bitrate} in Ogg")
    print(f"= {len(clips)} Sarvam calls (saaras:v3 transcribe, en-IN). Estimated cost: INR {minutes / 60 * PRICE_INR_PER_HOUR:.1f} "
          f"at INR {PRICE_INR_PER_HOUR:g}/hour (verify at https://www.sarvam.ai/api-pricing); at {args.sleep:.1f} s per call it takes about {len(clips) * args.sleep / 60:.0f} min.")
    if not sarvam.available():
        print("No SARVAM_API_KEY in the environment / .env.")
        return 1
    if not args.yes:
        print("\nPlan only. Nothing was sent. Add --yes to run it.")
        return 0

    variant = sarvam.variants(VARIANT_SPEC)[0]
    clips_dir = CLIPS_DIR if profile is None else CLIPS_DIR.parent / profile.folder
    clips_dir.mkdir(parents=True, exist_ok=True)
    noises = {n: wsim.load_noise(n) for n in profile.noises} if profile else {}
    cache = HERE / ".cache"
    transcripts: dict[str, str] = {}
    raw, errors_in_row, stopped, calls = [], 0, None, 0
    for i, c in enumerate(clips, 1):
        name, data = prepare_clip(c, i - 1, profile, noises, clips_dir)
        out = run.run_variant(sarvam, variant, name, data, cache, True)
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
    report = build_report(rows, plain, clips, lex, calls, minutes, stopped, spontaneous_summary(lex, inv) if profile is None else None)
    if profile:
        report = report.replace("# STT reality test: L2-ARCTIC SCRIPTED", f"# STT reality test ({profile.name}): L2-ARCTIC SCRIPTED", 1)
        clean_path = args.out / "results_l2arctic_scripted.json"
        if clean_path.exists():
            clean_t = {r["clip"]: r["transcript"] for r in json.loads(clean_path.read_text(encoding="utf-8")) if not r["error"]}
            crows, cplain = analyse(clips, clean_t, lex)
            accents = sorted(per)
            conds = {"clean": {a: condition_row(crows, cplain, a, lex) for a in accents + ["all"]},
                     profile.name: {a: condition_row(rows, plain, a, lex) for a in accents + ["all"]}}
            empty = {"clean": sum(1 for v in clean_t.values() if not v.strip()), profile.name: sum(1 for v in transcripts.values() if not v.strip())}
            report = report.replace("## Real-word swaps", "\n".join(build_comparison(conds, accents, empty)) + "\n## Real-word swaps", 1)
    (args.out / f"report_l2arctic_scripted{tag}.md").write_text(report, encoding="utf-8", newline="\n")
    (args.out / f"results_l2arctic_scripted{tag}.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'STOPPED EARLY: ' + stopped if stopped else 'Done'}: {len(transcripts)} transcripts. Wrote {args.out / f'report_l2arctic_scripted{tag}.md'}")
    return 0 if not stopped else 3


if __name__ == "__main__":
    sys.exit(main())
