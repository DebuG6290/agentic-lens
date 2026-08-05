"""
intent_parser.py
Takes user free-text intent -> asks clarifying Qs if needed -> returns mechanism object (dict)
Uses Ollama locally. Prompt lives in prompts/intent_decomposition.txt
Logs every call (input, output, tokens) to data/logs.jsonl for debugging.
"""

from pathlib import Path

from mechanism import is_mechanism_object
from utils import _try_parse_json, call_ollama

PROMPT_PATH = Path("prompts/intent_decomposition.txt")


def _normalise_questions(parsed):
    """Return safe MCQ question data while tolerating older model formats."""
    if not isinstance(parsed, dict) or not isinstance(parsed.get("questions"), list):
        return None
    questions = []
    for index, item in enumerate(parsed["questions"][:3], start=1):
        if isinstance(item, str):
            questions.append({"id": f"question_{index}", "question": item.strip(), "options": [], "allow_custom": True})
            continue
        if not isinstance(item, dict) or not str(item.get("question", "")).strip():
            continue
        options = []
        for option in item.get("options", [])[:4]:
            if isinstance(option, str):
                options.append({"value": option.strip(), "label": option.strip()})
            elif isinstance(option, dict) and str(option.get("label", "")).strip():
                options.append({
                    "value": str(option.get("value", option["label"])).strip(),
                    "label": str(option["label"]).strip(),
                })
        questions.append({
            "id": str(item.get("id", f"question_{index}")).strip() or f"question_{index}",
            "question": str(item["question"]).strip(),
            "options": options,
            "allow_custom": bool(item.get("allow_custom", True)),
        })
    return questions or None


def _clarification_result(parsed, output_text, messages, tokens):
    questions = _normalise_questions(parsed)
    if questions:
        return {
            "status": "needs_clarification",
            "questions": questions,
            "history": messages[1:] + [{"role": "assistant", "content": output_text}],
            "tokens": tokens,
        }
    return None


def _initial_questions(user_input: str):
    """Catch obviously underspecified intents before asking the model to guess."""
    words = [word for word in user_input.strip().split() if word]
    if len(words) > 3:
        return None
    subject = " ".join(words[1:]) if len(words) > 1 else "this topic"
    return [
        {
            "id": "scope",
            "question": f"What part of {subject} should Lens track?",
            "options": [
                {"value": "policy_regulation", "label": "Government policy and regulation"},
                {"value": "business_market", "label": "Business and market impact"},
                {"value": "research_technology", "label": "Research and technology developments"},
            ],
            "allow_custom": True,
        },
        {
            "id": "impact",
            "question": "What kind of impact matters most to you?",
            "options": [
                {"value": "costs", "label": "Costs and profitability"},
                {"value": "risk", "label": "Risks and compliance"},
                {"value": "opportunity", "label": "Opportunities and growth"},
            ],
            "allow_custom": True,
        },
        {
            "id": "horizon",
            "question": "What time horizon should the lens use?",
            "options": [
                {"value": "now", "label": "Current developments"},
                {"value": "next_year", "label": "The next 12 months"},
                {"value": "long_term", "label": "Long-term structural change"},
            ],
            "allow_custom": False,
        },
    ]


def parse_intent(user_input: str, conversation_history: list = None, progress_callback=None) -> dict:
    system_prompt = PROMPT_PATH.read_text()
    conversation_history = conversation_history or []

    if not conversation_history:
        initial_questions = _initial_questions(user_input)
        if initial_questions:
            return {
                "status": "needs_clarification",
                "questions": initial_questions,
                "history": [{"role": "user", "content": user_input}],
                "tokens": {"prompt": 0, "completion": 0, "total": 0},
            }

    messages = [{"role": "system", "content": system_prompt}]
    messages += conversation_history
    messages.append({"role": "user", "content": user_input})

    result = call_ollama(
        stage="intent_decomposition",
        messages=messages,
        input_data={"user_input": user_input, "history_len": len(conversation_history)},
        progress_callback=progress_callback,
    )

    if not result["ok"]:
        return {"status": "error", "error": result["error"], "tokens": result["tokens"]}

    output_text = result["text"]
    tokens = result["tokens"]

    parsed = _try_parse_json(output_text)

    if is_mechanism_object(parsed):
        return {"status": "complete", "mechanism_object": parsed, "tokens": tokens}
    clarification = _clarification_result(parsed, output_text, messages, tokens)
    if clarification:
        return clarification

    # A local model will occasionally return JSON-shaped output with a small
    # syntax error (for example, a missing closing bracket). Give it one
    # constrained repair attempt before treating the response as a question.
    stripped = output_text.strip()
    if stripped.startswith("{") or stripped.startswith("```"):
        repair_messages = messages + [{
            "role": "user",
            "content": (
                "Your previous response was intended to be a mechanism object but was not valid JSON. "
                "Repair it and return only valid JSON matching the requested schema. "
                "Do not add prose or markdown."
            ),
        }]
        retry = call_ollama(
            stage="intent_decomposition_retry",
            messages=repair_messages,
            input_data={"user_input": user_input, "history_len": len(conversation_history)},
            progress_callback=progress_callback,
        )
        if retry["ok"]:
            repaired = _try_parse_json(retry["text"])
            if is_mechanism_object(repaired):
                return {"status": "complete", "mechanism_object": repaired, "tokens": retry["tokens"]}
            clarification = _clarification_result(repaired, retry["text"], messages, retry["tokens"])
            if clarification:
                return clarification

    # Model asked clarifying questions instead of giving a full mechanism object
    updated_history = messages[1:] + [{"role": "assistant", "content": output_text}]
    return {
        "status": "needs_clarification",
        "questions": output_text,
        "history": updated_history,
        "tokens": tokens,
    }
