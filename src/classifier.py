"""
classifier.py
Scores a single article against the mechanism object via Ollama.
Prompt lives in prompts/classification.txt, every call is logged to data/logs.jsonl.
"""

import json
from pathlib import Path

from utils import _try_parse_json, call_ollama

PROMPT_PATH = Path("prompts/classification.txt")


def _empty_verdict(reason: str) -> dict:
    return {
        "relevant": False,
        "confidence": 0.0,
        "mechanism_id": None,
        "evidence": "",
        "impact_chain": "",
        "reason": reason,
    }


def _normalise_confidence(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _normalise_relevance(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalised = value.strip().casefold()
        if normalised in {"true", "yes", "1"}:
            return True
        if normalised in {"false", "no", "0", ""}:
            return False
    return bool(value)


def _parse_verdict(text: str):
    parsed = _try_parse_json(text)
    if not isinstance(parsed, dict) or "relevant" not in parsed:
        return None
    mechanism_id = parsed.get("mechanism_id")
    if mechanism_id is not None:
        mechanism_id = str(mechanism_id).strip() or None
    return {
        "relevant": _normalise_relevance(parsed["relevant"]),
        "confidence": _normalise_confidence(parsed.get("confidence", 0)),
        "mechanism_id": mechanism_id,
        "evidence": str(parsed.get("evidence", "")).strip(),
        "impact_chain": str(parsed.get("impact_chain", "")).strip(),
        "reason": str(parsed.get("reason", "")).strip(),
    }


def classify_article(article: dict, mechanism_object: dict, feedback: list[dict] = None) -> dict:
    system_prompt = PROMPT_PATH.read_text()

    feedback_context = ""
    if feedback:
        examples = [
            {
                "label": item.get("label"),
                "title": item.get("article", {}).get("title", ""),
                "reason": item.get("article", {}).get("reason", ""),
                "note": item.get("note", ""),
            }
            for item in feedback
        ]
        feedback_context = "\n\nPRIOR USER FEEDBACK (use as preference examples):\n" + json.dumps(examples)

    source_type = article.get("source_type", "news")
    source_guidance = (
        "This is a research paper. Distinguish preliminary findings from established facts and use the abstract only."
        if source_type == "paper" else
        "This is a news item. Use the reported event and publication context only."
    )
    user_content = (
        "MECHANISM OBJECT:\n"
        + json.dumps(mechanism_object)
        + "\n\nARTICLE:\n"
        + json.dumps(
            {"title": article.get("title", ""), "summary": article.get("summary", "")}
        )
        + f"\n\nSOURCE TYPE: {source_type}\n{source_guidance}"
        + feedback_context
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
            "source_type": source_type,
        },
    )

    if not result["ok"]:
        return _empty_verdict(f"classification failed: {result['error']}")

    parsed = _parse_verdict(result["text"])
    if parsed is None:
        retry_messages = messages + [{"role": "user", "content": "Return only valid JSON matching the requested schema. Do not include markdown or prose."}]
        retry = call_ollama(
            stage="classification_retry",
            messages=retry_messages,
            input_data={"title": article.get("title", ""), "link": article.get("link", ""), "source_type": source_type},
        )
        if retry["ok"]:
            parsed = _parse_verdict(retry["text"])
    return parsed or _empty_verdict("model did not return valid JSON")
