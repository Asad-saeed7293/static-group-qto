"""Footings, rafts and blinding from the foundation plan + footing schedule."""
from __future__ import annotations

from shapely.geometry import Point

from ..geometry import centroid, rectangle_dims
from ..models import (CrossCheck, Element, Flag, Measurement, SEV_INFO, SEV_WARN, SEV_ERROR,
                      SRC_CAD_GEOMETRY, SRC_SCHEDULE, SRC_SLAB_TAG, SRC_MISSING, ST_CHECK, ST_MISSING, ST_REVIEW)
from .common import (confidence_from_distance, dedupe, flag_dup, greedy_pairs, poly, ref_from, ref_from_dict)


def build_footings(fp: dict, schedule: dict, blinding_t: dict | None, rules: dict) -> tuple[list, list, list]:
    """Return (elements incl. rafts and blinding, warnings, unattached footing tags)."""
    pr = rules["pairing"]
    facts = fp["facts"]
    warnings = []
    outlines, dups = dedupe(facts["outlines"].get("footing_outline", []), pr["duplicate_tolerance"])
    tags = facts["texts"].get("footing_tag", [])
    slab_tags = facts["blocks"].get("slab_thickness_tag", [])

    # 1. Rafts: footing-layer outlines that contain a slab-thickness tag of type RAFT.
    raft_idx = {}
    for i, o in enumerate(outlines):
        p = poly(o)
        inside = [t for t in slab_tags if p.contains(Point(t["insert"]))]
        rafts = [t for t in inside if "RAFT" in t["values"].get("slab_type", "").upper()]
        if rafts:
            raft_idx[i] = rafts
    pad_outlines = [o for i, o in enumerate(outlines) if i not in raft_idx]
    pairs, unpaired_tags = greedy_pairs(pad_outlines, tags, pr["footing_tag_max_dist"])

    elements = []
    seq = {}
    # --- pad / combined footings
    for i, o in enumerate(pad_outlines):
        ref = ref_from(fp, o, "Footing outline (closed polyline)")
        rect = rectangle_dims(o["points"])
        e = Element(uid="", element_type="footing", mark="", floor="FDN", drawing_id=fp["drawing_id"],
                    drawing=fp["file"], layer=o["layer"], geometry=o["points"], sources=[ref])
        if i in pairs:
            ti, d = pairs[i]
            t = tags[ti]
            e.mark = t["text"]
            e.sources.append(ref_from(fp, t, f"Footing tag '{t['text']}' ({'inside outline' if d == 0 else f'{d:.2f} m from outline'})"))
            e.confidence, e.confidence_reason = confidence_from_distance(d, pr["footing_tag_max_dist"])
        else:
            e.confidence, e.confidence_reason = 0.4, "no footing tag within pairing distance"
            e.flags.append(Flag("UNIDENTIFIED_ELEMENT", "Footing outline has no ID tag",
                                f"Closed outline {o['handle']} on {o['layer']} has no footing tag within {pr['footing_tag_max_dist']} m. "
                                "Area is measured exactly from the outline; the footing type (and so its thickness) must be confirmed by an engineer.",
                                SEV_WARN, ST_REVIEW))
        n = seq.get(e.mark or "UNID", 0) + 1
        seq[e.mark or "UNID"] = n
        e.uid = f"FTG-{e.mark or 'UNID'}-{n:02d}"
        e.description = f"Footing {e.mark}" if e.mark else "Unidentified footing outline"
        e.attributes["shape"] = "Rectangular" if rect else f"Irregular ({len(o['points'])}-point outline)"
        e.attributes["category_hint"] = "Combined footing" if e.mark.startswith("CF") else "Isolated footing"
        if o.get("has_bulge"):
            e.flags.append(Flag("ARC_SEGMENTS", "Outline contains arc segments",
                                "Area uses straight chords between vertices; arc bulges are not yet integrated.", SEV_WARN, ST_CHECK))
        e.dims["plan_area"] = Measurement("plan_area", round(o["area"], 4), "m2", SRC_CAD_GEOMETRY,
                                          f"Shoelace area of {len(o['points'])}-vertex outline {o['handle']}", ref)
        if rect:
            e.dims["length"] = Measurement("length", round(rect["long"], 4), "m", SRC_CAD_GEOMETRY, "Long side of drawn outline", ref)
            e.dims["width"] = Measurement("width", round(rect["short"], 4), "m", SRC_CAD_GEOMETRY, "Short side of drawn outline", ref)
        sch = schedule.get(e.mark) if e.mark else None
        if sch:
            sref = ref_from_dict(sch["source"])
            e.sources.append(sref)
            if sch["d"] is not None:
                e.dims["depth"] = Measurement("depth", sch["d"], "m", SRC_SCHEDULE, f"D (mm) column of footing schedule row {e.mark}", sref)
            if rect and sch["w"] and sch["l"]:
                tol = pr["geometry_match_tolerance"]
                ok = abs(rect["short"] - sch["w"]) <= tol and abs(rect["long"] - sch["l"]) <= tol
                e.cross_checks.append(CrossCheck("Drawn size vs schedule W x L",
                                                 f"{sch['w']:.3f} x {sch['l']:.3f}", f"{rect['short']:.3f} x {rect['long']:.3f}", ok,
                                                 "Plan outline matches the schedule" if ok else "Plan outline differs from the schedule - one of them is wrong"))
                if not ok:
                    e.flags.append(Flag("SCHEDULE_MISMATCH", "Drawn footing size differs from schedule",
                                        f"Schedule {e.mark}: {sch['w']*1000:.0f} x {sch['l']*1000:.0f} mm; drawn outline: "
                                        f"{rect['short']*1000:.0f} x {rect['long']*1000:.0f} mm.", SEV_WARN, ST_REVIEW))
        elif e.mark:
            e.flags.append(Flag("SCHEDULE_ENTRY_MISSING", "No schedule entry for footing tag",
                                f"Tag '{e.mark}' does not appear in any footing schedule table, so thickness is not available.",
                                SEV_WARN, ST_MISSING))
        if "depth" not in e.dims:
            e.dims["depth"] = Measurement("depth", None, "m", SRC_MISSING,
                                          "Thickness not available: " + ("footing not identified" if not e.mark else "no schedule entry"))
            e.flags.append(Flag("MISSING_THICKNESS", "Footing thickness not available",
                                "Volume cannot be calculated without a thickness from the schedule. Area is still reported.",
                                SEV_WARN, ST_MISSING))
        elements.append(e)

    # --- rafts
    for k, (i, rtags) in enumerate(sorted(raft_idx.items()), start=1):
        o = outlines[i]
        ref = ref_from(fp, o, "Raft outline (closed polyline on footing layer)")
        e = Element(uid=f"RAFT-{k:02d}", element_type="raft", mark=f"RAFT-{k}", floor="FDN", drawing_id=fp["drawing_id"],
                    drawing=fp["file"], layer=o["layer"], geometry=o["points"], sources=[ref])
        e.description = f"Raft foundation zone {k}"
        e.attributes["id_note"] = "System-generated ID: rafts are not numbered on the drawing"
        thick = {t["values"].get("thickness_mm") for t in rtags}
        for t in rtags:
            e.sources.append(ref_from(fp, t, f"Slab thickness tag {t['values']}"))
        e.dims["plan_area"] = Measurement("plan_area", round(o["area"], 4), "m2", SRC_CAD_GEOMETRY,
                                          f"Shoelace area of {len(o['points'])}-vertex outline {o['handle']}", ref)
        rect = rectangle_dims(o["points"])
        if rect:
            e.dims["length"] = Measurement("length", round(rect["long"], 4), "m", SRC_CAD_GEOMETRY, "Long side of outline", ref)
            e.dims["width"] = Measurement("width", round(rect["short"], 4), "m", SRC_CAD_GEOMETRY, "Short side of outline", ref)
        e.attributes["shape"] = "Rectangular" if rect else f"Irregular ({len(o['points'])}-point outline)"
        if len(thick) == 1:
            v = next(iter(thick))
            e.dims["depth"] = Measurement("depth", float(v) / 1000.0, "m", SRC_SLAB_TAG,
                                          f"SLAB_THICKNESS={v} on 'Iden-Slab Thickness' tag inside the outline", ref_from(fp, rtags[0]))
            e.confidence, e.confidence_reason = 0.9, "raft tag inside outline"
        else:
            e.dims["depth"] = Measurement("depth", None, "m", SRC_MISSING, f"Conflicting raft thickness tags: {sorted(thick)}")
            e.flags.append(Flag("AMBIGUOUS_THICKNESS", "Conflicting raft thickness tags",
                                f"Tags inside this raft give different thicknesses ({sorted(thick)}).", SEV_WARN, ST_REVIEW))
            e.confidence = 0.5
        elements.append(e)

    for dup, orig in dups:
        warnings.append(f"Duplicate footing outline {dup['handle']} (same as {orig['handle']}) excluded")
        tgt = next((x for x in elements if x.sources and x.sources[0].handle == orig["handle"]), None)
        if tgt:
            tgt.flags.append(flag_dup(dup, orig))
    for ti in unpaired_tags:
        t = tags[ti]
        warnings.append(f"Footing tag '{t['text']}' ({t['handle']}) at {t['insert']} is not attached to any footing outline"
                        + ("" if t["text"] in schedule else " and has no schedule row"))
    # --- blinding under footings and rafts
    blinding = build_blinding(fp, elements, blinding_t, rules)
    return elements + blinding, warnings, [tags[i] for i in unpaired_tags]


def build_blinding(fp, footings, blinding_t, rules):
    out = []
    outlines, _ = dedupe(fp["facts"]["outlines"].get("blinding_outline", []), rules["pairing"]["duplicate_tolerance"])
    for k, o in enumerate(outlines, start=1):
        p = poly(o)
        host = next((f for f in footings if p.contains(Point(centroid(f.geometry)))), None)
        ref = ref_from(fp, o, "Blinding boundary (closed polyline)")
        mark = f"BL-{host.mark}" if host and host.mark else ""
        e = Element(uid=f"BLD-{mark or 'UNID'}-{k:02d}", element_type="blinding", mark=mark, floor="FDN",
                    drawing_id=fp["drawing_id"], drawing=fp["file"], layer=o["layer"], geometry=o["points"], sources=[ref])
        e.description = f"Blinding under {host.description}" if host else "Blinding (no footing inside outline)"
        e.attributes["host_uid"] = host.uid if host else None
        e.attributes["id_note"] = "Blinding ID = 'BL-' + ID of the footing/raft it sits under (blinding is not tagged on the drawing)"
        e.dims["plan_area"] = Measurement("plan_area", round(o["area"], 4), "m2", SRC_CAD_GEOMETRY,
                                          f"Shoelace area of outline {o['handle']}", ref)
        if blinding_t:
            sref = ref_from_dict(blinding_t["source"])
            e.dims["thickness"] = Measurement("thickness", blinding_t["value"], "m", "Drawing note", blinding_t["source"]["note"], sref)
            e.sources.append(sref)
            if len(blinding_t["distinct_values"]) > 1:
                e.flags.append(Flag("AMBIGUOUS_THICKNESS", "Several blinding thicknesses noted",
                                    f"Notes give {blinding_t['distinct_values']} m; the most frequent was used.", SEV_INFO, ST_CHECK))
        else:
            e.dims["thickness"] = Measurement("thickness", None, "m", SRC_MISSING, "No blinding thickness note found")
            e.flags.append(Flag("MISSING_THICKNESS", "Blinding thickness not available", "No 'xx mm BLINDING CONCRETE' note found.", SEV_WARN, ST_MISSING))
        if not host:
            e.flags.append(Flag("UNIDENTIFIED_ELEMENT", "Blinding outline without footing",
                                "No footing/raft lies inside this blinding outline.", SEV_WARN, ST_CHECK))
        e.confidence = 0.9 if host else 0.5
        e.confidence_reason = "encloses a footing outline" if host else "no footing inside"
        out.append(e)
    return out
