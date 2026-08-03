"""
utils.py
Shared helpers for the pipeline: JSONL logging, lenient JSON parsing and a
guarded Ollama call wrapper. Kept raw/framework-free on purpose.
"""

import json
import time
from pathlib import Path
import ollama

LOG_PATH = Path("data/logs.jsonl")
MODEL = "llama3.2:latest"


def _log(stage: str, input_data: dict, output_data: dict, tokens: dict):
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


def _try_parse_json(text: str):
    """Returns dict if text contains JSON (fences tolerated), else None."""
    if not text:
        return None

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None

    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


def call_ollama(stage: str, messages: list, input_data: dict) -> dict:
    """
    Calls Ollama and returns {"ok": True, "text": str, "tokens": dict} or
    {"ok": False, "error": str, "tokens": dict} when the model/server is
    unreachable. Every call (success or failure) is logged.
    """
    zero_tokens = {"prompt": 0, "completion": 0, "total": 0}

    try:
        response = ollama.chat(model=MODEL, messages=messages)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        _log(
            stage=stage,
            input_data=input_data,
            output_data={"error": error},
            tokens=zero_tokens,
        )
        return {"ok": False, "error": error, "tokens": zero_tokens}

    text = response["message"]["content"]
    tokens = {
        "prompt": response.get("prompt_eval_count", 0),
        "completion": response.get("eval_count", 0),
    }
    tokens["total"] = tokens["prompt"] + tokens["completion"]

    _log(
        stage=stage,
        input_data=input_data,
        output_data={"raw_output": text},
        tokens=tokens,
    )

    return {"ok": True, "text": text, "tokens": tokens}
