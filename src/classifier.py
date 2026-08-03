"""
classifier.py
Scores one article against the mechanism object using Ollama.
Prompt lives in prompts/classification.txt. Every call is logged to data/logs.jsonl.
"""

import json
from pathlib import Path

from utils import MODEL, call_ollama, try_parse_json

PROMPT_PATH = Path("prompts/classification.txt")


def classify_article(article: dict, mechanism_object: dict) -> dict:
    """Returns {"relevant": bool, "reason": str} for a single article."""
    system_prompt = PROMPT_PATH.read_text()

    user_content = json.dumps(
        {
            "entity": mechanism_object.get("entity"),
            "user_context": mechanism_object.get("user_context"),
            "reasoning_paths": mechanism_object.get("reasoning_paths"),
            "article": {
                "title": article.get("title", ""),
                "summary": article.get("summary", ""),
            },
        }
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    result = call_ollama(
        stage="classification",
        messages=messages,
        input_data={"article_link": article.get("link", ""), "title": article.get("title", "")},
        model=MODEL,
    )
    if not result["ok"]:
        return {"relevant": False, "reason": f"classification failed: {result['error']}"}

    parsed = try_parse_json(result["text"])
    if not isinstance(parsed, dict) or "relevant" not in parsed:
        return {"relevant": False, "reason": "unparseable classifier output"}

    return {"relevant": bool(parsed["relevant"]), "reason": str(parsed.get("reason", "")).strip()}
