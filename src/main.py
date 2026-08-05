"""
main.py
End-to-end v1 pipeline: user intent -> mechanism object -> RSS fetch/filter ->
per-article classification -> daily digest printed to stdout.

Run from the repo root (paths to prompts/ and data/ are relative):
    python src/main.py
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from classifier import classify_article
from feedback_store import recent_feedback, record_feedback
from digest_store import record_digest
from evaluation import evaluate_lens
from intent_parser import parse_intent
from lens_store import list_lenses, load_lens, save_lens
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
            if item.get("impact_chain"):
                lines.append(f"   path: {item['impact_chain']}")
            lines.append(f"   {item['link']}")

    lines.append("")
    return "\n".join(lines)


def run(user_intent: str = "", lens_name: str = "", save_lens_name: str = "", progress_callback=None) -> str:
    feedback = []
    if lens_name:
        try:
            lens = load_lens(lens_name)
        except ValueError as exc:
            return f"Could not load lens: {exc}"
        user_intent = lens["user_intent"]
        mechanism_object = lens["mechanism_object"]
        source_config = lens.get("source_config")
        feedback = recent_feedback(lens_name)
        print(f"Loaded lens: {lens_name}")
    else:
        result = resolve_mechanism(user_intent)

        if result["status"] != "complete":
            return f"Could not build a mechanism object: {result.get('error', result['status'])}"

        mechanism_object = result["mechanism_object"]
        if save_lens_name:
            try:
                save_lens(save_lens_name, user_intent, mechanism_object)
            except ValueError as exc:
                return f"Could not save lens: {exc}"
            print(f"Saved lens: {save_lens_name}")

    paths = mechanism_object.get("mechanisms") or mechanism_object.get("reasoning_paths") or []
    if progress_callback:
        progress_callback("retrieval", "running")
    print(f"\nEntity: {mechanism_object['entity']}")
    print(f"Context: {mechanism_object['user_context']}")
    print(f"Mechanisms: {len(paths)}")

    candidates = fetch_articles(mechanism_object, source_config=source_config if lens_name else None)
    if progress_callback:
        progress_callback("retrieval", "complete", count=len(candidates))
    print(f"Articles sent for relevance analysis: {len(candidates)}")

    relevant = []
    verdicts = []
    for index, article in enumerate(candidates, start=1):
        if progress_callback:
            progress_callback("classification", "running", current=index, total=len(candidates),
                              title=article.get("title", ""))
        verdict = classify_article(article, mechanism_object, feedback=feedback)
        verdicts.append({**article, **verdict})
        if verdict["relevant"]:
            relevant.append({**article, **verdict})

    if lens_name:
        record_digest(lens_name, verdicts)

    if progress_callback:
        progress_callback("complete", "complete", count=len(candidates))

    return render_digest(user_intent, relevant)


def main():
    parser = argparse.ArgumentParser(description="Local personal news intelligence")
    parser.add_argument("intent", nargs="*", help="free-text stake to track")
    parser.add_argument("--lens", help="run a saved lens")
    parser.add_argument("--save-lens", metavar="NAME", help="save this intent as a reusable lens")
    parser.add_argument("--list-lenses", action="store_true", help="list saved lenses")
    parser.add_argument("--feedback-lens", metavar="NAME", help="record feedback for a saved lens")
    parser.add_argument("--feedback-label", choices=["relevant", "not_relevant"])
    parser.add_argument("--feedback-link", metavar="URL")
    parser.add_argument("--feedback-title", default="")
    parser.add_argument("--feedback-note", default="")
    parser.add_argument("--evaluate-lens", metavar="NAME", help="show feedback-based metrics")
    args = parser.parse_args()

    if args.list_lenses:
        for name in list_lenses():
            print(name)
        return

    if args.feedback_lens:
        if not args.feedback_label or not args.feedback_link:
            parser.error("--feedback-lens requires --feedback-label and --feedback-link")
        try:
            record_feedback(
                args.feedback_lens,
                {"title": args.feedback_title, "link": args.feedback_link},
                args.feedback_label,
                args.feedback_note,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(f"Recorded {args.feedback_label} feedback for {args.feedback_lens}")
        return

    if args.evaluate_lens:
        metrics = evaluate_lens(args.evaluate_lens)
        print(json.dumps(metrics, indent=2))
        return

    user_intent = " ".join(args.intent).strip()
    if args.lens and user_intent:
        parser.error("provide either an intent or --lens, not both")
    if not user_intent:
        if args.lens:
            print(run(lens_name=args.lens))
            return
        user_intent = input("What do you want to track? ").strip()
    if not user_intent:
        print("No intent given.")
        return
    print(run(user_intent, save_lens_name=args.save_lens))


if __name__ == "__main__":
    main()
