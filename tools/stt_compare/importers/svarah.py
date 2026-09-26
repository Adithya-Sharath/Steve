"""Svarah (ai4bharat/Svarah): Indian-accented English speech with human transcripts, as a 5th evaluation source (`svarah`).

STATUS: `inspect` only (same stop-before-running rule as the L2-ARCTIC importer). It reads ONLY the metadata columns of the remote parquet
(no audio is downloaded), prints the columns, clips and hours per primary language, and estimates speech-to-text usage. It calls no speech
provider, writes no audio and no transcripts.

    python tools/stt_compare/importers/svarah.py inspect [--languages Hindi,Malayalam] [--file local.parquet]

Facts from the dataset card (read 2026-09-26): 9.6 hours, 117 speakers, 65 districts in 19 states, read and spontaneous speech; single `test` split of
6,656 rows (about 1.1 GB); columns audio_filepath, duration, text, gender, age-group, primary_language, native_place_state, native_place_district,
highest_qualification, job_category, occupation_domain; licence CC BY 4.0 (cite Javed et al., "Svarah: Evaluating English ASR Systems on Indian
Accents", INTERSPEECH 2023); gated: you must agree to share your contact information on huggingface.co and use a token from that account.

What it can and cannot measure: `text` is a human transcript of the speech, and there are no phone-level annotations. So Svarah answers
"how well does the STT transcribe Indian-accented English" (word error rate) but NOT "did it keep the accent word as spoken or fix it": for that
we would need `spoken_as_heard` vs `intended_meaning`, which this dataset does not provide (D39).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

REPO = "ai4bharat/Svarah"
HERE = Path(__file__).resolve().parents[1]
SOURCE = "svarah"
SARVAM_VARIANTS = {"--quick": 2, "default matrix": 6}
MAX_SECONDS = 30.0


class GatedAccess(Exception):
    pass


def hf_token() -> str:
    from dotenv import load_dotenv

    load_dotenv(HERE.parents[1] / ".env")
    tok = os.getenv("HF_TOKEN", "").strip()
    if not tok:
        raise SystemExit("HF_TOKEN is not set. Put it in .env (never commit it).")
    return tok


def open_remote_parquet(token: str):
    """A ParquetFile over HTTP range requests: only the footer and the columns we ask for are downloaded."""
    import pyarrow.parquet as pq
    from huggingface_hub import HfApi, HfFileSystem
    from huggingface_hub.errors import GatedRepoError, HfHubHTTPError

    try:
        files = [s.rfilename for s in HfApi(token=token).dataset_info(REPO).siblings if s.rfilename.endswith(".parquet")]
        if not files:
            raise SystemExit(f"No parquet files found in {REPO}.")
        fs = HfFileSystem(token=token)
        return pq.ParquetFile(fs.open(f"datasets/{REPO}/{sorted(files)[0]}", "rb"))
    except (GatedRepoError, HfHubHTTPError) as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if isinstance(e, GatedRepoError) or status in (401, 403):
            raise GatedAccess(
                f"Access to {REPO} is gated. On huggingface.co open https://huggingface.co/datasets/{REPO} with the SAME account as the token, "
                "agree to share your contact information, and make sure the token can read gated repos."
            ) from e
        raise SystemExit(f"Hugging Face error {status} while opening {REPO}.") from e


def inspect(pf, languages: tuple[str, ...] = (), out=None) -> dict:
    out = out or sys.stdout
    names = pf.schema_arrow.names
    print(f"Columns ({len(names)}): " + ", ".join(f"{n}:{pf.schema_arrow.field(n).type}" for n in names), file=out)
    print(f"Rows: {pf.metadata.num_rows}", file=out)
    need = [c for c in ("duration", "text", "primary_language", "native_place_state", "gender", "age-group") if c in names]
    rows = pf.read(columns=need).to_pylist()
    lang_col = "primary_language" if "primary_language" in names else None
    print("Word-level transcript column `text`: " + ("present" if "text" in names else "MISSING"), file=out)
    print("Phone-level annotation: none (so accent-word survival cannot be scored on this source; word error rate can)", file=out)
    if not lang_col:
        print("No primary_language column: cannot filter by accent.", file=out)
        return {"columns": names}

    want = {x.lower() for x in languages}
    agg: dict[str, dict] = defaultdict(lambda: {"clips": 0, "seconds": 0.0, "long": 0, "speakers": set(), "states": set()})
    for r in rows:
        lang = str(r.get(lang_col) or "?")
        if want and lang.lower() not in want:
            continue
        a = agg[lang]
        a["clips"] += 1
        dur = r.get("duration")
        if isinstance(dur, (int, float)):
            a["seconds"] += dur
            a["long"] += dur > MAX_SECONDS
        if r.get("native_place_state"):
            a["states"].add(r["native_place_state"])
    print(f"\nSelected languages: {', '.join(languages) if languages else 'all'}", file=out)
    print("| Primary language | Clips | Audio (min) | Clips over 30 s |\n|---|---:|---:|---:|", file=out)
    tot_clips = tot_sec = 0
    for lang, a in sorted(agg.items(), key=lambda kv: -kv[1]["clips"]):
        print(f"| {lang} | {a['clips']} | {a['seconds'] / 60:.1f} | {a['long']} |", file=out)
        tot_clips += a["clips"]
        tot_sec += a["seconds"]
    print(f"\nTotal selected: {tot_clips} clips, about {tot_sec / 60:.1f} min of audio.", file=out)
    print("Estimated speech-to-text usage (calls = clips x provider variants; Sarvam's REST limit is 30 s per call):", file=out)
    for label, n in SARVAM_VARIANTS.items():
        print(f"  - {label}: {tot_clips} x {n} = {tot_clips * n} calls, {tot_sec / 60 * n:.1f} audio-minutes", file=out)
    print("  (Check Sarvam's current price list before running; this tool does not know your plan or credits.)", file=out)
    return {"columns": names, "clips": tot_clips, "seconds": tot_sec, "languages": {k: v["clips"] for k, v in agg.items()}}


def main(argv: list[str] | None = None) -> int:
    import pyarrow.parquet as pq

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect", help="columns, clips and hours per primary language, estimated STT usage")
    p.add_argument("--languages", default="", help="comma list of primary languages to keep (default: all)")
    p.add_argument("--file", type=Path, help="a local parquet instead of the remote one (for tests)")
    args = ap.parse_args(argv)
    langs = tuple(x.strip() for x in args.languages.split(",") if x.strip())
    try:
        pf = pq.ParquetFile(args.file) if args.file else open_remote_parquet(hf_token())
    except GatedAccess as e:
        print(e)
        return 2
    inspect(pf, langs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
