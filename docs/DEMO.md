# 5-minute demonstration script

Before the meeting: run `run.bat`, open <http://127.0.0.1:8765>, make sure a processing run exists and the test BOQ is
imported (BOQ page → upload `samples/TEST_BOQ_SYNTHETIC_NOT_REAL.xlsx`, accept the suggested mapping, keep
"This is a TEST BOQ" ticked). Use a wide screen (≥ 1400 px).

| # | Step | Where | What to say |
|---|---|---|---|
| 1 | Open the project | **Dashboard** | "This is the Ramzi villa, loaded from the consultant's own DXF files – 80 drawings, every discipline." Point at drawings processed, elements detected, calculated concrete, verified / review / missing counts. Point at the red **TEST BOQ** banner: the BOQ is synthetic, for the demo only. |
| 2 | Show the drawings | **Drawings** | Filter "Only drawings used for quantities". Units, entity counts, and the elements extracted from each file. |
| 3 | Show that the system scans the real files | **Processing** | Click **Run processing** (or show the previous run). Each stage turns green as the server finishes it; the log shows each DXF file being opened. ~3 minutes for 80 files – start it and continue, or use "Structural only". |
| 4 | Detected elements | **Quantity Takeoff** | Tabs: Footing, Raft, Blinding, Column, RC wall, Beam, Slab, Pedestal. Footings are all *Verified*: drawn size = schedule size. |
| 5 | Open one element | click **F3** | Evidence drawer opens. |
| 6 | Exact CAD source | Identification card | Drawing S-FP.dxf, layer S-FNDN-FTNG, LWPOLYLINE handle, tag MTEXT. Click **Show on drawing** – the viewer zooms to the highlighted footing; toggle layers, zoom, pan. |
| 7 | Extracted dimensions | "Where each number came from" | Length/width from CAD geometry, depth 450 mm from the footing schedule table row F3 on S-FD. |
| 8 | The calculation | Calculation card | `L × W × D = 2.600 × 2.200 × 0.450 = 2.574 m³`. |
| 9 | Calculated quantity | BOQ comparison card | Generated BOQ item 02.xx. |
| 10 | Compare against BOQ | **Variance Analysis** | Status bar, by-category table, tolerance bands (configurable). |
| 11 | Show variance | sort by *Var %* | e.g. a −8.24 % row = Review Required; +3.5 % = Check; ±0 = Verified. |
| 12 | Flag a mismatch | filter *Review Required* | Unit mismatch row, BOQ item "LPW1" not in drawings, drawing items missing from BOQ. |
| 13 | Open the review item | **Review Queue** | Open **Column C7 – GR**: "Plan column size differs from schedule" (plan 300×600, schedule 250×600) – a real inconsistency in the consultant's drawings. Also show **PHB7** (beam drawn 200 wide, scheduled 300). |
| 14 | Why it was flagged | review drawer | The explanation states both values and their sources. Show a slab zone with a *suggested* thickness: the engineer enters/accepts it → recorded as **User input**, audit-logged, quantities recalculated. In **Settings**, confirm a storey height → columns move from *Check* to *Verified*. |
| 15 | Export | **Reports & Audit** | Download *Generated BOQ* (with Calculation Detail sheet: formula, substitution, layer, handle for every quantity) and *Variance report*. Show the audit trail. |

Key messages: numbers come from the CAD geometry and the consultant's own schedules; nothing is guessed; every number is
traceable to a drawing entity; when the drawings are incomplete or inconsistent, the system says so.
