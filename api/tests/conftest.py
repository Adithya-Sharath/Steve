import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.as_posix()}"
os.environ["LLM_ENABLED"] = "false"
os.environ["GEMINI_API_KEY"] = ""
os.environ["SARVAM_API_KEY"] = ""
os.environ["REPLY_RATE_LIMIT"] = "1000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

KEY_A = "sk_" + "A" * 32
KEY_B = "sk_" + "B" * 32


@pytest.fixture(scope="session")
def client():
    """A sender (browser A). Reader endpoints ignore the header; sender endpoints need it."""
    with TestClient(app, headers={"X-Sender-Key": KEY_A}) as c:
        yield c


@pytest.fixture()
def anon():
    """No sender key at all (also what a reader's browser looks like)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def other():
    """A different sender (browser B)."""
    with TestClient(app, headers={"X-Sender-Key": KEY_B}) as c:
        yield c
