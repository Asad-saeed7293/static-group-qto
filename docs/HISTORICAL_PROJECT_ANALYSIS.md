# Historical project analysis – the Static Group reference dataset

This is the Phase-1 study requested before redesigning the application. Everything below
was read from the files; nothing was assumed.

## 1. The three projects

| | Ramzi villa | Al-Kawari villa | Al-Sulaiti villa |
|---|---|---|---|
| Folder | `D:\Mr. Ramzi T A Mari Villa …` | `D:\Mr. Abdulrahman Ali M R Al-Kawari Villa` | `D:\Mr. Abdulla Ali J Alsulaiti  Villa Construction` |
| Scope | Villa (B+G+F+PH) + annex | Villa (G+F+PH) + Majlis + Driver's room + Out kitchen + boundary wall | Villa (G+F+PH) + Driver's room annex + boundary wall |
| Location | Huzoom Lusail | Al Daayen (PIN 70312232) | Al Daayen (PIN 70224931) |
| Files | 80 DXF + images/fonts | 236: 80 DXF, 80 DWG, 47 PDF, 24 JPG, 1 XLSX, specs | 155: 80 DXF, 22 DWG, 10 PDF, 4 DWF, 1 ZIP (CAD set), 1 XLSX |
| Issue status | eTransmit set | "IFC – Pricing" | "Pricing" |
| **Static Group BOQ** | **None supplied** | Un-priced BOQ, ref QUO-SCC-1525-2026, 06-Aug-2026 | Un-priced BOQ, ref QUO-SCC-1509-2026, 25-Jul-2026 |
| Built-up area (BOQ summary) | – | 1,343.00 m² (GF 383.51, FF 469.97, PH 256.48, annexes 233.48) | 1,771.26 m² (GF 622.89, FF 738.04, PH 361.12, annex 50.22) |

**Only two of the three projects can be used as validation benchmarks** – the Ramzi folder
contains drawings but no BOQ. Ramzi remains the reference for drawing extraction.

## 2. Drawing sets – same consultant standard

All three sets come from the same structural consultant and share the sheet structure:

| Discipline | Sheets | Notes |
|---|---|---|
| Architectural | A-000 cover … A-1xx floor plans (dimension / furniture / annotation), A-2xx elevations & sections, A-3xx wall sections, A-4xx stair/pergola/skylight details, A-5xx door/window/aluminium schedules | Sulaiti uses long names (`AAS - Construction Drawings-Sheet - A - 101 - …`) and adds tiling, lighting, reflected-ceiling plans and an underground-tanks sheet |
| Structural | General notes/details, **S-FP** foundation plan, **S-FD** foundation details + footing schedule tables, **S-CD** column schedule, **S-CP-GR/L1/PH** column layouts, **S-FR-xx** framing plans, **S-BD01** beam schedule tables, S-BD02, S-SD01, S-PD | Ramzi has a basement (S-CP-BS, S-FR-GR); the new villas have no basement and call the ground framing plan **S-FR-S.O.G** |
| Mechanical | DR-050…601 drainage, WS-050…601 water supply | 2 Al-Kawari annex DXFs (DR-200, WS-200) are corrupt and cannot be opened (reported, not fatal) |
| Electrical | E-050 site, E-100…105 floors, E-700 DB schedule, E-800 SLD | some E-sheets have $INSUNITS = 0 (unitless) |

Units: model space in metres ($INSUNITS 6) everywhere except a few MEP sheets (mm or unitless) – the
engine converts per file.

### Layer / block conventions (structural) and the differences found

| Information | Ramzi | Al-Kawari | Al-Sulaiti |
|---|---|---|---|
| Footing outlines | S-FNDN-FTNG | S-FNDN-FTNG | S-FNDN-FTNG |
| Footing tags | MTEXT on S-FRAM-BEAM-ATXT | text on **S-COLS-ANNO-TEXT** | S-FRAM-BEAM-ATXT |
| Footing schedule | 2 ACAD_TABLEs on S-FD | 2 ACAD_TABLEs (32 types) | 2 ACAD_TABLEs (24 types) |
| Column outlines | xref X-CO-<floor>, layer X-CO-COLS-OTLN | X-CO-COLS-OTLN | xref X-CO-<floor>, layer **A-COLS-OTLN** |
| Column tags | S-COLS-ANNO-TEXT | S-COLS-ANNO-TEXT | **S-FRAM-BEAM-ATXT** |
| Column schedule (S-CD) | section drawn as closed polylines | closed polylines | **plain lines + dimension strings** (no closed outline) |
| Neck columns | – (basement) | column outlines inside X-CO-F xref on S-FP | inside X-CO-FO xref on S-FP |
| Beams | rectangles S-FRAM-BEAM-HIDD | S-FRAM-BEAM-HIDD | S-FRAM-BEAM-HIDD + **S-FRAM-BEAM-INV** (inverted) |
| Tie beams | `T.B1` | `T.B1` | **`T.B.1`** |
| Lintels | – | **BA Lintels** layer on framing plans | **BA - Lintels** |
| Slab boundaries / tags | X-LOS-<floor> xref, Iden-Slab Thickness | same | same xref names; boundary linework sparser |
| Level tags | Iden-Level Plan (T.O.S / T.O.F) | same | same |

These differences are now handled by `config/rules_villa_std.json`, which *extends* the Ramzi rules and
lists only the deviations – the pattern for onboarding any new consultant.

## 3. Static Group BOQ structure (identical template in both projects)

Workbook sheets: `CP` (commercial proposal letter), `Summary`, `Preliminaries`, `BOQ FOR VILLA`, plus
`Plastering works` (Al-Kawari) or `BOQ of Boundarywall` (Al-Sulaiti; Al-Kawari keeps the boundary
wall as section F inside the main sheet). Columns: ITEM · DESCRIPTION · QTY · UNIT · RATE · AMOUNT.

Coding: summary letters (A Preliminaries, B Villa core & shell, C Plastering / Boundary wall, D Services, E MEP,
F Boundary wall) → sub-sections `b.1 EARTH WORKS`, `b.2 STRUCTURAL WORKS`, `b.2.1 Sub-Structure`, `b.2.2
Substructure Waterproofing`, `b.2.3 Planter`, `b.2.4/5 Super-Structure`, `ARCHITECTURAL WORKS` → items
`1`, `1.1`, `2.1` …

**Scope is "core & shell".** The CP sheet excludes design, dewatering, *finishing works*, roof
waterproofing, MEP 2nd/3rd fix and approvals. So tiles, paint, doors, windows, ceilings, sanitary
ware etc. are **not** Static Group BOQ items in these projects and are deliberately not modelled
(the architecture allows them to be added when a future BOQ contains them).

Units used: m³ (concrete, earthworks), m² (block work, waterproofing, plaster, earth filling), lm
(lintels), nr (manholes, soakaways), item/ls (lump sums), "–" (excluded).

### Every BOQ category and item found

| Section | Items (Al-Kawari / Al-Sulaiti) | Unit |
|---|---|---|
| Preliminaries | design (excl.), permits (excl.), temporary fencing (lump sum, perimeter in description: 161.06 / 151.20 Lm), site clearance, offices, H&S, plant, mobilisation, cleaning, management | item |
| Earthworks | bulk excavation, removal (= excavation), backfilling, anti-termite (ls), dewatering (excl.) | m³ |
| Sub-structure concrete | blinding, footings, neck columns, lift walls & additional, ground beams, slab on grade (T10/150 mesh), steps & landing | m³ |
| Sub-structure masonry / external | 200mm fillet block in outer ground beams (m²), earth filling under landscape concrete (m²), landscape SOG 150/100mm (m³) | m² / m³ |
| Tanks (holding + water tank; sizes in heading) | blinding, 400mm footings, walls (incl. PVC water stop), 250mm cover slab | m³ |
| Substructure waterproofing | tanks horizontal / vertical (SBS membrane), footings+GB+neck horizontal / vertical (rubberised bitumen) | m² |
| Planter | block planter box (m²), RC base (m³, Sulaiti) | m² / m³ |
| Water-tank plinth (Sulaiti only) | RC plinth | m³ |
| Super-structure | columns & walls, beams, slabs, staircase (GF+FF+PH) | m³ |
| Architectural – external block | 8 (Kawari) / 13 (Sulaiti) wall types by thickness 100–500mm and type (insulated hollow, double, parapet, duct) | m² |
| Architectural – internal block | 100mm, 200mm | m² |
| Lintels | all lintels in one line | lm |
| Services | drainage manholes, rain-water manholes, soakaways, electrical manholes | nr |
| MEP | 1st-fix electrical in slabs, HVAC sleeves, Ooredoo sleeves, manhole connections, drainage system, riser sleeves | item |
| Plastering (Kawari) | external villa, external boundary wall, internal (incl. stair soffit) | m² |
| Boundary wall | excavation, removal, backfill, anti-termite, dewatering, blinding, strip footing 300mm, neck columns, ground beam, solid block in GB, waterproofing, columns, stiffener beam, block work 200/300 | m³ / m² |

Totals: Al-Kawari 69 lines (57 measured, 8 lump sum, 4 excluded); Al-Sulaiti 74 lines (61 measured, 9 lump sum, 4 excluded).

## 4. What the BOQs reveal – and what they do not

* Quantities are **typed values** (e.g. 2131.23288, 106.4691, 0.9176-type decimals) – no take-off sheets,
  no formulas, no dimensions. The measurement methodology therefore has to be reconstructed by
  re-measuring the drawings and comparing; this is what the benchmark does (see GAP_ANALYSIS_AND_ROADMAP.md).
* Removal of excavated material always equals bulk excavation (both projects) – a rule, not a coincidence.
* Item wording carries data: tank sizes ("4.20 m/L x 2.50 m/W x 5.34 m/H"), boundary-wall length and height
  ("166.5 m/L x 3.15 m/H"), fencing length, block-wall make-up, SOG thickness. These are inputs, not outputs.
* Templates are re-used between quotations: the Al-Sulaiti sheets still link to other clients' summaries
  (`[39]Summary` → "Mrs. Hamda Hassan J Allanjawi", "Mr. Nasser Abdulrahman H Y Al-Emadi"). The system should
  flag such stale header links when a BOQ is imported.

## 5. Generalisable vs project-specific vs not automatable (today)

| Group | Items |
|---|---|
| Generalisable and automatable from structural CAD | footings, blinding (footing part), ground/tie beams, columns & walls, beams, slabs, slab on grade, pedestals, neck columns (sections on S-FP) |
| Generalisable with an agreed convention (needs engineer sign-off once) | blinding under ground beams, storey/neck heights, beam depth vs slab, earthworks (excavation footprint, working space, ground level), substructure waterproofing areas, lintel lengths, fillet block |
| Automatable with additional extraction work | block work by wall type (architectural plans + wall-type legend + heights), plaster (derived from wall faces), manholes / soakaways (drainage symbols in xrefs), tanks (tank drawings), boundary wall (length × typical section) |
| Project-specific / estimator judgement | "lift walls & additional concrete", steps & landing, planter boxes, landscape filling/paving, water-tank plinth |
| Not quantity items | lump sums (MEP 1st fix, sleeves, anti-termite, preliminaries), exclusions (design, permits, dewatering) |

## 6. Phase 3 – how the analysis became rules

Everything in §4–5 that the BOQs do not prove is now a **methodology rule** with an explicit status
(CONFIRMED / INFERRED / ASSUMED / UNKNOWN – see BOQ_KNOWLEDGE_MODEL.md, "Methodology rules"):

* INFERRED from both projects: footing volume = outline × schedule depth; ground-beam volume = drawn length ×
  section; removal of excavated material = bulk excavation.
* ASSUMED (development only): storey level per floor = the most frequent level tag.
* UNKNOWN (18): blinding extent and projection, column/wall height, beam depth, neck height, block wall height,
  opening deductions (block work and plaster), internal plaster faces, lintel bearing, excavation working space and
  ground level, backfill, substructure waterproofing faces, electrical manhole source, slab-on-grade extent, tank
  and boundary-wall geometry source.

For every UNKNOWN rule the engine computes one candidate per option on all three projects and the benchmark
shows which candidate is closest to Static Group's figure – as an observation, not a decision. The data shows that
several gaps are **not** explained by any option (e.g. columns & walls stay ~18 % low on both projects under the
most generous height option; beams fit a different depth option on each project), so approving the closest option
blindly would hide real extraction gaps. The estimator decides on the Rule Approval page; the decision is versioned
and every project is recalculated.

Data typed into BOQ headings (tank sizes, boundary-wall length × height) is treated as an **input** to the
Project Inputs page, never read back as a measured result.
