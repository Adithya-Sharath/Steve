"""steve_engine — deterministic, LLM-free fact checking for mixed-language teach-back replies."""

from .check import check_reply, inspect_reply, lexicon_stats
from .compare import EngineConfig
from .copycheck import COPY_REASON, copy_similarity, looks_copied
from .schema import Fact, FactResult, FactType, Span, Status

__all__ = [
    "COPY_REASON",
    "EngineConfig",
    "Fact",
    "FactResult",
    "FactType",
    "Span",
    "Status",
    "check_reply",
    "copy_similarity",
    "inspect_reply",
    "lexicon_stats",
    "looks_copied",
]
