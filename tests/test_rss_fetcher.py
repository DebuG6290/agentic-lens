import json
import time

import pytest

import rss_fetcher

MECHANISM = {
    "entity": "Trump",
    "user_context": "hospital business",
    "reasoning_paths": [
        {"path": "healthcare policy", "keywords": ["Medicaid", "hospital"]},
        {"path": "trade policy", "keywords": ["tariff", "Hospital"]},
    ],
}

ENTRIES = [
    {"title": "Medicaid cuts loom", "link": "a", "summary": "", "published": "d1"},
    {"title": "Hospital funding bill", "link": "a", "summary": "", "published": "d1"},
    {"title": "New tariff round", "link": "b", "summary": "on steel", "published": "d2"},
    {"title": "Football results", "link": "c", "summary": "goals", "published": "d3"},
]


@pytest.fixture(autouse=True)
def temp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(rss_fetcher, "CACHE_DIR", tmp_path / "rss_cache")


@pytest.fixture
def feed(monkeypatch):
    fetches = []

    def _fetch(url):
        fetches.append(url)
        return ENTRIES

    monkeypatch.setattr(rss_fetcher, "_fetch_entries", _fetch)
    return fetches


def test_collect_keywords_dedupes_across_paths():
    assert rss_fetcher._collect_keywords(MECHANISM) == ["Medicaid", "hospital", "tariff"]


def test_filters_and_dedupes_articles_by_link(feed):
    articles = rss_fetcher.fetch_articles(MECHANISM)
    assert {article["link"] for article in articles} == {"a", "b", "c"}


def test_does_not_drop_articles_without_signal_match(feed, monkeypatch):
    entries = ENTRIES + [
        {"title": "Unexpected supply chain disruption", "link": "d", "summary": "", "published": "d4"}
    ]
    monkeypatch.setattr(rss_fetcher, "_fetch_entries", lambda url: entries)
    articles = rss_fetcher.fetch_articles(MECHANISM)
    assert {article["link"] for article in articles} == {"a", "b", "c", "d"}


def test_ranks_signal_matches_first(feed):
    articles = rss_fetcher.fetch_articles(MECHANISM)
    assert articles[0]["link"] == "a"
    assert "Medicaid" in articles[0]["_matched_signals"]


def test_cache_reused_within_ttl_and_refetched_after(feed):
    rss_fetcher.fetch_articles(MECHANISM)
    rss_fetcher.fetch_articles(MECHANISM)
    assert len(feed) == 1

    cache_file = rss_fetcher._cache_path(rss_fetcher.RSS_URL)
    cached = json.loads(cache_file.read_text())
    cached["fetched_at"] = time.time() - (rss_fetcher.CACHE_TTL_SECONDS + 1)
    cache_file.write_text(json.dumps(cached))

    rss_fetcher.fetch_articles(MECHANISM)
    assert len(feed) == 2


def test_config_filters_candidates_before_classification(feed):
    articles = rss_fetcher.fetch_articles(
        MECHANISM,
        source_config={
            "rss_urls": [rss_fetcher.RSS_URL],
            "min_retrieval_score": 1,
            "max_candidates": 1,
            "max_candidates_by_type": {"news": 10, "paper": 10},
        },
    )
    assert len(articles) == 1
    assert articles[0]["_retrieval_score"] >= 1


def test_paper_connector_is_combined_and_normalized(monkeypatch):
    monkeypatch.setattr(rss_fetcher, "fetch_openalex", lambda **kwargs: [{
        "title": "Hospital research", "link": "paper-1", "summary": "hospital", "published": "2026-08-01",
        "source": "Journal", "source_type": "paper", "authors": [], "doi": None,
    }])
    articles = rss_fetcher.fetch_articles(
        MECHANISM,
        source_config={"rss_urls": [], "openalex": {"enabled": True, "max_results": 1}, "min_retrieval_score": 0},
    )
    assert articles[0]["source_type"] == "paper"
