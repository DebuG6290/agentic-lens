import json

import pytest

import utils
from classifier import classify_article

ARTICLE = {"title": "Medicaid cuts loom", "link": "a", "summary": "budget deal"}
MECHANISM = {
    "entity": "Trump",
    "user_context": "hospital business",
    "reasoning_paths": [{"path": "healthcare policy", "keywords": ["Medicaid"]}],
}


@pytest.fixture
def model_says(monkeypatch):
    def _set(content):
        def _chat(model, messages):
            return {
                "message": {"content": content},
                "prompt_eval_count": 3,
                "eval_count": 2,
            }

        monkeypatch.setattr(utils.ollama, "chat", _chat)

    return _set


def test_parses_fenced_verdict(model_says):
    model_says('```json\n{"relevant": true, "reason": "Medicaid funds hospitals"}\n```')
    assert classify_article(ARTICLE, MECHANISM) == {
        "relevant": True,
        "reason": "Medicaid funds hospitals",
    }


def test_unparseable_output_is_not_relevant(model_says):
    model_says("I think maybe yes?")
    assert classify_article(ARTICLE, MECHANISM)["relevant"] is False


def test_ollama_failure_is_not_relevant_and_logged(monkeypatch, isolated_runtime):
    def _boom(model, messages):
        raise RuntimeError("model not found")

    monkeypatch.setattr(utils.ollama, "chat", _boom)

    verdict = classify_article(ARTICLE, MECHANISM)
    assert verdict["relevant"] is False
    assert "model not found" in verdict["reason"]

    entry = json.loads(isolated_runtime.read_text().strip())
    assert entry["stage"] == "classification"
    assert entry["input"]["link"] == "a"
