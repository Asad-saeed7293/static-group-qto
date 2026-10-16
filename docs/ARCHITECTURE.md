# Architecture

## Layers (each independently testable)

```
DXF folder
  │  qto/scan.py            list files, per-file scan, never stops on one bad file
  ▼
1 Ingestion      qto/ingest/dxf_reader.py   ezdxf (+recover), $INSUNITS→metres, flatten model space incl. nested
                                            blocks & bound xrefs (virtual entities, depth ≤ 4), unsupported-entity log,
                                            render-ready viewer geometry
2 Geometry       qto/geometry.py            shoelace area, rectangle detection (rotated), duplicates, distances
3 Classification qto/classify/rules.py      drawing role (file pattern), layer/text/block rules → candidates ("facts")
                 config/rules_<project>.json  ← the CAD standard lives here, not in code
4 Extraction     qto/extract/tables.py       ACAD_TABLE decoding (rebuilt from the table's *T block)
                 qto/extract/schedules.py    footing & beam schedules, column-schedule grid, section-detail depths,
                                             level tags, blinding note
5 Elements       qto/elements/*.py           pairing labels↔geometry, cross-checks, flags, provenance
6 Calculation    qto/calc/engine.py          the ONLY place quantities are computed (formula + substitution + inputs)
7 BOQ            qto/boq/generate.py         BOQ lines grouped by type/mark/floor, traceable to instances
                 qto/boq/importer.py         XLSX/CSV, header detection, user-confirmed column mapping
                 qto/boq/compare.py          matching, variance, configurable tolerances, statuses
8 Review         qto/review/queue.py         one queue for element, comparison and drawing-level issues
9 Persistence    qto/store.py                JSON on disk per project/run, overrides, decisions, audit log (JSONL)
10 Presentation  server/app.py + web/        FastAPI + vanilla JS SPA; qto/export/excel.py for Excel
   AI (optional) qto/ai/explain.py           wording/search on top of the evidence; never touches numbers
```

`qto/pipeline.py` runs stages 1–8 with observable progress. Stages 4–8 (`qto/build.py`) work only on the stored
*facts*, so a user correction (storey height, slab thickness, tolerance, convention) recalculates in about a second
without re-reading the 80 DXF files. Each recalculation is a new run and is audit-logged.

## Data model

* **Measurement** – value, unit, *source* (CAD geometry / schedule table / plan label / section dimension / level tag /
  slab tag / user input / not available), human-readable detail, CAD reference, `is_assumption`.
* **Element** – uid, type, mark (drawing ID), floor, drawing, layer, polygon, dims (Measurements), sources (SourceRefs with
  handles), cross-checks, flags, confidence.
* **QuantityRecord** – one per element and quantity type: formula, substitution, inputs, assumptions, status.
* **BOQ line** – grouping of quantity records; keeps `element_uids`/`qids` so every BOQ number drills down to entities.
* **Comparison row** – BOQ row ↔ BOQ line(s), variance, tolerance status, reasons.

## Multi-project

`config/projects.json` lists projects (name, DXF folder, rules file). Each project has its own `data/projects/<id>/`
(runs, cache, BOQ imports, overrides, decisions, audit log). New projects can be added in Settings; a different
consultant's CAD standard is supported by copying and editing the rules file.

## Extension points / roadmap

| Future capability | Where it plugs in |
|---|---|
| PDF / scanned drawings / OCR | New ingestion adapter producing the same `FlatEntity` list (vector PDF → paths/text; raster → OCR text + vectorised lines). Everything downstream is unchanged. |
| DWG | Convert with ODA File Converter to DXF, then the existing reader. |
| IFC / Revit / BIM | An adapter that emits `Element`s directly (BIM already carries element type and dimensions); calculation, BOQ, comparison, review and UI are reused. |
| AI drawing classification | A classifier proposing rules for unknown layers/blocks (inspection report already lists unclassified layers); proposals go into the rules file after human approval. |
| Automatic BOQ mapping | `compare.match_rows` already has a description-similarity *suggestion* path; an LLM matcher can replace it, results remain suggestions marked "confirm". |
| Rebar, formwork, masonry, finishes | New element builders + calculators; formwork areas follow from the same geometry (perimeter × depth). |
| Cost estimation / pricing / tender comparison | Rate tables joined to BOQ lines by category/description. |
| Revision change detection | Runs are immutable snapshots; diffing two runs' elements by mark/floor/geometry gives added/removed/changed items. |
| Historical comparison | Same, across projects (quantities per m² of GFA etc.). |
