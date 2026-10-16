# Data extraction – how each element is found and measured

All conventions below were **derived from the files** (see INSPECTION_REPORT.md) and are stored in
`config/rules_ramzi_villa.json`. Units: every structural file has `$INSUNITS = 6` (metres), confirmed against dimension
entities (a 200 mm column face measures 0.200).

## Drawing roles

| Role | File | Used for |
|---|---|---|
| Foundation plan | `S-FP.dxf` | footing / raft / blinding outlines, footing tags, raft tags, T.O.F levels |
| Foundation details | `S-FD.dxf` | footing schedule tables (2 × ACAD_TABLE), tie-beam section details, blinding note |
| Column schedule | `S-CD.dxf` | "SCHEDULE OF COLUMNS" grids (column mark × floor, drawn sections) |
| Column layouts | `S-CP- BS/GR/L1/PH.dxf` | column and wall outlines per floor (bound xref `X-CO-<floor>`), C/PC/W tags |
| Framing plans | `S-FR-GR/L1/PH/TOR.dxf` | beam outlines + labels, slab boundary linework (`X-LOS-<floor>`), slab thickness and level tags, pedestals |
| Beam schedule | `S-BD01.dxf` | 4 × ACAD_TABLE beam schedules (mark, span, width, depth) |

The other 61 files (architectural, mechanical, electrical, general structural) are opened and inventoried; no quantity rule
applies to them in this MVP.

## Footings (S-FP + S-FD)

* **Instances:** closed polylines on `S-FNDN-FTNG` (15). Identical outlines are detected and excluded as duplicates.
* **ID:** MTEXT tags matching `^C?F\d+$`. In this drawing set they sit on layer `S-FRAM-BEAM-ATXT`, so the *text pattern*
  identifies them. Pairing: one-to-one, nearest first (0 m if inside the outline), max 2.5 m.
* **Length/Width:** long/short side of the drawn rectangle (rotation-independent). **Plan area:** shoelace polygon area
  (irregular outlines are never approximated as rectangles).
* **Thickness:** `D (mm)` column of the footing schedule table row for that mark. ACAD_TABLE content is rebuilt from the
  table's anonymous `*T` block: texts clustered into rows (Y) and columns (X).
* **Cross-check:** drawn W×L vs schedule W×L (±11 mm).
* **Rafts:** a footing-layer outline containing an `Iden-Slab Thickness` block with `SLAB_TYPE=RAFT`; thickness from its
  `SLAB_THICKNESS` attribute. IDs `RAFT-n` are system-generated (not numbered on the drawing).
* **Blinding:** closed polylines on `S-BLND-BNDY`, each linked to the footing/raft it encloses; thickness from the note
  "100mm BLINDING CONCRETE" on S-FD (12 occurrences). ID `BL-<footing>`.

## Columns and RC walls (S-CP-* + S-CD)

* **Instances per floor:** closed polylines on base layer `X-CO-COLS-OTLN` inside the bound xref block `X-CO-<floor>`
  (layer names like `X-CO-GR$0$X-CO-COLS-OTLN`; the engine uses the part after the last `$`). Blocks are expanded with
  ezdxf `virtual_entities()`; handles reported are those inside the block definition.
* **ID:** TEXT on `S-COLS-ANNO-TEXT` matching `^P?C\d+$` (C1–C18, PC1–PC5), nearest one-to-one ≤ 1.2 m.
* **Section:** measured from the outline. **Cross-check** against the column-schedule cell (mark, floor): the schedule
  on S-CD is a drawn grid – marks across the top, floor names (`BASEMENT FLOOR`…`PENTHOUSE FLOOR`) down the side, a closed
  section polyline on `S-ELEV` in each cell. 48 cells for 23 column types were read.
* **Height:** see CALCULATION_METHODOLOGY (from level tags; flagged "confirm" until an engineer confirms).
* **Walls:** closed polylines on `X-CO-WALL-RCNC`, tagged W1/W2 (tags within 1 m; several tags may surround one wall).

## Beams and pedestals (S-FR-* + S-BD01 + S-FD)

* **Instances:** closed polylines on `S-FRAM-BEAM-HIDD`. Rectangles with aspect ≥ 2 are beams (long side = clear span
  drawn between supports, short side = width). Elongated non-rectangular outlines are irregular beams (volume from polygon
  area). Squares matching a `PEDESTAL` / `500X500X500 MM` note within 2 m are pedestals.
* **Labels** on `S-FRAM-BEAM-ATXT` are written along the beam edge. A label is attached to a beam only if its rotation
  matches the beam axis (±10°), its centre lies within the beam's length, and its perpendicular offset from the edge is
  ≤ 0.45 m. Mark pattern `L1B6-2` = beam L1B6 span 2; size pattern `B200X600`; remarks `INVERTED`…
* **Depth**, per beam family (rules file):
  * L1B/PHB/TORB/GRB → beam schedule row (mark, span) from S-BD01 ACAD_TABLEs (56 rows);
  * T.B (tie beams) → largest vertical DIMENSION in the "TYPICAL SECTION THROUGH T.B.n" detail on S-FD;
  * fallback → plan size label (flagged "depth from label");
  * C.B → no schedule entry → Missing data.
* **Cross-checks:** drawn width vs schedule width; drawn width vs plan size label; plan label depth vs schedule depth.
* **Overlaps** between beam outlines are measured and flagged (junction overlaps are small and reported as Check).

## Slabs (S-FR-*)

There are no closed slab polygons in the drawings. Zones are **reconstructed** by polygonising the slab boundary
linework (`X-LOS-SLAB-BNDY` in the `X-LOS-<floor>` xref). Each zone takes its thickness from the
`Iden-Slab Thickness` tags inside it:

* one distinct thickness → volume calculated;
* several distinct thicknesses → the zone is split along beam outlines; untagged slivers (< 2 m²) are grouped into a
  residual zone; anything still ambiguous is flagged **Review Required** (never averaged);
* no tag → **Missing thickness**; a tag lying ≤ 0.75 m outside the zone is offered as a *suggestion* that the engineer
  can accept in the Review Queue (recorded as User input).

Shafts (`X-LOS-SLAB-SHAFT` closed outlines) inside a zone are deducted; zones that are entirely shafts are dropped.
Zone IDs (`GR-S05`…) are system-generated.

## Levels

`Iden-Level Plan` blocks carry `%%P0.000` (value) and `F.F.L.` (kind: T.O.S / T.O.F). For each floor the most frequent
value of the required kind on its drawing is used; ties are resolved to the lowest value and flagged. All candidate
values are shown in Settings.

## Robustness

* `ezdxf.recover` fallback for damaged files; per-entity try/except; files that fail are reported, processing continues.
* Unsupported entity types (HATCH, IMAGE, WIPEOUT, OLE, 3D solids …) are counted per file in the processing summary.
* Nested blocks up to 4 levels; deeper nesting is logged.
* Duplicated geometry is detected (same vertices within 2 mm) and excluded with a flag.
* Unknown layers: closed outlines on unrecognised layers in role drawings are counted (`unclassified_layers`).
* Labels that cannot be attached to geometry and outlines that match no rule appear in the Review Queue.
