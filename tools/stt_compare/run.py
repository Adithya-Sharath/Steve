"""STT reality test: send accented-English recordings to speech-to-text providers and measure what survives.

    python tools/stt_compare/run.py                       # plan only: lists the calls it WOULD make, sends nothing
    python tools/stt_compare/run.py --yes                 # really call the providers (uses your API quota)
    python tools/stt_compare/run.py --yes --quick         # Sarvam saaras:v3 transcribe + verbatim, en-IN only (fewest calls)
    python tools/stt_compare/run.py --yes --providers sarvam,gemini
    python tools/stt_compare/run.py --recordings "../demo voice" --truth my_truth.csv --yes

Nothing is sent without --yes. Raw answers are cached in `.cache/` (gitignored), so re-running the report is free.
Audio is only ever sent to the providers you list; it is never written anywhere by this tool.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dotenv import load_dotenv  # noqa: E402

from providers import PROVIDERS, Provider, ProviderError, Sarvam, Variant  # noqa: E402
from report import build_report  # noqa: E402
from scoring import FileResult, score_file  # noqa: E402

load_dotenv(HERE.parents[1] / ".env")
COLUMNS = ["file", "spoken_as_heard", "intended_meaning", "accent", "notes"]
AUDIO = {".mp3", ".wav", ".m4a", ".mp4", ".ogg", ".opus", ".webm", ".flac", ".aac", ".amr", ".wma"}


def load_truth(path: Path, recordings: Path) -> tuple[dict[str, dict], list[str]]:
    """truth.csv -> {file: row}; plus human-readable problems (missing audio, blank fields, unknown columns)."""
    problems: list[str] = []
    if not path.exists():
        raise SystemExit(f"{path} not found. See tools/stt_compare/README.md for how to fill it in.")
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"{path.name} is missing columns: {missing}. Expected: {COLUMNS}")
        rows: dict[str, dict] = {}
        for i, row in enumerate(reader, start=2):
            name = (row["file"] or "").strip()
            if not name:
                continue
            if name in rows:
                problems.append(f"line {i}: {name} is listed twice (first one kept)")
                continue
            if not (recordings / name).exists():
                problems.append(f"line {i}: audio file {recordings / name} not found (skipped)")
                continue
            if Path(name).suffix.lower() not in AUDIO:
                problems.append(f"line {i}: {name} is not a supported audio type (skipped)")
                continue
            if not (row["spoken_as_heard"] or "").strip() or not (row["intended_meaning"] or "").strip():
                problems.append(f"line {i}: {name} needs both spoken_as_heard and intended_meaning (skipped)")
                continue
            rows[name] = {k: (row.get(k) or "").strip() for k in COLUMNS} | {"accent": (row.get("accent") or "unspecified").strip() or "unspecified"}
    return rows, problems


def cache_path(cache: Path, audio: bytes, variant: Variant) -> Path:
    h = hashlib.sha256(audio + json.dumps([variant.provider, variant.label, variant.params], sort_keys=True).encode()).hexdigest()[:32]
    return cache / f"{h}.json"


def run_variant(provider: Provider, variant: Variant, name: str, audio: bytes, cache: Path, use_cache: bool) -> dict:
    """-> {text, latency, error, cached}. Never raises: one bad file must not stop the run."""
    cp = cache_path(cache, audio, variant)
    if use_cache and cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8")) | {"cached": True}
        except ValueError:
            cp.unlink(missing_ok=True)
    t0 = time.perf_counter()
    try:
        tr = provider.transcribe(audio, name, variant)
        out = {"text": tr.text, "latency": time.perf_counter() - t0, "error": None, "extra": tr.extra}
    except ProviderError as e:
        return {"text": "", "latency": None, "error": str(e), "cached": False}
    cache.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp")
    tmp.write_text(json.dumps(out), encoding="utf-8")
    tmp.replace(cp)  # atomic: a crash cannot leave a half-written cache file
    return out | {"cached": False}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--truth", type=Path, default=HERE / "truth.csv")
    ap.add_argument("--recordings", type=Path, default=HERE / "recordings")
    ap.add_argument("--providers", default="sarvam", help="comma list from: " + ", ".join(PROVIDERS))
    ap.add_argument("--sarvam-matrix", help="comma list of model|mode|language, e.g. 'saaras:v3|verbatim|en-IN,saaras:v4||unknown'")
    ap.add_argument("--quick", action="store_true", help="Sarvam: only saaras:v3 transcribe and verbatim with en-IN")
    ap.add_argument("--limit", type=int, default=0, help="only the first N recordings")
    ap.add_argument("--yes", action="store_true", help="actually call the providers (otherwise: plan only)")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.3, help="seconds between calls")
    ap.add_argument("--out", type=Path, default=HERE)
    args = ap.parse_args(argv)

    truth, problems = load_truth(args.truth, args.recordings)
    if args.limit:
        truth = dict(list(truth.items())[: args.limit])
    for p in problems:
        print("warning:", p, file=sys.stderr)
    if not truth:
        print("No usable rows in truth.csv yet (each needs an existing audio file, spoken_as_heard and intended_meaning).")
        return 1

    plan: list[tuple[Provider, Variant]] = []
    notes: list[str] = []
    for pname in [x.strip() for x in args.providers.split(",") if x.strip()]:
        if pname not in PROVIDERS:
            raise SystemExit(f"unknown provider {pname!r}; choose from {', '.join(PROVIDERS)}")
        prov = PROVIDERS[pname]()
        if not prov.available():
            msg = f"{pname}: no API key in the environment / .env, skipped"
            print("note:", msg)
            notes.append(msg)
            continue
        spec = (Sarvam.QUICK_SPEC if args.quick else None) if pname == "sarvam" else None
        if pname == "sarvam" and args.sarvam_matrix:
            spec = args.sarvam_matrix
        plan += [(prov, v) for v in prov.variants(spec)]

    calls = len(plan) * len(truth)
    print(f"{len(truth)} recordings x {len(plan)} provider variants = {calls} calls")
    for _, v in plan:
        print("  -", v.label)
    if not plan:
        print("Nothing to run: no provider has a key.")
        return 1
    if not args.yes:
        print("\nPlan only. Nothing was sent. Add --yes to run it.")
        return 0

    cache = HERE / ".cache"
    results: list[FileResult] = []
    raw: list[dict] = []
    done = 0
    for name, row in truth.items():
        audio = (args.recordings / name).read_bytes()
        for prov, v in plan:
            out = run_variant(prov, v, name, audio, cache, not args.no_cache)
            done += 1
            r = score_file(name, row["accent"], v.label, row["spoken_as_heard"], row["intended_meaning"], out["text"], out["latency"])
            r.error = out["error"]
            if r.error:
                r.pairs, r.edit_count, r.ref_len = [], 0, 0
            results.append(r)
            raw.append({"file": name, "variant": v.label, "text": out["text"], "latency": out["latency"], "error": out["error"], "cached": out["cached"]})
            print(f"  [{done}/{calls}] {name} | {v.label}: " + (f"ERROR {out['error']}" if out["error"] else out["text"][:70]))
            if not out["cached"]:
                time.sleep(args.sleep)

    variants = [v.label for _, v in plan]
    (args.out / "results.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.out / "report.md").write_text(build_report(results, variants, truth, notes + problems), encoding="utf-8", newline="\n")
    print(f"\nWrote {args.out / 'report.md'} and results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
