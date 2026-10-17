# QTO & BOQ Automation

A drawing-led quantity takeoff and bill of quantities workspace for civil engineers, quantity surveyors, estimators and construction teams. Bring a project’s drawing folder into one place, review what the system found, trace quantities back to source drawings, and prepare BOQ outputs for engineering review.

## Built for construction takeoff workflows

- **Project folder intake:** upload a complete project folder. The app sorts supported files into drawings, schedules, specifications, client BOQs and reference documents, then starts processing when CAD drawings are present.
- **CAD drawing processing:** read DXF drawings and their layers, blocks, text, units and geometry. DWG conversion is available when the ODA File Converter is installed on the server.
- **Engineering schedules and project inputs:** use drawing schedules, notes, dimensions, levels and confirmed project inputs to support takeoff calculations.
- **Measured quantities with evidence:** inspect detected elements and quantities with source drawing, layer, entity and calculation details. Missing information and assumptions are surfaced for review rather than silently filled in.
- **Civil and structural takeoff:** includes supported calculators for foundations, columns, walls, beams, slabs, blockwork, plaster, lintels, earthworks, waterproofing, manholes, tanks and boundary walls. Coverage depends on the drawing content and configured measurement rules.
- **BOQ preparation and comparison:** generate detailed BOQ lines, import an existing client BOQ for comparison, review variances, and export Excel reports. A reference BOQ template can be used where configured.
- **Review and methodology controls:** resolve missing inputs, inspect candidate quantities, approve project measurement rules, and retain review decisions and audit history.
- **Drawing viewer and structural 3D view:** inspect drawings and explore a generated structural model with floor and element filters, fit-to-view, zoom controls, orbit and pan.
- **Project tracking:** see processing status, BOQ readiness, open review items, changes between runs, and project reports in one workspace.
- **Data-grounded assistant:** ask about stored project records and receive answers with sources. The assistant does not measure drawings or invent quantities.

## Measurement integrity

The quantity engine uses drawing geometry and recorded inputs; it does not claim to measure quantities from scanned images. A generated 3D view is a visualization of supported takeoff elements and inferred placements, not a coordinated BIM model or a design-authoring model. Engineers and quantity surveyors should review flagged items, assumptions and measurement rules before issuing a BOQ.

PDF, Word and other reference documents can be stored with a project. Their content is not automatically measured; supported DXF schedules and spreadsheets can be used as inputs. DWG measurement requires a compatible ODA conversion installation.

## Run on Windows

1. Install Python 3.10 or newer.
2. Open this project folder and run `run.bat` (or `npm run dev`). The launcher creates the environment and starts the local web app.
3. Open <http://127.0.0.1:8765> and create or select a project.
4. Upload the complete project folder or add files by category, review the intake summary, then process the drawings.

The app uses a local FastAPI server. Project files and processing records are kept in the local `data/` directory. For DWG support, install ODA File Converter on the machine running the server.

## Main areas

| Area | Purpose |
|---|---|
| `server/app.py` | FastAPI endpoints, file intake, project workflows and exports |
| `qto/ingest`, `qto/extract` | CAD loading, drawing extraction and schedule reading |
| `qto/elements`, `qto/calc`, `qto/takeoff` | Element detection, measurement and BOQ quantity calculations |
| `qto/boq`, `qto/export` | BOQ generation, comparison and report exports |
| `qto/knowledge`, `qto/review` | Measurement rules, project references and engineering review |
| `qto/viewer3d.py`, `web/model3d.js` | Structural 3D model data and interactive viewer |
| `web/` | Browser interface (no front-end build step) |
| `config/` | Application settings, rules and BOQ configuration |
| `data/` | Local project files, runs, caches, decisions and audit records |

## Command line

```powershell
python -m pip install -r requirements.txt
python -m uvicorn server.app:app --port 8765
```

For command-line processing and exports:

```powershell
python qto_cli.py run
python qto_cli.py export --out samples
```

## Configuration and project data

Keep project drawings, client BOQs, credentials and other confidential project information in local storage. The `data/` directory is runtime data; do not commit live project uploads or customer records to a public repository. Configure measurement rules and any reference BOQ template for your own organization before using exports in a live tender or contract.
