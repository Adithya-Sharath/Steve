"""Speech Accent Archive (George Mason University, https://accent.gmu.edu) as a 6th evaluation source (`speech-accent-archive`).

STATUS: `inspect` only. It reads a LOCAL copy you downloaded yourself (nothing is fetched), lists the metadata and recordings per native language,
and estimates speech-to-text usage. It calls no speech provider and writes nothing.

    python tools/stt_compare/importers/speech_accent_archive.py inspect --dir <folder> [--languages arabic,hindi,malayalam,tagalog]

Expected layout of `<folder>` (this is the layout of the widely used Kaggle copy, `rtatman/speech-accent-archive`; NOT verified against the
official site, whose download page was being renovated when checked on 2026-09-26; the tool says clearly what it cannot find):
    speakers_all.csv        one row per speaker/recording, with columns like filename, native_language, country, sex, age, birthplace
    recordings/*.mp3        (or the audio directly in the folder)

Facts: every speaker reads the same short paragraph ("Please call Stella. ..."), so the intended words are known for every recording; the archive
does NOT give a by-ear "as heard" transcription per speaker in machine-readable form (it has narrow IPA transcriptions on the website for
some speakers), so like Svarah this source measures overall accuracy and, at most, how often the words we KNOW are commonly reshaped survive;
it cannot score "kept vs fixed" without our own by-ear `spoken_as_heard` (D39). Licence: CC BY-NC-SA 4.0 per the archive's home page (non-commercial,
attribution, SHARE-ALIKE: anything derived from it, such as transcripts, would have to carry the same licence, another reason none is committed).
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import audio as audio_tools  # noqa: E402

SOURCE = "speech-accent-archive"
SARVAM_VARIANTS = {"--quick": 2, "default matrix": 6}
DEFAULT_LANGUAGES = ("arabic", "hindi", "malayalam", "tagalog")
# The paragraph every speaker reads (from the archive's instructions; verify against https://accent.gmu.edu before relying on it).
PARAGRAPH = (
    "Please call Stella. Ask her to bring these things with her from the store: Six spoons of fresh snow peas, five thick slabs of blue "
    "cheese, and maybe a snack for her brother Bob. We also need a small plastic snake and a big toy frog for the kids. She can scoop "
    "these things into three red bags, and we will go meet her Wednesday at the train station."
)
COLUMN_CANDIDATES = {
    "file": ("filename", "file", "recording", "audio"),
    "language": ("native_language", "language", "native language", "l1"),
    "country": ("country",),
    "sex": ("sex", "gender"),
    "age": ("age",),
}
AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac")


def _pick(fieldnames: list[str], key: str) -> str | None:
    lower = {f.lower().strip(): f for f in fieldnames}
    return next((lower[c] for c in COLUMN_CANDIDATES[key] if c in lower), None)


def find_audio(folder: Path, stem: str) -> Path | None:
    for base in (folder / "recordings", folder / "recordings" / "recordings", folder):
        for ext in AUDIO_EXTS:
            p = base / f"{stem}{ext}"
            if p.exists():
                return p
    return None


def inspect(folder: Path, languages: tuple[str, ...] = DEFAULT_LANGUAGES, out=None) -> dict:
    out = out or sys.stdout
    meta = folder / "speakers_all.csv"
    if not meta.exists():
        print(f"{meta} not found. Download the Speech Accent Archive yourself (see the module docstring) and pass its folder with --dir.", file=out)
        return {"error": "no metadata"}
    with meta.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    cols = {k: _pick(fields, k) for k in COLUMN_CANDIDATES}
    print(f"Metadata columns: {', '.join(fields)}  ({len(rows)} rows)", file=out)
    missing = [k for k in ("file", "language") if not cols[k]]
    if missing:
        print(f"Cannot find the {' and '.join(missing)} column(s); expected one of {[COLUMN_CANDIDATES[k] for k in missing]}.", file=out)
        return {"error": "columns"}

    want = {x.lower() for x in languages}
    agg: dict[str, dict] = defaultdict(lambda: {"rows": 0, "with_audio": 0, "seconds": 0.0, "long": 0, "unknown_len": 0, "countries": set()})
    all_langs: dict[str, int] = defaultdict(int)
    for r in rows:
        lang = (r.get(cols["language"]) or "?").strip()
        all_langs[lang.lower()] += 1
        if lang.lower() not in want:
            continue
        a = agg[lang.lower()]
        a["rows"] += 1
        if cols["country"] and r.get(cols["country"]):
            a["countries"].add(r[cols["country"]].strip())
        stem = Path((r.get(cols["file"]) or "").strip()).stem
        path = find_audio(folder, stem) if stem else None
        if path:
            a["with_audio"] += 1
            sec = audio_tools.duration_seconds(path)
            if sec is None:
                a["unknown_len"] += 1
            else:
                a["seconds"] += sec
                a["long"] += sec > audio_tools.MAX_SECONDS
    print(f"\nLanguages in the metadata: {len(all_langs)}; the biggest: " + ", ".join(f"{k}={v}" for k, v in sorted(all_langs.items(), key=lambda kv: -kv[1])[:8]), file=out)
    print(f"Selected: {', '.join(languages)}", file=out)
    print("| Native language | Speakers (rows) | With audio here | Audio (min) | Over 30 s |\n|---|---:|---:|---:|---:|", file=out)
    tot = tot_sec = 0
    for lang, a in sorted(agg.items()):
        extra = f" (+{a['unknown_len']} of unknown length)" if a["unknown_len"] else ""
        print(f"| {lang} | {a['rows']} | {a['with_audio']} | {a['seconds'] / 60:.1f}{extra} | {a['long']} |", file=out)
        tot += a["with_audio"]
        tot_sec += a["seconds"]
    print(f"\nTotal selected with audio: {tot} recordings, about {tot_sec / 60:.1f} min. (Every speaker reads the same {len(PARAGRAPH.split())}-word paragraph.)", file=out)
    print("Estimated speech-to-text usage (calls = recordings x provider variants; Sarvam's REST limit is 30 s per call):", file=out)
    for label, n in SARVAM_VARIANTS.items():
        print(f"  - {label}: {tot} x {n} = {tot * n} calls, {tot_sec / 60 * n:.1f} audio-minutes", file=out)
    print("  (Check Sarvam's current price list before running; this tool does not know your plan or credits.)", file=out)
    return {"recordings": tot, "seconds": tot_sec, "languages": {k: v["with_audio"] for k, v in agg.items()}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect", help="speakers and recordings per native language, estimated STT usage")
    p.add_argument("--dir", type=Path, required=True, help="folder holding speakers_all.csv and the recordings")
    p.add_argument("--languages", default=",".join(DEFAULT_LANGUAGES))
    args = ap.parse_args(argv)
    inspect(args.dir, tuple(x.strip().lower() for x in args.languages.split(",") if x.strip()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
