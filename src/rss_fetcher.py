"""
rss_fetcher.py
Takes a mechanism object -> fetches a single RSS feed -> keeps articles matching any keyword.
Feed payloads are cached under data/rss_cache/ with a freshness window so a daily digest
doesn't hammer the source or reprocess stale articles.
"""

import hashlib
import json
import time
from pathlib import Path

import feedparser

from utils import log

# v1 scope: a single hardcoded RSS source.
RSS_URL = "https://feeds.bbci.co.uk/news/world/rss.xml"
CACHE_DIR = Path("data/rss_cache")
CACHE_TTL_SECONDS = 6 * 60 * 60


def _cache_path(url: str) -> Path:
    return CACHE_DIR / f"{hashlib.sha256(url.encode()).hexdigest()[:16]}.json"


def collect_keywords(mechanism_object: dict) -> list:
    """Flattens keywords across every reasoning path, preserving order and dropping dupes."""
    keywords = []
    for path in mechanism_object.get("reasoning_paths") or []:
        if not isinstance(path, dict):
            continue
        for keyword in path.get("keywords") or []:
            if not isinstance(keyword, str):
                continue
            keyword = keyword.strip()
            if keyword and keyword.lower() not in [k.lower() for k in keywords]:
                keywords.append(keyword)
    return keywords


def _read_cache(url: str, ttl_seconds: int):
    path = _cache_path(url)
    if not path.exists():
        return None
    try:
        cached = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - cached.get("fetched_at", 0) > ttl_seconds:
        return None
    return cached.get("entries")


def _write_cache(url: str, entries: list):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"url": url, "fetched_at": time.time(), "entries": entries}
    _cache_path(url).write_text(json.dumps(payload))


def _fetch_entries(url: str) -> list:
    feed = feedparser.parse(url)
    entries = []
    for entry in feed.entries:
        entries.append(
            {
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
            }
        )
    return entries


def _matches(article: dict, keywords: list) -> bool:
    haystack = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def fetch_articles(
    mechanism_object: dict,
    url: str = RSS_URL,
    ttl_seconds: int = CACHE_TTL_SECONDS,
) -> list:
    """Fetches the feed (cache-first) and returns keyword-matching articles, deduped by link."""
    keywords = collect_keywords(mechanism_object)

    entries = _read_cache(url, ttl_seconds)
    cache_hit = entries is not None
    if not cache_hit:
        entries = _fetch_entries(url)
        _write_cache(url, entries)

    matched = []
    seen_links = set()
    for article in entries:
        if not _matches(article, keywords):
            continue
        link = article.get("link", "")
        if link and link in seen_links:
            continue
        seen_links.add(link)
        matched.append(article)

    log(
        stage="rss_fetch",
        input_data={"url": url, "keywords": keywords, "cache_hit": cache_hit},
        output_data={"fetched": len(entries), "matched": len(matched)},
        tokens={"prompt": 0, "completion": 0, "total": 0},
    )
    return matched
