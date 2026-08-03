"""
classifier.py
Scores a single article against the mechanism object via Ollama.
Prompt lives in prompts/classification.txt, every call is logged to data/logs.jsonl.
"""

import json
from pathlib import Path

from utils import _try_parse_json, call_ollama

PROMPT_PATH = Path("prompts/classification.txt")


def classify_article(article: dict, mechanism_object: dict) -> dict:
    system_prompt = PROMPT_PATH.read_text()

    user_content = (
        "MECHANISM OBJECT:\n"
        + json.dumps(mechanism_object)
        + "\n\nARTICLE:\n"
        + json.dumps(
            {"title": article.get("title", ""), "summary": article.get("summary", "")}
        )
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    result = call_ollama(
        stage="classification",
        messages=messages,
        input_data={
            "title": article.get("title", ""),
            "link": article.get("link", ""),
            "entity": mechanism_object.get("entity", ""),
        },
    )

    if not result["ok"]:
        return {"relevant": False, "reason": f"classification failed: {result['error']}"}

    parsed = _try_parse_json(result["text"])
    if not isinstance(parsed, dict) or "relevant" not in parsed:
        return {"relevant": False, "reason": "model did not return valid JSON"}

    return {
        "relevant": bool(parsed["relevant"]),
        "reason": str(parsed.get("reason", "")).strip(),
    }
