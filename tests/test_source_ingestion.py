import json

import source_ingestion


def test_reconstructs_openalex_abstract():
    assert source_ingestion._abstract_from_inverted_index({"paper": [1], "A": [0]}) == "A paper"


def test_fetch_openalex_normalizes_work(monkeypatch):
    payload = {
        "results": [{
            "title": "Tariffs and trade",
            "publication_date": "2026-08-01",
            "doi": "https://doi.org/10.1234/example",
            "abstract_inverted_index": {"trade": [1], "Policy": [0]},
            "authorships": [{"author": {"display_name": "A Researcher"}}],
            "primary_location": {"landing_page_url": "https://example.test/paper", "source": {"display_name": "Journal"}},
        }]
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr(source_ingestion, "urlopen", lambda request, timeout: Response())
    result = source_ingestion.fetch_openalex("tariffs", max_results=1)
    assert result[0]["source_type"] == "paper"
    assert result[0]["summary"] == "Policy trade"
    assert result[0]["authors"] == ["A Researcher"]
