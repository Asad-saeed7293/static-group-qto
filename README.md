# QTO & BOQ Automation

A working system that reads real CAD drawings (DXF, and native DWG via the ODA File
Converter) for residential villa projects and:

1. scans every drawing file across all disciplines, inventories layers, blocks, text and units;
2. identifies **footings, rafts, blinding, columns, RC walls, beams, tie beams, pedestals and slabs**
   using a configurable, per-CAD-standard rules file;
3. measures each element from CAD geometry and reads thicknesses, depths and levels from the
   drawings' own schedules, sections and tags;
4. calculates quantities with a deterministic, independently-tested engine — every number has a
   formula and a CAD source, never a guess;
5. generates a Bill of Quantities, imports an existing BOQ (XLSX/CSV with column mapping), and
   compares the two with configurable tolerances;
6. flags everything questionable in a review queue, and shows the evidence for each number
   (drawing, layer, entity handle, schedule row, formula) on an in-app drawing viewer;
7. exports a BOQ, a tender-ready PDF, a variance report, a drawing-revision diff report and a
   processing summary, and keeps a full audit trail.

> No numbers in this application are hard-coded or estimated from images. Where the drawings do
> not contain a value, the system shows the line as **Missing** and flags it. Assumptions are
> always listed separately from measured values.

This repository is a sanitized, public copy of a project built for a real construction company's
own internal use. Real client project data, drawings and historical BOQs have been removed —
see [What isn't in this repo](#what-isnt-in-this-repo) below.

---

## Key features

- **Exact client-BOQ format matching** — the generated workbook mirrors a real company's own
  historical BOQ layout: multi-sheet structure, header block, column layout, and section/item
  numbering convention (section codes on heading rows only, plain sequential item numbers that
  reset per section).
- **In-app preview before export** — review the exact sheets, headings and numbering the
  download will contain, without leaving the browser.
- **Tender PDF export** — a client-ready, letterhead-style PDF built from the same data as the
  Excel export, so the two can never drift apart.
- **Rate memory** — re-import a priced BOQ (with a Rate column mapped) and the app remembers
  those real rates; future projects show them as a clearly-marked, editable *suggestion*, never
  a confirmed price.
- **Cost benchmarking dashboard** — compares QR/m² indicative cost across projects, built only
  from real rate memory, honest about partial coverage.
- **Drawing-revision diff report** — compares two processing runs (drawings added/removed/
  modified, element and BOQ-line changes) and exports it as a shareable Excel report.
- **Methodology rules engine** — every measurement convention (e.g. "do we deduct openings from
  wall area?") is a versioned, auditable rule with CONFIRMED / INFERRED / ASSUMED / UNKNOWN
  status. An UNKNOWN rule never guesses — the engine shows every candidate quantity per option
  until an estimator approves one.
- **Native DWG support** — DWG files are converted to DXF via the free ODA File Converter
  (auto-detected on the host machine) and cached, so the whole pipeline works transparently
  whether a drawing arrives as DXF or DWG.
- **Folder upload** — point the app at a whole folder of scattered drawings (not just
  individual files) and it recursively picks up everything, preserving subfolder structure so
  same-named files in different disciplines never collide or go missing.

## Run it locally

1. **Install Python 3.10+** from <https://www.python.org/downloads/> (tick "Add python.exe to PATH").
2. Clone this repo.
3. Point a project's `source_folder` in `config/projects.json` at your own drawing folder
   (the three seeded entries use placeholder paths).
4. ```bash
   python -m pip install -r requirements.txt
   python -m uvicorn server.app:app --port 8765
   ```
   Then open <http://127.0.0.1:8765>.
5. In the app: **Processing → Run processing**.

Command line (no UI):

```bash
python qto_cli.py run
python qto_cli.py export --out samples
```

Tests:

```bash
python -m pytest -q
```

## What is in the folder

| Path | Purpose |
|---|---|
| `qto/ingest` | DXF/DWG loading (ezdxf, ODA File Converter, recover mode), units, flattening of blocks/xrefs, viewer geometry |
| `qto/classify` | Rules engine: drawing roles, layer/text/block rules from `config/rules_*.json` |
| `qto/extract` | Schedule tables, column-schedule grid, section-detail dimensions, level tags |
| `qto/elements` | Element builders: footings/rafts/blinding, columns/walls, beams/pedestals, slab zones |
| `qto/calc` | **The only place quantities are computed** (formulas, substitutions, provenance) |
| `qto/boq` | BOQ generation, import + column mapping, comparison / variance |
| `qto/knowledge` | Methodology rules engine, rate memory, BOQ knowledge model, benchmarking |
| `qto/review` | Review queue |
| `qto/export` | Excel and PDF exports |
| `qto/ai` | Optional AI layer (explanations/search only — never measurements) |
| `qto/pipeline.py`, `qto/build.py` | Stage orchestration (full scan and fast recalculation) |
| `server/app.py`, `web/` | FastAPI backend + single-page web UI (no build step) |
| `config/` | Projects, rules (per CAD standard), default settings, BOQ knowledge model |
| `tests/` | Full test suite |
| `samples/` | Sample exported reports and a clearly-labelled synthetic test BOQ |

## What isn't in this repo

This is a sanitized public copy. The following were intentionally left out:

- `data/` — real client project runs, drawings metadata, audit logs and cached geometry.
- Real project/client names and locations in `config/projects.json` — replaced with generic
  placeholders (`Reference Villa A/B/C`, `[redacted]`).
- Internal documentation, scratch notes and presentation decks that named real clients.

The three seeded project entries (`ramzi-villa`, `kawari-villa`, `sulaiti-villa`) are kept only
as internal IDs the codebase already references in tests and examples — they carry no name or
address once the fields above are redacted.

## Optional AI

AI is off by default; the assistant then answers deterministically from application data (no
data leaves the machine). To enable an LLM-phrased assistant, install the relevant SDK, set the
appropriate API key, and set `"ai": {"enabled": true}` in `config/settings.json`. The model
receives project data only through the same data tools the app itself uses, is instructed never
to compute or estimate quantities, and every answer still carries citations back to source data.
