"""
main.py
v1 orchestrator: user intent -> mechanism object -> RSS fetch/filter -> classify -> daily digest.
Run from the repo root: python src/main.py "Trump affects my hospital business"
"""

import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from classifier import classify_article
from intent_parser import parse_intent
from rss_fetcher import fetch_articles


def render_digest(mechanism_object: dict, results: list) -> str:
    lines = [
        f"Daily digest - {date.today().isoformat()}",
        f"Entity: {mechanism_object.get('entity')}",
        f"Context: {mechanism_object.get('user_context')}",
        "",
    ]
    relevant = [r for r in results if r["classification"]["relevant"]]
    if not relevant:
        lines.append("No relevant articles today.")
        return "\n".join(lines)

    for item in relevant:
        article = item["article"]
        lines.append(f"- {article['title']}")
        lines.append(f"  {article['link']}")
        lines.append(f"  why: {item['classification']['reason']}")
        lines.append("")
    return "\n".join(lines)


def run(user_intent: str, conversation_history: list = None) -> dict:
    """Runs the pipeline once. Returns the parse result plus a digest when complete."""
    parsed = parse_intent(user_intent, conversation_history=conversation_history)

    if parsed["status"] != "complete":
        return parsed

    mechanism_object = parsed["mechanism_object"]
    articles = fetch_articles(mechanism_object)

    results = []
    for article in articles:
        results.append(
            {"article": article, "classification": classify_article(article, mechanism_object)}
        )

    return {
        "status": "complete",
        "mechanism_object": mechanism_object,
        "results": results,
        "digest": render_digest(mechanism_object, results),
    }


def main():
    user_intent = " ".join(sys.argv[1:]).strip()
    if not user_intent:
        user_intent = input("What do you want to track? ")

    outcome = run(user_intent)

    if outcome["status"] == "error":
        print("ERROR:", outcome["message"])
        return
    if outcome["status"] == "needs_clarification":
        print("The model needs more detail:\n")
        print(outcome["questions"])
        return

    print(outcome["digest"])


if __name__ == "__main__":
    main()
