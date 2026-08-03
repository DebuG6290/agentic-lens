import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(REPO_ROOT / "src"))

import utils
from intent_parser import parse_intent

VALID_MECHANISM = """{
  "entity": "Trump",
  "user_context": "hospital business",
  "reasoning_paths": [
    {"path": "healthcare policy", "keywords": ["medicaid", "healthcare reform"]}
  ]
}"""


def _fake_chat(content: str):
    def chat(model, messages):
        return {
            "message": {"content": content},
            "prompt_eval_count": 10,
            "eval_count": 5,
        }

    return chat


@pytest.fixture(autouse=True)
def isolate_logs(monkeypatch, tmp_path):
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(utils, "LOG_PATH", tmp_path / "logs.jsonl")


def test_strips_json_fenced_block(monkeypatch):
    monkeypatch.setattr(utils.ollama, "chat", _fake_chat(f"```json\n{VALID_MECHANISM}\n```"))

    result = parse_intent("Trump affects my hospital business")

    assert result["status"] == "complete"
    assert result["mechanism_object"]["entity"] == "Trump"


def test_strips_plain_fences_and_preamble(monkeypatch):
    noisy = f"Here is the mechanism object:\n```\n{VALID_MECHANISM}\n```\nHope that helps!"
    monkeypatch.setattr(utils.ollama, "chat", _fake_chat(noisy))

    result = parse_intent("Trump affects my hospital business")

    assert result["status"] == "complete"
    assert result["mechanism_object"]["user_context"] == "hospital business"


def test_tokens_are_reported(monkeypatch):
    monkeypatch.setattr(utils.ollama, "chat", _fake_chat(VALID_MECHANISM))

    result = parse_intent("Trump affects my hospital business")

    assert result["tokens"] == {"prompt": 10, "completion": 5, "total": 15}


@pytest.mark.parametrize(
    "content",
    [
        "{}",
        '{"entity": "Trump"}',
        '["entity", "user_context", "reasoning_paths"]',
        '"just a string"',
        '{"entity": "Trump", "user_context": "hospital business"}',
    ],
)
def test_json_missing_required_keys_routes_to_clarification(monkeypatch, content):
    monkeypatch.setattr(utils.ollama, "chat", _fake_chat(content))

    result = parse_intent("Trump affects my hospital business")

    assert result["status"] == "needs_clarification"
    assert result["questions"] == content


def test_plain_text_questions_route_to_clarification(monkeypatch):
    questions = "1. Which hospital? 2. What time horizon? 3. Policy or funding?"
    monkeypatch.setattr(utils.ollama, "chat", _fake_chat(questions))

    result = parse_intent("Trump affects my hospital business")

    assert result["status"] == "needs_clarification"
    assert result["questions"] == questions
    assert result["history"][-1] == {"role": "assistant", "content": questions}
    assert result["history"][0]["role"] == "user"


def test_clarification_history_is_replayed(monkeypatch):
    monkeypatch.setattr(utils.ollama, "chat", _fake_chat("Which hospital?"))
    first = parse_intent("Trump affects my hospital business")

    seen = {}

    def chat(model, messages):
        seen["messages"] = messages
        return {"message": {"content": VALID_MECHANISM}, "prompt_eval_count": 1, "eval_count": 2}

    monkeypatch.setattr(utils.ollama, "chat", chat)
    second = parse_intent("A 200-bed hospital in Ohio", conversation_history=first["history"])

    assert second["status"] == "complete"
    assert seen["messages"][0]["role"] == "system"
    assert seen["messages"][-1]["content"] == "A 200-bed hospital in Ohio"
    assert any(m["content"] == "Which hospital?" for m in seen["messages"])


def test_ollama_failure_returns_error_status(monkeypatch, tmp_path):
    log_path = tmp_path / "failure_logs.jsonl"
    monkeypatch.setattr(utils, "LOG_PATH", log_path)

    def boom(model, messages):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(utils.ollama, "chat", boom)

    result = parse_intent("Trump affects my hospital business")

    assert result["status"] == "error"
    assert "connection refused" in result["message"]
    assert "connection refused" in log_path.read_text()
