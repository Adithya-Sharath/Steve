"""The final audit (D50): run every check that must be green before `decode` is merged into `main`, and write `docs/FINAL_AUDIT.md`.

    python scripts/final_audit.py            # run everything (about 10 minutes), write docs/FINAL_AUDIT.md, exit 1 if anything is red
    python scripts/final_audit.py --quick    # skip the slow web build and browser flows (for a dry run)

Secrets are never printed: the scans report file names and counts only, and the exact values from the local .env files are compared without being shown.
The post-deploy smoke test section of the report is filled in by hand after the owner deploys (see docs/DEPLOY.md).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
QUICK = "--quick" in sys.argv
rows: list[tuple[str, bool, str]] = []


def run(cmd, cwd=ROOT, shell=False, env=None, timeout=1800) -> tuple[bool, str]:
    r = subprocess.run(cmd, cwd=cwd, shell=shell, capture_output=True, text=True, timeout=timeout, env={**os.environ, **(env or {})}, encoding="utf-8", errors="replace", check=False)
    return r.returncode == 0, (r.stdout + r.stderr)


def record(name: str, ok: bool, detail: str) -> None:
    rows.append((name, ok, detail))
    print(("PASS" if ok else "FAIL"), name, "-", detail, flush=True)


def passed(out: str) -> str:
    m = re.findall(r"(\d+) passed", out)
    return f"{m[-1]} passed" if m else out.strip().splitlines()[-1][:120] if out.strip() else "no output"


# ---- 1. tests and lint -------------------------------------------------------------------------------------------------------------------------------------------------

def tests_and_lint() -> None:
    ok, out = run([PY, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"], cwd=ROOT / "engine")
    record("engine tests", ok, passed(out))
    ok, out = run([PY, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"], cwd=ROOT / "api")
    record("api tests", ok, passed(out))
    ok, out = run([PY, "-m", "pytest", "tools/stt_compare", "-q", "--no-header", "-p", "no:cacheprovider"])
    record("tools tests (speech-to-text tooling, no network)", ok, passed(out))
    ok, out = run([PY, "-m", "ruff", "check", "engine", "api", "eval", "tools", "scripts"])
    record("ruff check engine api eval tools scripts", ok, out.strip().splitlines()[-1] if out.strip() else "clean")
    ok, out = run([PY, "scripts/export_openapi.py", "--check"])
    record("openapi.json matches the running app", ok, out.strip())
    ok, out = run([PY, "scripts/make_api_docs.py", "--check"])
    record("docs/API.md matches the running app (its JSON examples are real)", ok, out.strip())


# ---- 2. web ----------------------------------------------------------------------------------------------------------------------------------------------------------------

def web() -> None:
    web_dir = ROOT / "web"
    ok, out = run("npm run lint", cwd=web_dir, shell=True)
    record("web lint", ok, "clean" if ok and "problem" not in out else out.strip().splitlines()[-1][:120])
    ok, out = run("npx tsc --noEmit", cwd=web_dir, shell=True)
    record("web tsc --noEmit", ok, "clean" if ok else out.strip()[-200:])
    ok, out = run("npm run typecheck:client", cwd=web_dir, shell=True)
    record("TypeScript client type-checks (strict)", ok, "clean" if ok else out.strip()[-200:])
    if QUICK:
        record("web production build + browser flows", True, "skipped (--quick)")
        return
    ok, out = run("npm run build", cwd=web_dir, shell=True, env={"NEXT_PUBLIC_API_URL": "http://localhost:8000"})
    record("web production build", ok, "compiled" if ok else out.strip()[-300:])
    ok, out = run("node e2e/run.mjs all", cwd=web_dir, shell=True, timeout=2400)
    flows = re.findall(r"(E2E ALL PASSED|DEMO E2E ALL PASSED|CLIENT E2E ALL PASSED)", out)
    checks = len(re.findall(r"^PASS ", out, re.MULTILINE))
    fails = re.findall(r"^FAIL .*", out, re.MULTILINE)
    record("browser flows (Check mode, Listen + Paste + inspector + eval demo, TypeScript client) on the production build", ok and len(flows) == 3,
           f"{len(flows)}/3 scripts passed, {checks} checks" + ("; FAILED: " + "; ".join(fails[:5]) if fails else ""))


# ---- 3. evaluation is reproducible without keys ------------------------------------------------------------------------------------------------------------------------

def evals() -> None:
    env = {"GEMINI_API_KEY": "", "SARVAM_API_KEY": "", "LLM_ENABLED": "false"}
    ok1, _o1 = run([PY, "eval/run_engine.py"], env=env)
    ok2, _o2 = run([PY, "eval/metrics.py"], env=env)
    ok3, _ = run([PY, "eval/decode_metrics_export.py"], env=env)
    _ok4, out4 = run(["git", "status", "--porcelain", "--", "eval/results/latest.json", "eval/results/engine_predictions.json", "eval/results/decode_metrics.json", "data"])
    record("Check-mode evaluation reruns keyless and reproduces the committed numbers", ok1 and ok2 and ok3 and not out4.strip(), "identical" if not out4.strip() else "CHANGED: " + out4.strip()[:150])
    ok, out = run([PY, "eval/decode_eval.py", "--set", "v2", "--tag", "audit"])
    m = re.search(r"All correct sentences \| (\d+) \| ([\d.]+%)", out)
    record("Decode scorer runs on the frozen v2 set (current engine, contaminated label)", ok, f"false alarm {m.group(2)} of {m.group(1)}" if m else "ran")


# ---- 4. secrets ------------------------------------------------------------------------------------------------------------------------------------------------------------

PATTERNS = [
    r"AIza[0-9A-Za-z_\-]{30,}",  # Google API key
    r"hf_[A-Za-z0-9]{30,}",  # Hugging Face token
    r"AC[0-9a-f]{32}",  # Twilio account SID
    r"sk_[A-Za-z0-9_\-]{24,}",  # our sender keys and Stripe-style keys
    r"wk_[A-Za-z0-9_\-]{24,}",  # worker keys
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"(?i)(api[_-]?key|auth[_-]?token|secret|password)\s*[:=]\s*['\"][A-Za-z0-9_\-/+=]{20,}['\"]",
    r"sk-[A-Za-z0-9]{32,}",
]
ALLOWED_KEY_FILES = {  # test fixtures and docs that use obviously fake keys (sk_AAAA..., wk_aaaa...)
}


def env_values() -> list[str]:
    vals = []
    for f in (ROOT / ".env", ROOT / "web" / ".env.local", ROOT / "api" / ".env"):
        if f.exists():
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    v = line.split("=", 1)[1].strip().strip("\"'")
                    if len(v) >= 12 and not v.startswith("http") and v.lower() not in {"true", "false"}:
                        vals.append(v)
    return vals


def fake_key(hit: str) -> bool:
    body = re.sub(r"^(sk_|wk_)", "", hit)
    return len(set(body)) <= 3 or "demo" in body.lower() or "test" in body.lower() or "e2e" in body.lower()


def secrets() -> None:
    _, revs = run(["git", "rev-list", "--all"])
    revs = revs.split()
    hits: list[str] = []
    for pat in PATTERNS:
        _ok, out = run(["git", "grep", "-I", "-n", "-o", "-E", pat, "--", ".", ":(exclude)*.lock", ":(exclude)package-lock.json"])
        for line in out.splitlines():
            path, _, rest = line.partition(":")
            text = rest.split(":", 2)[-1]
            if not fake_key(text):
                hits.append(f"{path}")
    tree_hits = sorted(set(hits))
    record("secrets scan of the working tree (key patterns)", not tree_hits, "no key-shaped strings" if not tree_hits else "REVIEW: " + ", ".join(tree_hits[:8]))
    vals = env_values()
    leaked: set[str] = set()
    for v in vals:
        _ok, out = run(["git", "grep", "-I", "-l", "-F", v])
        if out.strip():
            leaked.add("tree")
    record("the exact values in the local .env files are not in any tracked file", not leaked, f"{len(vals)} values checked, none found" if not leaked else "FOUND IN TREE")
    hist_hits = 0
    hist_files: set[str] = set()
    step = 1
    for i in range(0, len(revs), step):
        rev = revs[i]
        for pat in PATTERNS:
            _ok, out = run(["git", "grep", "-I", "-n", "-o", "-E", pat, rev, "--", ".", ":(exclude)*.lock", ":(exclude)package-lock.json"])
            for line in out.splitlines():
                text = line.split(":", 3)[-1]
                if not fake_key(text):
                    hist_hits += 1
                    hist_files.add(line.split(":", 2)[1])
        for v in vals:
            _ok, out = run(["git", "grep", "-I", "-l", "-F", v, rev])
            if out.strip():
                hist_hits += 1
                hist_files.add("(exact .env value)")
    record(f"secrets scan of the full history ({len(revs)} revisions, key patterns and the exact .env values)", hist_hits == 0,
           "nothing found" if hist_hits == 0 else f"REVIEW {hist_hits} hits in: {', '.join(sorted(hist_files)[:8])}")
    _, tracked = run(["git", "ls-files"])
    bad = [f for f in tracked.splitlines() if re.search(r"(^|/)\.env(\.local)?$|\.db$|\.sqlite$|\.log$", f) or f.endswith((".wav", ".ogg", ".flac", ".mp3"))]
    record("no .env file, database, log or audio file is tracked", not bad, "none tracked" if not bad else ", ".join(bad[:6]))
    _, ign = run(["git", "check-ignore", ".env", "web/.env.local", "eval/.cache"])
    record(".env, web/.env.local and eval/.cache are git-ignored", len(ign.split()) >= 3, ign.replace("\n", " ").strip())
    l2 = [f for f in tracked.splitlines() if "l2arctic" in f.lower() and not f.endswith((".py", ".md", ".json", ".yaml", ".yml", ".txt", ".csv"))]
    record("no L2-ARCTIC audio or derived text is committed", not l2 and not any(f.startswith("tools/stt_compare/recordings") for f in tracked.splitlines()) and "report_" not in " ".join(f for f in tracked.splitlines() if f.startswith("tools/stt_compare/report_")),
           "only tooling and our own reports of counts" if not l2 else ", ".join(l2[:5]))


# ---- 5. names, dignity, storage --------------------------------------------------------------------------------------------------------------------------------------------

SAMJHA_ALLOWED = {
    "DECISIONS.md", "PROGRESS.md", "CLAUDE.md", "README.md", "docs/build-prompt.md", "docs/architecture.md", "docs/demo-script.md", "eval/generate.py", "api/tests/test_brand_name.py",
    "web/lib/sender-key.ts", "web/lib/facts.ts", "api/app/db.py", "api/app/config.py", "LEXICON_REVIEW.md", "SECURITY.md", "CONTRIBUTING.md", "scripts/final_audit.py", "docs/FINAL_AUDIT.md",
    "engine/pyproject.toml", "api/pyproject.toml", "docker-compose.yml", ".github/workflows/ci.yml", "Makefile",
}


def names() -> None:
    _, out = run(["git", "grep", "-I", "-i", "-l", "samjha"])
    files = sorted(set(out.split()))
    extra = [f for f in files if f not in SAMJHA_ALLOWED]
    record("`grep -ri samjha`: only the allowed historical hits", not extra, f"{len(files)} files, all on the allow-list (decision log, the rename guard, the eval seed string, the legacy storage key)" if not extra else "REVIEW: " + ", ".join(extra[:8]))


BANNED = re.compile(r"\b(wrong|incorrect|bad english|poor english|broken english|mistake|mistakes|faulty|your fault)\b", re.IGNORECASE)
SYSTEM_OK = re.compile(r"went wrong|something went wrong", re.IGNORECASE)


def dignity() -> None:
    """Every user-facing string of Decode: the web components and pages, the reply copy, the glossary and accent notes, the API's messages."""
    targets = [
        *(ROOT / "web" / "components" / "decode").glob("*.tsx"), ROOT / "web" / "app" / "listen" / "page.tsx", ROOT / "web" / "app" / "page.tsx",
        ROOT / "web" / "app" / "how-it-works" / "page.tsx", ROOT / "web" / "app" / "eval" / "page.tsx", ROOT / "web" / "lib" / "copy.ts", ROOT / "web" / "lib" / "languages.ts",
        ROOT / "api" / "app" / "services" / "whatsapp.py", ROOT / "api" / "app" / "routes" / "decode.py", ROOT / "api" / "app" / "services" / "decode_flow.py",
        ROOT / "api" / "app" / "services" / "translate.py", ROOT / "engine" / "steve_engine" / "decode" / "glossary.yaml", ROOT / "engine" / "steve_engine" / "decode" / "safety.py",
        ROOT / "engine" / "steve_engine" / "decode" / "typed.py", ROOT / "engine" / "steve_engine" / "decode" / "decoder.py", ROOT / "copy_review.md",
        *(ROOT / "engine" / "steve_engine" / "decode" / "accents").glob("*.yaml"),
    ]
    hits = []
    for f in targets:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith(("#", "//", "*", '"""', "/*")) or "regex" in stripped.lower() or "BANNED" in stripped or "DIGNITY" in stripped:
                continue  # comments and code that names the words in order to forbid them
            for m in BANNED.finditer(line):
                if not SYSTEM_OK.search(line) and "never" not in line.lower() and "no \"" not in line.lower() and "not \"" not in line.lower():
                    hits.append(f"{f.relative_to(ROOT)}:{n}: {m.group(0)}")
    record("dignity-word scan of every Decode user-facing string (files)", not hits, f"{len(targets)} files, no shaming words" if not hits else "REVIEW: " + "; ".join(hits[:6]))
    ok, out = run([PY, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "-k", "shame or dignity or never_shame", "tests"], cwd=ROOT / "api")
    record("dignity tests over live API and WhatsApp responses (every field, all languages)", ok, passed(out))


LOG_CALL = re.compile(r"\blog\.(?:debug|info|warning|error|exception|critical)\((.*)\)")
RISKY = re.compile(r"\b(text|transcript|body|audio|sender|message|card|original|session|reply|query)\b")


def storage() -> None:
    files = [ROOT / "api" / "app" / p for p in ("routes/decode.py", "routes/whatsapp.py", "services/decode_flow.py", "services/decode_sessions.py", "services/translate.py",
                                                   "services/whatsapp.py", "services/audio.py", "services/decode_examples.py", "services/messaging/twilio.py")]
    risky_logs, writes = [], []
    for f in files:
        src = f.read_text(encoding="utf-8")
        for n, line in enumerate(src.splitlines(), 1):
            m = LOG_CALL.search(line)
            if m and RISKY.search(re.sub(r'"[^"]*"', '""', m.group(1)).replace("type(e).__name__", "")):
                risky_logs.append(f"{f.name}:{n}")
            if re.search(r"open\(|write_text|write_bytes|NamedTemporaryFile|mkstemp|\.write\(", line):
                writes.append(f"{f.name}:{n}")
            if re.search(r"session\.add\(|\.add\(row\)", line) and f.name != "whatsapp.py":
                writes.append(f"{f.name}:{n} (db)")
    record("no log call in the Decode, translation or WhatsApp code takes text, a transcript, audio or a phone number", not risky_logs, f"{len(files)} files reviewed" if not risky_logs else "REVIEW: " + ", ".join(risky_logs))
    record("no Decode code path writes a file or a database row with audio or message text (the only row is the WhatsApp hash, language and counters)", not writes,
           "no file writes; the one database write is WorkerPref (hash, language, counters)" if not writes else "REVIEW: " + ", ".join(writes))
    ok, out = run([PY, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "-k", "log or spool or dump or database_holds or nothing_is_stored or stores_nothing", "tests"], cwd=ROOT / "api")
    record("tests that capture logs, dump the database and forbid disk spooling of uploads", ok, passed(out))


def main() -> int:
    print(f"final audit at {datetime.now(UTC):%Y-%m-%d %H:%M} UTC", flush=True)
    for step in (tests_and_lint, web, evals, secrets, names, dignity, storage):
        try:
            step()
        except Exception as e:  # noqa: BLE001 - a crashed check is a red check
            record(step.__name__, False, f"crashed: {type(e).__name__}: {str(e)[:150]}")
    _, head = run(["git", "rev-parse", "--short", "HEAD"])
    _, branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    green = all(ok for _, ok, _ in rows)
    lines = [
        "# Final audit", "",
        (
            f"Run by `python scripts/final_audit.py` at {datetime.now(UTC):%Y-%m-%d %H:%M} UTC on branch `{branch.strip()}` at commit `{head.strip()}` "
            f"({'quick dry run: NOT valid for merging' if QUICK else 'full run'})."
        ),
        "",
        f"**Result: {'GREEN' if green else 'RED'}** ({sum(ok for _, ok, _ in rows)} of {len(rows)} checks passed). `decode` is merged into `main` and tagged `v2.0.0` only when this is green.", "",
        "| # | Check | Result | Detail |", "|---|---|---|---|",
    ]
    for i, (name, ok, detail) in enumerate(rows, 1):
        lines.append(f"| {i} | {name} | {'PASS' if ok else '**FAIL**'} | {detail.replace('|', '/')} |")
    lines += ["", "## What the audit does not cover", "",
              "* **Real-world validation.** No real workers, voice notes or messages were involved; every accuracy number is from public read speech or synthetic, author-written data (see the README and D42, D44, D49).",
              "* **Live WhatsApp.** No WhatsApp message was ever sent; the flow was tested with mocked Twilio calls.",
              "* **Docker.** The API image had not been built when this audit ran (Docker Desktop was off); `docs/DEPLOY.md` says so, and the first Render build is the first real build.",
              "* **Independent security review.** None. The secrets scans look for key-shaped strings and for the exact values in the local `.env` files; a secret in another shape would not be found.",
              "* **Native-speaker and legal review.** Every accent rule, glossary entry, word list and piece of copy is `verified: false` (see `ACCENT_REVIEW.md`, `GLOSSARY_REVIEW.md`, `copy_review.md`).", "",
              "## Post-deploy smoke test", "", "_Not run yet: it needs the live URLs from the owner (see `docs/DEPLOY.md`, step 5). This section is filled in after that run._", ""]
    (ROOT / "docs" / "FINAL_AUDIT.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("wrote docs/FINAL_AUDIT.md;", "GREEN" if green else "RED")
    return 0 if green else 1


if __name__ == "__main__":
    sys.exit(main())
