"""The API image must bind to $PORT (PaaS hosts inject it) and fall back to 8000 locally."""

import json
import re
import subprocess
from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"


def _cmd() -> list[str]:
    lines = [ln for ln in DOCKERFILE.read_text(encoding="utf-8").splitlines() if ln.startswith("CMD")]
    assert len(lines) == 1
    return json.loads(lines[0][3:].strip())


def test_cmd_binds_to_port_env_with_8000_default():
    cmd = _cmd()
    assert cmd[:2] == ["sh", "-c"], "exec-form CMD does not expand ${PORT}; it must go through a shell"
    assert "${PORT:-8000}" in cmd[2]
    assert "--host 0.0.0.0" in cmd[2] and "app.main:app" in cmd[2]
    assert not re.search(r"--port\s+8000\b", cmd[2]), "port must not be hard-coded"


@pytest.mark.parametrize("env,expected", [({}, "8000"), ({"PORT": "10000"}, "10000")])
def test_shell_expansion_yields_the_right_port(env, expected):
    """Run the CMD's shell string with `uvicorn` replaced by echo, exactly as the container shell would expand it."""
    import shutil

    sh = shutil.which("sh")
    if not sh:
        pytest.skip("no POSIX sh on this machine")
    script = _cmd()[2].replace("exec uvicorn", "echo uvicorn")
    out = subprocess.run([sh, "-c", script], env={"PATH": "/usr/bin:/bin", **env}, capture_output=True, text=True, check=True).stdout
    assert f"--port {expected}" in out


def test_no_inline_comments_after_instructions():
    """Docker does not support trailing comments: `EXPOSE 8000  # x` would be parsed as extra ports."""
    for ln in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        if ln and not ln.startswith("#"):
            assert " #" not in ln, ln
