# agentic-lens

Local-only news filtering. A user's free-text intent becomes a *mechanism object*
(`entity`, `user_context`, `reasoning_paths`), which drives an RSS fetch and a
per-article relevance pass, rendered as a daily digest. Everything runs against a
local Ollama (`llama3.2:latest`); no frameworks.

## Pipeline

```
intent -> src/intent_parser.py -> mechanism object
       -> src/rss_fetcher.py   -> keyword-matched articles (single RSS source)
       -> src/classifier.py    -> {relevant, reason} per article
       -> src/main.py          -> digest
```

## Setup

```bash
pip install -r requirements.txt
ollama pull llama3.2:latest
```

## Run

Paths to `prompts/` and `data/` are relative, so run from the repo root:

```bash
python src/main.py
```

## Local UI

Run the dependency-free local cockpit:

```bash
python src/web_app.py
```

Open `http://127.0.0.1:8765`. It lets you create lenses, inspect their
mechanisms, run digests, and give article-level feedback.
The lens page also surfaces explainable tuning suggestions from repeated
feedback; applying a suggestion requires confirmation and records the change
in `tuning_history`.

If the intent is ambiguous the parser asks 2-3 clarifying questions and loops.
Lens creation validates the name before calling Ollama, then shows a live stage
and elapsed-time page while intent decomposition runs. Each Ollama log entry in
`data/logs.jsonl` also includes `duration_ms`, so slow model calls can be
identified directly.

Saved lenses ingest the configured RSS sources plus recent OpenAlex research
papers by default. Each document is normalized with source type, publication
date, authors, and provenance before ranking and classification. The OpenAlex
lookback window and result limit can be changed in a lens JSON file under
`data/lenses/`, for example:

```json
"source_config": {
  "rss_urls": ["https://feeds.bbci.co.uk/news/world/rss.xml"],
  "openalex": {"enabled": true, "lookback_days": 30, "max_results": 10}
}
```

## Tests

```bash
pytest                        # mocked ollama.chat, no model required
python scripts/try_intent.py  # manual smoke test against a live Ollama
```

## Logs

Every LLM call and RSS fetch is appended to `data/logs.jsonl`
(`timestamp`, `stage`, `input`, `output`, `tokens`). It is gitignored and grows
unbounded — clear it periodically (`> data/logs.jsonl`). Feed responses are cached
in `data/rss_cache/` with a 6-hour TTL.
