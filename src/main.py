"""
main.py
End-to-end v1 pipeline: user intent -> mechanism object -> RSS fetch/filter ->
per-article classification -> daily digest printed to stdout.

Run from the repo root (paths to prompts/ and data/ are relative):
    python src/main.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from classifier import classify_article
from intent_parser import parse_intent
from rss_fetcher import fetch_articles


def resolve_mechanism(user_intent: str) -> dict:
    """Runs the clarification loop until a complete mechanism object or an error."""
    result = parse_intent(user_intent)

    while result["status"] == "needs_clarification":
        print("\nI need a bit more detail:\n")
        print(result["questions"])
        answer = input("\nYour answer: ").strip()
        if not answer:
            return {"status": "error", "error": "no answer provided"}
        result = parse_intent(answer, conversation_history=result["history"])

    return result


def render_digest(user_intent: str, articles: list) -> str:
    lines = ["", "=" * 60, f"DAILY DIGEST - {user_intent}", "=" * 60]

    if not articles:
        lines.append("\nNothing relevant today.")
    else:
        for i, item in enumerate(articles, start=1):
            lines.append(f"\n{i}. {item['title']}")
            lines.append(f"   why: {item['reason']}")
            lines.append(f"   {item['link']}")

    lines.append("")
    return "\n".join(lines)


def run(user_intent: str) -> str:
    result = resolve_mechanism(user_intent)

    if result["status"] != "complete":
        return f"Could not build a mechanism object: {result.get('error', result['status'])}"

    mechanism_object = result["mechanism_object"]
    print(f"\nEntity: {mechanism_object['entity']}")
    print(f"Context: {mechanism_object['user_context']}")
    print(f"Reasoning paths: {len(mechanism_object['reasoning_paths'])}")

    candidates = fetch_articles(mechanism_object)
    print(f"Keyword-matched articles: {len(candidates)}")

    relevant = []
    for article in candidates:
        verdict = classify_article(article, mechanism_object)
        if verdict["relevant"]:
            relevant.append({**article, "reason": verdict["reason"]})

    return render_digest(user_intent, relevant)


def main():
    user_intent = " ".join(sys.argv[1:]).strip()
    if not user_intent:
        user_intent = input("What do you want to track? ").strip()
    if not user_intent:
        print("No intent given.")
        return
    print(run(user_intent))


if __name__ == "__main__":
    main()
