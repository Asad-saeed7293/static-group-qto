# Calculation methodology

All quantities are computed in `qto/calc/engine.py`. Every record stores the symbolic formula, the formula with the
numbers substituted, and each input with its source. If any input is missing the result is **not calculated**
(status *Missing Data*) – no defaults are applied.

| Element | Formula | Inputs and sources |
|---|---|---|
| Footing (rectangular) | `L × W × D` | L, W: drawn outline · D: footing schedule |
| Footing / raft (irregular) | `Plan area (polygon) × D` | area: shoelace of the drawn outline · D: schedule / RAFT tag |
| Blinding | `Plan area × t` | area: `S-BLND-BNDY` outline · t: "100mm BLINDING CONCRETE" note |
| Column (rectangular) | `W × D × H` | W, D: drawn outline (cross-checked with schedule) · H: storey height |
| Column (irregular) | `Section area × H` | |
| RC wall | `Plan area × H` | area: drawn outline · H: storey height (openings not deducted) |
| Beam | `L × W × (D − slab t)` | L: drawn clear span · W: schedule (else drawn) · D: schedule / section detail / label · slab t: thickness of the slab zone at the beam centre |
| Beam (irregular) | `Plan area × (D − slab t)` | |
| Pedestal | `L × W × H` | L, W: drawn · H: size note `500X500X500 MM` |
| Slab zone | `(Zone area − openings) × thickness` | area: polygonised boundary · thickness: slab tag (or user input) |

Worked example (from the drawings): footing F3 – outline 2.600 × 2.200 m, schedule D = 450 mm →
`2.600 × 2.200 × 0.450 = 2.574 m³`.

## Conventions (configurable in Settings)

* **Column height basis** – `to_slab_soffit` (default): `level(top floor T.O.S) − level(base) − slab thickness at top`;
  alternative `floor_to_floor`. Base of basement columns = top of footing (T.O.F).
* **Beam depth basis** – `below_slab` (default): slab thickness is deducted for families whose schedule depth includes
  the slab (L1B/PHB/TORB/GRB); tie beams (T.B) are already measured below the slab on grade per their section details.
  Alternative `full_depth`.
* **Slabs** measured over beams (gross zone area less shafts). Together with the two rules above, this avoids counting
  beam/slab and column/slab intersections twice.
* Columns are measured between slabs; beams between supports (drawn clear spans) – column/beam intersections are not
  double counted.

## Storey heights (from the drawings)

Levels are read from `Iden-Level Plan` tags (most frequent T.O.S per framing plan; T.O.F on the foundation plan).
Because levels vary across each floor (e.g. GR T.O.S +0.00 … +0.35), the derived height is marked **assumption /
Check** until an engineer confirms it or enters a corrected value in Settings. The derivation is shown on every column.

## BOQ generation

BOQ lines group quantity records by (section, mark, floor): e.g. *07.03 Reinforced concrete in column C5 – Ground floor*.
Unidentified elements get their own lines (never merged). A line's status is the worst status of its instances; if any
instance lacks data the line is *Missing Data* and the note states how many instances were not quantified.

## Comparison

* **Variance** = Drawing quantity − BOQ quantity.
* **Variance %** = Variance ÷ BOQ quantity × 100. Undefined (shown as —) when the BOQ quantity is 0 or blank.
* **Tolerance bands** (Settings; default): |%| ≤ 2 → OK, ≤ 5 → Check, above → Review Required.
* **Verified** = within the OK band **and** every independent cross-check on the underlying elements passed and no element
  flag lowers the status. Otherwise the worse of the tolerance status and the evidence status is used.
* Matching: BOQ *element* column ↔ drawing mark (normalised: `T.B1` = `TB1`); a floor in the BOQ row narrows the match;
  a mark that exists on several floors is compared against the **sum** (reported). When a mark is shared by several element
  types (e.g. a footing and its blinding), keywords in the BOQ description choose the type. Rows without an element ID
  get a *suggested* match by description similarity (≥ 80 %), always marked "confirm".
* Units are normalised (`m3`, `m³`, `cu.m`, `cum` …). A different unit is flagged *Unit mismatch* and not compared.
* Outcomes flagged: BOQ item not found in drawings · drawing item missing from BOQ · unit mismatch · BOQ quantity zero ·
  BOQ quantity missing · drawing data missing · variance to check · large variance.

## Statuses

`Verified` → `OK` → `Check` → `Review Required` → `Missing Data` (worst wins); `BOQ not provided` when no BOQ is active.
