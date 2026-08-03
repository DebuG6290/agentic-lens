import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(REPO_ROOT / "src"))

import utils
from classifier import classify_article

ARTICLE = {"title": "Medicaid cuts loom", "link": "https://x/1", "summary": "funding squeeze"}
MECHANISM = {
    "entity": "Trump",
    "user_context": "hospital business",
    "reasoning_paths": [{"path": "healthcare policy", "keywords": ["Medicaid"]}],
}


@pytest.fixture(autouse=True)
def isolate_logs(monkeypatch, tmp_path):
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(utils, "LOG_PATH", tmp_path / "logs.jsonl")


def _fake_chat(content: str):
    def chat(model, messages):
        return {"message": {"content": content}, "prompt_eval_count": 7, "eval_count": 3}

    return chat


def test_parses_fenced_classification(monkeypatch):
    fenced = '```json\n{"relevant": true, "reason": "Medicaid funding hits hospital revenue"}\n```'
    monkeypatch.setattr(utils.ollama, "chat", _fake_chat(fenced))

    assert classify_article(ARTICLE, MECHANISM) == {
        "relevant": True,
        "reason": "Medicaid funding hits hospital revenue",
    }


def test_negative_classification(monkeypatch):
    monkeypatch.setattr(
        utils.ollama, "chat", _fake_chat('{"relevant": false, "reason": "sports story"}')
    )

    assert classify_article(ARTICLE, MECHANISM)["relevant"] is False


def test_unparseable_output_is_not_relevant(monkeypatch):
    monkeypatch.setattr(utils.ollama, "chat", _fake_chat("I think maybe yes?"))

    result = classify_article(ARTICLE, MECHANISM)

    assert result == {"relevant": False, "reason": "unparseable classifier output"}


def test_ollama_failure_is_not_relevant(monkeypatch, tmp_path):
    log_path = tmp_path / "logs2.jsonl"
    monkeypatch.setattr(utils, "LOG_PATH", log_path)

    def boom(model, messages):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(utils.ollama, "chat", boom)

    result = classify_article(ARTICLE, MECHANISM)

    assert result["relevant"] is False
    assert "connection refused" in result["reason"]
    assert "classification" in log_path.read_text()


def test_logs_every_call(monkeypatch, tmp_path):
    log_path = tmp_path / "logs3.jsonl"
    monkeypatch.setattr(utils, "LOG_PATH", log_path)
    monkeypatch.setattr(utils.ollama, "chat", _fake_chat('{"relevant": true, "reason": "ok"}'))

    classify_article(ARTICLE, MECHANISM)

    import json

    entry = json.loads(log_path.read_text().splitlines()[0])
    assert entry["stage"] == "classification"
    assert entry["tokens"] == {"prompt": 7, "completion": 3, "total": 10}
    assert set(entry) == {"timestamp", "stage", "input", "output", "tokens"}
