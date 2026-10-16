# Gap analysis and roadmap – Static Group BOQ platform

Status at the end of phase 3 (2026-10-08). The Static Group BOQ knowledge model has **57 canonical items**
(BOQ_KNOWLEDGE_MODEL.md). Measurement conventions are **22 methodology rules**, each with a status:

| Status | Meaning | Rules today |
|---|---|---|
| CONFIRMED | Static Group evidence or estimator approval | 0 – no estimator has answered yet |
| INFERRED | repeated pattern in both historical projects, not confirmed | 3 (footing volume, ground-beam volume, removal = excavation) |
| ASSUMED | temporary development rule | 1 (storey level = most frequent level tag per floor) |
| UNKNOWN | cannot be determined from the data – no option is used | 18 |

An UNKNOWN rule never produces a measured quantity. The item shows one **candidate per option** and the status
"Needs Review" (tank and boundary-wall values typed in by the estimator are shown, but stay "Needs Review" until
the geometry-source rule is approved). When an estimator approves an option on the **Rule Approval** page, every project is recalculated,
the benchmark re-run, and the change versioned (who, when, before/after, comment) and audited.

## 1. Coverage against the knowledge model

| BOQ area | Items | Phase 2 | Phase 3 (now) |
|---|---|---|---|
| Sub/super-structure concrete | footings, blinding, ground beams, SOG, columns & walls, beams, slabs | measured | measured; blinding, column height and beam depth are UNKNOWN rules with candidates per option |
| Neck columns | 1 | outlines extracted | candidates `tof_to_sog_top` / `tof_to_gb_soffit` from level tags; "Missing" when no outlines (Ramzi has a basement) |
| Earthworks | excavation, removal, backfill | modelled | candidates per working space (0 / 0.3 / 0.5 / 1.0 m); natural ground level is a **project input** (never assumed); removal = excavation (INFERRED) |
| Waterproofing | substructure H/V | modelled | candidates `sides_and_tops` / `sides_only` from drawn footing / ground-beam surfaces only |
| Block work | per wall type, external/internal | modelled | walls measured from A-WALL hatches (thickness from area/perimeter, composite stacks, external = on building outline); gross area per height option; opening deduction is a separate UNKNOWN rule |
| Plaster | external, internal | modelled | derived from wall faces (outer / both / inner faces) per height option; staircase soffit flagged as missing |
| Lintels | 1 | source layer found | candidates: detected openings × bearing 0.15 / 0.20 / 0.25 m, and `BA Lintels` line length; opening detection flagged as partial |
| Services | drainage / rainwater manholes, soakaway, electrical manholes | counts modelled | symbol/label counts as candidates (block-name and label patterns in rules files) |
| Tanks | 6 | not covered | calculated from estimator-entered tank sizes (Project Inputs page); "Missing" until entered |
| Boundary wall | 13 | not covered | calculated from estimator-entered length + typical section; plot-boundary polyline offered as length evidence |
| Lift walls, steps, fillet, plinth, staircase, planters, landscape | 9 | not covered | listed as "Needs Review" with the reason; no automated extraction yet |
| Lump sums / exclusions | 13 | recognised | unchanged – never given a fabricated quantity |

New platform capabilities in phase 3: rule configuration engine and approval UI with per-project impact; Static
Group BOQ template output (sections A–F, codes, calculation status, rule status, source, confidence, review status,
"New BOQ item detected"); line-by-line benchmark with "why is this line different?" diagnostics and reconciliation
notes; new-project workflow (create, upload drawings / schedules / specifications / client BOQ, process, review,
export); revision change detection with BOQ impact (implemented; not yet validated on a real revised drawing set); data-only AI assistant with citations; management dashboard;
daily report with issue snapshots; 35 new tests (84 in total, all passing).

## 2. Benchmark today

Measured historical lines (Al-Kawari 56, Al-Sulaiti 61):

| Result | Al-Kawari | Al-Sulaiti |
|---|---|---|
| Within Tolerance (≤5 %) | 1 (ground beams +1.2 %) | 1 (footings −4.4 %) |
| Difference | 2 (footings −9.2 %, slabs −34.5 %) | 1 (ground beams −90.5 %) |
| Candidates Only (rule UNKNOWN) | 24 | 24 |
| Unable to Calculate | 29 | 35 |

"Candidates Only" lines are **not** compared as if they were results. The closest candidate is reported as an
observation, never as a conclusion, for example:

| Item | Al-Kawari closest candidate | Al-Sulaiti closest candidate | What it may indicate (not decided) |
|---|---|---|---|
| Columns & walls | floor_to_floor −17.9 % | floor_to_floor −18.4 % | systematic gap beyond the height rule – e.g. roof/pergola columns or wall extents |
| Beams | full_depth −38.3 % | below_slab −22.6 % | different closest option per project → the rule alone does not explain it; unlabelled/unscheduled beams |
| Blinding | footings + GB, 0 mm projection | footings + GB, 150 mm projection | blinding under ground beams is likely measured; projection unclear |
| Substructure waterproofing (H) | sides_and_tops −40 % | sides_and_tops +1.7 % | inconsistent between projects |
| Excavation | working space 0.5 m (NGL ±0.00) | working space 1.0 m (NGL ±0.00) | real ground level is missing; Static Group may measure bulk excavation, not pits |
| Electrical manholes | 8 labels vs 3 | 6 labels vs 6 | label count is the right source on one project only |
| Slab on grade | tagged S.O.G. zones +74.8 % | not detected | tagged zones include areas not measured as SOG |
| Block work | per-type −83 % … +266 % | per-type −86 % … +4948 % | annex buildings not measured; wall-type assignment (composite stacks, parapets) still imperfect |

## 3. Open methodology questions

All 18 UNKNOWN and 4 INFERRED/ASSUMED rules are on the **Rule Approval** page, each with its options, the evidence
from both projects and the quantity every option would produce on every project. They replace the question list of
phase 2. The highest-impact ones:

1. Column & wall height (floor-to-floor vs to slab soffit) – SUP-COLW, block work, plaster.
2. Beam depth (below slab vs full depth) – SUP-BEAM.
3. Blinding extent and projection – SUB-BLD.
4. Excavation: ground level source, working space, bulk vs pits – EW-EXC/REM/BF.
5. Block wall height and opening deduction – all BLK items, plaster.
6. Substructure waterproofing surfaces.
7. Lintel bearing.
8. Tank and boundary-wall geometry source (drawings vs typed sizes in the BOQ heading).

## 4. Roadmap

| Phase | Content | Exit criterion | State |
|---|---|---|---|
| 1 | Historical analysis, knowledge model, benchmark harness, multi-project engine | both historical projects processed end to end | done |
| 2 | Structural conventions as rules; neck columns; earthworks, waterproofing, block work, plaster, lintels, services, tanks, boundary wall calculators; rule approval UI; Static Group BOQ output; new-project workflow; change detection; AI assistant; management dashboard; daily report | every item has a calculator, a "Missing" reason or a lump-sum/excluded status; no UNKNOWN rule produces a value | **done (this phase)** |
| 3 | Estimator answers the rule questions on the Rule Approval page | rules CONFIRMED; benchmark re-run automatically | waiting for Static Group |
| 4 | Close extraction gaps the benchmark exposes: annex buildings and parapets in block work, Al-Sulaiti slab boundaries and tie-beam depths, opening sizes from door/window schedules, tank drawings, drainage symbols in xrefs, staircase | structural concrete within 5 % on both projects, or each residual explained | next |
| 5 | Pilot on a live tender: new-project workflow end to end with an estimator timing manual vs system | measured time / accuracy figures | not started |
| 6 | Integrations (email / Teams delivery of the daily report, document management) | only after explicit approval of where project data may go | not started |

Value metrics (time saved, savings) are still not reported: no measured manual-effort baseline exists. The
dashboard and the daily report state this explicitly instead of showing an estimate.
