# Lens (v1)

Local-only, framework-free news filtering. A user's free-text intent is decomposed by a local
Ollama model (`llama3.2:latest`) into a *mechanism object*, which drives an RSS fetch and a
per-article relevance pass, ending in a daily digest.

```
user intent -> src/intent_parser.py -> mechanism object
            -> src/rss_fetcher.py   -> keyword-matched articles (single RSS source)
            -> src/classifier.py    -> {relevant, reason} per article
            -> src/main.py          -> daily digest
```

## Setup

```bash
pip install -r requirements.txt
ollama pull llama3.2:latest
```

## Run

From the repo root (paths are resolved relative to the working directory):

```bash
python src/main.py "Trump affects my hospital business"
```

Manual smoke test of the clarification loop: `python scripts/try_intent.py`.

## Tests

```bash
pytest tests
```

The suite mocks `ollama.chat`, so it needs neither Ollama nor network access.

## Logs

Every LLM call and each RSS fetch appends one JSON line to `data/logs.jsonl`
(`timestamp`, `stage`, `input`, `output`, `tokens`). This file grows unbounded and is
gitignored — clear or rotate it periodically:

```bash
: > data/logs.jsonl
```

Fetched feeds are cached in `data/rss_cache/` and reused within a freshness window
(`CACHE_TTL_SECONDS` in `src/rss_fetcher.py`); it is safe to delete.
