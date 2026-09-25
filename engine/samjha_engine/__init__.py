"""samjha_engine — deterministic, LLM-free fact checking for mixed-language teach-back replies."""

from .check import check_reply, inspect_reply, lexicon_stats
from .compare import EngineConfig
from .schema import Fact, FactResult, FactType, Span, Status

__all__ = [
    "EngineConfig",
    "Fact",
    "FactResult",
    "FactType",
    "Span",
    "Status",
    "check_reply",
    "inspect_reply",
    "lexicon_stats",
]
