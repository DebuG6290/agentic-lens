"""
intent_parser.py
Takes user free-text intent -> asks clarifying Qs if needed -> returns mechanism object (dict)
Uses Ollama locally. Prompt lives in prompts/intent_decomposition.txt
Logs every call (input, output, tokens) to data/logs.jsonl for debugging.
"""

from pathlib import Path

from utils import _try_parse_json, call_ollama

PROMPT_PATH = Path("prompts/intent_decomposition.txt")
MECHANISM_KEYS = ("entity", "user_context", "reasoning_paths")


def _is_mechanism_object(candidate) -> bool:
    if not isinstance(candidate, dict):
        return False
    if not all(key in candidate for key in MECHANISM_KEYS):
        return False
    return isinstance(candidate["reasoning_paths"], list) and bool(candidate["reasoning_paths"])


def parse_intent(user_input: str, conversation_history: list = None) -> dict:
    system_prompt = PROMPT_PATH.read_text()
    conversation_history = conversation_history or []

    messages = [{"role": "system", "content": system_prompt}]
    messages += conversation_history
    messages.append({"role": "user", "content": user_input})

    result = call_ollama(
        stage="intent_decomposition",
        messages=messages,
        input_data={"user_input": user_input, "history_len": len(conversation_history)},
    )

    if not result["ok"]:
        return {"status": "error", "error": result["error"], "tokens": result["tokens"]}

    output_text = result["text"]
    tokens = result["tokens"]

    parsed = _try_parse_json(output_text)

    if _is_mechanism_object(parsed):
        return {"status": "complete", "mechanism_object": parsed, "tokens": tokens}

    # Model asked clarifying questions instead of giving a full mechanism object
    updated_history = messages[1:] + [{"role": "assistant", "content": output_text}]
    return {
        "status": "needs_clarification",
        "questions": output_text,
        "history": updated_history,
        "tokens": tokens,
    }
