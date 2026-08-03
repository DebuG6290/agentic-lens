import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(REPO_ROOT / "src"))

import rss_fetcher
import utils

MECHANISM = {
    "entity": "Trump",
    "user_context": "hospital business",
    "reasoning_paths": [
        {"path": "healthcare policy", "keywords": ["Medicaid", "hospital"]},
        {"path": "labour costs", "keywords": ["hospital", "nurse pay"]},
    ],
}

ENTRIES = [
    {"title": "Medicaid cuts loom", "link": "https://x/1", "summary": "", "published": "mon"},
    {"title": "Same story", "link": "https://x/1", "summary": "hospital", "published": "mon"},
    {"title": "Nurse pay deal", "link": "https://x/2", "summary": "NURSE PAY rise", "published": "mon"},
    {"title": "Sports roundup", "link": "https://x/3", "summary": "football", "published": "mon"},
]


@pytest.fixture(autouse=True)
def isolate_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(utils, "LOG_PATH", tmp_path / "logs.jsonl")
    monkeypatch.setattr(rss_fetcher, "CACHE_DIR", tmp_path / "rss_cache")


def test_collect_keywords_dedupes_across_paths():
    assert rss_fetcher._collect_keywords(MECHANISM) == ["Medicaid", "hospital", "nurse pay"]


def test_filters_and_dedupes_by_link(monkeypatch):
    monkeypatch.setattr(rss_fetcher, "_fetch_entries", lambda url: list(ENTRIES))

    articles = rss_fetcher.fetch_articles(MECHANISM)

    assert [a["link"] for a in articles] == ["https://x/1", "https://x/2"]


def test_cache_is_reused_within_ttl(monkeypatch):
    calls = []

    def fetch(url):
        calls.append(url)
        return list(ENTRIES)

    monkeypatch.setattr(rss_fetcher, "_fetch_entries", fetch)

    rss_fetcher.fetch_articles(MECHANISM)
    rss_fetcher.fetch_articles(MECHANISM)

    assert len(calls) == 1


def test_stale_cache_triggers_refetch(monkeypatch):
    calls = []

    def fetch(url):
        calls.append(url)
        return list(ENTRIES)

    monkeypatch.setattr(rss_fetcher, "_fetch_entries", fetch)

    rss_fetcher.fetch_articles(MECHANISM)
    monkeypatch.setattr(rss_fetcher, "CACHE_TTL_SECONDS", 0)
    rss_fetcher.fetch_articles(MECHANISM)

    assert len(calls) == 2
