"""Small JSON-backed store for reusable personal Lens configurations."""

import json
import re
from pathlib import Path

LENS_DIR = Path("data/lenses")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
DEFAULT_SOURCE_CONFIG = {
    "rss_urls": ["https://feeds.bbci.co.uk/news/world/rss.xml"],
    "openalex": {"enabled": True, "lookback_days": 30, "max_results": 10},
    "pubmed": {"enabled": False, "lookback_days": 30, "max_results": 10},
    "crossref": {"enabled": False, "lookback_days": 30, "max_results": 10},
    "min_retrieval_score": 1,
    "max_candidates": 15,
    "max_candidates_by_type": {"news": 10, "paper": 10},
}


def validate_lens_name(name: str) -> None:
    """Raise a friendly error without doing any model or filesystem work."""
    if not isinstance(name, str) or not _SAFE_NAME.fullmatch(name):
        raise ValueError("lens name must be 1-64 characters: letters, numbers, _ or -")


def _path(name: str) -> Path:
    validate_lens_name(name)
    return LENS_DIR / f"{name}.json"


def save_lens(name: str, user_intent: str, mechanism_object: dict, source_config: dict = None, tuning_history: list = None) -> dict:
    """Persist a resolved intent and its mechanism object."""
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    lens = {
        "name": name,
        "user_intent": user_intent,
        "mechanism_object": mechanism_object,
        "source_config": source_config or DEFAULT_SOURCE_CONFIG,
    }
    if tuning_history is not None:
        lens["tuning_history"] = tuning_history
    path.write_text(json.dumps(lens, indent=2) + "\n")
    return lens


def load_lens(name: str) -> dict:
    path = _path(name)
    try:
        lens = json.loads(path.read_text())
        lens.setdefault("source_config", DEFAULT_SOURCE_CONFIG)
        return lens
    except FileNotFoundError:
        raise ValueError(f"lens not found: {name}") from None
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"could not read lens '{name}': {exc}") from exc


def list_lenses() -> list[str]:
    if not LENS_DIR.exists():
        return []
    return sorted(path.stem for path in LENS_DIR.glob("*.json"))
