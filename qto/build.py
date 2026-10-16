"""Stage 4-6 orchestration: from per-drawing *facts* to elements and quantities.

Kept separate from DXF loading so a recalculation (after a user changes a
storey height or tolerance) takes a second instead of re-reading 80 files.
"""
from __future__ import annotations

from collections import Counter

from .calc.engine import calculate
from .elements.beams import build_beams
from .elements.columns import build_columns, build_walls, storey_heights
from .elements.footings import build_footings
from .elements.slabs import slab_zones
from .extract.schedules import (beam_schedule, blinding_thickness, column_schedule, floor_level,
                                footing_schedule, section_detail_depths)


def _by_role(drawings, role, floor=None):
    out = [d for d in drawings if d.get("role") == role and (floor is None or d.get("role_groups", {}).get("floor") == floor)]
    return out


def dominant_slab_thickness(fr: dict) -> dict:
    tags = fr["facts"]["blocks"].get("slab_thickness_tag", [])
    vals = Counter()
    for t in tags:
        if t["values"].get("slab_type", "").upper().replace(" ", "") in ("S.S", "S.S."):
            try:
                vals[float(t["values"]["thickness_mm"]) / 1000] += 1
            except (KeyError, ValueError):
                pass
    if not vals:
        return {"value": None}
    v, n = vals.most_common(1)[0]
    tag = next(t for t in tags if t["values"].get("thickness_mm") and abs(float(t["values"]["thickness_mm"]) / 1000 - v) < 1e-9)
    return {"value": v, "candidates": {str(k): c for k, c in vals.items()},
            "source": {"drawing_id": fr["drawing_id"], "drawing": fr["file"], "entity_type": "INSERT", "handle": tag["handle"],
                       "layer": tag["layer"], "block": tag["block_name"],
                       "note": f"Most frequent suspended-slab thickness on {fr['file']} ({n} of {sum(vals.values())} S.S tags)"}}


def build_all(drawings: list, rules: dict, settings: dict, overrides: dict, log) -> dict:
    """drawings: list of drawing dicts that include 'facts' (and 'tables') for role drawings."""
    warnings = []
    design = {}

    # --- design data from schedules / details --------------------------------
    fsched = {}
    for d in _by_role(drawings, "foundation_details"):
        fsched.update(footing_schedule(d, rules))
    design["footing_schedule"] = {k: {kk: vv for kk, vv in v.items() if kk != "raw"} for k, v in fsched.items()}
    log(f"Footing schedule: {len(fsched)} rows ({', '.join(sorted(fsched))})")

    bsched = {}
    for d in _by_role(drawings, "beam_schedule"):
        bsched.update(beam_schedule(d, rules))
    design["beam_schedule"] = {f"{k[0]}|{k[1]}": {kk: vv for kk, vv in v.items() if kk != "raw"} for k, v in bsched.items()}
    log(f"Beam schedule: {len(bsched)} rows")

    csched, cw = {}, []
    for d in _by_role(drawings, "column_schedule"):
        r, w = column_schedule(d, rules)
        csched.update(r)
        cw += w
    warnings += cw
    design["column_schedule"] = {f"{k[0]}|{k[1]}": v for k, v in csched.items()}
    log(f"Column schedule: {len(csched)} cells ({len({k[0] for k in csched})} column types)")

    tie, blind = {}, None
    for d in _by_role(drawings, "foundation_details"):
        tie.update(section_detail_depths(d, rules))
        blind = blind or blinding_thickness(d)
    design["tie_beam_sections"] = tie
    design["blinding"] = blind

    # --- levels ---------------------------------------------------------------
    levels = {}
    for fid, src in rules["levels"]["sources"].items():
        cands = _by_role(drawings, src["drawing_role"], src.get("floor"))
        if not cands:
            levels[fid] = {"value": None, "kind": src["kind"], "note": "source drawing not found"}
            continue
        lv = floor_level(cands[0], src["kind"])
        lv["kind"] = src["kind"]
        user = overrides.get("levels", {}).get(fid)
        if user not in (None, ""):
            lv["drawing_value"] = lv.get("value")
            lv["value"] = float(user)
            lv["user_override"] = True
        levels[fid] = lv
    slab_thk = {}
    for f in rules["floors"]:
        if f.get("framing_plan"):
            fr = _by_role(drawings, "framing_plan", f["framing_plan"])
            if fr:
                slab_thk[f["id"]] = dominant_slab_thickness(fr[0])
    storey = storey_heights(levels, slab_thk, rules, settings, overrides)
    design["levels"] = levels
    design["slab_thickness_by_floor"] = slab_thk
    design["storey_heights"] = storey

    # --- elements ---------------------------------------------------------------
    elements = []
    orphans = {"labels": [], "outlines": []}
    for fp in _by_role(drawings, "foundation_plan"):
        els, w, unl = build_footings(fp, fsched, blind, rules)
        elements += els
        warnings += w
        orphans["labels"] += [dict(t, drawing=fp["file"], drawing_id=fp["drawing_id"]) for t in unl]
    slabs_by_floor = {}
    for f in rules["floors"]:
        if not f.get("framing_plan"):
            continue
        for fr in _by_role(drawings, "framing_plan", f["framing_plan"]):
            sl, w = slab_zones(fr, f["id"], settings, overrides.get("slab_thickness", {}))
            slabs_by_floor[f["id"]] = sl
            elements += sl
            warnings += w
    for f in rules["floors"]:
        if not f.get("framing_plan"):
            continue
        for fr in _by_role(drawings, "framing_plan", f["framing_plan"]):
            els, w, unl, oth = build_beams(fr, f["id"], bsched, tie, slabs_by_floor.get(f["id"], []), rules, settings)
            elements += els
            warnings += w
            orphans["labels"] += [dict(t, drawing=fr["file"], drawing_id=fr["drawing_id"]) for t in unl]
            orphans["outlines"] += [dict(o, drawing=fr["file"], drawing_id=fr["drawing_id"]) for o in oth]
    for f in rules["floors"]:
        if not f.get("column_plan"):
            continue
        for cp in _by_role(drawings, "column_plan", f["column_plan"]):
            els, w = build_columns(cp, f["id"], csched, storey, rules)
            elements += els
            warnings += w
            wl, w2 = build_walls(cp, f["id"], storey, rules)
            elements += wl
            warnings += w2

    quantities = calculate(elements)
    counts = Counter(e.element_type for e in elements)
    log("Elements: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return {"elements": elements, "quantities": quantities, "warnings": warnings, "design": design, "orphans": orphans}
