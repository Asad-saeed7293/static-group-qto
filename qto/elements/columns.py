"""Columns and RC walls from the per-floor column layout plans.

Instances: closed outlines on X-CO-COLS-OTLN / X-CO-WALL-RCNC inside the bound
'X-CO-<floor>' xref, paired to the C/PC/W tags on S-COLS-ANNO-TEXT.
Section size: measured from the outline and cross-checked against the
'SCHEDULE OF COLUMNS' cell for (mark, floor) on S-CD.
Height: from structural level tags (base/top floor) - see storey_heights().
"""
from __future__ import annotations

import math

from ..geometry import centroid, rectangle_dims, min_rotated_rect
from ..models import (CrossCheck, Element, Flag, Measurement, SEV_INFO, SEV_WARN, SRC_CAD_GEOMETRY, SRC_SCHEDULE,
                      SRC_LEVEL_TAG, SRC_MISSING, SRC_USER, SRC_DERIVED, ST_CHECK, ST_MISSING, ST_REVIEW)
from .common import confidence_from_distance, dedupe, flag_dup, greedy_pairs, ref_from, ref_from_dict, text_centre, dist_point_outline


def storey_heights(levels: dict, slab_thk: dict, rules: dict, settings: dict, overrides: dict) -> dict:
    """Per floor: {height, base_level, top_level, slab_top, basis, confirmed, explanation, source}.

    Nothing is assumed silently: a missing level gives height=None.
    """
    basis = settings["measurement"]["column_height_basis"]
    out = {}
    user_h = overrides.get("storey_heights", {})
    confirmed = overrides.get("storey_heights_confirmed", {})
    for f in rules["floors"]:
        if not f.get("column_plan"):
            continue
        fid = f["id"]
        base, top = levels.get(f["base"], {}), levels.get(f["top"], {})
        rec = {"floor": fid, "base_floor": f["base"], "top_floor": f["top"], "basis": basis,
               "base_level": base.get("value"), "top_level": top.get("value"),
               "slab_top": slab_thk.get(f["top"], {}).get("value"), "confirmed": bool(confirmed.get(fid)),
               "sources": [s for s in (base.get("source"), top.get("source"), slab_thk.get(f["top"], {}).get("source")) if s]}
        if fid in user_h and user_h[fid] not in (None, ""):
            rec.update(height=float(user_h[fid]), origin=SRC_USER, confirmed=True,
                       explanation=f"Entered by user ({user_h[fid]} m) - overrides drawing-derived value")
        elif rec["base_level"] is None or rec["top_level"] is None:
            rec.update(height=None, origin=SRC_MISSING,
                       explanation="Height unavailable from drawing: "
                       + ("base level" if rec["base_level"] is None else "top level") + " not found in level tags")
        else:
            h = rec["top_level"] - rec["base_level"]
            expl = f"{rec['top_level']:+.2f} ({f['top']} {top.get('kind')}) - {rec['base_level']:+.2f} ({f['base']} {base.get('kind')})"
            if basis == "to_slab_soffit":
                if rec["slab_top"] is None:
                    rec.update(height=None, origin=SRC_MISSING,
                               explanation=f"Height unavailable: slab thickness at {f['top']} not determinable (basis = to slab soffit)")
                    out[fid] = rec
                    continue
                h -= rec["slab_top"]
                expl += f" - {rec['slab_top']:.3f} ({f['top']} slab thickness)"
            rec.update(height=round(h, 4), origin=SRC_LEVEL_TAG, explanation=expl + f" = {h:.3f} m")
        out[fid] = rec
    return out


def _measure(o):
    r = rectangle_dims(o["points"])
    if r:
        return r["short"], r["long"], "rectangular"
    m = min_rotated_rect(o["points"])
    return m["short"], m["long"], "non-rectangular"


def build_columns(cp: dict, floor: str, col_sched: dict, storey: dict, rules: dict) -> tuple[list, list]:
    pr = rules["pairing"]
    facts = cp["facts"]
    warnings = []
    outlines, dups = dedupe(facts["outlines"].get("column_outline", []), pr["duplicate_tolerance"])
    tags = facts["texts"].get("column_tag", [])
    pairs, unpaired = greedy_pairs(outlines, tags, pr["column_tag_max_dist"])
    st = storey.get(floor, {})
    els = []
    seq = {}
    for i, o in enumerate(outlines):
        ref = ref_from(cp, o, f"Column outline in bound xref block '{o['block']}'")
        w, d, shape = _measure(o)
        e = Element(uid="", element_type="column", mark="", floor=floor, drawing_id=cp["drawing_id"], drawing=cp["file"],
                    layer=o["layer"], geometry=o["points"], sources=[ref])
        if i in pairs:
            ti, dist = pairs[i]
            t = tags[ti]
            e.mark = t["text"]
            e.sources.append(ref_from(cp, t, f"Column tag '{t['text']}' {dist:.2f} m from outline"))
            e.confidence, e.confidence_reason = confidence_from_distance(dist, pr["column_tag_max_dist"])
        else:
            e.confidence, e.confidence_reason = 0.4, "no column tag nearby"
            e.flags.append(Flag("UNIDENTIFIED_ELEMENT", "Column outline has no tag",
                                f"Outline {o['handle']} has no C/PC tag within {pr['column_tag_max_dist']} m.", SEV_WARN, ST_REVIEW))
        key = e.mark or "UNID"
        seq[key] = seq.get(key, 0) + 1
        e.uid = f"COL-{floor}-{key}-{seq[key]:02d}"
        e.description = f"Column {e.mark} - {floor}" if e.mark else f"Unidentified column - {floor}"
        e.attributes["shape"] = shape
        e.dims["width"] = Measurement("width", round(w, 4), "m", SRC_CAD_GEOMETRY, "Short side of drawn outline", ref)
        e.dims["depth"] = Measurement("depth", round(d, 4), "m", SRC_CAD_GEOMETRY, "Long side of drawn outline", ref)
        e.dims["section_area"] = Measurement("section_area", round(o["area"], 5), "m2", SRC_CAD_GEOMETRY,
                                             "Area of drawn outline (shoelace)", ref)
        if shape != "rectangular":
            e.flags.append(Flag("NON_RECTANGULAR", "Non-rectangular column outline",
                                "Volume uses the exact outline area x height; width/depth are the minimum bounding rectangle.",
                                SEV_INFO, ST_CHECK))
        sch = col_sched.get((e.mark, floor)) if e.mark else None
        if sch:
            sref = ref_from_dict(sch["source"])
            e.sources.append(sref)
            ok = abs(sch["w"] - w) <= pr["geometry_match_tolerance"] and abs(sch["d"] - d) <= pr["geometry_match_tolerance"]
            e.cross_checks.append(CrossCheck("Plan outline vs column schedule section",
                                             f"{sch['w']:.3f} x {sch['d']:.3f}", f"{w:.3f} x {d:.3f}", ok,
                                             f"Schedule cell dimension strings: {sch['dims_in_cell']}"))
            if not ok:
                e.flags.append(Flag("SCHEDULE_MISMATCH", "Plan column size differs from schedule",
                                    f"Schedule {e.mark}/{floor}: {sch['w']*1000:.0f} x {sch['d']*1000:.0f} mm; plan outline "
                                    f"{w*1000:.0f} x {d*1000:.0f} mm.", SEV_WARN, ST_REVIEW))
        elif e.mark:
            e.flags.append(Flag("SCHEDULE_ENTRY_MISSING", "Column not in schedule for this floor",
                                f"No section for {e.mark} in the {floor} row of the column schedule; plan dimensions used.",
                                SEV_INFO, ST_CHECK))
        _apply_height(e, st)
        els.append(e)
    for dup, orig in dups:
        tgt = next((x for x in els if x.sources[0].handle == orig["handle"]), None)
        if tgt:
            tgt.flags.append(flag_dup(dup, orig))
    for ti in unpaired:
        warnings.append(f"{cp['file']}: column tag '{tags[ti]['text']}' ({tags[ti]['handle']}) not attached to an outline")
    return els, warnings


def _apply_height(e: Element, st: dict):
    if st.get("height") is None:
        e.dims["height"] = Measurement("height", None, "m", SRC_MISSING,
                                       st.get("explanation", "Height unavailable from drawing"))
        e.flags.append(Flag("MISSING_HEIGHT", "Height unavailable from drawing",
                            st.get("explanation", "No level information") + ". Enter or confirm the storey height in Settings.",
                            SEV_WARN, ST_MISSING))
        return
    src = SRC_USER if st.get("origin") == SRC_USER else SRC_LEVEL_TAG
    first = st["sources"][0] if st.get("sources") else None
    e.dims["height"] = Measurement("height", st["height"], "m", src, st["explanation"],
                                   ref_from_dict(first) if first and src != SRC_USER else None,
                                   is_assumption=(src != SRC_USER and not st.get("confirmed")))
    for s in st.get("sources", []):
        e.sources.append(ref_from_dict(s))
    if not st.get("confirmed"):
        e.flags.append(Flag("HEIGHT_DERIVED", "Height derived from level tags - confirm",
                            f"Storey height {st['height']:.3f} m = {st['explanation']}. Levels vary across the plan, so the most "
                            "frequent level was used. Confirm (or correct) the storey height in Settings.", SEV_INFO, ST_CHECK))


def build_walls(cp: dict, floor: str, storey: dict, rules: dict) -> tuple[list, list]:
    pr = rules["pairing"]
    facts = cp["facts"]
    outlines, dups = dedupe(facts["outlines"].get("wall_outline", []), pr["duplicate_tolerance"])
    tags = facts["texts"].get("wall_tag", [])
    st = storey.get(floor, {})
    els = []
    for i, o in enumerate(outlines, start=1):
        ref = ref_from(cp, o, f"RC wall outline in block '{o['block']}'")
        near = sorted(((dist_point_outline(text_centre(t), o), t) for t in tags), key=lambda x: x[0])
        near = [(d, t) for d, t in near if d <= pr["wall_tag_max_dist"]]
        marks = sorted({t["text"] for _, t in near})
        e = Element(uid=f"WAL-{floor}-{i:02d}", element_type="wall", mark="/".join(marks), floor=floor,
                    drawing_id=cp["drawing_id"], drawing=cp["file"], layer=o["layer"], geometry=o["points"], sources=[ref])
        e.description = f"RC wall {e.mark or '(untagged)'} - {floor}"
        for d, t in near[:3]:
            e.sources.append(ref_from(cp, t, f"Wall tag '{t['text']}' {d:.2f} m away"))
        e.dims["plan_area"] = Measurement("plan_area", round(o["area"], 4), "m2", SRC_CAD_GEOMETRY,
                                          f"Shoelace area of {len(o['points'])}-vertex wall outline", ref)
        r = rectangle_dims(o["points"])
        if r:
            e.dims["length"] = Measurement("length", round(r["long"], 4), "m", SRC_CAD_GEOMETRY, "Long side", ref)
            e.dims["thickness"] = Measurement("thickness", round(r["short"], 4), "m", SRC_CAD_GEOMETRY, "Short side", ref)
        if len(marks) > 1:
            e.flags.append(Flag("AMBIGUOUS_ID", "Several wall tags near one outline", f"Tags {marks}", SEV_INFO, ST_CHECK))
        if not marks:
            e.flags.append(Flag("UNIDENTIFIED_ELEMENT", "Wall outline has no W tag", "Wall type not identified on plan.", SEV_INFO, ST_CHECK))
        e.confidence, e.confidence_reason = (0.8, "wall tag nearby") if marks else (0.6, "untagged wall outline")
        _apply_height(e, st)
        e.flags.append(Flag("WALL_HEIGHT_STOREY", "Wall height taken as storey height",
                            "Wall height uses the same storey height as columns; openings in walls are not deducted.", SEV_INFO, ST_CHECK))
        els.append(e)
    return els, [f"{cp['file']}: duplicate wall outline {d['handle']} excluded" for d, _ in dups]
