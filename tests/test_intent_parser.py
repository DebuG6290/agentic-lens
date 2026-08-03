import json

import pytest

import utils
from intent_parser import parse_intent

MECHANISM = {
    "entity": "Trump",
    "user_context": "hospital business",
    "reasoning_paths": [{"path": "healthcare policy", "keywords": ["medicaid"]}],
}
INTENT = "Trump affects my hospital business"


@pytest.fixture
def model_says(monkeypatch):
    """Make ollama.chat return a fixed string, and record the messages sent."""
    calls = []

    def _set(content):
        def _chat(model, messages):
            calls.append(messages)
            return {
                "message": {"content": content},
                "prompt_eval_count": 10,
                "eval_count": 5,
            }

        monkeypatch.setattr(utils.ollama, "chat", _chat)
        return calls

    return _set


def test_plain_json_is_complete(model_says):
    model_says(json.dumps(MECHANISM))
    result = parse_intent(INTENT)
    assert result["status"] == "complete"
    assert result["mechanism_object"] == MECHANISM
    assert result["tokens"] == {"prompt": 10, "completion": 5, "total": 15}


@pytest.mark.parametrize(
    "wrapper",
    [
        "```json\n{body}\n```",
        "```\n{body}\n```",
        "   ```json\n{body}\n```   ",
        "Here is the mechanism object:\n{body}\nLet me know if this helps!",
        "```json\n{body}\n```\nHope that works.",
    ],
)
def test_fence_and_prose_stripping(model_says, wrapper):
    model_says(wrapper.format(body=json.dumps(MECHANISM)))
    result = parse_intent(INTENT)
    assert result["status"] == "complete"
    assert result["mechanism_object"] == MECHANISM


@pytest.mark.parametrize(
    "content",
    [
        "[]",
        '["entity", "user_context"]',
        '"just a string"',
        "{}",
        '{"entity": "Trump"}',
        '{"entity": "Trump", "user_context": "hospitals"}',
        '{"entity": "Trump", "user_context": "hospitals", "reasoning_paths": []}',
    ],
)
def test_json_without_usable_keys_needs_clarification(model_says, content):
    model_says(content)
    result = parse_intent(INTENT)
    assert result["status"] == "needs_clarification"
    assert result["questions"] == content


def test_clarifying_questions_branch(model_says):
    questions = "1. Which hospitals?\n2. What time horizon?"
    model_says(questions)
    result = parse_intent(INTENT)
    assert result["status"] == "needs_clarification"
    # history drops the system prompt, keeps the user turn + model reply
    assert result["history"] == [
        {"role": "user", "content": INTENT},
        {"role": "assistant", "content": questions},
    ]


def test_clarification_round_trip_passes_history(model_says):
    calls = model_says("Which hospitals?")
    first = parse_intent(INTENT)

    model_says(json.dumps(MECHANISM))
    second = parse_intent("US hospitals, next 6 months", conversation_history=first["history"])

    assert second["status"] == "complete"
    sent = calls[-1]
    assert sent[0]["role"] == "system"
    assert sent[1:] == first["history"] + [
        {"role": "user", "content": "US hospitals, next 6 months"}
    ]


def test_ollama_failure_returns_error_and_logs(monkeypatch, isolated_runtime):
    def _boom(model, messages):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(utils.ollama, "chat", _boom)

    result = parse_intent(INTENT)
    assert result["status"] == "error"
    assert "connection refused" in result["error"]

    entry = json.loads(isolated_runtime.read_text().strip())
    assert entry["stage"] == "intent_decomposition"
    assert "connection refused" in entry["output"]["error"]
    assert entry["tokens"] == {"prompt": 0, "completion": 0, "total": 0}


def test_raw_output_is_logged_verbatim(model_says, isolated_runtime):
    raw = "```json\n" + json.dumps(MECHANISM) + "\n```"
    model_says(raw)
    parse_intent(INTENT)

    entry = json.loads(isolated_runtime.read_text().strip())
    assert entry["output"]["raw_output"] == raw
    assert entry["input"] == {"user_input": INTENT, "history_len": 0}
