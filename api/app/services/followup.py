"""Re-explain draft covering ONLY the facts that failed. Template-based: nothing is translated by a model.

The sender edits the draft before sending. Templates exist for English and romanised Hindi; other languages fall back
to English until a native speaker adds templates here (see LEXICON_REVIEW.md for the process).
"""

from __future__ import annotations

from collections import Counter

from steve_engine.matcher import prepare

FAILED = ("wrong", "missing", "negated", "unclear")

TEMPLATES = {
    "en": {
        "intro": "Thanks for explaining! One more check on {n} thing{s} 🙏",
        "line": {
            "wrong": "• Please note: {label}",
            "missing": "• Also important: {label}",
            "negated": "• Please note, the opposite of what you said: {label}",
            "unclear": "• Just to be sure: {label}",
        },
        "outro": "Could you tell me again, in your own words? Any language is fine.",
    },
    "hi": {
        "intro": "Samjhane ke liye shukriya! {n} baat dobara check karni hai 🙏",
        "line": {
            "wrong": "• Yeh dhyan rakhiye: {label}",
            "missing": "• Yeh bhi zaroori hai: {label}",
            "negated": "• Yeh ulta samjha gaya, sahi yeh hai: {label}",
            "unclear": "• Pakka karne ke liye: {label}",
        },
        "outro": "Kya aap apne shabdon mein dobara bata sakte hain? Kisi bhi bhasha mein chalega.",
    },
}


def detect_lang(text: str) -> str:
    votes = Counter(m.lang for m in prepare(text).matches if m.lang in TEMPLATES and m.category != "filler")
    if votes and votes.most_common(1)[0][0] != "en" and votes.most_common(1)[0][1] >= 2:
        return votes.most_common(1)[0][0]
    return "en"


def build_followup(message_text: str, facts: list[dict], latest: dict[str, str], lang: str | None = None) -> tuple[str, str, list[dict]]:
    lang = lang if lang in TEMPLATES else detect_lang(message_text)
    tpl = TEMPLATES[lang]
    failed = [
        {"fact_id": f["fact_id"], "label": f["label"], "status": latest.get(f["fact_id"], "missing")}
        for f in facts
        if latest.get(f["fact_id"], "missing") in FAILED
    ]
    if not failed:
        return "Everything checked out. Thank you!", lang, []
    lines = [tpl["intro"].format(n=len(failed), s="" if len(failed) == 1 else "s")]
    lines += [tpl["line"][x["status"]].format(label=x["label"]) for x in failed]
    lines.append(tpl["outro"])
    return "\n".join(lines), lang, failed
