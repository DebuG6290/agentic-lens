import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import utils  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    """src/ reads prompts/ and writes data/ relative to the cwd, so pin the cwd
    to the repo root and send logs to a temp file instead of data/logs.jsonl."""
    monkeypatch.chdir(ROOT)
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(utils, "LOG_PATH", log_path)
    return log_path
