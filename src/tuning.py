"""Explainable, feedback-based tuning suggestions for saved lenses."""

import copy
import time
from collections import Counter

from digest_store import digest_history
from feedback_store import latest_feedback_by_link
from lens_store import load_lens, save_lens


def _mechanisms(mechanism_object: dict) -> list[dict]:
    return mechanism_object.get("mechanisms") or mechanism_object.get("reasoning_paths") or []


def _all_terms(mechanism_object: dict, field: str) -> set[str]:
    terms = set()
    for mechanism in _mechanisms(mechanism_object):
        fallback = mechanism.get("keywords", []) if field == "signals" else []
        for term in mechanism.get(field, fallback) or []:
            terms.add(str(term).strip().casefold())
    return terms


def _suggestion_id(action: str, term: str) -> str:
    return f"{action}:{term.casefold()}"


def build_tuning_report(lens_name: str, minimum_count: int = 2) -> dict:
    """Summarise labeled digest items and return deterministic suggestions."""
    lens = load_lens(lens_name)
    labels = latest_feedback_by_link(lens_name)
    labeled = []
    for digest in digest_history(lens_name):
        for article in digest.get("articles", []):
            link = article.get("link")
            if link in labels:
                labeled.append({**article, "feedback_label": labels[link]})

    relevant = [item for item in labeled if item["feedback_label"] == "relevant"]
    not_relevant = [item for item in labeled if item["feedback_label"] == "not_relevant"]
    current_signals = _all_terms(lens["mechanism_object"], "signals")
    current_exclusions = _all_terms(lens["mechanism_object"], "exclusions")

    def counts(items):
        result = {}
        mechanism_ids = {}
        for item in items:
            values = item.get("matched_signals") or item.get("_matched_signals") or []
            for value in values:
                key = str(value).strip()
                if key:
                    result[key] = result.get(key, 0) + 1
                    mechanism_ids.setdefault(key, []).append(item.get("mechanism_id"))
        return result, mechanism_ids

    relevant_counts, relevant_mechanisms = counts(relevant)
    excluded_counts, excluded_mechanisms = counts(not_relevant)
    suggestions = []
    for term, count in sorted(relevant_counts.items(), key=lambda pair: (-pair[1], pair[0].casefold())):
        if count >= minimum_count and term.casefold() not in current_signals:
            suggestions.append({
                "id": _suggestion_id("add_signal", term),
                "action": "add_signal",
                "term": term,
                "count": count,
                "mechanism_id": next((value for value, _ in Counter(relevant_mechanisms.get(term, [])).most_common() if value), None),
                "explanation": f"This signal appeared on {count} articles you marked relevant.",
            })
    for term, count in sorted(excluded_counts.items(), key=lambda pair: (-pair[1], pair[0].casefold())):
        if count >= minimum_count and term.casefold() not in current_exclusions:
            suggestions.append({
                "id": _suggestion_id("add_exclusion", term),
                "action": "add_exclusion",
                "term": term,
                "count": count,
                "mechanism_id": next((value for value, _ in Counter(excluded_mechanisms.get(term, [])).most_common() if value), None),
                "explanation": f"This signal appeared on {count} articles you marked not relevant.",
            })

    return {
        "labeled": len(labeled),
        "relevant": len(relevant),
        "not_relevant": len(not_relevant),
        "suggestions": suggestions,
    }


def apply_tuning_suggestion(lens_name: str, suggestion: dict) -> dict:
    """Apply one approved suggestion and append an auditable history record."""
    lens = load_lens(lens_name)
    action = suggestion.get("action")
    term = str(suggestion.get("term", "")).strip()
    if action not in {"add_signal", "add_exclusion"} or not term:
        raise ValueError("invalid tuning suggestion")

    mechanism_object = copy.deepcopy(lens["mechanism_object"])
    mechanisms = _mechanisms(mechanism_object)
    if not mechanisms:
        raise ValueError("lens has no mechanisms to tune")
    field = "signals" if action == "add_signal" else "exclusions"
    mechanism_id = suggestion.get("mechanism_id")
    target = next((item for item in mechanisms if mechanism_id and item.get("id") == mechanism_id), mechanisms[0])
    target.setdefault(field, [])
    if any(str(existing).casefold() == term.casefold() for existing in target[field]):
        raise ValueError(f"{term} is already in {field}")
    target[field].append(term)

    history = list(lens.get("tuning_history", []))
    history.append({
        "timestamp": time.time(),
        "action": action,
        "term": term,
        "suggestion_id": suggestion.get("id", _suggestion_id(action, term)),
    })
    return save_lens(
        lens_name,
        lens["user_intent"],
        mechanism_object,
        lens.get("source_config"),
        tuning_history=history,
    )
