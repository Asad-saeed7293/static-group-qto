# Static Group – Quantity Take-off & BOQ Verification MVP

A working prototype that reads the **real DXF drawings** of the Mr. Ramzi T A Mari Villa and:

1. scans every DXF file (80 files, all disciplines), inventories layers, blocks, text and units;
2. identifies **footings, rafts, blinding, columns, RC walls, beams, tie beams, pedestals and slabs** using a configurable rules file;
3. measures each element from CAD geometry and reads thicknesses, depths and levels from the drawings' own schedules, sections and tags;
4. calculates quantities with a deterministic, independently-tested engine (every number has a formula and a CAD source);
5. generates a BOQ, imports an existing BOQ (XLSX/CSV with column mapping), and compares the two with configurable tolerances;
6. flags everything questionable in a review queue, and shows the evidence for each number (drawing, layer, entity handle, schedule row, formula) on a drawing viewer;
7. exports a professional BOQ, a variance report, a review report and a processing summary to Excel, and keeps an audit trail.

> No numbers in this application are hard-coded or estimated from images. Where the drawings do not contain a value, the system shows **"Not available"** and flags the item. Assumptions are listed separately from measured values.

---

## Run it on a clean Windows machine

1. **Install Python 3.10 or newer** from <https://www.python.org/downloads/>. During setup tick **"Add python.exe to PATH"**.
2. Copy this folder (`Static-Group-QTO`) anywhere, e.g. `D:\Static-Group-QTO`.
3. Make sure the drawing folder exists. By default the villa project points at
   `D:\Mr. Ramzi T A Mari Villa Construction Works Villa  (DXF Drawings Files)` (note the double space in the name).
   If the drawings are elsewhere, edit `source_folder` in `config\projects.json`.
4. Double-click **`run.bat`** (or in a terminal inside the folder type `.\run.bat` or `npm run dev`). The first start creates a virtual environment and installs the dependencies (internet access is needed once). A black server window stays open - keep it open - and after a few seconds your browser opens **<http://127.0.0.1:8765>**. Close the black window to stop the app.
   * In a terminal, type `.\run.bat`, not `run.bat` - some Windows setups refuse to run programs from the current folder without the `.\`.
   * If the browser says "can't be reached", wait 5 seconds and refresh.
5. In the app, open **Processing** → **Run processing**. Scanning all 80 files takes about 3 minutes; the screen shows each stage as the server completes it.

Manual alternative (PowerShell):

```bash
python -m pip install -r requirements.txt
```

```bash
python -m uvicorn server.app:app --port 8765
```

Command line (no UI):

```bash
python qto_cli.py run
```

```bash
python qto_cli.py export --out samples
```

Tests:

```bash
python -m pytest -q
```

## What is in the folder

| Path | Purpose |
|---|---|
| `qto/ingest` | DXF loading (ezdxf, recover mode), units, flattening of blocks/xrefs, viewer geometry |
| `qto/classify` | Rules engine: drawing roles, layer/text/block rules from `config/rules_*.json` |
| `qto/extract` | Schedule tables (ACAD_TABLE), column-schedule grid, section-detail dimensions, level tags |
| `qto/elements` | Element builders: footings/rafts/blinding, columns/walls, beams/pedestals, slab zones |
| `qto/calc` | **The only place quantities are computed** (formulas, substitutions, provenance) |
| `qto/boq` | BOQ generation, import + column mapping, comparison / variance |
| `qto/review` | Review queue |
| `qto/export` | Excel exports |
| `qto/ai` | Optional AI layer (explanations/search only – never measurements) |
| `qto/pipeline.py`, `qto/build.py` | Stage orchestration (full scan and fast recalculation) |
| `server/app.py`, `web/` | FastAPI backend + single-page web UI (no build step) |
| `config/` | Projects, rules (per CAD standard), default settings |
| `data/` | Runs, cached viewer geometry, BOQ imports, overrides, review decisions, audit log |
| `docs/` | Architecture, extraction, methodology, limitations, demo script, inspection and validation reports |
| `samples/` | Sample exported BOQ / variance / review / processing reports and the synthetic **test** BOQ |
| `tools/make_test_boq.py` | Builds the clearly-labelled synthetic test BOQ used to demonstrate the comparison |

## Historical projects, BOQ knowledge model and benchmark (phase 2 of the platform)

Three projects are registered in `config/projects.json`:

| Project | Role |
|---|---|
| Ramzi villa | drawings only (no BOQ supplied) – extraction reference |
| Al-Kawari villa | drawings + Static Group BOQ QUO-SCC-1525-2026 – benchmark |
| Al-Sulaiti villa | drawings + Static Group BOQ QUO-SCC-1509-2026 – benchmark |

* `config/knowledge/static_boq_model.json` – the **Static Group BOQ knowledge model**: 57 canonical items learned from
  the historical BOQs (wording, unit, drawing sources, measurement method, formula, automation status).
* `python qto_cli.py run --project kawari-villa` then `python qto_cli.py benchmark --project kawari-villa` – processes the
  drawings and compares every quantity with Static Group's own figure (Exact / Within tolerance / Difference / Unable
  to calculate). In the app: **Historical Benchmark** and **Knowledge / Rules** pages.
* Read first: [docs/HISTORICAL_PROJECT_ANALYSIS.md](docs/HISTORICAL_PROJECT_ANALYSIS.md),
  [docs/BOQ_KNOWLEDGE_MODEL.md](docs/BOQ_KNOWLEDGE_MODEL.md), [docs/GAP_ANALYSIS_AND_ROADMAP.md](docs/GAP_ANALYSIS_AND_ROADMAP.md).

## Phase 3 – methodology rules, Static Group BOQ, management layer

* **Methodology rules** (`config/knowledge/methodology_rules.json`): 22 measurement conventions, each CONFIRMED /
  INFERRED / ASSUMED / UNKNOWN. An UNKNOWN rule never produces a measured quantity – the item shows one candidate per option.
  **Rule Approval** page: approve / reject / edit / note, with the quantity each option gives on every project;
  approvals are versioned, audited and trigger recalculation + benchmark of all projects.
* **Calculators** for block work, plaster, lintels, earthworks, waterproofing, manholes, tanks and boundary wall
  (tanks / boundary wall / ground level from the **Project Inputs** page – never assumed).
* **Static Group BOQ** page and `static-boq` Excel export in the company's own section structure with
  Calculated / Estimated / Missing / Needs Review / Lump Sum / Excluded status, rule status, source and confidence;
  client-BOQ lines that match no known item are shown as "New BOQ item detected".
* **Historical Benchmark**: line by line with rules, missing information and "why is this line different?";
  reconciliation notes are stored as knowledge.
* **New Project**: create, upload drawings / schedules / specifications / client BOQ, process, review, export.
* **Management Dashboard** (`#/ceo`) with a data-only **assistant** (citations, no measurement, no LLM memory;
  offline by default), **daily report** (`python qto_cli.py daily-report`), **Revision Changes** between runs.
* Read: [docs/GAP_ANALYSIS_AND_ROADMAP.md](docs/GAP_ANALYSIS_AND_ROADMAP.md), [docs/AI_AND_MANAGEMENT.md](docs/AI_AND_MANAGEMENT.md).
* Tests: 84 (49 existing + 35 phase 3), all passing.

## Documentation

* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) – layers, data flow, extension points, roadmap hooks
* [docs/INSPECTION_REPORT.md](docs/INSPECTION_REPORT.md) – Phase 1: what the DXF files actually contain
* [docs/DATA_EXTRACTION.md](docs/DATA_EXTRACTION.md) – how each element type is found and measured
* [docs/CALCULATION_METHODOLOGY.md](docs/CALCULATION_METHODOLOGY.md) – formulas, conventions, variance rules
* [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)
* [docs/DEMO.md](docs/DEMO.md) – the 5-minute demonstration script
* [docs/VALIDATION_REPORT.md](docs/VALIDATION_REPORT.md) – results on the real drawings, accuracy checks, test counts
* [docs/HISTORICAL_PROJECT_ANALYSIS.md](docs/HISTORICAL_PROJECT_ANALYSIS.md), [docs/BOQ_KNOWLEDGE_MODEL.md](docs/BOQ_KNOWLEDGE_MODEL.md) (57 items + 22 rules, generated), [docs/GAP_ANALYSIS_AND_ROADMAP.md](docs/GAP_ANALYSIS_AND_ROADMAP.md)
* [docs/AI_AND_MANAGEMENT.md](docs/AI_AND_MANAGEMENT.md) – assistant, dashboard, daily report, change detection

## About the BOQ data

No Bill of Quantities was supplied for this project. Until one is imported the app shows **"BOQ not provided"**. To demonstrate the comparison engine, `samples/TEST_BOQ_SYNTHETIC_NOT_REAL.xlsx` was generated from the drawing quantities with documented, deliberate changes. It is labelled as synthetic on every sheet, in the import dialog, on the dashboard and in every export. **It is not Static Group data.**

## Optional AI

AI is off by default; the assistant then answers deterministically from application data (no data leaves the machine). To let Claude (`claude-opus-5-5`) phrase answers, `pip install anthropic`, sign in (`ANTHROPIC_API_KEY` or `ant auth login`) and set `"ai": {"enabled": true}` in `config/settings.json`. Claude then receives project data **through the same data tools only**, is instructed never to compute or estimate quantities, and every answer still carries citations. See docs/AI_AND_MANAGEMENT.md.
