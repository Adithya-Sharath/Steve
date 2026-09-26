"""Write the API's OpenAPI schema to `openapi.json` at the repo root (the public contract for other front ends, D47).

    python scripts/export_openapi.py            # rewrite openapi.json
    python scripts/export_openapi.py --check    # exit 1 if the file is stale (also enforced by api/tests/test_api_contract.py)

Run it, and add a decision record, whenever a response shape changes on purpose.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(Path(tempfile.mkdtemp()) / 'openapi.db').as_posix()}")  # importing the app must not touch a real database

from app.main import app


def render() -> str:
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


if __name__ == "__main__":
    target = ROOT / "openapi.json"
    text = render()
    if "--check" in sys.argv:
        same = target.exists() and target.read_text(encoding="utf-8").replace("\r\n", "\n") == text
        print("openapi.json is up to date" if same else "openapi.json is STALE: run python scripts/export_openapi.py")
        sys.exit(0 if same else 1)
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {target} ({len(text)} bytes)")
