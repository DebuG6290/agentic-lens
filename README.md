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

If the intent is ambiguous the parser asks 2-3 clarifying questions and loops.

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
