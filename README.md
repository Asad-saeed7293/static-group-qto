<div align="center">

# 📐 QTO & BOQ Automation

**Turn a folder of CAD drawings into a priced, audit-ready Bill of Quantities — automatically.**

[![Tests](https://img.shields.io/badge/tests-176%20passing-2e8b57)](#tests)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![No framework, no build step](https://img.shields.io/badge/frontend-vanilla%20JS-F7DF1E?logo=javascript&logoColor=black)](#-what-is-in-the-folder)

</div>

---

Quantity surveying on a real villa project means opening dozens of DXF/DWG files by hand,
measuring footings and beams one by one, and re-typing it all into a spreadsheet in the exact
layout your company already uses. This project automates that — not by guessing, but by actually
reading the drawings.

It scans every drawing, finds the structural and architectural elements on it, measures them
from the real geometry, and produces a Bill of Quantities in your company's own historical
format — same sheets, same header block, same numbering convention a QS would recognize on
sight.

**The one rule everything else follows:** if the drawings don't support a number, the line says
**Missing**. Nothing is ever estimated, hard-coded, or quietly filled in to make the output look
complete.

> This repo is a sanitized public copy of a system originally built for one construction
> company's internal use. Real client data has been stripped out — see
> [What isn't in this repo](#-what-isnt-in-this-repo).

---

## What it actually does

1. **Reads the drawings.** Every DXF — and native DWG, converted on the fly via the free ODA
   File Converter — across every discipline, scanned for layers, blocks, text and units.
2. **Finds the elements.** Footings, rafts, blinding, columns, RC walls, beams, tie beams,
   pedestals, slabs — identified with a configurable, per-CAD-standard rules file, not hard-wired
   to one drawing set.
3. **Measures them for real.** Dimensions, depths and levels come from the drawing's own
   geometry, schedules, sections and tags — never from a human squinting at a PDF.
4. **Calculates with a paper trail.** Every quantity has a formula and a CAD source. The
   calculation engine is deterministic and independently tested — same input, same output, every
   time.
5. **Builds the BOQ.** Generates a Bill of Quantities, can import an existing one for comparison
   (column-mapped, tolerance-checked), and flags anything questionable in a review queue with
   full evidence — drawing, layer, entity handle, schedule row, formula.
6. **Exports what a QS actually needs.** A priced-format Excel workbook, a tender-ready PDF, a
   variance report, a drawing-revision diff, and a full audit trail of who decided what and when.

## ✨ What makes this more than a BOQ generator

| | |
|---|---|
| 🧾 **Exact format matching** | The output mirrors a real company's historical BOQ layout down to the numbering convention — section codes only on heading rows, plain item numbers that reset per section. |
| 👀 **Preview before you export** | See every sheet, heading and number exactly as the download will look, without leaving the browser. |
| 📄 **Tender-ready PDF** | A client-facing PDF built from the same data as the Excel file, so the two can never quietly drift apart. |
| 💰 **Rate memory** | Re-import a priced BOQ once, and the app remembers those real rates — future projects see them as a clearly-marked *suggestion*, never a silent confirmed price. |
| 📊 **Cost benchmarking** | Compares indicative cost per m² across projects, built only from real rate history, honest about how much of each project is actually priced yet. |
| 🔄 **Drawing-revision diffs** | Compares two processing runs and reports exactly what changed — added, removed, modified — as a shareable report. |
| ⚖️ **A rules engine with a memory** | Every measurement convention ("do we deduct openings from wall area?") is a versioned, auditable rule. An undecided rule shows every candidate answer instead of picking one — and a rule can only ever become CONFIRMED through one explicit, attributable approval action. |
| 🗂️ **Folder upload, not file-by-file** | Point it at a whole folder of scattered drawings and it recursively finds everything, preserving subfolder structure so two files named the same thing in different disciplines never collide. |

## Getting started

```bash
git clone <this repo>
cd Static-Group-QTO
python -m pip install -r requirements.txt
python -m uvicorn server.app:app --port 8765
```

Open **http://127.0.0.1:8765**, point a project's `source_folder` in `config/projects.json` at
your own drawing folder (the three seeded entries use placeholder paths), and hit
**Processing → Run processing**.

No build step, no JavaScript framework, no Node toolchain for the frontend — it's a single static
page served by the same FastAPI app that runs the backend.

<details>
<summary><strong>Command line, no UI</strong></summary>

```bash
python qto_cli.py run
python qto_cli.py export --out samples
```

</details>

### Tests

```bash
python -m pytest -q
```

176 tests, covering the measurement engine, the rules engine, every export format, the import
pipeline, and the handful of path-safety and approval-bypass edge cases that only show up once
you go looking for them.

## 🗺️ What is in the folder

| Path | Purpose |
|---|---|
| `qto/ingest` | DXF/DWG loading (ezdxf, ODA File Converter, recover mode), units, block/xref flattening, viewer geometry |
| `qto/classify` | Rules engine for drawing roles — layer/text/block rules from `config/rules_*.json` |
| `qto/extract` | Schedule tables, column-schedule grid, section-detail dimensions, level tags |
| `qto/elements` | Element builders: footings/rafts/blinding, columns/walls, beams/pedestals, slab zones |
| `qto/calc` | **The only place quantities are computed** — formulas, substitutions, provenance |
| `qto/boq` | BOQ generation, import + column mapping, comparison / variance |
| `qto/knowledge` | Methodology rules engine, rate memory, BOQ knowledge model, benchmarking |
| `qto/review` | Review queue |
| `qto/export` | Excel and PDF exports |
| `qto/ai` | Optional AI layer — explanations and search only, never measurements |
| `qto/pipeline.py`, `qto/build.py` | Stage orchestration: full scan and fast recalculation |
| `server/app.py`, `web/` | FastAPI backend + single-page web UI |
| `config/` | Projects, rules (per CAD standard), default settings, BOQ knowledge model |
| `tests/` | The full test suite |
| `samples/` | Sample exported reports and a clearly-labelled synthetic test BOQ |

## 🔒 What isn't in this repo

This is a sanitized public copy. Left out on purpose:

- `data/` — real client project runs, drawing metadata, audit logs, cached geometry.
- Real project and client names in `config/projects.json` — replaced with generic placeholders
  (`Reference Villa A/B/C`, `[redacted]`).
- Internal docs, scratch notes and presentation decks that named real clients.

The three seeded project IDs (`ramzi-villa`, `kawari-villa`, `sulaiti-villa`) are kept only
because the codebase's tests and examples already reference them — once the fields above are
redacted, they carry no name or address on their own.

## 🤖 Optional AI

AI is off by default; the built-in assistant answers purely from the app's own data, with no
data leaving the machine. Flip it on with `"ai": {"enabled": true}` in `config/settings.json`
and the relevant API key, and it still only *phrases* answers pulled through the same data tools
the app itself uses — it's instructed never to compute or estimate a quantity, and every answer
still carries a citation back to source.

---

<div align="center">
<sub>Built for quantity surveyors who'd rather trust a number than guess one.</sub>
</div>
