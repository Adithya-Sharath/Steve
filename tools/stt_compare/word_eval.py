"""Word-level kept / fixed / garbled for the L2-ARCTIC spontaneous clips, from Sarvam transcripts that are ALREADY cached (no new calls).

    python tools/stt_compare/word_eval.py            # reads results_l2arctic_spont.json (from phone_eval.py) and the two cached parquets

How each clip gets its words (validated: all 25 clips are exact substrings of their speaker's full recording, D38/D39):
  1. find the clip's perceived phones (`ipa`) inside the full recording's `ipa` from the sibling dataset `KoelLabs/L2Arctic`;
  2. find the clip's canonical phones (`g2p`) inside the full `g2p`; the full `text` is segmented into words over the full `g2p`
     (word_align.segment), so the words inside that window are the clip's words;
  3. per word, word_align.utterance_words gives the phones heard and, only when clear, the single real word they spell ("spoken_as_heard").
Then each STT transcript is aligned to the intended words at word level and every ACCENT WORD is classified:
  real-word swap (heard form is a different real word):  kept = the transcript has the heard word, fixed = the intended word, garbled = other
  non-word distortion (heard form is not a word):        recognised = the transcript has the intended word, other, no counterpart
DIRECTIONAL SIGNAL ONLY: a few dozen words per accent.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "importers"))

import phone_scoring as ps  # noqa: E402
import phones  # noqa: E402
import word_align as wa  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402

FULL_RECORDING_UNKNOWN = 10  # a 150-word recording may contain several words whose pronunciation differs from the dictionary
CLIP_UNKNOWN = 6
KEPT, FIXED, GARBLED, NONE, RECOGNISED, OTHER = "kept", "fixed", "garbled", "no counterpart", "recognised as intended", "other"


def find(hay: list, needle: list) -> list[int]:
    n = len(needle)
    return [i for i in range(len(hay) - n + 1) if hay[i : i + n] == needle] if n else []


def clip_words(full: dict, clip: dict, lex: dict) -> list[str] | None:
    """The words of `clip` (a piece of the full recording `full`), or None if it cannot be located unambiguously."""
    fi, ci = phones.tokenize(full["ipa"]), phones.tokenize(clip["ipa"])
    fg, cg = phones.tokenize(full["g2p"]), phones.tokenize(clip["g2p"])
    if len(find(fi, ci)) != 1:
        return None
    gs = find(fg, cg)
    if len(gs) != 1:
        return None
    spans = wa.segment(wa.words_of(full["text"]), fg, lex, FULL_RECORDING_UNKNOWN)
    if spans is None:
        return None
    words = wa.words_of(full["text"])
    lo, hi = gs[0], gs[0] + len(cg)
    return [w for w, (s, e, _, _) in zip(words, spans, strict=True) if s >= lo and e <= hi]


def classify_words(views: list[wa.WordView], transcript: str) -> list[tuple[wa.WordView, str, str | None]]:
    """[(accent word, outcome, transcript word)] using a word-level alignment of the transcript to the intended words."""
    intended = [v.word for v in views]
    got = wa.words_of(transcript)
    aligned: dict[int, str | None] = {}
    for tag, i1, i2, j1, j2 in Levenshtein.opcodes(intended, got):
        if tag in ("equal", "replace"):
            for k in range(i2 - i1):
                aligned[i1 + k] = got[j1 + k] if j1 + k < j2 else None
        elif tag == "delete":
            for k in range(i1, i2):
                aligned[k] = None
    out = []
    for i, v in enumerate(views):
        if not v.accent:
            continue
        w = aligned.get(i)
        if v.swap_word:
            kind = NONE if w is None else KEPT if w == v.swap_word else FIXED if w == v.word else GARBLED
        else:
            kind = NONE if w is None else RECOGNISED if w == v.word else OTHER
        out.append((v, kind, w))
    return out


def evaluate(clips: list[dict], full: dict[str, dict], results: list[dict], lex: dict, inv: dict):
    """-> (rows, skipped) with rows = [(accent, variant, clip id, [(WordView, outcome, transcript word)])]."""
    view_cache: dict[str, list[wa.WordView] | None] = {}
    rows, skipped = [], []
    for c in clips:
        f = full.get(c["speaker"].lower())
        words = clip_words(f, c, lex) if f else None
        views = wa.utterance_words(" ".join(words), c["g2p"], c["ipa"], lex, inv, CLIP_UNKNOWN) if words else None
        view_cache[c["id"]] = views
        if views is None:
            skipped.append(c["id"])
    for r in results:
        views = view_cache.get(r["clip"])
        if views is not None and not r["error"]:
            rows.append((r["accent"], r["variant"], r["clip"], classify_words(views, r["transcript"])))
    return rows, skipped, view_cache


def build_report(rows, skipped, view_cache, variants: list[str], accents: list[str]) -> str:
    L = ["# STT reality test: L2-ARCTIC spontaneous, WORD level (cached Sarvam transcripts, no new calls)", "",
         f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}.", "",
         "> **DIRECTIONAL SIGNAL ONLY.** Tens of words per accent, 6 speakers, story-telling speech. Source data is CC-BY-NC-4.0; this report is not committed.", "",
         f"Clips whose words could not be located unambiguously: {len(skipped)} ({', '.join(skipped) or 'none'}).", ""]
    allviews = [v for vs in view_cache.values() if vs for v in vs]
    L += [f"Words in the analysed clips: {len(allviews)}; accent words (heard differently): {sum(v.accent for v in allviews)}; "
          f"of which real-word swaps: {sum(bool(v.swap_word) for v in allviews)}.", ""]
    L += ["## Real-word swaps (the heard form is a DIFFERENT real word, the case a decoder cares about)", "",
          "| Accent | Mode | Swap words | Kept (heard word written) | Fixed (intended word written) | Garbled | No counterpart |", "|---|---|---:|---:|---:|---:|---:|"]
    for a in accents + ["all"]:
        for v in variants:
            c = Counter(k for ac, var, _, ws in rows if var == v and (a == "all" or ac == a) for wv, k, _ in ws if wv.swap_word)
            n = sum(c.values())
            L.append(f"| {a} | {v} | {n} | {c[KEPT]} | {c[FIXED]} | {c[GARBLED]} | {c[NONE]} |")
    L += ["", "## Non-word distortions (the heard form is not a word, so an intended word is the right answer)", "",
          "| Accent | Mode | Distorted words | Recognised as intended | Other | No counterpart |", "|---|---|---:|---:|---:|---:|"]
    for a in accents + ["all"]:
        for v in variants:
            c = Counter(k for ac, var, _, ws in rows if var == v and (a == "all" or ac == a) for wv, k, _ in ws if not wv.swap_word)
            L.append(f"| {a} | {v} | {sum(c.values())} | {c[RECOGNISED]} | {c[OTHER]} | {c[NONE]} |")
    L += ["", "## Every real-word swap (intended -> heard) and what each mode wrote", "", "| Clip | Intended | Heard (clear mapping) | " + " | ".join(variants) + " |",
          "|---|---|---|" + "---|" * len(variants)]
    seen: dict[tuple, dict] = {}
    for _, var, clip, ws in rows:
        for wv, k, w in ws:
            if wv.swap_word:
                seen.setdefault((clip, wv.word, wv.swap_word), {})[var] = f"{w or '-'} ({k})"
    for (clip, intended, heard), by in sorted(seen.items()):
        L.append(f"| {clip} | {intended} | {heard} | " + " | ".join(by.get(v, "") for v in variants) + " |")
    L += ["", "## Caveats", "",
          "- A swap is 'clear' only if the heard phones spell exactly one COMMON English word (wordfreq Zipf >= 3.5); some odd survivors remain. Words that are not in CMUdict are left out.",
          "- Perceived schwa is treated as the dictionary's AH vowel for the lookup (an assumption).",
          "- A transcript word is compared by spelling with the intended or heard word after a word-level alignment; mis-alignment near omissions can turn a match into 'garbled'.", ""]
    return "\n".join(L)


def main() -> int:
    import pyarrow.parquet as pq

    lex = ps.pronunciations()
    inv = wa.inverse_lexicon(lex)
    fullrows = pq.read_table(HERE / ".cache/l2arctic-full/data/spontaneous-00000-of-00001.parquet",
                             columns=["text", "g2p", "ipa", "speaker_code", "speaker_native_language"]).to_pylist()
    full = {r["speaker_code"].lower(): r for r in fullrows}
    import phone_eval

    clips = phone_eval.load_clips(HERE / ".cache/l2arctic/data/train-00000-of-00001.parquet", ("Arabic", "Hindi"))
    results = json.loads((HERE / "results_l2arctic_spont.json").read_text(encoding="utf-8"))
    rows, skipped, view_cache = evaluate(clips, full, results, lex, inv)
    variants = sorted({r["variant"] for r in results})
    accents = sorted({c["accent"] for c in clips})
    (HERE / "report_l2arctic_spont_words.md").write_text(build_report(rows, skipped, view_cache, variants, accents), encoding="utf-8", newline="\n")
    print("Wrote", HERE / "report_l2arctic_spont_words.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
