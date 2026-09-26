"""OPTIONAL embedding fallback — condition facts only, and only when the lexicon found nothing.

* Disabled unless `STEVE_EMBEDDINGS=1` AND `sentence-transformers` is installed AND the thresholds in
  fallback_config.json have been calibrated (they ship as `null`, see DECISIONS D8).
* It may raise a `missing` condition result to `unclear` (or `understood` if an even higher threshold is set).
* It can NEVER touch dose / frequency / duration / date / amount / timing, and it never lowers a status.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from .schema import Fact, FactResult, FactType, Status

CONFIG_PATH = Path(__file__).with_name("fallback_config.json")


@lru_cache(maxsize=1)
def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"model": "intfloat/multilingual-e5-small", "unclear_threshold": None, "understood_threshold": None}


def enabled() -> bool:
    cfg = load_config()
    return os.getenv("STEVE_EMBEDDINGS") == "1" and cfg.get("unclear_threshold") is not None


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer  # lazy: heavy optional dependency

    return SentenceTransformer(load_config().get("model", "intfloat/multilingual-e5-small"))


def similarity(fact_text: str, reply: str) -> float | None:
    """Max cosine similarity between the fact text and any sentence of the reply."""
    try:
        model = _model()
    except Exception:  # library missing / model not downloadable: degrade silently
        return None
    sents = [s.strip() for s in re.split(r"[.!?\n]+", reply) if s.strip()] or [reply]
    vecs = model.encode([f"query: {fact_text}"] + [f"passage: {s}" for s in sents], normalize_embeddings=True)
    q, ps = vecs[0], vecs[1:]
    return float(max(ps @ q))


def apply(fact: Fact, result: FactResult, reply: str) -> FactResult:
    if fact.type != FactType.condition or result.status != Status.missing or not enabled():
        return result
    val = fact.value if isinstance(fact.value, dict) else {}
    fact_text = str(val.get("text") or fact.label)
    sim = similarity(fact_text, reply)
    if sim is None:
        return result
    cfg = load_config()
    up = cfg.get("understood_threshold")
    if up is not None and sim >= up:
        return result.model_copy(update={"status": Status.understood, "confidence": round(min(sim, 0.75), 3),
                                         "reason": f"No exact words matched, but the reply is semantically close to '{fact_text}' (similarity {sim:.2f})."})
    if sim >= cfg["unclear_threshold"]:
        return result.model_copy(update={"status": Status.unclear, "confidence": round(min(sim, 0.55), 3),
                                         "reason": f"No exact words matched, but the reply may be about '{fact_text}' (similarity {sim:.2f}); please check."})
    return result
