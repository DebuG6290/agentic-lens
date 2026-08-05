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
    model_says(
        '```json\n{"relevant": true, "confidence": 0.9, '
        '"mechanism_id": "healthcare_policy", '
        '"evidence": "The article describes Medicaid cuts", '
        '"impact_chain": "Cuts -> less hospital funding", '
        '"reason": "Medicaid funds hospitals"}\n```'
    )
    assert classify_article(ARTICLE, MECHANISM) == {
        "relevant": True,
        "confidence": 0.9,
        "mechanism_id": "healthcare_policy",
        "evidence": "The article describes Medicaid cuts",
        "impact_chain": "Cuts -> less hospital funding",
        "reason": "Medicaid funds hospitals",
    }


def test_unparseable_output_is_not_relevant(model_says):
    model_says("I think maybe yes?")
    assert classify_article(ARTICLE, MECHANISM)["relevant"] is False


def test_confidence_is_clamped(model_says):
    model_says('{"relevant": true, "confidence": 4, "reason": "strong"}')
    assert classify_article(ARTICLE, MECHANISM)["confidence"] == 1.0


def test_string_false_is_not_relevant(model_says):
    model_says('{"relevant": "false", "confidence": 0.9, "reason": "does not match"}')
    assert classify_article(ARTICLE, MECHANISM)["relevant"] is False


def test_ollama_failure_is_not_relevant_and_logged(monkeypatch, isolated_runtime):
    def _boom(model, messages):
        raise RuntimeError("model not found")

    monkeypatch.setattr(utils.ollama, "chat", _boom)

    verdict = classify_article(ARTICLE, MECHANISM)
    assert verdict["relevant"] is False
    assert verdict["confidence"] == 0.0
    assert "model not found" in verdict["reason"]

    entry = json.loads(isolated_runtime.read_text().strip())
    assert entry["stage"] == "classification"
    assert entry["input"]["link"] == "a"


def test_invalid_json_is_retried(monkeypatch):
    responses = iter([
        "not json",
        '{"relevant": true, "confidence": 0.8, "reason": "matches"}',
    ])

    def _chat(model, messages):
        return {"message": {"content": next(responses)}, "prompt_eval_count": 1, "eval_count": 1}

    monkeypatch.setattr(utils.ollama, "chat", _chat)
    result = classify_article(ARTICLE, MECHANISM)
    assert result["relevant"] is True
    assert result["confidence"] == 0.8
