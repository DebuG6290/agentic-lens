"""
rss_fetcher.py
Fetches and lightly ranks RSS candidates for mechanism-based classification.
Signals are useful for ordering and diagnostics, but do not filter articles
out before the classifier sees them.
"""

import hashlib
import json
import time
from pathlib import Path

import feedparser

from mechanism import mechanism_signals
from source_ingestion import fetch_crossref, fetch_openalex, fetch_pubmed
from utils import _log

# v1: single hardcoded source.
RSS_URL = "https://feeds.bbci.co.uk/news/world/rss.xml"
CACHE_DIR = Path("data/rss_cache")
CACHE_TTL_SECONDS = 6 * 60 * 60  # daily digest: refetch at most a few times a day
DEFAULT_SOURCE_CONFIG = {
    "rss_urls": [RSS_URL],
    "openalex": {"enabled": False, "lookback_days": 30, "max_results": 10},
    "pubmed": {"enabled": False, "lookback_days": 30, "max_results": 10},
    "crossref": {"enabled": False, "lookback_days": 30, "max_results": 10},
    "min_retrieval_score": 1,
    "max_candidates": 15,
    "max_candidates_by_type": {"news": 10, "paper": 10},
}


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
    return mechanism_signals(mechanism_object)


def _fetch_entries(url: str) -> list:
    feed = feedparser.parse(url)
    return [
        {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", ""),
            "published": entry.get("published", ""),
            "source": url,
            "source_type": "news",
        }
        for entry in feed.entries
    ]


def _rank_entry(entry: dict, mechanism_object: dict) -> tuple[int, list[str]]:
    """Return a cheap lexical score and the signals found in an entry."""
    signals = mechanism_signals(mechanism_object)
    haystack = (entry.get("title", "") + " " + entry.get("summary", "")).casefold()
    matched_signals = [signal for signal in signals if signal.casefold() in haystack]
    entity = str(mechanism_object.get("entity", ""))
    context = str(mechanism_object.get("user_context", ""))
    generic_matches = sum(
        term.casefold() in haystack
        for term in (entity, *context.split())
        if term.strip()
    )
    return generic_matches + (2 * len(matched_signals)), matched_signals


def fetch_articles(mechanism_object: dict, url: str = RSS_URL, source_config: dict = None) -> list:
    """Return deduplicated, ranked entries from configured news and paper sources."""
    signals = _collect_keywords(mechanism_object)
    config = {**DEFAULT_SOURCE_CONFIG, **(source_config or {})}
    rss_urls = config.get("rss_urls") or []
    if source_config is None:
        rss_urls = [url]

    entries = []
    cache_states = {}
    for rss_url in rss_urls:
        cached = _read_cache(rss_url)
        from_cache = cached is not None
        if not from_cache:
            cached = _fetch_entries(rss_url)
            _write_cache(rss_url, cached)
        cache_states[rss_url] = from_cache
        entries.extend(cached)

    paper_sources = {
        "openalex": fetch_openalex,
        "pubmed": fetch_pubmed,
        "crossref": fetch_crossref,
    }
    for source_name, fetcher in paper_sources.items():
        paper_config = config.get(source_name) or {}
        if not paper_config.get("enabled"):
            continue
        query = " ".join([str(mechanism_object.get("entity", "")), str(mechanism_object.get("user_context", "")), *signals])
        try:
            entries.extend(fetcher(
                query=query,
                lookback_days=paper_config.get("lookback_days", 30),
                max_results=paper_config.get("max_results", 10),
            ))
        except Exception as exc:
            _log(
                stage=f"{source_name}_fetch",
                input_data={"query": query, "lookback_days": paper_config.get("lookback_days", 30)},
                output_data={"error": f"{type(exc).__name__}: {exc}"},
                tokens={"prompt": 0, "completion": 0, "total": 0},
            )

    matched = []
    seen_links = set()
    for entry in entries:
        link = entry.get("link", "")
        dedupe_key = link or entry.get("title", "").casefold()
        if dedupe_key in seen_links:
            continue
        seen_links.add(dedupe_key)
        score, matched_signals = _rank_entry(entry, mechanism_object)
        matched.append({**entry, "_retrieval_score": score, "_matched_signals": matched_signals})

    matched.sort(key=lambda entry: entry["_retrieval_score"], reverse=True)
    deduped_count = len(matched)
    filtered = []
    type_counts = {}
    min_score = float(config.get("min_retrieval_score", 0))
    per_type_limits = config.get("max_candidates_by_type") or {}
    for entry in matched:
        source_type = entry.get("source_type", "news")
        if source_config is not None and entry["_retrieval_score"] < min_score:
            continue
        if source_config is not None and type_counts.get(source_type, 0) >= int(per_type_limits.get(source_type, config.get("max_candidates", 15))):
            continue
        type_counts[source_type] = type_counts.get(source_type, 0) + 1
        filtered.append(entry)
        if source_config is not None and len(filtered) >= int(config.get("max_candidates", 15)):
            break
    if source_config is None:
        filtered = matched

    _log(
        stage="ingestion",
        input_data={"rss_urls": rss_urls, "paper_sources": {name: config.get(name) for name in paper_sources}, "signals": signals, "cache": cache_states},
        output_data={"fetched": len(entries), "deduped": deduped_count, "candidates": len(filtered), "filtered_out": len(entries) - len(filtered), "by_type": type_counts},
        tokens={"prompt": 0, "completion": 0, "total": 0},
    )

    return filtered
