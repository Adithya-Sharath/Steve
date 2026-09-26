"""Run the STT reality test on the L2-ARCTIC spontaneous clips and score it at phone level (see phone_scoring.py).

    python tools/stt_compare/phone_eval.py                 # plan only: clip counts and calls, sends nothing
    python tools/stt_compare/phone_eval.py --quick --yes   # Sarvam saaras:v3 transcribe + verbatim, en-IN: clips x 2 calls

Reads the gated parquet from the cache (downloads it with HF_TOKEN if needed), writes the clips as WAV files into
`recordings/l2arctic-spont/` (gitignored; CC-BY-NC audio is never committed), and writes `report_l2arctic_spont.md` and
`results_l2arctic_spont.json` next to this file (gitignored: they contain transcripts of licensed audio).
DIRECTIONAL SIGNAL ONLY: a few dozen clips, phone-level proxy, one listener-annotation scheme (D39).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "importers"))

import l2arctic_spontaneous as l2  # noqa: E402
import phone_scoring as ps  # noqa: E402

import run  # noqa: E402
from providers import Sarvam  # noqa: E402

CLIPS_DIR = HERE / "recordings" / "l2arctic-spont"


def load_clips(parquet: Path, l1s: tuple[str, ...]) -> list[dict]:
    import pyarrow.parquet as pq

    want = {x.lower() for x in l1s}
    counters: dict[str, int] = {}
    clips = []
    for r in pq.read_table(parquet).to_pylist():
        l1 = str(r["speaker_native_language"])
        if l1.lower() not in want:
            continue
        n = counters[r["speaker_code"]] = counters.get(r["speaker_code"], 0) + 1
        clips.append({
            "id": f"{r['speaker_code']}_{n:02d}", "accent": l1, "speaker": r["speaker_code"], "ipa": r["ipa"], "g2p": r["g2p"],
            "wav": r["audio"]["bytes"],
        })
    return clips


def write_clips(clips: list[dict], folder: Path | None = None) -> None:
    folder = folder or CLIPS_DIR  # looked up at call time
    folder.mkdir(parents=True, exist_ok=True)
    for c in clips:
        p = folder / f"{c['id']}.wav"
        if not p.exists():
            p.write_bytes(c["wav"])


def _f(x: float | None, d: int = 0, unit: str = "%") -> str:
    return "n/a" if x is None else f"{x:.{d}f}{unit}"


def build_report(scores: list[ps.ClipScore], variants: list[str], accents: list[str], n_clips: int, errors: dict[str, int]) -> str:
    L = [
        "# STT reality test: L2-ARCTIC spontaneous (Arabic and Hindi), phone-level",
        "",
        f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}. {n_clips} clips (10-12.5 s each).",
        "",
        "> **DIRECTIONAL SIGNAL ONLY.** A few dozen clips, a phone-level proxy (not word-level), one annotation scheme, a first dictionary pronunciation per "
        "word. It shows a tendency, not a rate you can quote for real speakers. Source data is CC-BY-NC-4.0; this report contains transcripts of it and is not committed.",
        "",
        "## What was measured",
        "",
        "For every position where the annotators heard a different phone from the canonical one (for example /p/ heard as /b/), what did the speech-to-text "
        "transcript do there? The transcript was turned back into phones (CMUdict) and aligned to the canonical phones. **kept** = the transcript has the "
        "phone that was actually heard; **fixed** = it has the canonical phone (the recogniser corrected it); **garbled** = something else; "
        "**no counterpart** = nothing aligned there. Percentages use kept + fixed + garbled as the base.",
        "",
        "## Per accent and provider mode",
        "",
        "| Accent | Provider / mode / language | Clips | Accent positions | Kept | Fixed | Garbled | No counterpart | Phone error vs heard | Phone error vs canonical | Words in dictionary |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for a in accents + ["all"]:
        for v in variants:
            sub = [s for s in scores if s.variant == v and (a == "all" or s.accent == a)]
            t = ps.tally(sub)
            k = t.kinds
            avg = lambda xs: 100 * sum(xs) / len(xs) if xs else None  # noqa: E731
            L.append(f"| {a} | {v} | {t.clips} | {t.positions} | {_f(t.pct(ps.KEPT))} ({k[ps.KEPT]}) | {_f(t.pct(ps.FIXED))} ({k[ps.FIXED]}) | "
                     f"{_f(t.pct(ps.GARBLED))} ({k[ps.GARBLED]}) | {k[ps.NONE]} | {_f(avg(t.per_p), 1)} | {_f(avg(t.per_c), 1)} | "
                     f"{_f(100 * t.words_found / t.words_total if t.words_total else None)} |")
    L += ["", "Phone error vs heard / vs canonical: how far the transcript's sounds are from what was actually said / from the textbook pronunciation "
          "(lower is closer). If a mode is closer to \"heard\" than to \"canonical\", it tends to preserve the accent.", ""]
    for v in variants:
        pairs = ps.by_pair([s for s in scores if s.variant == v])
        rows = sorted(pairs.items(), key=lambda kv: -sum(kv[1].values()))[:12]
        L += [f"## Most common heard-differently sounds: {v}", "", "| Canonical -> heard | Occurrences | Kept | Fixed | Garbled | No counterpart |", "|---|---:|---:|---:|---:|---:|"]
        for (c, p), cnt in rows:
            L.append(f"| {c} -> {p} | {sum(cnt.values())} | {cnt[ps.KEPT]} | {cnt[ps.FIXED]} | {cnt[ps.GARBLED]} | {cnt[ps.NONE]} |")
        L.append("")
    if any(errors.values()):
        L += ["## Errors", "", *[f"- {k}: {n} failed calls" for k, n in errors.items() if n], ""]
    L += ["## Caveats", "",
          "- Phone-level, through a dictionary: a transcript word that is not in CMUdict contributes no phones (coverage is in the table).",
          "- Alignment between the transcript's phones and the canonical ones can put a phone opposite the wrong one when the transcript is very different.",
          "- `g2p` and `ipa` come from a processed copy of L2-ARCTIC (perceived phones from the annotators); annotation is itself a judgement.",
          "- 3 speakers per accent: individual speakers dominate. Speech is a spontaneous story-telling task, not workplace speech.", ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--l1", default=",".join(l2.DEFAULT_L1))
    ap.add_argument("--quick", action="store_true", help="Sarvam saaras:v3 transcribe + verbatim, en-IN only")
    ap.add_argument("--sarvam-matrix", help="model|mode|language,... (overrides --quick)")
    ap.add_argument("--file", type=Path, help="local parquet instead of the cached download")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--yes", action="store_true", help="really call Sarvam (otherwise plan only)")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--out", type=Path, default=HERE)
    args = ap.parse_args(argv)

    l1s = tuple(x.strip() for x in args.l1.split(",") if x.strip())
    parquet = args.file or l2.download(l2.PARQUET, l2.hf_token())
    clips = load_clips(parquet, l1s)
    if args.limit:
        clips = clips[: args.limit]
    sarvam = Sarvam()
    if not sarvam.available():
        print("No SARVAM_API_KEY in the environment / .env.")
        return 1
    variants = sarvam.variants(args.sarvam_matrix or (Sarvam.QUICK_SPEC if args.quick else None))
    calls = len(clips) * len(variants)
    per_l1 = {a: sum(1 for c in clips if c["accent"] == a) for a in sorted({c["accent"] for c in clips})}
    print(f"{len(clips)} clips ({', '.join(f'{k}={v}' for k, v in per_l1.items())}) x {len(variants)} variants = {calls} Sarvam calls")
    for v in variants:
        print("  -", v.label)
    if not args.yes:
        print("\nPlan only. Nothing was sent. Add --yes to run it.")
        return 0

    write_clips(clips)
    cache = HERE / ".cache"
    scores: list[ps.ClipScore] = []
    raw: list[dict] = []
    errors = {v.label: 0 for v in variants}
    done = 0
    for c in clips:
        for v in variants:
            out = run.run_variant(sarvam, v, f"{c['id']}.wav", c["wav"], cache, True)
            done += 1
            if out["error"]:
                errors[v.label] += 1
            else:
                scores.append(ps.score_clip(c["accent"], v.label, c["g2p"], c["ipa"], out["text"]))
            raw.append({"clip": c["id"], "accent": c["accent"], "variant": v.label, "transcript": out["text"], "error": out["error"],
                        "latency": out["latency"], "cached": out["cached"]})
            print(f"  [{done}/{calls}] {c['id']} | {v.label}: " + (f"ERROR {out['error']}" if out["error"] else f"{len(out['text'].split())} words"))
            if not out["cached"]:
                time.sleep(args.sleep)
    accents = sorted(per_l1)
    (args.out / "report_l2arctic_spont.md").write_text(build_report(scores, [v.label for v in variants], accents, len(clips), errors), encoding="utf-8", newline="\n")
    (args.out / "results_l2arctic_spont.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {args.out / 'report_l2arctic_spont.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
