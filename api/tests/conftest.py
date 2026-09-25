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


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
