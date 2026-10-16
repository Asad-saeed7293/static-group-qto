# Known limitations (MVP)

These are stated plainly so nobody relies on the prototype beyond what it can prove.

## Data that the drawings do not provide (flagged, never invented)

| Item | Why | How it is shown |
|---|---|---|
| Storey heights | No column elevations; levels vary across each floor (GR T.O.S +0.00…+0.35, FDN T.O.F −3.30…−4.10) | Derived from the most frequent level tag, marked **assumption / Check** until confirmed in Settings |
| Thickness of some slab zones | Slab boundary linework does not always close around each slab type; some tags sit just outside their zone | *Missing thickness* or *conflicting tags*; nearby tag offered as a suggestion only |
| Ground-floor main zone (GR-S01, 227 m² net) | Contains both S.O.G. 150 and S.S 250 tags with no separating boundary | Review Required; no volume |
| Roof main zone (TOR-S01) | Contains S.S 250 and D.P 400 tags | Review Required; no volume |
| Tie beam T.B4 depth | Its section detail has no vertical dimension inside the search window | Missing Data on all T.B4 beams |
| C.B beams | No schedule entry or size label | Missing Data |
| One irregular 12-point footing outline near tag F10 | F10 is 2.6 m away and has no schedule row | Unidentified, area only |
| Footing levels / excavation depths | General notes state no soil report was submitted | Not used |

## Method limitations

* **Beam length** is the drawn clear span of each beam rectangle. Beams drawn through junctions overlap; the overlap is
  measured and flagged but not yet automatically deducted.
* **Slab zones** are reconstructed from linework; where boundaries are incomplete, zone splitting along beam edges is a
  heuristic and flagged as such.
* **Walls**: height = storey height; door/window openings in walls are not deducted; the core wall W1 is measured from
  its drawn outline per floor.
* **Columns** are measured from the per-floor layout plans; column continuation into the roof (e.g. pergola columns
  above the PH slab) follows the same storey-height rule.
* **Arc segments** (bulges) in outlines are treated as straight chords; footing outlines with bulges are flagged
  (other element types are not yet checked for bulges).
* **Rebar, formwork, waterproofing, masonry, MEP and finishes** are out of scope for this MVP (architecture supports
  adding them).
* Architectural, mechanical and electrical drawings are inventoried only.
* `ACAD_PROXY_OBJECT` / `DIMASSOC` objects in two files are ignored by ezdxf (logged); they do not affect geometry.
* The viewer is a verification viewer, not a CAD replacement: no hatches, no line types/weights, simplified text.
* Label pairing uses distances/orientation tuned for this drawing set (configurable in the rules file); another
  consultant's standard needs its own rules file.
* The column schedule grid reader assumes marks across the top and floor names down the side (true for S-CD).

## BOQ

* No real BOQ was supplied. The comparison has been demonstrated only with the **synthetic test BOQ**
  (`samples/TEST_BOQ_SYNTHETIC_NOT_REAL.xlsx`), labelled as such everywhere.
* Matching relies on an element ID column in the BOQ (or a confirmed description match). Real BOQs that describe items
  only in prose ("RC columns ground floor") will need the description-matching suggestions to be confirmed, or an
  element-to-BOQ mapping table.
* Only volumes (m³) are compared; area/number items in a BOQ are flagged as unit mismatches.

## Platform

* Single-user local web app; no authentication. The audit log records the Windows user name.
* Data is stored as JSON files under `data/`.
