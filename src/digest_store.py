"""Local digest history for recurring lenses and evaluation."""

import json
import time
from pathlib import Path

from lens_store import _path as lens_path

DIGEST_DIR = Path("data/digests")


def _path(lens_name: str) -> Path:
    return DIGEST_DIR / lens_path(lens_name).name.replace(".json", ".jsonl")


def record_digest(lens_name: str, articles: list[dict]) -> dict:
    entry = {
        "timestamp": time.time(),
        "articles": [
            {
                "title": article.get("title", ""),
                "link": article.get("link", ""),
                "source": article.get("source", ""),
                "source_type": article.get("source_type", ""),
                "published": article.get("published", ""),
                "authors": article.get("authors", []),
                "doi": article.get("doi"),
                "retrieval_score": article.get("_retrieval_score", 0),
                "matched_signals": article.get("_matched_signals", []),
                "relevant": bool(article.get("relevant", False)),
                "confidence": article.get("confidence", 0.0),
                "mechanism_id": article.get("mechanism_id"),
                "evidence": article.get("evidence", ""),
                "impact_chain": article.get("impact_chain", ""),
                "reason": article.get("reason", ""),
            }
            for article in articles
        ],
    }
    path = _path(lens_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def digest_history(lens_name: str) -> list[dict]:
    path = _path(lens_name)
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries
