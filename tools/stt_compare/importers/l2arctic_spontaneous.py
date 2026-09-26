"""L2-ARCTIC "Suitcase" spontaneous split (KoelLabs/L2ArcticSpontaneousSplit) as a 4th evaluation source (`l2arctic-spont`).

STATUS: `inspect` only. It downloads the gated parquet, prints the columns and counts per accent (L1) and split, and estimates the
speech-to-text usage of a run. It calls NO speech provider, writes NO audio and NO transcripts, and commits nothing. The import step
(audio + truth rows) is added after the columns and the transcript question are settled with the owner (see DECISIONS D38).

    python tools/stt_compare/importers/l2arctic_spontaneous.py inspect [--l1 Arabic,Hindi]

Needs `pip install -r tools/requirements.txt` and HF_TOKEN in .env (a token with read access to gated repos, from an account that
has accepted the dataset's terms on huggingface.co). The token is never printed or written anywhere.

Licence: CC-BY-NC-4.0 (Zhao et al. 2018, "L2-ARCTIC: A Non-native English Speech Corpus", Interspeech). Non-commercial use, cite the paper,
do not redistribute the audio. Audio and anything derived from it stays in gitignored folders.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from collections import defaultdict
from pathlib import Path

REPO = "KoelLabs/L2ArcticSpontaneousSplit"
PARQUET = "data/train-00000-of-00001.parquet"
HERE = Path(__file__).resolve().parents[1]
CACHE = HERE / ".cache" / "l2arctic"
SOURCE = "l2arctic-spont"
DEFAULT_L1 = ("Arabic", "Hindi")
SPLIT_COLUMNS = ("split", "subset", "type", "kind")  # none is documented; used only if the file happens to have one
SARVAM_VARIANTS = {"--quick": 2, "default matrix": 6}  # see tools/stt_compare/providers.py


class GatedAccess(Exception):
    """The dataset is gated and this token has not been granted access."""


def hf_token() -> str:
    from dotenv import load_dotenv

    load_dotenv(HERE.parents[1] / ".env")
    tok = os.getenv("HF_TOKEN", "").strip()
    if not tok:
        raise SystemExit("HF_TOKEN is not set. Put it in .env (never commit it); see the module docstring.")
    return tok


def download(filename: str, token: str, cache: Path = CACHE) -> Path:
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import GatedRepoError, HfHubHTTPError

    try:
        return Path(hf_hub_download(REPO, filename, repo_type="dataset", token=token, local_dir=str(cache)))
    except GatedRepoError as e:
        raise GatedAccess(
            f"Access to {REPO} is gated and this token has no access yet. On huggingface.co, open "
            f"https://huggingface.co/datasets/{REPO} with the SAME account as the token, accept the terms, and make sure the token "
            "can read gated repos (a fine-grained token needs 'Read access to contents of all public gated repos')."
        ) from e
    except HfHubHTTPError as e:
        raise SystemExit(f"Hugging Face error {getattr(e.response, 'status_code', '?')} while downloading {filename}.") from e


def wav_seconds(data: bytes) -> float | None:
    """Duration of a RIFF/WAVE payload (PCM or float32) without extra dependencies; None if it is not WAV."""
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    pos, rate, block = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos : pos + 4], struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        if cid == b"fmt ":
            rate = struct.unpack("<I", data[pos + 12 : pos + 16])[0]
            block = struct.unpack("<H", data[pos + 20 : pos + 22])[0]
        elif cid == b"data" and rate and block:
            return min(size, len(data) - pos - 8) / (rate * block)
        pos += 8 + size + (size & 1)
    return None


def _looks_like_word_transcript(values: list[str]) -> bool:
    """Heuristic for the question 'is there an English word-level transcript?': several words made of plain letters,
    separated by spaces, no IPA symbols."""
    ipa_only = set("ɑæəɛɪɔʊʌðθŋʃʒˈˌːɹɾʔɡɜɚɝ")
    plain = 0
    for v in values:
        toks = v.split()
        if len(toks) >= 4 and not (set(v) & ipa_only) and all(t.strip(".,;:!?'\"-").isalpha() for t in toks):
            plain += 1
    return plain >= max(1, len(values) // 2)


def inspect(path: Path, l1s: tuple[str, ...] = DEFAULT_L1, out=None) -> dict:
    import pyarrow.parquet as pq

    out = out or sys.stdout  # looked up at call time so redirection (and tests) work

    pf = pq.ParquetFile(path)
    schema = pf.schema_arrow
    names = schema.names
    print(f"Columns ({len(names)}): " + ", ".join(f"{n}:{schema.field(n).type}" for n in names), file=out)
    print(f"Rows: {pf.metadata.num_rows}   Row groups: {pf.metadata.num_row_groups}", file=out)

    meta_cols = [n for n in names if n != "audio"]
    table = pf.read(columns=meta_cols + (["audio"] if "audio" in names else []))
    rows = table.to_pylist()

    text_cols = {n: [str(r[n]) for r in rows if isinstance(r.get(n), str) and r[n]] for n in meta_cols}
    word_cols = [n for n, vals in text_cols.items() if vals and _looks_like_word_transcript(vals[:20])]
    print("Word-level English transcript column: " + (", ".join(word_cols) if word_cols else "NONE found (only IPA / g2p / speaker fields)"), file=out)
    for n in ("ipa", "g2p"):
        if text_cols.get(n):
            print(f"  sample {n}: {text_cols[n][0][:90]}", file=out)

    l1_col = next((n for n in ("speaker_native_language", "native_language", "l1") if n in names), None)
    split_col = next((n for n in SPLIT_COLUMNS if n in names), None)
    speaker_col = "speaker_code" if "speaker_code" in names else None
    if not l1_col:
        print("No native-language column: cannot filter by accent.", file=out)
        return {"columns": names, "word_columns": word_cols, "counts": {}}

    want = [x.lower() for x in l1s]
    counts: dict[tuple[str, str], dict] = defaultdict(lambda: {"clips": 0, "seconds": 0.0, "unknown_len": 0, "speakers": set()})
    all_l1 = defaultdict(int)
    for r in rows:
        l1 = str(r.get(l1_col) or "?")
        all_l1[l1] += 1
        if l1.lower() not in want:
            continue
        split = str(r.get(split_col)) if split_col else "spontaneous"
        c = counts[(l1, split)]
        c["clips"] += 1
        a = r.get("audio")
        sec = wav_seconds(a["bytes"]) if isinstance(a, dict) and a.get("bytes") else None
        if sec is None:
            c["unknown_len"] += 1
        else:
            c["seconds"] += sec
        if speaker_col:
            c["speakers"].add(r.get(speaker_col))

    print("\nAll clips by native language: " + ", ".join(f"{k}={v}" for k, v in sorted(all_l1.items())), file=out)
    if not split_col:
        print("This file has no split/subset column: every clip is treated as 'spontaneous' (the card's snippet mentions a "
              "'scripted' split but the repo holds a single `train` split).", file=out)
    print(f"\nSelected: {', '.join(l1s)}", file=out)
    print("| Accent (L1) | Split | Clips | Speakers | Audio (min) |\n|---|---|---:|---:|---:|", file=out)
    tot_clips = tot_sec = 0
    for (l1, split), c in sorted(counts.items()):
        print(f"| {l1} | {split} | {c['clips']} | {len(c['speakers'])} | {c['seconds'] / 60:.1f}"
              + (f" (+{c['unknown_len']} clips of unknown length)" if c["unknown_len"] else "") + " |", file=out)
        tot_clips += c["clips"]
        tot_sec += c["seconds"]
    print(f"\nTotal selected: {tot_clips} clips, about {tot_sec / 60:.1f} min of audio.", file=out)
    print("Estimated speech-to-text usage (calls = clips x provider variants; Sarvam's REST limit is 30 s per call, clips are 10-12.5 s):", file=out)
    for label, n in SARVAM_VARIANTS.items():
        print(f"  - {label}: {tot_clips} x {n} = {tot_clips * n} calls, {tot_sec / 60 * n:.1f} audio-minutes", file=out)
    print("  (Check Sarvam's current price list before running; this tool does not know your plan or credits.)", file=out)
    return {"columns": names, "word_columns": word_cols, "counts": dict(counts), "clips": tot_clips, "seconds": tot_sec}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect", help="columns, transcript check, clip counts per accent/split, estimated STT usage")
    p.add_argument("--l1", default=",".join(DEFAULT_L1), help="comma list of native languages to keep")
    p.add_argument("--file", type=Path, help="use this local parquet instead of downloading (for tests)")
    args = ap.parse_args(argv)
    l1s = tuple(x.strip() for x in args.l1.split(",") if x.strip())
    try:
        path = args.file or download(PARQUET, hf_token())
    except GatedAccess as e:
        print(e)
        return 2
    inspect(path, l1s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
