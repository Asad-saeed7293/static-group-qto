# AI assistant, management dashboard, daily report, change detection

## Principle

The assistant **queries the application's own data** – stored runs, Static Group BOQ item calculations, review
queues, benchmarks, methodology rules and the audit log – and cites the records it used. It never measures CAD,
never estimates a quantity, and never answers from a language model's memory. When a methodology rule is UNKNOWN
it says so and states that no conclusion has been made.

## Data tools (`qto/ai/tools.py`)

| Tool | Returns |
|---|---|
| list_projects | projects and processing status |
| project_status | BOQ items by status, items with a value / needing review / missing data, open and critical review items, calculated concrete, drawing/schedule conflicts |
| boq_items | item calculations of a project (optionally by status), open rules, missing data |
| item_detail | calculation, candidates, rules and historical-benchmark lines (with diagnostics) for one item |
| benchmark_lines | benchmark rows, optionally only those above a variance % |
| review_items | open review-queue items |
| unknown_rules | rules that are not CONFIRMED |
| concrete_all | calculated concrete per project |
| compare_projects | item quantities of two projects side by side |
| recent_activity | audit-log events in the last N hours |
| search | elements, BOQ lines and drawings |

Every tool returns `{"data": ..., "citations": [...]}`; a citation names the record type, project, reference
(run id, BOQ sheet/row, rule …) and the page of the app where it can be checked.

## Assistant modes (`qto/ai/agent.py`)

* **Deterministic (default, offline).** The question is routed to tools by intent (project update, issues/risk,
  concrete across projects, "why is X different", unknown rules, what changed, compare projects, status). Answers
  are assembled from the returned records. A question that matches no data intent gets the list of questions it can
  answer – it does not improvise.
* **LLM (optional).** With `"ai": {"enabled": true}` in `config/settings.json`, the `anthropic` package installed and
  credentials configured, Claude (`claude-opus-5-5`) receives the same tools and a system prompt that forbids
  computing or estimating quantities. Project data leaves the machine **only** in this mode, which is off by default
  (brief §40). If the model is unavailable the deterministic answer is returned with a note.

Every question is logged to `data/knowledge/chat_log.jsonl` and the audit log (`platform`).

Example (deterministic, Al-Kawari):

> RC Concrete works in Beams - (GF + FF + PH ): the engine has no approved quantity yet against 135.51 m3 in the
> historical BOQ.
> - Unknown Static Group convention: Rule 'Beam depth' (beam_depth_method) is UNKNOWN - no option is approved.
> - Candidate comparison (not a conclusion): Closest candidate to the historical 135.51: 'full_depth' = 83.58 (-38.3 %). Other candidates: below_slab = 69.00
> - …
> Open rules: Beam depth (UNKNOWN). No conclusion has been made.

## Management dashboard (`#/ceo`)

Projects, BOQ items with a quantity / needing review / missing data, open and critical review items, drawing and
schedule conflicts, calculated concrete, historical benchmark results, pending rule approvals, the assistant and the
daily report. **Time saved and savings are not shown**: no measured manual-effort baseline exists, and the page says
so.

## Daily report (`qto/reports/daily.py`)

`python qto_cli.py daily-report` (or the dashboard button) writes `data/reports/daily_<date>.md` and `.json`:
per project – last run, BOQ completion, items needing review / missing data, open and critical issues, **new and
resolved issues** since the previous snapshot (`data/reports/snapshots/<date>.json`), benchmark lines ≥20 % off,
missing information, changes against the previous run; then pending rule approvals and recommended actions.
Schedule it with Windows Task Scheduler. No e-mail / Teams delivery is configured (no external integrations).

## Change detection (`qto/changes.py`, `#/changes`)

> **Status: implemented, not yet validated against a real revised drawing set.** It is exercised by a synthetic regression test only; the first real revision received should be used to validate it.

Compares two stored runs: drawings added / removed / modified (file size, entity count, extents), elements added /
removed / modified (dimensions and quantities before → after), and the **BOQ impact** – every Static Group item whose
quantity or status changed, with Δ and Δ %. API: `GET /api/projects/{pid}/changes?old=<run>&new=<run>`.

## API

| Endpoint | Purpose |
|---|---|
| POST /api/chat `{message, project}` | assistant answer with citations and tool calls |
| GET /api/chat/history | logged questions |
| GET /api/ceo | dashboard data |
| GET /api/reports/daily?save=true | daily report (save = write files + snapshot) |
| GET /api/projects/{pid}/runs, /changes | run list and run comparison |
