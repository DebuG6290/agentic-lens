"""
utils.py
Shared helpers: JSONL logging, tolerant JSON parsing, Ollama call wrapper.
Used by intent_parser.py and classifier.py so the logic isn't duplicated.
"""

import json
import time
from pathlib import Path

import ollama

LOG_PATH = Path("data/logs.jsonl")
MODEL = "llama3.2:latest"


def log(stage: str, input_data: dict, output_data: dict, tokens: dict):
    entry = {
        "timestamp": time.time(),
        "stage": stage,
        "input": input_data,
        "output": output_data,
        "tokens": tokens,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def strip_fences(text: str) -> str:
    """Removes surrounding markdown code fences and an optional language tag."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
        newline = cleaned.find("\n")
        first_line = cleaned[:newline] if newline != -1 else cleaned
        if first_line.strip().isalpha():
            cleaned = cleaned[newline + 1:] if newline != -1 else ""
        cleaned = cleaned.strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    return cleaned


def try_parse_json(text: str):
    """Parses JSON out of a model response, tolerating fences and stray prose.

    Returns the parsed value, or None if nothing parseable is found.
    """
    if not text:
        return None

    cleaned = strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None


def is_mechanism_object(candidate) -> bool:
    """True when the parsed result is a dict carrying every required key."""
    required = ("entity", "user_context", "reasoning_paths")
    return isinstance(candidate, dict) and all(key in candidate for key in required)


def call_ollama(stage: str, messages: list, input_data: dict, model: str = MODEL) -> dict:
    """Calls Ollama and logs the result.

    Returns {"ok": True, "text": str, "tokens": dict} on success, or
    {"ok": False, "error": str} when the model or server is unreachable.
    """
    try:
        response = ollama.chat(model=model, messages=messages)
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        log(
            stage=stage,
            input_data=input_data,
            output_data={"error": message},
            tokens={"prompt": 0, "completion": 0, "total": 0},
        )
        return {"ok": False, "error": message}

    text = response["message"]["content"]
    tokens = {
        "prompt": response.get("prompt_eval_count", 0),
        "completion": response.get("eval_count", 0),
    }
    tokens["total"] = tokens["prompt"] + tokens["completion"]

    log(
        stage=stage,
        input_data=input_data,
        output_data={"raw_output": text},
        tokens=tokens,
    )
    return {"ok": True, "text": text, "tokens": tokens}
