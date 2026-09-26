"""Environment-driven settings. Every key is optional: with none set the whole product still works."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "api" / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


# Lite model on purpose: on a free key the larger Gemini models allow only ~20 requests per DAY (D25/D26), which
# would make "Find key facts" fail after a handful of clicks. Override with GEMINI_MODEL.
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"


@dataclass
class Settings:
    llm_enabled: bool = field(default_factory=lambda: _bool("LLM_ENABLED", False))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL))
    sarvam_api_key: str = field(default_factory=lambda: os.getenv("SARVAM_API_KEY", ""))
    stt_flag: bool = field(default_factory=lambda: _bool("STT_ENABLED", True))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./steve.db"))
    public_web_url: str = field(default_factory=lambda: os.getenv("PUBLIC_WEB_URL", "http://localhost:3000").rstrip("/"))
    cors_origins: list[str] = field(
        default_factory=lambda: [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    )
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("STEVE_DATA_DIR", REPO_ROOT / "data")))
    eval_dir: Path = field(default_factory=lambda: Path(os.getenv("STEVE_EVAL_DIR", REPO_ROOT / "eval" / "results")))
    # the optional LLM may never make the composer wait: hard deadline, then fall back to the built-in extractor
    llm_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "10")))
    llm_cooldown_seconds: float = field(default_factory=lambda: float(os.getenv("LLM_COOLDOWN_SECONDS", "60")))
    # X-Forwarded-For / CF-Connecting-IP are only believed when a proxy really sits in front (D31)
    trust_proxy: bool = field(default_factory=lambda: _bool("TRUST_PROXY", False))
    trusted_proxies: list[str] = field(
        default_factory=lambda: [p.strip() for p in os.getenv("TRUSTED_PROXIES", "").split(",") if p.strip()]
    )
    # the global LLM switch is admin-only: without ADMIN_KEY the runtime toggle is disabled and LLM_ENABLED decides (D30)
    admin_key: str = field(default_factory=lambda: os.getenv("ADMIN_KEY", "").strip())
    # global daily caps on paid / quota-limited calls (D33): 0 blocks the service, a negative value means unlimited
    llm_daily_cap: int = field(default_factory=lambda: _int("LLM_DAILY_CAP", 200))
    stt_daily_cap: int = field(default_factory=lambda: _int("STT_DAILY_CAP", 300))
    max_body_bytes: int = field(default_factory=lambda: _int("MAX_BODY_BYTES", 5 * 1024 * 1024))  # global request-body cap (D35)
    # rate limits (in-memory sliding windows, D32). A value <= 0 switches that rule off.
    rl_messages_per_min: int = field(default_factory=lambda: _int("RL_MESSAGES_PER_MIN", 10))  # POST /messages, per IP
    rl_messages_per_day: int = field(default_factory=lambda: _int("RL_MESSAGES_PER_DAY", 100))  # per IP
    rl_messages_per_sender_day: int = field(default_factory=lambda: _int("RL_MESSAGES_PER_SENDER_DAY", 30))  # per sender key
    reply_rate_limit: int = field(default_factory=lambda: _int("REPLY_RATE_LIMIT", 12))  # per reader link + IP, per minute
    reply_rate_window: int = 60
    reply_cap_per_message: int = field(default_factory=lambda: _int("REPLY_CAP_PER_MESSAGE", 30))  # hard cap, replies in total
    rl_check_per_min: int = field(default_factory=lambda: _int("RL_CHECK_PER_MIN", 60))  # POST /check and /analyze, per IP each
    rl_seed_per_min: int = field(default_factory=lambda: _int("RL_SEED_PER_MIN", 5))  # POST /demo/seed, per IP
    rl_default_per_min: int = field(default_factory=lambda: _int("RL_DEFAULT_PER_MIN", 120))  # everything else, per IP

    @property
    def llm_available(self) -> bool:
        """LLM is used only when switched on AND a key exists. Never required."""
        return self.llm_enabled and bool(self.gemini_api_key)

    @property
    def stt_enabled(self) -> bool:
        return self.stt_flag and bool(self.sarvam_api_key)


settings = Settings()
