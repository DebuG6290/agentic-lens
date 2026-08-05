"""Local feedback history for improving a saved lens over time."""

import json
import time
from pathlib import Path

FEEDBACK_DIR = Path("data/feedback")


def _path(lens_name: str) -> Path:
    # Reuse lens-name validation without importing private path helpers.
    from lens_store import _path

    return FEEDBACK_DIR / _path(lens_name).name.replace(".json", ".jsonl")


def record_feedback(
    lens_name: str,
    article: dict,
    label: str,
    note: str = "",
) -> dict:
    if label not in {"relevant", "not_relevant"}:
        raise ValueError("feedback label must be relevant or not_relevant")
    entry = {
        "timestamp": time.time(),
        "label": label,
        "note": note.strip(),
        "article": {
            "title": article.get("title", ""),
            "link": article.get("link", ""),
            "reason": article.get("reason", ""),
        },
    }
    path = _path(lens_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def recent_feedback(lens_name: str, limit: int = 5) -> list[dict]:
    path = _path(lens_name)
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries[-limit:]


def latest_feedback_by_link(lens_name: str) -> dict[str, str]:
    """Return the latest saved label for each article link in a lens."""
    path = _path(lens_name)
    if not path.exists():
        return {}
    latest = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        link = entry.get("article", {}).get("link", "")
        label = entry.get("label")
        if link and label in {"relevant", "not_relevant"}:
            latest[link] = label
    return latest
