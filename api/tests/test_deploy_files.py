"""Deployment files (D50): render.yaml, vercel.json, docs/DEPLOY.md. No secret may ever be committed; the app must start with no keys and an empty disk."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SECRET_NAMES = {"ADMIN_KEY", "WORKER_HASH_SECRET", "SARVAM_API_KEY", "GEMINI_API_KEY", "TWILIO_AUTH_TOKEN", "TWILIO_ACCOUNT_SID"}


def render():
    return yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))["services"][0]


def test_render_blueprint_is_a_docker_web_service_built_from_the_repo_root():
    s = render()
    assert s["type"] == "web" and s["runtime"] == "docker" and s["plan"] == "free" and s["branch"] == "main"
    assert (ROOT / s["dockerfilePath"]).exists() and s["dockerContext"] == "." and s["healthCheckPath"] == "/health"


def test_no_secret_value_is_in_render_yaml():
    env = {e["key"]: e for e in render()["envVars"]}
    for name in SECRET_NAMES & set(env):
        e = env[name]
        assert "value" not in e and (e.get("sync") is False or e.get("generateValue") is True), name
    assert env["ADMIN_KEY"]["generateValue"] is True and env["WORKER_HASH_SECRET"]["generateValue"] is True
    assert env["SARVAM_API_KEY"]["sync"] is False and env["GEMINI_API_KEY"]["sync"] is False


def test_production_settings_are_the_safe_ones():
    env = {e["key"]: e.get("value") for e in render()["envVars"]}
    assert env["TRUST_PROXY"] == "true" and env["WHATSAPP_ENABLED"] == "false" and env["LLM_ENABLED"] == "false"
    for cap in ("STT_DAILY_CAP", "TRANSLATE_DAILY_CAP", "LLM_DAILY_CAP"):
        assert 0 < int(env[cap]) <= 300, cap  # the daily caps stay ON in production


def test_every_variable_in_render_yaml_is_documented_and_read_by_the_app():
    keys = {e["key"] for e in render()["envVars"]}
    doc = (ROOT / "docs" / "DEPLOY.md").read_text(encoding="utf-8")
    settings_src = (ROOT / "api" / "app" / "settings.py").read_text(encoding="utf-8")
    for k in keys:
        assert k in doc, f"{k} is not explained in docs/DEPLOY.md"
        assert k in settings_src, f"{k} is set in render.yaml but the app never reads it"
    assert "NEXT_PUBLIC_API_URL" in doc and "CORS_ORIGINS" in doc and "Root Directory" in doc


def test_the_dockerfile_binds_the_platform_port():
    text = (ROOT / "api" / "Dockerfile").read_text(encoding="utf-8")
    assert "${PORT:-8000}" in text and "--host 0.0.0.0" in text and "COPY eval/results" in text


def test_vercel_json_is_valid_and_lets_the_page_use_the_microphone():
    v = json.loads((ROOT / "web" / "vercel.json").read_text(encoding="utf-8"))
    assert v["framework"] == "nextjs"
    hdrs = {h["key"]: h["value"] for rule in v["headers"] for h in rule["headers"]}
    assert "microphone=(self)" in hdrs["Permissions-Policy"] and hdrs["X-Content-Type-Options"] == "nosniff"


def test_local_env_files_are_ignored_and_not_tracked():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"^\.env$", ignore, re.M) and re.search(r"^\.env\.\*$", ignore, re.M) and "!.env.example" in ignore
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    assert not [f for f in tracked if f.endswith(".env") or f.endswith(".env.local") or f.endswith(".db")], "an env file or a database is tracked"
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for name in SECRET_NAMES:
        assert re.search(rf"^#?\s*{name}=\s*(#.*)?$", example, re.M) or name not in example, f"{name} must have no value in .env.example"


def test_the_app_starts_with_no_keys_and_an_empty_disk_and_decodes(tmp_path):
    """What Render's free plan gives us after every restart: no database file, no keys. Decode must not care."""
    code = (
        "import os; os.environ['DATABASE_URL']='sqlite:///" + (tmp_path / "fresh.db").as_posix() + "'\n"
        "for k in ('SARVAM_API_KEY','GEMINI_API_KEY','ADMIN_KEY','LLM_ENABLED','WHATSAPP_ENABLED'): os.environ[k]=''\n"
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "with TestClient(app) as c:\n"
        "    h = c.get('/decode/health').json(); assert h['typed'] and not h['voice'] and not h['translation']['available'], h\n"
        "    r = c.post('/decode', json={'text': 'yalla come to the barking gate tree', 'accent_hint': 'ar', 'reply_language': 'ml'}, headers={'X-Worker-Key': 'wk_' + 'z'*32}).json()\n"
        "    assert r['card']['actions']['where']['value'] == 'parking gate 3' and r['translation'] is None and r['notes'], r\n"
        "    assert c.get('/decode/examples').status_code == 200 and c.get('/decode/eval').json()['available']\n"
        "    assert c.get('/health').status_code == 200\n"
        "print('ok')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT / "api", capture_output=True, text=True, timeout=120, env={**os.environ, "PYTHONPATH": str(ROOT / "api")})
    assert r.returncode == 0 and "ok" in r.stdout, r.stdout + r.stderr
    assert (tmp_path / "fresh.db").exists()  # tables were created on boot
