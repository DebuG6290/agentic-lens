"""Simple feedback-based metrics for a saved lens."""

from collections import Counter

from digest_store import digest_history
from feedback_store import recent_feedback


def evaluate_lens(lens_name: str) -> dict:
    feedback = recent_feedback(lens_name, limit=10000)
    labels = {
        item.get("article", {}).get("link"): item.get("label")
        for item in feedback
        if item.get("article", {}).get("link")
    }
    predictions = {}
    for digest in digest_history(lens_name):
        for article in digest.get("articles", []):
            link = article.get("link")
            if link in labels:
                predictions[link] = bool(article.get("relevant", False))

    counts = Counter()
    for link, label in labels.items():
        if link not in predictions:
            continue
        expected = label == "relevant"
        actual = predictions[link]
        counts["labeled"] += 1
        if actual and expected:
            counts["true_positive"] += 1
        elif actual and not expected:
            counts["false_positive"] += 1
        elif not actual and expected:
            counts["false_negative"] += 1
        else:
            counts["true_negative"] += 1

    tp = counts["true_positive"]
    fp = counts["false_positive"]
    fn = counts["false_negative"]
    return {
        **counts,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
    }
