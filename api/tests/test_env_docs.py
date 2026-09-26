"""Every environment variable the API reads must be documented in .env.example and in the README configuration table."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _variables() -> set[str]:
    src = (ROOT / "api" / "app" / "settings.py").read_text(encoding="utf-8")
    return set(re.findall(r'(?:os\.getenv|_int|_bool)\("([A-Z][A-Z0-9_]+)"', src))


def test_settings_reads_the_variables_we_expect():
    found = _variables()
    assert {"ADMIN_KEY", "TRUST_PROXY", "TRUSTED_PROXIES", "LLM_DAILY_CAP", "STT_DAILY_CAP", "MAX_BODY_BYTES", "RL_DEFAULT_PER_MIN"} <= found
    assert len(found) >= 25


def test_env_example_mentions_every_variable():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    missing = [v for v in sorted(_variables()) if not re.search(rf"^#?\s*{v}=", example, re.M)]
    assert not missing, f".env.example is missing: {missing}"


def test_readme_configuration_table_mentions_every_variable():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = [v for v in sorted(_variables()) if v not in readme]
    assert not missing, f"README.md is missing: {missing}"
