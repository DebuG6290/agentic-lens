"""
rss_fetcher.py
Takes a mechanism object -> fetches a single RSS feed (v1 scope) -> keeps
articles matching any reasoning-path keyword. Feed responses are cached under
data/rss_cache/ for a daily-digest freshness window.
"""

import hashlib
import json
import time
from pathlib import Path

import feedparser

from utils import _log

# v1: single hardcoded source.
RSS_URL = "https://feeds.bbci.co.uk/news/world/rss.xml"
CACHE_DIR = Path("data/rss_cache")
CACHE_TTL_SECONDS = 6 * 60 * 60  # daily digest: refetch at most a few times a day


def _cache_path(url: str) -> Path:
    return CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest() + ".json")


def _read_cache(url: str):
    path = _cache_path(url)
    if not path.exists():
        return None
    try:
        cached = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - cached.get("fetched_at", 0) > CACHE_TTL_SECONDS:
        return None
    return cached.get("entries")


def _write_cache(url: str, entries: list):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(url).write_text(json.dumps({"fetched_at": time.time(), "entries": entries}))


def _collect_keywords(mechanism_object: dict) -> list:
    keywords = []
    for path in mechanism_object.get("reasoning_paths", []) or []:
        for keyword in path.get("keywords", []) or []:
            keyword = str(keyword).strip()
            if keyword and keyword.lower() not in [k.lower() for k in keywords]:
                keywords.append(keyword)
    return keywords


def _fetch_entries(url: str) -> list:
    feed = feedparser.parse(url)
    return [
        {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", ""),
            "published": entry.get("published", ""),
        }
        for entry in feed.entries
    ]


def fetch_articles(mechanism_object: dict, url: str = RSS_URL) -> list:
    """Returns deduplicated articles matching any keyword of the mechanism object."""
    keywords = _collect_keywords(mechanism_object)

    entries = _read_cache(url)
    from_cache = entries is not None
    if not from_cache:
        entries = _fetch_entries(url)
        _write_cache(url, entries)

    lowered = [k.lower() for k in keywords]
    matched = []
    seen_links = set()
    for entry in entries:
        haystack = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
        if not any(keyword in haystack for keyword in lowered):
            continue
        link = entry.get("link", "")
        if link in seen_links:
            continue
        seen_links.add(link)
        matched.append(entry)

    _log(
        stage="rss_fetch",
        input_data={"url": url, "keywords": keywords, "from_cache": from_cache},
        output_data={"fetched": len(entries), "matched": len(matched)},
        tokens={"prompt": 0, "completion": 0, "total": 0},
    )

    return matched
