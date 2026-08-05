"""Dependency-free local web UI for Lens.

Run from the repository root with:
    python src/web_app.py
"""

import html
import json
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

sys.path.insert(0, str(Path(__file__).parent))

from digest_store import digest_history
from feedback_store import latest_feedback_by_link, record_feedback
from intent_parser import parse_intent
from lens_store import list_lenses, load_lens, save_lens, validate_lens_name
from main import run
from tuning import apply_tuning_suggestion, build_tuning_report

HOST = "127.0.0.1"
PORT = 8765
RELEVANCE_THRESHOLD = 0.60
HIGH_CONFIDENCE_THRESHOLD = 0.80


def esc(value) -> str:
    return html.escape(str("" if value is None else value))


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Lens</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap');
:root {{ --paper:#faf8f5; --ink:#1f2328; --muted:#747a78; --line:#e7e1da; --teal:#1f7068; --teal-soft:#e4f0ed; --amber:#aa721c; --amber-soft:#fff4dc; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink); font:15px/1.55 'DM Sans',system-ui,sans-serif; }}
header {{ background:var(--paper); border-bottom:1px solid var(--line); padding:22px max(24px,calc((100% - 1120px)/2)); }}
header strong {{ font-size:18px; letter-spacing:-.02em; }} header .muted {{ margin-left:10px; }}
main {{ max-width:1120px; margin:42px auto; padding:0 24px 72px; }}
h1,h2,h3 {{ letter-spacing:-.03em; }} h1,h2 {{ font-family:Newsreader,Georgia,serif; font-weight:600; }} h1 {{ font-size:42px; line-height:1.05; margin:0 0 8px; }} h2 {{ font-size:28px; margin:34px 0 12px; }} h3 {{ margin:0 0 6px; }}
a {{ color:var(--teal); text-decoration:none; }} a:hover {{ text-decoration:underline; }}
.card {{ background:#fffefa; border:1px solid var(--line); border-radius:12px; padding:22px; margin:16px 0; }} .card:hover {{ border-color:#d4cbc1; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; }}
.lens-card {{ display:block; color:var(--ink); min-height:150px; }} .lens-card:hover {{ text-decoration:none; transform:translateY(-1px); }} .lens-card h3 {{ font-family:Newsreader,Georgia,serif; font-size:25px; }}
.lens-meta,.eyebrow {{ color:var(--muted); font-size:12px; letter-spacing:.08em; text-transform:uppercase; }} .intent {{ color:#505653; margin:12px 0 20px; }}
.stats {{ display:flex; gap:20px; }} .stat strong {{ display:block; font-size:22px; color:var(--teal); }} .stat small {{ color:var(--muted); }}
input, textarea {{ width:100%; box-sizing:border-box; padding:11px 12px; border:1px solid #cfc7bf; background:#fffefa; border-radius:7px; margin:6px 0 14px; font:inherit; color:inherit; }} input:focus,textarea:focus {{ outline:2px solid #b8d8d2; border-color:var(--teal); }}
button {{ background:var(--teal); color:white; border:0; border-radius:7px; padding:10px 15px; cursor:pointer; font:600 14px 'DM Sans',sans-serif; }} button:hover {{ filter:brightness(.94); }} button.secondary {{ background:#ece8e2; color:var(--ink); }}
.muted {{ color:var(--muted); }} .pill,.chip {{ display:inline-block; background:var(--teal-soft); color:var(--teal); border-radius:20px; padding:4px 10px; margin:3px; font-size:13px; }} .chip {{ cursor:pointer; }}
.tabs {{ display:flex; gap:4px; border-bottom:1px solid var(--line); margin:30px 0 24px; overflow:auto; }} .tabs a {{ padding:11px 14px; color:var(--muted); white-space:nowrap; border-bottom:2px solid transparent; }} .tabs a:hover,.tabs a.active {{ color:var(--ink); border-color:var(--teal); text-decoration:none; }}
.article {{ background:#fffefa; border:1px solid var(--line); border-left:4px solid #b9c0bd; border-radius:9px; padding:20px 22px; margin:14px 0; }} .article.relevant {{ border-left-color:var(--teal); }} .article.review {{ border-left-color:var(--amber); }} .article h3 {{ font-family:Newsreader,Georgia,serif; font-size:25px; line-height:1.15; }}
.article-actions {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:16px; }} .impact {{ color:#4f5754; font-size:13px; }} .impact strong {{ color:var(--ink); }}
.confidence {{ display:flex; align-items:center; gap:10px; color:var(--muted); font-size:13px; margin-top:14px; }} .meter {{ height:5px; width:110px; background:#e9e5df; border-radius:9px; overflow:hidden; }} .meter span {{ display:block; height:100%; background:var(--teal); }} .review .meter span {{ background:var(--amber); }} .positive {{ color:var(--teal); }} .negative {{ color:var(--muted); }}
.section-head {{ display:flex; justify-content:space-between; align-items:end; margin-top:28px; }} .section-head h2 {{ margin-bottom:0; }} .mechanism {{ position:relative; }}
.chain {{ display:flex; align-items:stretch; gap:10px; margin:18px 0; }} .chain-step {{ flex:1; background:#f4f1ec; border:1px solid var(--line); border-radius:8px; padding:14px; }} .chain-step small {{ color:var(--muted); display:block; margin-bottom:4px; text-transform:uppercase; letter-spacing:.08em; font-size:10px; }} .chain-arrow {{ align-self:center; color:var(--teal); font-size:20px; }}
.filter-bar {{ display:flex; gap:8px; flex-wrap:wrap; padding:12px 0; position:sticky; top:0; z-index:2; background:var(--paper); }} .filter-bar select {{ border:1px solid var(--line); background:#fffefa; border-radius:7px; padding:8px; color:var(--ink); }} .source-badge {{ color:var(--muted); border:1px solid var(--line); border-radius:20px; padding:2px 8px; font-size:11px; }}
.empty {{ text-align:center; padding:58px 24px; }} .empty p {{ color:var(--muted); }} .toast {{ background:var(--teal-soft); color:var(--teal); padding:12px 15px; border-radius:8px; margin:16px 0; }} details.card summary {{ cursor:pointer; font-weight:600; }}
.drawer {{ width:min(620px,calc(100% - 32px)); margin:0 0 0 auto; height:100%; max-height:none; border:0; border-left:1px solid var(--line); padding:32px; background:var(--paper); color:var(--ink); }} .drawer::backdrop {{ background:#1f232855; }} .drawer h2 {{ margin-top:8px; }}
@media(max-width:700px) {{ h1 {{ font-size:34px; }} .chain {{ flex-direction:column; }} .chain-arrow {{ transform:rotate(90deg); text-align:center; }} main {{ margin-top:28px; }} }}
</style></head><body><header><strong>Lens</strong> <span class="muted">personal news intelligence</span></header><main>{body}</main></body></html>"""


def form_value(values: dict, key: str) -> str:
    return values.get(key, [""])[0].strip()


def confidence_value(article: dict) -> float:
    try:
        return max(0.0, min(1.0, float(article.get("confidence", 0))))
    except (TypeError, ValueError):
        return 0.0


def source_config_from_form(values: dict, current: dict) -> dict:
    def number(name, default, minimum, maximum):
        try:
            return max(minimum, min(maximum, int(form_value(values, name) or default)))
        except ValueError:
            return default

    rss_urls = [line.strip() for line in form_value(values, "rss_urls").splitlines() if line.strip()]
    def connector(name, enabled_key, days_key, max_key):
        existing = current.get(name, {})
        return {
            "enabled": enabled_key in values,
            "lookback_days": number(days_key, existing.get("lookback_days", 30), 1, 365),
            "max_results": number(max_key, existing.get("max_results", 10), 1, 50),
        }

    return {
        "rss_urls": rss_urls or current.get("rss_urls", []),
        "openalex": connector("openalex", "openalex", "openalex_days", "openalex_max"),
        "pubmed": connector("pubmed", "pubmed", "pubmed_days", "pubmed_max"),
        "crossref": connector("crossref", "crossref", "crossref_days", "crossref_max"),
        "min_retrieval_score": number("min_score", 1, 0, 20),
        "max_candidates": number("max_candidates", 15, 1, 100),
        "max_candidates_by_type": {"news": number("max_news", 10, 1, 100), "paper": number("max_papers", 10, 1, 100)},
    }


def article_bucket(article: dict) -> str:
    confidence = confidence_value(article)
    reason = str(article.get("reason", "")).casefold()
    if "model did not return valid json" in reason or "classification failed" in reason:
        return "review"
    if article.get("relevant") and confidence >= RELEVANCE_THRESHOLD:
        return "relevant"
    if article.get("relevant"):
        return "review"
    if confidence >= HIGH_CONFIDENCE_THRESHOLD:
        return "excluded"
    return "hidden"


_JOBS = {}
_JOBS_LOCK = threading.Lock()


def update_job(job_id: str, **changes):
    with _JOBS_LOCK:
        _JOBS[job_id].update(changes)


def _run_intent_job(job_id: str, intent: str, history: list, original_intent: str = None):
    try:
        update_job(job_id, stage="intent_decomposition", message="Understanding the lens intent")

        def progress(stage, status, duration_ms=None):
            update_job(job_id, stage=stage,
                       message=f"{stage.replace('_', ' ').title()} ({status})",
                       last_duration_ms=duration_ms)

        result = parse_intent(intent, conversation_history=history, progress_callback=progress)
        if result["status"] == "error":
            update_job(job_id, status="error", stage="error",
                       message=result.get("error", "Could not understand the intent"),
                       finished_at=time.time())
            return
        if result["status"] != "complete":
            update_job(job_id, status="needs_clarification", stage="clarification",
                       message="The model needs clarification", questions=result.get("questions", []),
                       history=result.get("history", history), finished_at=time.time())
            return
        update_job(job_id, stage="saving", message="Saving lens")
        with _JOBS_LOCK:
            name = _JOBS[job_id]["lens"]
        save_lens(name, original_intent or intent, result["mechanism_object"])
        update_job(job_id, status="complete", stage="complete", message="Lens created",
                   finished_at=time.time(), redirect=f"/lens/{quote(name)}")
    except (ValueError, OSError, KeyError) as exc:
        update_job(job_id, status="error", stage="error", message=str(exc), finished_at=time.time())


def create_job(name: str, intent: str) -> str:
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        _JOBS[job_id] = {"status": "running", "stage": "queued", "message": "Queued",
                         "started_at": time.time(), "finished_at": None, "lens": name,
                         "intent": intent, "history": []}
    threading.Thread(target=_run_intent_job, args=(job_id, intent, [], intent), daemon=True).start()
    return job_id


def continue_job(job_id: str, answer: str):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job or job.get("status") != "needs_clarification":
            raise ValueError("clarification job is no longer available")
        intent = job["intent"]
        history = job.get("history", [])
        job.update({"status": "running", "stage": "queued", "message": "Processing your answers",
                    "finished_at": None})
    threading.Thread(target=_run_intent_job, args=(job_id, answer, history, intent), daemon=True).start()


def create_run_job(name: str) -> str:
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        _JOBS[job_id] = {"status": "running", "stage": "queued", "message": "Queued",
                         "started_at": time.time(), "finished_at": None, "lens": name}

    def worker():
        try:
            def progress(stage, status, **details):
                message = f"{stage.replace('_', ' ').title()} ({status})"
                if stage == "classification" and details.get("total"):
                    message += f" — article {details['current']} of {details['total']}"
                update_job(job_id, stage=stage, message=message, **details)

            run(lens_name=name, progress_callback=progress)
            update_job(job_id, status="complete", stage="complete", message="Lens run complete",
                       finished_at=time.time(), redirect=f"/lens/{quote(name)}")
        except Exception as exc:
            update_job(job_id, status="error", stage="error",
                       message=f"{type(exc).__name__}: {exc}", finished_at=time.time())

    threading.Thread(target=worker, daemon=True).start()
    return job_id


def progress_page(job_id: str, heading: str) -> str:
    return f"""
<h1>{esc(heading)}</h1><p class=\"muted\">This page updates as each stage completes.</p>
<div class=\"card\"><p id=\"message\">Queued</p><p><strong>Elapsed:</strong> <span id=\"elapsed\">0.0s</span></p><div id=\"details\"></div></div>
<p><a href=\"/\">Cancel</a></p>
<script>
const started = Date.now();
function renderClarification(job) {{
  const target = document.getElementById('details');
  target.textContent = '';
  const intro = document.createElement('p');
  intro.textContent = 'Choose the answers that best describe what you want this lens to track.';
  target.appendChild(intro);
  const form = document.createElement('form');
  form.method = 'post'; form.action = '/clarify/{job_id}';
  (job.questions || []).forEach((question, index) => {{
    const field = document.createElement('fieldset');
    const legend = document.createElement('legend');
    legend.textContent = question.question;
    field.appendChild(legend);
    (question.options || []).forEach(option => {{
      const label = document.createElement('label'); label.style.display = 'block';
      const input = document.createElement('input');
      input.type = 'radio'; input.name = question.id || ('question_' + index);
      input.value = option.value || option.label; input.required = true;
      label.appendChild(input); label.appendChild(document.createTextNode(' ' + (option.label || option.value)));
      field.appendChild(label);
    }});
    if (question.allow_custom || !(question.options || []).length) {{
      const custom = document.createElement('input');
      custom.name = (question.id || ('question_' + index)) + '_custom';
      custom.placeholder = 'Other answer (optional)'; custom.style.marginTop = '8px';
      field.appendChild(custom);
    }}
    form.appendChild(field);
  }});
  const submit = document.createElement('button'); submit.textContent = 'Continue';
  form.appendChild(submit); target.appendChild(form);
}}
async function poll() {{
  const r = await fetch('/job/{job_id}'); const j = await r.json();
  document.getElementById('message').textContent = j.message;
  document.getElementById('elapsed').textContent = ((Date.now()-started)/1000).toFixed(1)+'s';
  if (j.status !== 'needs_clarification') document.getElementById('details').textContent = j.title || j.message || '';
  if (j.status === 'complete') {{ window.location = j.redirect; return; }}
  if (j.status === 'needs_clarification') {{ renderClarification(j); return; }}
  if (j.status === 'error') {{ document.getElementById('details').textContent = j.message; return; }}
  setTimeout(poll, 500);
}}
poll();
</script>"""


class LensHandler(BaseHTTPRequestHandler):
    def send_html(self, content: str, status: int = 200):
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def redirect(self, location: str):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def read_form(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        return parse_qs(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.home()
            return
        if parsed.path.startswith("/lens/"):
            self.lens_page(parsed.path.removeprefix("/lens/"))
            return
        if parsed.path.startswith("/job/"):
            self.job_status(parsed.path.removeprefix("/job/"))
            return
        self.send_html(page("Not found", "<h1>Not found</h1>"), 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        values = self.read_form()
        if parsed.path == "/create":
            self.create_lens(values)
        elif parsed.path.startswith("/clarify/"):
            self.clarify(parsed.path.removeprefix("/clarify/"), values)
        elif parsed.path.startswith("/settings/"):
            self.update_settings(parsed.path.removeprefix("/settings/"), values)
        elif parsed.path.startswith("/run/"):
            name = parsed.path.removeprefix("/run/")
            try:
                load_lens(name)
            except ValueError as exc:
                self.send_html(page("Could not run lens", f"<h1>Could not run lens</h1><p>{esc(exc)}</p><a href=\"/\">Back</a>"), 404)
                return
            job_id = create_run_job(name)
            self.send_html(page("Running lens", progress_page(job_id, "Running lens")))
        elif parsed.path.startswith("/tune/") and parsed.path.endswith("/apply"):
            self.apply_tuning(parsed.path.removeprefix("/tune/").removesuffix("/apply"), values)
        elif parsed.path == "/feedback":
            self.feedback(values)
        else:
            self.send_html(page("Not found", "<h1>Not found</h1>"), 404)

    def home(self):
        cards = []
        for name in list_lenses():
            try:
                latest = digest_history(name)[-1] if digest_history(name) else {}
                articles = latest.get("articles", [])
                relevant = sum(1 for item in articles if article_bucket(item) == "relevant")
                review = sum(1 for item in articles if article_bucket(item) == "review")
                lens = load_lens(name)
                cards.append(
                    f'<a class="card lens-card" href="/lens/{quote(name)}">'
                    f'<div class="lens-meta">Lens · {esc(name)}</div>'
                    f'<h3>{esc(name.replace("_", " "))}</h3>'
                    f'<p class="intent">{esc(lens.get("user_intent", ""))}</p>'
                    f'<div class="stats"><div class="stat"><strong>{relevant}</strong><small>relevant</small></div>'
                    f'<div class="stat"><strong>{review}</strong><small>needs review</small></div></div></a>'
                )
            except ValueError:
                continue
        lens_html = "".join(cards) or '<div class="card empty"><h2>No lenses yet</h2><p>Create your first lens to start tracking the news through your own point of view.</p><button onclick="document.getElementById(\'create-lens\').showModal()">Create your first lens</button></div>'
        body = f"""
<div class="section-head"><div><div class="eyebrow">Personal intelligence cockpit</div><h1>Your lenses</h1><p class="muted">A calm view of the news that matters to your situation.</p></div><button onclick="document.getElementById('create-lens').showModal()">Create lens</button></div>
<div class="grid">{lens_html}</div>
<dialog id="create-lens" class="card" style="max-width:560px;width:calc(100% - 48px);border:1px solid var(--line);border-radius:14px;padding:28px;background:var(--paper);color:var(--ink)">
<form method="dialog"><button class="secondary" style="float:right">Close</button></form><div class="eyebrow">New lens</div><h2 style="margin-top:8px">What should Lens watch for you?</h2>
<form method="post" action="/create">
<label>Name</label><input name="name" placeholder="hospital_business" required>
<label>Your stake</label>
<textarea name="intent" rows="3" placeholder="Trump affects my hospital business" required></textarea>
<p class="muted">Try: “How could AI regulation affect my healthcare startup?”</p><button>Create lens</button></form></dialog>
<script>document.querySelectorAll('dialog').forEach(d => d.addEventListener('click', e => {{ if (e.target === d) d.close(); }}));</script>
"""
        self.send_html(page("Lenses", body))

    def create_lens(self, values: dict):
        name = form_value(values, "name")
        intent = form_value(values, "intent")
        try:
            validate_lens_name(name)
            if not intent:
                raise ValueError("intent is required")
        except ValueError as exc:
            self.send_html(page("Could not create lens", f"<h1>Could not create lens</h1><p>{esc(exc)}</p><a href=\"/\">Back</a>"), 400)
            return
        job_id = create_job(name, intent)
        body = progress_page(job_id, "Creating lens")
        self.send_html(page("Creating lens", body))

    def clarify(self, job_id: str, values: dict):
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
            questions = job.get("questions", []) if job else []
        if not job:
            self.send_html(page("Clarification error", "<h1>Job not found</h1>"), 404)
            return
        answers = []
        for question in questions:
            question_id = question.get("id", "")
            selected = form_value(values, question_id)
            custom = form_value(values, question_id + "_custom")
            answer = custom or selected
            if answer:
                answers.append(f"{question.get('question', question_id)}: {answer}")
        if not answers:
            self.send_html(page("Clarification error", "<h1>Please answer at least one question</h1><a href='/'>Back</a>"), 400)
            return
        try:
            continue_job(job_id, "\n".join(answers))
        except ValueError as exc:
            self.send_html(page("Clarification error", f"<h1>{esc(exc)}</h1>"), 400)
            return
        self.send_html(page("Continuing lens creation", progress_page(job_id, "Creating lens")))

    def job_status(self, job_id: str):
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
        if not job:
            self.send_json({"status": "error", "message": "job not found"}, 404)
            return
        result = dict(job)
        result["elapsed_ms"] = round(((result.get("finished_at") or time.time()) - result["started_at"]) * 1000, 1)
        self.send_json(result)

    def send_json(self, value: dict, status: int = 200):
        payload = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def lens_page(self, name: str):
        try:
            lens = load_lens(name)
        except ValueError as exc:
            self.send_html(page("Lens not found", f"<h1>{esc(exc)}</h1><a href=\"/\">Back</a>"), 404)
            return

        mechanism = lens["mechanism_object"]
        source_config = lens.get("source_config", {})
        mechanisms = mechanism.get("mechanisms", [])
        if not mechanisms:
            mechanisms = [
                {"name": item.get("path", "Legacy path"), "causal_chain": [], "signals": item.get("keywords", [])}
                for item in mechanism.get("reasoning_paths", [])
            ]
        mechanism_html = "".join(
            "<div class='card'><h3>" + esc(item.get("name")) + "</h3>"
            + "<p><strong>Causal chain:</strong> " + esc(" → ".join(item.get("causal_chain", []))) + "</p>"
            + "<p><strong>Signals:</strong> "
            + " ".join(f"<span class='pill'>{esc(signal)}</span>" for signal in item.get("signals", item.get("keywords", [])))
            + "</p></div>"
            for item in mechanisms
        )
        def mechanism_card(item):
            chain = item.get("causal_chain", [])
            steps = "".join(
                "<div class='chain-step'><small>" + ("Signal" if index == 0 else "Consequence" if index == len(chain) - 1 else "Effect") + "</small>" + esc(step) + "</div>"
                + ("<div class='chain-arrow'>→</div>" if index < len(chain) - 1 else "")
                for index, step in enumerate(chain)
            )
            signals = " ".join(f"<span class='pill'>{esc(signal)}</span>" for signal in item.get("signals", item.get("keywords", [])))
            exclusions = " ".join(f"<span class='pill' style='background:#f0eeeb;color:var(--muted)'>{esc(value)}</span>" for value in item.get("exclusions", [])) or "<span class='muted'>None defined</span>"
            return f"<div class='card mechanism'><h3>{esc(item.get('name'))}</h3><div class='chain'>{steps}</div><p class='eyebrow'>Signals</p>{signals}<p class='eyebrow' style='margin-top:14px'>Exclusions</p>{exclusions}</div>"

        mechanism_html = "".join(mechanism_card(item) for item in mechanisms)
        tuning = build_tuning_report(name)
        tuning_suggestions = "".join(
            f"<div class='article'><p><strong>{esc(item['action'].replace('_', ' ').title())}:</strong> {esc(item['term'])}</p>"
            f"<p class='muted'>{esc(item['explanation'])}</p>"
            f"<form method='post' action='/tune/{quote(name)}/apply'><input type='hidden' name='suggestion' value='{esc(json.dumps(item))}'><button>Apply suggestion</button></form></div>"
            for item in tuning["suggestions"]
        )
        tuning_html = (
            f"<p class='muted'>{tuning['labeled']} labeled articles · {tuning['relevant']} relevant · {tuning['not_relevant']} not relevant</p>"
            + (tuning_suggestions or "<p class='muted'>No suggestions yet. Label at least two similar articles to surface a pattern.</p>")
        )
        history = digest_history(name)
        latest = history[-1]["articles"] if history else []
        feedback_by_link = latest_feedback_by_link(name)
        feedback_message = parse_qs(urlparse(self.path).query).get("feedback", [""])[0]
        feedback_banner = ""
        if feedback_message in {"relevant", "not_relevant"}:
            label = "relevant" if feedback_message == "relevant" else "not relevant"
            feedback_banner = f'<div class="card positive"><strong>Feedback saved:</strong> marked {label}.</div>'
        grouped = {"relevant": [], "review": [], "excluded": []}
        for article in latest:
            bucket = article_bucket(article)
            if bucket in grouped:
                grouped[bucket].append(article)

        def section(title, articles, note=""):
            if not articles:
                return ""
            return "<h3>" + esc(title) + "</h3><p class='muted'>" + esc(note) + "</p>" + "".join(
                self.article_html(name, article, feedback_by_link.get(article.get("link", ""))) for article in articles
            )

        articles_html = (
            section("Relevant", grouped["relevant"], f"Confidence ≥ {RELEVANCE_THRESHOLD:.2f}")
            + section("Needs review", grouped["review"], "Low-confidence or invalid model classifications")
            + section("High-confidence exclusions", grouped["excluded"], f"Not relevant with confidence ≥ {HIGH_CONFIDENCE_THRESHOLD:.2f}")
            or '<p class="muted">No articles met the display thresholds. Run this lens to generate a digest.</p>'
        )
        body = f"""
<p><a href="/">← All lenses</a></p>
<h1>{esc(name)}</h1><p class="muted">{esc(lens['user_intent'])}</p>{feedback_banner}
<div class="tabs"><a class="active" href="#overview">Overview</a><a href="#mechanisms">Mechanisms</a><a href="#sources">Sources</a><a href="#tuning">Tuning &amp; feedback</a><a href="#evaluation">Evaluation</a></div>
<div id="overview" class="card"><div class="eyebrow">Watching through</div><p>{''.join(f'<a class="chip" href="#mechanisms">{esc(item.get("name"))}</a>' for item in mechanisms)}</p></div>
<form method="post" action="/run/{quote(name)}"><button>Run lens now</button></form>
<div id="sources"><details class="card"><summary><strong>Source settings</strong></summary>
<form method="post" action="/settings/{quote(name)}">
<label>RSS URLs (one per line)</label><textarea name="rss_urls" rows="3">{esc(chr(10).join(source_config.get('rss_urls', [])))}</textarea>
<label><input type="checkbox" name="openalex" {'checked' if source_config.get('openalex', {}).get('enabled') else ''}> OpenAlex papers</label><br>
<label><input type="checkbox" name="pubmed" {'checked' if source_config.get('pubmed', {}).get('enabled') else ''}> PubMed papers</label><br>
<label><input type="checkbox" name="crossref" {'checked' if source_config.get('crossref', {}).get('enabled') else ''}> Crossref papers</label>
<p><label>OpenAlex lookback days <input name="openalex_days" type="number" min="1" max="365" value="{esc(source_config.get('openalex', {}).get('lookback_days', 30))}"></label>
<label>OpenAlex max results <input name="openalex_max" type="number" min="1" max="50" value="{esc(source_config.get('openalex', {}).get('max_results', 10))}"></label></p>
<p><label>PubMed lookback days <input name="pubmed_days" type="number" min="1" max="365" value="{esc(source_config.get('pubmed', {}).get('lookback_days', 30))}"></label>
<label>PubMed max results <input name="pubmed_max" type="number" min="1" max="50" value="{esc(source_config.get('pubmed', {}).get('max_results', 10))}"></label></p>
<p><label>Crossref lookback days <input name="crossref_days" type="number" min="1" max="365" value="{esc(source_config.get('crossref', {}).get('lookback_days', 30))}"></label>
<label>Crossref max results <input name="crossref_max" type="number" min="1" max="50" value="{esc(source_config.get('crossref', {}).get('max_results', 10))}"></label></p>
<p><label>Minimum retrieval score <input name="min_score" type="number" min="0" max="20" value="{esc(source_config.get('min_retrieval_score', 1))}"></label>
<label>Maximum candidates <input name="max_candidates" type="number" min="1" max="100" value="{esc(source_config.get('max_candidates', 15))}"></label></p>
<button>Save source settings</button></form></details></div>
<div id="mechanisms"><h2>Mechanisms</h2>{mechanism_html}</div>
<div id="tuning"><h2>Lens learning from your feedback</h2><div class="card"><p>Suggestions are based on repeated signals in your labeled articles. Review each change before applying it.</p>{tuning_html}</div></div>
<div id="evaluation"><h2>Evaluation</h2><div class="card"><p class="muted">Feedback-based quality metrics will appear as you label articles.</p></div></div>
<div id="digest"><div class="section-head"><h2>Latest digest</h2><span class="muted">{len(latest)} articles from the latest run</span></div><div class="filter-bar"><select><option>All mechanisms</option></select><select><option>All sources</option><option>News</option><option>Research</option></select><select><option>Any confidence</option><option>High confidence</option><option>Needs review</option></select></div><div class="card">{articles_html}</div></div>
<dialog id="article-detail" class="drawer"><form method="dialog"><button class="secondary" style="float:right">Close</button></form><div class="eyebrow">Article explanation</div><h2 id="detail-title"></h2><p><strong>Why it matters</strong></p><p id="detail-reason"></p><p><strong>Evidence</strong></p><p id="detail-evidence"></p><p><strong>Impact path</strong></p><p id="detail-impact" class="impact"></p></dialog>
<script>
function openArticle(button) {{
  const dialog = document.getElementById('article-detail');
  document.getElementById('detail-title').textContent = button.dataset.title;
  document.getElementById('detail-reason').textContent = button.dataset.reason || 'No explanation was returned.';
  document.getElementById('detail-evidence').textContent = button.dataset.evidence || 'No evidence was returned.';
  document.getElementById('detail-impact').textContent = button.dataset.impact || 'No impact path was returned.';
  dialog.showModal();
}}
</script>
"""
        self.send_html(page(name, body))

    def update_settings(self, name: str, values: dict):
        try:
            lens = load_lens(name)
            config = source_config_from_form(values, lens.get("source_config", {}))
            save_lens(name, lens["user_intent"], lens["mechanism_object"], config)
        except (ValueError, OSError, KeyError) as exc:
            self.send_html(page("Settings error", f"<h1>Could not save settings</h1><p>{esc(exc)}</p>"), 400)
            return
        self.redirect(f"/lens/{quote(name)}")

    def apply_tuning(self, name: str, values: dict):
        try:
            suggestion = json.loads(form_value(values, "suggestion"))
            apply_tuning_suggestion(name, suggestion)
        except (ValueError, json.JSONDecodeError, OSError, KeyError) as exc:
            self.send_html(page("Tuning error", f"<h1>Could not apply suggestion</h1><p>{esc(exc)}</p><a href='/lens/{quote(name)}'>Back</a>"), 400)
            return
        self.redirect(f"/lens/{quote(name)}?tuned=1")

    def article_html(self, lens_name: str, article: dict, feedback_label: str = "") -> str:
        relevant = bool(article.get("relevant"))
        status = "relevant" if relevant else "not relevant"
        color = "positive" if relevant else "negative"
        matched = ", ".join(article.get("matched_signals", []))
        provenance = " · ".join(str(value) for value in (article.get("source"), article.get("published")) if value)
        if feedback_label in {"relevant", "not_relevant"}:
            saved_label = "relevant" if feedback_label == "relevant" else "not relevant"
            feedback_html = f'<p class="positive"><strong>Feedback saved: {saved_label}</strong></p>'
        else:
            feedback_html = f"""
<form method="post" action="/feedback">
<input type="hidden" name="lens" value="{esc(lens_name)}">
<input type="hidden" name="link" value="{esc(article.get('link'))}">
<input type="hidden" name="title" value="{esc(article.get('title'))}">
<button name="label" value="relevant">Mark relevant</button>
<button class="secondary" name="label" value="not_relevant">Mark not relevant</button>
</form>"""
        article_class = "relevant" if relevant else ("review" if article_bucket(article) == "review" else "")
        confidence = round(confidence_value(article) * 100)
        return f"""
<div class="article {article_class}"><h3><a href="{esc(article.get('link'))}">{esc(article.get('title'))}</a></h3>
<p class="muted">{esc(provenance)}</p>
<span class="source-badge">{esc('Research' if article.get('source_type') == 'paper' else 'News')}</span>
<p class="muted">Matched signals: {esc(matched or 'none')}</p>
<p class="{color}"><strong>{status}</strong> · confidence {esc(article.get('confidence', 0))}</p>
<div class="confidence"><span>Confidence</span><div class="meter"><span style="width:{confidence}%"></span></div><strong>{confidence}%</strong></div>
<p>{esc(article.get('reason'))}</p>
<p class="muted">{esc(article.get('impact_chain'))}</p>
<button type="button" class="secondary" onclick="openArticle(this)" data-title="{esc(article.get('title'))}" data-reason="{esc(article.get('reason'))}" data-impact="{esc(article.get('impact_chain'))}" data-evidence="{esc(article.get('evidence'))}">Read explanation</button>
{feedback_html}</div>"""

    def feedback(self, values: dict):
        try:
            record_feedback(
                form_value(values, "lens"),
                {"title": form_value(values, "title"), "link": form_value(values, "link")},
                form_value(values, "label"),
            )
        except ValueError as exc:
            self.send_html(page("Feedback error", f"<h1>{esc(exc)}</h1>"), 400)
            return
        label = form_value(values, "label")
        self.redirect(f"/lens/{quote(form_value(values, 'lens'))}?feedback={quote(label)}")


if __name__ == "__main__":
    print(f"Lens UI running at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), LensHandler).serve_forever()
