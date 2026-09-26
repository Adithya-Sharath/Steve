"""Markdown report for the STT reality test."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from scoring import FIXED, GARBLED, SURVIVED, FileResult, Summary, by_accent, summarise


def _f(x: float | None, digits: int = 1, unit: str = "") -> str:
    return "n/a" if x is None else f"{x:.{digits}f}{unit}"


def _cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def summary_table(rows: list[Summary]) -> list[str]:
    out = [
        "| Provider / mode / language | Files ok | Errors | WER vs. what was said | Accent words | Kept as spoken | \"Fixed\" to the intended word | Garbled | Latency mean / median / p95 (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for s in rows:
        out.append(
            f"| {_cell(s.variant)} | {s.files} | {s.errors} | {_f(None if s.wer is None else 100 * s.wer, 1, '%')} | {s.pairs} | "
            f"{_f(s.pct(s.survived), 0, '%')} ({s.survived}) | {_f(s.pct(s.fixed), 0, '%')} ({s.fixed}) | {_f(s.pct(s.garbled), 0, '%')} ({s.garbled}) | "
            f"{_f(s.latency_mean, 2)} / {_f(s.latency_median, 2)} / {_f(s.latency_p95, 2)} |"
        )
    return out


def build_report(results: list[FileResult], variants: list[str], truth: dict[str, dict], notes: list[str]) -> str:
    rows = sorted((summarise(results, v) for v in variants), key=lambda s: (s.wer is None, s.wer or 0))
    lines = [
        "# STT reality test",
        "",
        f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} by `tools/stt_compare/run.py`. {len(truth)} recordings in `truth.csv`, "
        f"{len(variants)} provider variants.",
        "",
        "**The question:** does speech-to-text keep the words the speaker actually said (\"barking\"), or silently \"fix\" them to what it "
        "expects (\"parking\")? That decides how the decoder works: if accent words survive, sound-swap candidates can find them; if they are "
        "\"fixed\" already, the decoder must lean on phrases, action extraction and clarifying questions.",
        "",
        "## Summary",
        "",
        *summary_table(rows),
        "",
        "How to read it:",
        "- **WER** is word error rate against `spoken_as_heard` (what a person listening wrote down), not against the intended sentence. Lower is closer to what was said.",
        "- **Accent words** are the words where `spoken_as_heard` differs from `intended_meaning`. For each one the transcript either **kept the spoken word**, "
        "**\"fixed\"** it to the intended word, or **garbled** it into something else. \"Kept as spoken\" is what the decoder needs; \"fixed\" is "
        "convenient but hides the accent (and would be a silent guess if it is wrong); if both forms appear it counts as kept.",
        "- Neither Sarvam nor Gemini documents word-level confidence or alternative hypotheses, so this report cannot use them.",
        "",
    ]
    if notes:
        lines += ["## Notes on this run", "", *[f"- {n}" for n in notes], ""]

    lines += ["## By accent", ""]
    for v in variants:
        per = by_accent(results, v)
        if len(per) > 1:
            lines += [f"**{_cell(v)}**", "", *summary_table([replace(s, variant=a) for a, s in per.items()]), ""]

    for kind, title in ((FIXED, "Accent words that were \"fixed\" (the transcript shows the intended word)"),
                        (GARBLED, "Accent words that were garbled"), (SURVIVED, "Accent words that were kept as spoken")):
        ex = [(r, p) for r in results for p, k in r.pairs if k == kind and r.error is None]
        lines += [f"## {title}", ""]
        if not ex:
            lines += ["_None._", ""]
            continue
        lines += ["| File | Provider variant | Heard | Meant | Transcript |", "|---|---|---|---|---|"]
        lines += [f"| {_cell(r.file)} | {_cell(r.variant)} | {_cell(p.heard)} | {_cell(p.meant)} | {_cell(r.hypothesis)} |" for r, p in ex[:60]]
        if len(ex) > 60:
            lines.append(f"\n_{len(ex) - 60} more not shown; see `results.json`._")
        lines.append("")

    lines += ["## Every recording", ""]
    for f, row in truth.items():
        lines += [f"### {f}  ({_cell(row['accent'])})", "", f"- **Spoken (as heard):** {_cell(row['spoken_as_heard'])}",
                  f"- **Intended:** {_cell(row['intended_meaning'])}"]
        if row.get("notes"):
            lines.append(f"- **Notes:** {_cell(row['notes'])}")
        for v in variants:
            r = next((x for x in results if x.file == f and x.variant == v), None)
            if r is None:
                continue
            lines.append(f"- {_cell(v)}: " + (f"_error: {_cell(r.error)}_" if r.error else f"{_cell(r.hypothesis)}  (WER {_f(100 * r.edit_count / r.ref_len if r.ref_len else None, 0, '%')})"))
        lines.append("")
    lines += [
        "## Caveats", "",
        "- Small samples: a handful of accent words per accent is an anecdote, not a rate. Treat percentages as directional.",
        "- `spoken_as_heard` is one listener's transcription by ear; another listener may hear differently.",
        "- A \"fixed\" word may be the recogniser being right about the speaker's intent, or the speaker actually saying the right word; "
        "only `spoken_as_heard` tells them apart.",
        "- Providers change: repeat the test before relying on a result.",
        "",
    ]
    return "\n".join(lines)
