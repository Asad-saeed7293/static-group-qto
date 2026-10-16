"""Beams and pedestals from framing plans.

Beam instances are the closed rectangular outlines on S-FRAM-BEAM-HIDD. Each
rectangle is drawn between supports, so its long side is the measured clear
span and its short side the measured width. Labels (mark e.g. 'L1B6-2', size
e.g. 'B200X600', remarks e.g. 'INVERTED') are written along the beam edge, so
they are attached by orientation + perpendicular offset + position along the beam.

Depth comes from (in order of preference, per beam family in the rules file):
  schedule table row (mark, span) -> section-detail dimension -> plan size label.
Each source is cross-checked against the others and against the drawn width.
"""
from __future__ import annotations

import math
import re

from shapely.geometry import Polygon

from ..geometry import angle_diff, centroid, clean_ring, rectangle_dims
from ..models import (CrossCheck, Element, Flag, Measurement, SEV_INFO, SEV_WARN, SRC_CAD_GEOMETRY, SRC_SCHEDULE,
                      SRC_PLAN_LABEL, SRC_SECTION_DIM, SRC_MISSING, SRC_SLAB_TAG, ST_CHECK, ST_MISSING, ST_REVIEW)
from .common import dedupe, flag_dup, ref_from, ref_from_dict, text_centre
from .slabs import thickness_at


def _mrr(points):
    rect = Polygon(clean_ring(points)).minimum_rotated_rectangle
    c = list(rect.exterior.coords)[:4]
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    p, q = (c[0], c[1]) if a >= b else (c[1], c[2])
    ang = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 180.0
    return {"long": max(a, b), "short": min(a, b), "angle_deg": ang}


def _family(mark: str, rules: dict):
    for fam in rules["beam_families"]:
        if re.match(fam["regex"], mark):
            return fam
    return None


def _label_fit(t, rect, o):
    """Perpendicular offset of the label from the beam axis edge, or None if it does not fit."""
    if angle_diff(t["rotation"], rect["angle_deg"]) > 10:
        return None
    cx, cy = centroid(o["points"])
    a = math.radians(rect["angle_deg"])
    ux, uy = math.cos(a), math.sin(a)          # along beam
    vx, vy = -uy, ux                           # across beam
    px, py = text_centre(t)
    along = (px - cx) * ux + (py - cy) * uy
    across = abs((px - cx) * vx + (py - cy) * vy)
    if abs(along) > rect["long"] / 2 + 0.15:
        return None
    return max(0.0, across - rect["short"] / 2)


def assign_labels(beams, labels, max_off):
    """Each label goes to the best-fitting beam. Returns {beam_idx: [(label, offset)]}."""
    out = {}
    for t in labels:
        best = None
        for bi, (o, rect) in enumerate(beams):
            off = _label_fit(t, rect, o)
            if off is not None and off <= max_off and (best is None or off < best[1]):
                best = (bi, off)
        if best:
            out.setdefault(best[0], []).append((t, best[1]))
    return out


def build_beams(fr: dict, floor: str, schedule: dict, tie_depths: dict, slabs: list, rules: dict, settings: dict):
    pr = rules["pairing"]
    facts = fr["facts"]
    warnings = []
    outlines, dups = dedupe(facts["outlines"].get("beam_outline", []), pr["duplicate_tolerance"])
    ped_sizes = facts["texts"].get("pedestal_size", [])
    ped_labels = facts["texts"].get("pedestal_label", [])
    beams, pedestals, other = [], [], []
    for o in outlines:
        r = rectangle_dims(o["points"])
        if r is None:
            # Irregular beam outline (e.g. tapered cantilever): orientation from the minimum rotated rectangle,
            # volume later from the exact polygon area.
            mr = _mrr(o["points"])
            if mr["long"] / max(mr["short"], 1e-6) >= rules["element_classes"]["beam_min_aspect"]:
                mr["irregular"] = True
                beams.append((o, mr))
            else:
                other.append((o, "non-rectangular, not elongated"))
            continue
        if r["long"] / max(r["short"], 1e-6) >= rules["element_classes"]["beam_min_aspect"]:
            beams.append((o, r))
            continue
        # square-ish: pedestal if it matches a PEDESTAL size note nearby
        cx, cy = centroid(o["points"])
        match = None
        for s in ped_sizes:
            a, b = float(s["groups"]["a"]) / 1000, float(s["groups"]["b"]) / 1000
            if abs(min(a, b) - r["short"]) <= pr["geometry_match_tolerance"] and abs(max(a, b) - r["long"]) <= pr["geometry_match_tolerance"]:
                d = math.dist((cx, cy), text_centre(s))
                if d <= pr["pedestal_label_max_dist"] and (match is None or d < match[1]):
                    match = (s, d)
        if match or not rules["element_classes"].get("pedestal_requires_label", True):
            pedestals.append((o, r, match))
        else:
            other.append((o, f"{r['short']:.2f} x {r['long']:.2f} rectangle, aspect < {rules['element_classes']['beam_min_aspect']}"))

    marks = assign_labels(beams, facts["texts"].get("beam_mark", []), pr["beam_label_max_offset"])
    sizes = assign_labels(beams, facts["texts"].get("beam_size", []), pr["beam_label_max_offset"])
    remarks = assign_labels(beams, facts["texts"].get("beam_remark", []), pr["beam_label_max_offset"])
    basis = settings["measurement"]["beam_depth_basis"]
    els = []
    seq = {}
    for bi, (o, r) in enumerate(beams):
        ref = ref_from(fr, o, "Beam outline (closed rectangle)")
        e = Element(uid="", element_type="beam", mark="", floor=floor, drawing_id=fr["drawing_id"], drawing=fr["file"],
                    layer=o["layer"], geometry=o["points"], sources=[ref])
        ml = sorted(marks.get(bi, []), key=lambda x: x[1])
        sl = sorted(sizes.get(bi, []), key=lambda x: x[1])
        rl = remarks.get(bi, [])
        mark, span = "", "-"
        if ml:
            t, off = ml[0]
            g = re.match(r"^(?P<m>.+?)(?:-(?P<s>\d+))?$", t["text"])
            mark, span = g.group("m"), (g.group("s") or "-")
            mark = re.sub(r"^T\.B\.", "T.B", mark)  # 'T.B.2' and 'T.B2' are the same tie beam
            e.sources.append(ref_from(fr, t, f"Beam mark '{t['text']}' ({off:.2f} m from beam edge)"))
            if len({x[0]["text"] for x in ml}) > 1:
                e.flags.append(Flag("AMBIGUOUS_ID", "More than one beam mark fits this beam",
                                    f"Candidates: {[x[0]['text'] for x in ml]}; nearest used.", SEV_WARN, ST_REVIEW))
        e.mark = f"{mark}-{span}" if mark and span != "-" else mark
        e.attributes.update({"beam_mark": mark, "span": span, "remarks": [x[0]["text"] for x in rl]})
        key = e.mark or "UNID"
        seq[key] = seq.get(key, 0) + 1
        e.uid = f"BM-{floor}-{key}-{seq[key]:02d}"
        fam = _family(mark, rules) if mark else None
        e.attributes["family"] = fam["name"] if fam else None
        e.description = (f"{fam['name'] if fam else 'Beam'} {e.mark} - {floor}" if mark else f"Unidentified beam - {floor}")
        if r.get("irregular"):
            e.attributes["shape"] = f"Irregular ({len(o['points'])}-point outline)"
            e.dims["plan_area"] = Measurement("plan_area", round(o["area"], 4), "m2", SRC_CAD_GEOMETRY,
                                              f"Shoelace area of irregular beam outline {o['handle']}", ref)
            e.dims["length"] = Measurement("length", round(r["long"], 4), "m", SRC_CAD_GEOMETRY,
                                           "Long side of the minimum bounding rectangle (for information)", ref)
            e.dims["width_drawn"] = Measurement("width_drawn", round(o["area"] / r["long"], 4), "m", SRC_CAD_GEOMETRY,
                                                "Average width = outline area / length", ref)
            e.flags.append(Flag("NON_RECTANGULAR", "Irregular beam outline",
                                "Volume uses the exact plan area of the outline x depth (not length x width).", SEV_INFO, ST_CHECK))
        else:
            e.attributes["shape"] = "rectangular"
            e.dims["length"] = Measurement("length", round(r["long"], 4), "m", SRC_CAD_GEOMETRY,
                                           "Long side of drawn beam rectangle (clear span between supports)", ref)
            e.dims["width_drawn"] = Measurement("width_drawn", round(r["short"], 4), "m", SRC_CAD_GEOMETRY, "Short side of drawn rectangle", ref)
        conf = [0.9 if mark else 0.45]
        reasons = ["mark label on beam edge" if mark else "no beam mark label"]

        # --- size label (plan)
        size_lbl = None
        if sl:
            t, off = sl[0]
            size_lbl = (float(t["groups"]["w"]) / 1000, float(t["groups"]["d"]) / 1000, t)
            e.sources.append(ref_from(fr, t, f"Size label '{t['text']}' ({off:.2f} m from beam edge)"))
        # --- schedule
        sch = None
        if mark:
            sch = schedule.get((mark, span)) or (schedule.get((mark, "-")) if span != "-" else None)
            if sch is None and span == "-":
                spans = [k for k in schedule if k[0] == mark]
                if len(spans) == 1:
                    sch = schedule[spans[0]]
        if sch:
            e.sources.append(ref_from_dict(sch["source"]))
        # --- width
        width = None
        if sch and sch["w"]:
            width = Measurement("width", sch["w"], "m", SRC_SCHEDULE, f"Schedule WIDTH for {mark} span {span}", ref_from_dict(sch["source"]))
        else:
            width = Measurement("width", round(r["short"], 4), "m", SRC_CAD_GEOMETRY,
                                "Drawn width" + (f" (schedule says '{sch['w_raw']}')" if sch else ""), ref)
        e.dims["width"] = width
        # --- depth
        depth = None
        src_order = (fam or {}).get("depth_source", "schedule")
        if src_order == "schedule" and sch and sch["d"]:
            depth = Measurement("depth", sch["d"], "m", SRC_SCHEDULE, f"Schedule DEPTH for {mark} span {span}", ref_from_dict(sch["source"]))
        elif src_order == "section_detail" and mark in tie_depths and tie_depths[mark]["depth"]:
            td = tie_depths[mark]
            depth = Measurement("depth", td["depth"], "m", SRC_SECTION_DIM, td["source"]["note"], ref_from_dict(td["source"]))
            e.sources.append(ref_from_dict(td["source"]))
        elif size_lbl:
            depth = Measurement("depth", size_lbl[1], "m", SRC_PLAN_LABEL, f"Plan label '{size_lbl[2]['text']}'", ref_from(fr, size_lbl[2]))
            conf.append(0.75); reasons.append("depth from plan label only")
            if mark and src_order != "none":
                e.flags.append(Flag("DEPTH_FROM_LABEL", "Depth taken from plan label, not schedule",
                                    f"No usable {'schedule row' if src_order == 'schedule' else 'section detail'} for {mark}; "
                                    f"depth read from plan label '{size_lbl[2]['text']}'.", SEV_INFO, ST_CHECK))
        if depth is None:
            why = ("beam not identified" if not mark else
                   f"no {'schedule row' if src_order == 'schedule' else 'section-detail dimension' if src_order == 'section_detail' else 'schedule entry'} "
                   f"for {mark} and no size label on the plan")
            depth = Measurement("depth", None, "m", SRC_MISSING, f"Depth not available: {why}")
            e.flags.append(Flag("MISSING_DEPTH", "Beam depth not available", f"Depth not available: {why}. Volume not calculated.",
                                SEV_WARN, ST_MISSING))
        e.dims["depth"] = depth

        # --- cross checks
        tol = pr["geometry_match_tolerance"]
        if sch and sch["w"]:
            ok = abs(sch["w"] - r["short"]) <= tol
            e.cross_checks.append(CrossCheck("Drawn width vs schedule width", f"{sch['w']:.3f}", f"{r['short']:.3f}", ok))
            if not ok:
                e.flags.append(Flag("SCHEDULE_MISMATCH", "Drawn beam width differs from schedule",
                                    f"Schedule {sch['w']*1000:.0f} mm, drawn {r['short']*1000:.0f} mm.", SEV_WARN, ST_REVIEW))
        if size_lbl:
            ok = abs(size_lbl[0] - r["short"]) <= tol
            e.cross_checks.append(CrossCheck("Drawn width vs plan size label", f"{size_lbl[0]:.3f}", f"{r['short']:.3f}", ok))
            if sch and sch["d"]:
                okd = abs(size_lbl[1] - sch["d"]) <= 1e-6
                e.cross_checks.append(CrossCheck("Plan size label depth vs schedule depth", f"{sch['d']:.3f}", f"{size_lbl[1]:.3f}", okd))
                if not okd:
                    e.flags.append(Flag("LABEL_SCHEDULE_CONFLICT", "Plan label and schedule disagree on depth",
                                        f"Label '{size_lbl[2]['text']}' vs schedule {sch['d']*1000:.0f} mm for {e.mark}.", SEV_WARN, ST_REVIEW))
        if mark and fam and fam["depth_source"] == "schedule" and not sch:
            e.flags.append(Flag("SCHEDULE_ENTRY_MISSING", "Beam mark not found in beam schedule",
                                f"No schedule row for {mark} span {span}.", SEV_WARN, ST_CHECK))
        if not mark:
            e.flags.append(Flag("UNIDENTIFIED_ELEMENT", "Beam has no mark label",
                                "No beam mark sits along this beam outline; it cannot be linked to the schedule.", SEV_WARN, ST_REVIEW))

        # --- slab overlap (avoid double counting with slab volume)
        e.dims["slab_deduction"] = Measurement("slab_deduction", 0.0, "m", SRC_SLAB_TAG, "No deduction")
        includes = (fam or {}).get("depth_includes_slab", True)
        if basis == "below_slab" and includes and depth.value is not None:
            t_slab, zone = thickness_at(slabs, centroid(o["points"]))
            if t_slab:
                e.dims["slab_deduction"] = Measurement("slab_deduction", t_slab, "m", SRC_SLAB_TAG,
                                                       f"Slab thickness of zone {zone.mark} at beam centre (overlap counted in slab)",
                                                       zone.sources[0] if zone.sources else None)
            else:
                e.flags.append(Flag("SLAB_OVERLAP_NOT_DEDUCTED", "Beam/slab overlap not deducted",
                                    "Slab thickness at this beam is unknown, so the full beam depth was used. "
                                    "Beam and slab volumes may overlap here.", SEV_INFO, ST_CHECK))
        elif not includes:
            e.dims["slab_deduction"] = Measurement("slab_deduction", 0.0, "m", "Rule",
                                                   f"{fam['name']} depth is measured below the slab (rules file)")
        e.confidence = min(conf)
        e.confidence_reason = "; ".join(reasons)
        els.append(e)

    # overlapping beams (junctions drawn twice)
    polys = [Polygon(clean_ring(e.geometry)) for e in els]
    for i in range(len(els)):
        for j in range(i + 1, len(els)):
            if polys[i].intersects(polys[j]):
                a = polys[i].intersection(polys[j]).area
                if a > 1e-3:
                    big = a > 0.1
                    for x, y in ((els[i], els[j]), (els[j], els[i])):
                        dd = [v for v in (x.dim("depth"), y.dim("depth")) if v]
                        vol = f" (~{a * min(dd):.3f} m3 counted in both)" if dd else ""
                        x.attributes.setdefault("overlaps", []).append({"with": y.uid, "area_m2": round(a, 4)})
                        x.flags.append(Flag("OVERLAPPING_GEOMETRY", "Beam outline overlaps another beam",
                                            f"Overlaps {y.uid} by {a:.3f} m2 in plan{vol}. "
                                            + ("Large overlap - possible duplicated beam." if big else
                                               "Typical of a beam drawn through a junction; the shared volume is small but counted twice."),
                                            SEV_WARN if big else SEV_INFO, ST_REVIEW if big else ST_CHECK))
    # pedestals
    ped_els = []
    for k, (o, r, match) in enumerate(pedestals, start=1):
        ref = ref_from(fr, o, "Pedestal outline")
        e = Element(uid=f"PED-{floor}-{k:02d}", element_type="pedestal", mark="PEDESTAL", floor=floor, drawing_id=fr["drawing_id"],
                    drawing=fr["file"], layer=o["layer"], geometry=o["points"], sources=[ref])
        e.description = f"Pedestal {r['short']*1000:.0f}x{r['long']*1000:.0f} - {floor}"
        e.dims["length"] = Measurement("length", round(r["long"], 4), "m", SRC_CAD_GEOMETRY, "Drawn outline", ref)
        e.dims["width"] = Measurement("width", round(r["short"], 4), "m", SRC_CAD_GEOMETRY, "Drawn outline", ref)
        if match:
            s, d = match
            h = float(s["groups"]["c"]) / 1000
            e.dims["height"] = Measurement("height", h, "m", SRC_PLAN_LABEL, f"Third dimension of label '{s['text']}'", ref_from(fr, s))
            e.sources.append(ref_from(fr, s, f"Pedestal size note {d:.2f} m away"))
            e.confidence, e.confidence_reason = 0.8, "size note nearby"
            e.flags.append(Flag("LABEL_INTERPRETATION", "Pedestal height read from size note",
                                f"'{s['text']}' interpreted as L x W x H.", SEV_INFO, ST_CHECK))
        else:
            e.dims["height"] = Measurement("height", None, "m", SRC_MISSING, "No pedestal size note")
        ped_els.append(e)
    for o, why in other:
        warnings.append(f"{fr['file']}: outline {o['handle']} on {o['layer']} not classified ({why})")
    for dup, orig in dups:
        tgt = next((x for x in els if x.sources[0].handle == orig["handle"]), None)
        if tgt:
            tgt.flags.append(flag_dup(dup, orig))
    unl = [t for t in facts["texts"].get("beam_mark", [])
           if not any(t is x[0] for v in marks.values() for x in v)]
    for t in unl:
        warnings.append(f"{fr['file']}: beam mark '{t['text']}' ({t['handle']}) could not be attached to a drawn beam")
    return els + ped_els, warnings, unl, [o for o, _ in other]
