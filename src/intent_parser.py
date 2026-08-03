"""
intent_parser.py
Takes user free-text intent -> asks clarifying Qs if needed -> returns mechanism object (dict)
Uses Ollama locally. Prompt lives in prompts/intent_decomposition.txt
Logs every call (input, output, tokens) to data/logs.jsonl for debugging.
"""

from pathlib import Path

from utils import MODEL, call_ollama, is_mechanism_object, try_parse_json

PROMPT_PATH = Path("prompts/intent_decomposition.txt")


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
        model=MODEL,
    )
    if not result["ok"]:
        return {"status": "error", "message": result["error"]}

    output_text = result["text"]
    tokens = result["tokens"]

    mechanism_object = try_parse_json(output_text)

    if is_mechanism_object(mechanism_object):
        return {"status": "complete", "mechanism_object": mechanism_object, "tokens": tokens}
    else:
        # Model asked clarifying questions instead of giving a usable mechanism object
        updated_history = messages[1:] + [{"role": "assistant", "content": output_text}]
        return {
            "status": "needs_clarification",
            "questions": output_text,
            "history": updated_history,
            "tokens": tokens,
        }
