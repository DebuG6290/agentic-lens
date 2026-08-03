"""
intent_parser.py
Takes user free-text intent -> asks clarifying Qs if needed -> returns mechanism object (dict)
Uses Ollama locally. Prompt lives in prompts/intent_decomposition.txt
Logs every call (input, output, tokens) to data/logs.jsonl for debugging.
"""

import json
import time
from pathlib import Path
import ollama

LOG_PATH = Path("data/logs.jsonl")
MODEL = "llama3.2:latest"
PROMPT_PATH = Path("prompts/intent_decomposition.txt")


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
    """Returns dict if text is valid JSON, else None."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_intent(user_input: str, conversation_history: list = None) -> dict:
    system_prompt = PROMPT_PATH.read_text()
    conversation_history = conversation_history or []

    messages = [{"role": "system", "content": system_prompt}]
    messages += conversation_history
    messages.append({"role": "user", "content": user_input})

    response = ollama.chat(model=MODEL, messages=messages)

    output_text = response["message"]["content"]
    tokens = {
        "prompt": response.get("prompt_eval_count", 0),
        "completion": response.get("eval_count", 0),
    }
    tokens["total"] = tokens["prompt"] + tokens["completion"]

    _log(
        stage="intent_decomposition",
        input_data={"user_input": user_input, "history_len": len(conversation_history)},
        output_data={"raw_output": output_text},
        tokens=tokens,
    )

    mechanism_object = _try_parse_json(output_text)

    if mechanism_object:
        return {"status": "complete", "mechanism_object": mechanism_object, "tokens": tokens}
    else:
        # Model asked clarifying questions instead of giving JSON
        updated_history = messages[1:] + [{"role": "assistant", "content": output_text}]
        return {"status": "needs_clarification", "questions": output_text, "history": updated_history, "tokens": tokens}