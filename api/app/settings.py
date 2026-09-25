"""Environment-driven settings. Every key is optional: with none set the whole product still works."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "api" / ".env")


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    llm_enabled: bool = field(default_factory=lambda: _bool("LLM_ENABLED", False))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))
    sarvam_api_key: str = field(default_factory=lambda: os.getenv("SARVAM_API_KEY", ""))
    stt_flag: bool = field(default_factory=lambda: _bool("STT_ENABLED", True))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./samjha.db"))
    public_web_url: str = field(default_factory=lambda: os.getenv("PUBLIC_WEB_URL", "http://localhost:3000").rstrip("/"))
    cors_origins: list[str] = field(
        default_factory=lambda: [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    )
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("SAMJHA_DATA_DIR", REPO_ROOT / "data")))
    eval_dir: Path = field(default_factory=lambda: Path(os.getenv("SAMJHA_EVAL_DIR", REPO_ROOT / "eval" / "results")))
    reply_rate_limit: int = field(default_factory=lambda: int(os.getenv("REPLY_RATE_LIMIT", "12")))
    reply_rate_window: int = 60

    @property
    def llm_available(self) -> bool:
        """LLM is used only when switched on AND a key exists. Never required."""
        return self.llm_enabled and bool(self.gemini_api_key)

    @property
    def stt_enabled(self) -> bool:
        return self.stt_flag and bool(self.sarvam_api_key)


settings = Settings()
