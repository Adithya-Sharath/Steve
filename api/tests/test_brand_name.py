"""The product is called Steve (D28). The old working name must not reappear in anything a user can see.

Allowed: the migration constant for the old browser-storage key, and the ordinary Hindi words "samjhane" / "samjha gaya"
("to understand" / "was understood") in the follow-up templates, which are language content, not the brand.
"""

import re
from pathlib import Path

from test_api import MANGLISH, _flow

ROOT = Path(__file__).resolve().parents[2]
OLD_NAME = re.compile(r"samjha(?!ne\b| gaya\b)", re.I)
WEB_DIRS = ["app", "components", "lib", "public"]
WEB_SUFFIXES = {".ts", ".tsx", ".css", ".json", ".svg", ".md", ".mjs", ".html"}


def _hits(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if OLD_NAME.search(line)]


def test_no_old_name_in_user_facing_web_files():
    files = [p for d in WEB_DIRS for p in (ROOT / "web" / d).rglob("*") if p.is_file() and p.suffix in WEB_SUFFIXES]
    files += [ROOT / "web" / "package.json", ROOT / "web" / "next.config.ts"]
    assert len(files) > 30, "the scan found suspiciously few web files"
    found = {}
    for p in files:
        hits = [h for h in _hits(p) if "LEGACY_STORAGE_KEY" not in h]  # the one-time storage migration
        if hits:
            found[str(p.relative_to(ROOT))] = hits
    assert not found, f"old product name in web files: {found}"


def test_legacy_storage_key_is_only_used_for_the_migration():
    src = (ROOT / "web" / "lib" / "sender-key.ts").read_text(encoding="utf-8")
    assert 'const STORAGE_KEY = "steve_sender_key"' in src
    assert src.count("LEGACY_STORAGE_KEY") == 3  # declared, read, removed: nothing else may touch it
    assert "removeItem(LEGACY_STORAGE_KEY)" in src


def test_no_old_name_in_api_source_copy():
    found = {}
    for p in (ROOT / "api" / "app").rglob("*.py"):
        if hits := _hits(p):
            found[p.name] = hits
    assert not found, found


def test_no_old_name_in_api_responses(client, anon):
    texts = [client.get("/health").text, client.get("/openapi.json").text, anon.get("/messages").text]
    mid, _, conf = _flow(client)
    client.post(f"/r/{conf['reader_token']}/reply", data={"text": MANGLISH})
    texts.append(client.post(f"/messages/{mid}/followup").text)
    texts.append(client.get(f"/r/{conf['reader_token']}").text)
    for t in texts:
        assert not OLD_NAME.search(t), t[:200]
    assert "Steve" in client.get("/openapi.json").json()["info"]["title"]
    assert "Steve" in anon.get("/messages").json()["detail"]


def test_default_database_and_env_names_use_the_new_name(monkeypatch):
    from app.settings import Settings

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings().database_url == "sqlite:///./steve.db"
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "steve.db" in example and not re.search(r"SAMJHA_", example, re.I)
    for name in ("STEVE_DATA_DIR", "STEVE_EVAL_DIR"):
        assert name in (ROOT / "api" / "app" / "settings.py").read_text(encoding="utf-8")
