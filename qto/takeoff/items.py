"""Static Group BOQ item calculators.

Every canonical item of the knowledge model gets one ItemQuantity record:

  value       - the quantity, only when every rule it depends on is decided (CONFIRMED/INFERRED/ASSUMED)
                and every input exists
  candidates  - {option label: value} when a methodology rule is UNKNOWN: the engineer sees the
                consequence of each option instead of a silently chosen number
  status      - Automatically Calculated | Calculated With Assumption | Requires Engineer Review |
                Requires Input | Not Available From Drawing | Lump Sum | Not Applicable
  rules       - [{rule_id, status, selected}] used by the calculation
  inputs / missing / evidence / element_uids / formula

No dimension, height, allowance or deduction is invented here. Unknown conventions come from
config/knowledge/methodology_rules.json; project inputs (tank sizes, boundary wall section,
ground level) from data/projects/<id>/inputs.json.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..knowledge.rules_engine import effective

AUTO, ASSUMPTION, REVIEW, INPUT, NA_DRAWING, LUMP, NA = (
    "Automatically Calculated", "Calculated With Assumption", "Requires Engineer Review", "Requires Input",
    "Not Available From Drawing", "Lump Sum", "Not Applicable")


def _r(v, dp=3):
    return None if v is None else round(v, dp)


class Ctx:
    def __init__(self, results, variants, drawings, design, rules, inputs, model):
        self.els = results["elements"]
        self.q = {}
        for q in results["quantities"]:
            self.q.setdefault(q["element_uid"], {})[q["quantity_type"]] = q
        self.variants = variants or {}
        self.drawings = drawings
        self.design = design
        self.rules = rules
        self.inputs = inputs or {}
        self.model = model

    def rule(self, rid):
        opt, st = effective(self.rules, rid)
        r = self.rules.get(rid, {})
        return opt, {"rule_id": rid, "title": r.get("title", rid), "status": r.get("status", "UNKNOWN"), "selected": opt}

    def facts(self, role, floor=None):
        out = []
        for d in self.drawings:
            if d.get("role") == role and (floor is None or (d.get("role_groups") or {}).get("floor") == floor):
                out.append(d)
        return out

    def sum_elements(self, types, qtype="concrete_volume", floors=None, els=None, qmap=None):
        qmap = qmap or self.q
        total, uids, missing = 0.0, [], 0
        for e in (els or self.els):
            if e["element_type"] in types and (not floors or e["floor"] in floors):
                q = qmap.get(e["uid"], {}).get(qtype)
                if q is None:
                    continue
                uids.append(e["uid"])
                if q["value"] is None:
                    missing += 1
                else:
                    total += q["value"]
        return total, uids, missing

    def level(self, fid):
        return (self.design.get("levels", {}).get(fid) or {}).get("value")

    def slab_t(self, fid):
        return (self.design.get("slab_thickness_by_floor", {}).get(fid) or {}).get("value")


def rec(item, **kw):
    r = {"item_id": item["id"], "description": item["description"], "unit": item["unit"], "category": item["category"],
         "variant": "", "value": None, "candidates": {}, "status": REVIEW, "rules": [], "inputs": {}, "missing": [],
         "evidence": [], "element_uids": [], "formula": item.get("formula", ""), "confidence": None, "notes": []}
    r.update(kw)
    return r


def _status_from_rules(rule_refs, missing):
    if missing:
        return INPUT
    sts = [r["status"] for r in rule_refs]
    if any(r["selected"] is None for r in rule_refs):
        return REVIEW
    if all(s == "CONFIRMED" for s in sts):
        return AUTO
    return ASSUMPTION


# ---------------------------------------------------------------------------- structural
def element_item(c: Ctx, item, types, floors=None, rule_ids=(), qtype="concrete_volume"):
    tot, uids, miss = c.sum_elements(types, qtype, floors)
    refs = [c.rule(r)[1] for r in rule_ids]
    r = rec(item, element_uids=uids, rules=refs,
            evidence=[f"{len(uids)} {'/'.join(types)} element(s){' on ' + ','.join(floors) if floors else ''} from structural drawings"],
            formula="Sum of element quantities (see each element's formula)")
    if not uids:
        r.update(status=NA_DRAWING, notes=["No such elements were found in the drawings"],
                 missing=[f"No {'/'.join(types)} elements{' on ' + ','.join(floors) if floors else ''} were extracted from the drawings"])
        return r
    if miss:
        r["missing"].append(f"{miss} element(s) have no quantity (missing dimension/thickness) - excluded from the total")
    open_refs = [x for x in refs if x["selected"] is None]
    if open_refs:   # UNKNOWN rule: the element total is only the candidate for the option it represents
        opt = c.rules.get(open_refs[0]["rule_id"], {}).get("engine_option") or "drawn elements"
        r["candidates"] = {opt: _r(tot)}
        r["status"] = REVIEW
        r["confidence"] = 0.6
        return r
    r["value"] = _r(tot)
    r["status"] = _status_from_rules(refs, []) if not miss else REVIEW
    r["confidence"] = 0.85 if not miss else 0.6
    return r


def variant_item(c: Ctx, item, types, floors, rule_id, qtype="concrete_volume"):
    """Item whose quantity depends on a measurement rule with engine variants (heights, depths)."""
    opt, ref = c.rule(rule_id)
    r = element_item(c, item, types, floors, (rule_id,), qtype)
    cands = {}
    for o, res in (c.variants.get(rule_id) or {}).items():
        qmap = {}
        for q in res["quantities"]:
            qmap.setdefault(q["element_uid"], {})[q["quantity_type"]] = q
        tot, _, _ = c.sum_elements(types, qtype, floors, els=res["elements"], qmap=qmap)
        cands[o] = _r(tot)
    r["candidates"] = cands
    if opt is None:
        r["value"] = None
        r["status"] = REVIEW
        r["notes"].append(f"Rule '{ref['title']}' is UNKNOWN - candidates per option are shown; no value chosen")
    elif opt in cands:
        r["value"] = cands[opt]
    return r


def blinding_item(c: Ctx, item):
    base, uids, miss = c.sum_elements(["blinding"], "blinding_volume")
    ext_opt, ext_ref = c.rule("blinding_extent")
    proj_opt, proj_ref = c.rule("blinding_projection")
    t = (c.design.get("blinding") or {}).get("value")
    gb = [e for e in c.els if e["element_type"] == "beam" and e["floor"] == "GR"]
    def gb_blinding(p):
        if not t:
            return None
        s = 0.0
        for e in gb:
            L, W = e["dims"].get("length", {}).get("value"), e["dims"].get("width", {}).get("value")
            if L and W:
                s += L * (W + 2 * p) * t
        return s
    cands = {"footings_only": _r(base)}
    for p in ("0.0", "0.10", "0.15"):
        v = gb_blinding(float(p))
        if v is not None:
            cands[f"footings_and_ground_beams (projection {p} m)"] = _r(base + v)
    r = rec(item, element_uids=uids, rules=[ext_ref, proj_ref], candidates=cands,
            evidence=[f"{len(uids)} blinding outline(s) on S-FP x {t} m (blinding note)", f"{len(gb)} ground/tie beam(s) on the ground framing plan"],
            formula="Footing blinding outlines x t  (+ ground beams: L x (W + 2 x projection) x t)")
    if ext_opt == "footings_only":
        r["value"] = cands["footings_only"]
    elif ext_opt == "footings_and_ground_beams" and proj_opt is not None:
        r["value"] = cands.get(f"footings_and_ground_beams (projection {proj_opt} m)")
    r["status"] = _status_from_rules([ext_ref] + ([proj_ref] if ext_opt == "footings_and_ground_beams" else []), [])
    if r["value"] is None:
        r["status"] = REVIEW
    return r


def neck_item(c: Ctx, item):
    opt, ref = c.rule("neck_column_height")
    outlines = []
    for d in c.facts("foundation_plan"):
        outlines += [o for o in d["facts"]["outlines"].get("neck_column_outline", [])]
    area = sum(o["area"] for o in outlines)
    tof, gr = c.level("FDN"), c.level("GR")
    gb_depths = [e["dims"]["depth"]["value"] for e in c.els if e["element_type"] == "beam" and e["floor"] == "GR"
                 and e["dims"].get("depth", {}).get("value")]
    gb_d = max(set(gb_depths), key=gb_depths.count) if gb_depths else None
    cands, missing = {}, []
    if tof is None or gr is None:
        missing.append("Top-of-footing or ground-floor level not found in level tags")
    else:
        cands["tof_to_sog_top"] = _r(area * (gr - tof))
        if gb_d:
            cands["tof_to_gb_soffit"] = _r(area * (gr - gb_d - tof))
        else:
            missing.append("Ground-beam depth not available")
    r = rec(item, rules=[ref], candidates=cands, missing=missing if not cands else [],
            inputs={"neck_section_area_total_m2": _r(area, 4), "neck_count": len(outlines), "T.O.F": tof, "GR T.O.S": gr, "typical_GB_depth": gb_d},
            evidence=[f"{len(outlines)} column outline(s) at foundation level on S-FP (total section {area:.3f} m2)"],
            formula="Sum(section area) x neck height")
    if not outlines:
        r.update(status=NA_DRAWING, candidates={}, notes=["No column outlines found on the foundation plan"],
                 missing=["No neck-column outlines on the foundation plan (layer role 'neck_column_outline'); "
                          "the project may have no neck columns (e.g. basement) - confirm with the estimator"])
        return r
    if opt and opt in cands:
        r["value"] = cands[opt]
        r["status"] = _status_from_rules([ref], [])
    else:
        r["status"] = INPUT if missing and not cands else REVIEW
    return r


# ---------------------------------------------------------------------------- walls / plaster / lintels
def wall_heights(c: Ctx):
    """Per architectural floor: {floor: {option: height}} from structural levels."""
    out = {}
    pairs = {"GR": ("GR", "L1"), "L1": ("L1", "PH"), "PH": ("PH", "TOR"), "BS": ("BS", "GR")}
    for f, (b, t) in pairs.items():
        lb, lt = c.level(b), c.level(t)
        if lb is None or lt is None:
            continue
        h = {"floor_to_floor": lt - lb}
        st = c.slab_t(t)
        if st:
            h["to_slab_soffit"] = lt - lb - st
        out[f] = h
    return out


def wall_stacks(c: Ctx):
    """Primary wall pieces per floor with composite thickness and external flag."""
    rows = []
    for d in c.facts("arch_floor_plan"):
        fl = (d.get("role_groups") or {}).get("floor")
        for w in d["facts"].get("walls", []):
            if not w.get("primary"):
                continue
            if w["thickness"] < 0.09:   # insulation / finishes, not block
                continue
            rows.append({**w, "floor": fl, "drawing": d["file"], "drawing_id": d["drawing_id"]})
    return rows


def openings(c: Ctx):
    out = []
    for d in c.facts("arch_floor_plan"):
        fl = (d.get("role_groups") or {}).get("floor")
        out += [{**o, "floor": fl, "drawing": d["file"]} for o in d["facts"].get("openings", [])]
    return out


def _thk_label(t):
    """Thickness in m snapped to the nearest 50 mm when within 10 mm (0.345 -> 0.35), else nearest 10 mm."""
    mm = int(math.floor(t * 100 + 0.5)) * 10
    m50 = int(math.floor(mm / 50 + 0.5)) * 50
    return (m50 if abs(mm - m50) <= 10 else mm) / 1000


def blockwork_items(c: Ctx, item_ext, item_int):
    h_opt, h_ref = c.rule("wall_height_method")
    d_opt, d_ref = c.rule("blockwork_opening_deduction")
    heights = wall_heights(c)
    walls = wall_stacks(c)
    ops = openings(c)
    groups = defaultdict(lambda: {"length": 0.0, "pieces": 0, "floors": defaultdict(float), "drawings": set(), "handles": []})
    parapet = defaultdict(float)
    for w in walls:
        if w["floor"] == "TOR":
            parapet[_thk_label(w.get("composite_thickness") or w["thickness"])] += w["length"]
            continue
        key = ("external" if w["external"] else "internal", _thk_label(w.get("composite_thickness") or w["thickness"]))
        g = groups[key]
        g["length"] += w["length"]
        g["pieces"] += 1
        g["floors"][w["floor"]] += w["length"]
        g["drawings"].add(w["drawing"])
        g["handles"].append(w["handle"])
    out = []
    for (side, th), g in sorted(groups.items()):
        item = item_ext if side == "external" else item_int
        cands = {}
        for opt in ("floor_to_floor", "to_slab_soffit"):
            tot, ok = 0.0, True
            for fl, L in g["floors"].items():
                h = (heights.get(fl) or {}).get(opt)
                if h is None:
                    ok = False
                    break
                tot += L * h
            if ok:
                cands[f"gross, {opt}"] = _r(tot)
        op_w = sum(o["width"] for o in ops if o.get("host_wall") in g["handles"])
        missing = ["Annex buildings (majlis / driver's room / kitchen sheets) are not yet included - only main-villa floor dimension plans are measured"]
        if not heights:
            missing.append("Storey levels not found - wall height unavailable")
        if op_w:
            missing.append(f"Openings in these walls: {op_w:.2f} m total width detected; opening heights are not available from the plans (needed only if openings are deducted)")
        variant = f"{int(round(th * 1000))}mm {side}"
        r = rec(item, variant=variant, candidates=cands, rules=[h_ref, d_ref],
                inputs={"wall_length_m": _r(g["length"]), "length_by_floor": {k: _r(v) for k, v in g["floors"].items()},
                        "pieces": g["pieces"], "opening_width_detected_m": _r(op_w), "heights": heights},
                evidence=[f"{g['pieces']} hatched wall piece(s) on A-WALL-PATT in {', '.join(sorted(g['drawings']))}; "
                          f"thickness = composite of parallel layers"],
                missing=missing, formula="Sum(wall length per floor x wall height) - openings (if deducted)",
                description=f"{item['description'].split('<')[0].strip()} {variant}")
        if h_opt and d_opt == "do_not_deduct":
            r["value"] = cands.get(f"gross, {h_opt}")
            r["status"] = _status_from_rules([h_ref, d_ref], [])
        else:
            r["status"] = REVIEW
            r["notes"].append("Wall height and/or opening deduction methodology is UNKNOWN - gross candidates shown, net not calculated")
        out.append(r)
    for th, L in sorted(parapet.items()):
        out.append(rec(item_ext, variant=f"{int(round(th * 1000))}mm parapet", status=INPUT,
                       description=f"Parapet block wall {int(round(th * 1000))}mm",
                       inputs={"parapet_length_m": _r(L)}, missing=["Parapet height is not dimensioned on the roof plan - enter it or read it from the wall sections"],
                       evidence=["Wall pieces on the top-of-roof plan"], formula="Parapet length x parapet height"))
    return out, walls, heights, ops


def plaster_items(c: Ctx, item_ext, item_int, walls, heights, ops):
    h_opt, h_ref = c.rule("wall_height_method")
    d_opt, d_ref = c.rule("plaster_opening_deduction")
    f_opt, f_ref = c.rule("internal_plaster_faces")
    def face(filter_fn, mult):
        res = {}
        for opt in ("floor_to_floor", "to_slab_soffit"):
            tot, ok = 0.0, True
            for w in walls:
                if w["floor"] == "TOR" or not filter_fn(w):
                    continue
                h = (heights.get(w["floor"]) or {}).get(opt)
                if h is None:
                    ok = False
                    break
                tot += w["length"] * h * mult(w)
            if ok:
                res[opt] = _r(tot)
        return res
    ext = face(lambda w: w["external"], lambda w: 1)
    int_a = face(lambda w: True, lambda w: 1 if w["external"] else 2)
    int_b = face(lambda w: not w["external"], lambda w: 2)
    out = []
    r = rec(item_ext, rules=[h_ref, d_ref], candidates={f"gross outer face, {k}": v for k, v in ext.items()},
            evidence=["Outer faces of external walls (architectural plans) x storey height"], formula="Sum(external wall length x height) - openings (if deducted)")
    if h_opt and d_opt == "do_not_deduct":
        r["value"] = ext.get(h_opt)
        r["status"] = _status_from_rules([h_ref, d_ref], [])
    else:
        r["notes"].append("Height / opening-deduction methodology UNKNOWN - gross candidates only")
    out.append(r)
    cands = {f"both faces internal + inner face external, {k}": v for k, v in int_a.items()}
    cands.update({f"both faces internal only, {k}": v for k, v in int_b.items()})
    r = rec(item_int, rules=[h_ref, d_ref, f_ref], candidates=cands, evidence=["Wall faces from architectural plans x storey height"],
            formula="Sum(wall faces x height) - openings (if deducted)",
            missing=["Staircase soffit area (included in the historical BOQ line) is not yet measured"])
    sel = {"internal_both_plus_external_inner": int_a, "internal_both_only": int_b}.get(f_opt)
    if h_opt and d_opt == "do_not_deduct" and sel:
        r["value"] = sel.get(h_opt)
        r["status"] = _status_from_rules([h_ref, d_ref, f_ref], [])
    out.append(r)
    return out


def lintel_item(c: Ctx, item, ops):
    b_opt, b_ref = c.rule("lintel_bearing")
    cands = {}
    if ops:
        for b in ("0.15", "0.20", "0.25"):
            cands[f"detected openings, bearing {b} m"] = _r(sum(o["width"] + 2 * float(b) for o in ops))
    lines = 0.0
    n_lines = 0
    for d in c.facts("framing_plan"):
        for o in d["facts"]["outlines"].get("lintel_line", []):
            pts = o["points"]
            lines += sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
            n_lines += 1
    if n_lines:
        cands["'BA Lintels' lines on framing plans"] = _r(lines)
    r = rec(item, rules=[b_ref], candidates=cands,
            inputs={"openings_detected": len(ops), "lintel_lines": n_lines},
            evidence=[f"{len(ops)} door/window block(s) detected on architectural plans", f"{n_lines} lintel line(s) on framing plans"],
            missing=["Opening detection from plan blocks is partial (door/window schedules are elevation drawings without tabular sizes)"],
            formula="Sum(opening width + 2 x bearing)")
    r["status"] = REVIEW
    if b_opt:
        r["value"] = cands.get(f"detected openings, bearing {b_opt} m")
        r["status"] = ASSUMPTION
    return r


# ---------------------------------------------------------------------------- earthworks / waterproofing
def earthworks_items(c: Ctx, it_exc, it_rem, it_bf):
    ws_opt, ws_ref = c.rule("excavation_working_space")
    ngl_opt, ngl_ref = c.rule("excavation_ground_level")
    rem_opt, rem_ref = c.rule("removal_equals_excavation")
    bf_opt, bf_ref = c.rule("backfill_method")
    ngl = c.inputs.get("natural_ground_level")
    if ngl_opt == "0.0":
        ngl = 0.0
    fdn = c.level("FDN")
    blind_t = (c.design.get("blinding") or {}).get("value") or 0.0
    fts = [e for e in c.els if e["element_type"] in ("footing", "raft")]
    depths = [e["dims"].get("depth", {}).get("value") for e in fts if e["dims"].get("depth", {}).get("value")]
    missing = []
    if fdn is None:
        missing.append("Top-of-footing level not found")
    if not fts:
        missing.append("No footings found")
    buried, _, _ = c.sum_elements(["footing", "raft"])
    b2, _, _ = c.sum_elements(["blinding"], "blinding_volume")
    b3, _, _ = c.sum_elements(["beam"], floors=["GR"])
    buried_total = buried + b2 + b3
    def pits(ws, g):
        tot = 0.0
        for e in fts:
            A = e["dims"].get("plan_area", {}).get("value")
            L, W = e["dims"].get("length", {}).get("value"), e["dims"].get("width", {}).get("value")
            D = e["dims"].get("depth", {}).get("value")
            if not A or not D or fdn is None:
                continue
            if L and W:
                A = (L + 0.2 + 2 * ws) * (W + 0.2 + 2 * ws)
            else:
                A = A + (2 * ws + 0.2) * 2 * math.sqrt(A)
            tot += A * (g - (fdn - D - blind_t))
        return tot
    cands_exc, cands_bf = {}, {}
    glevels = [ngl] if ngl is not None else [0.0]
    for g in glevels:
        for ws in ("0.0", "0.3", "0.5", "1.0"):
            v = pits(float(ws), g)
            label = f"footing pits, NGL {g:+.2f}, working space {ws} m" + ("" if ngl is not None else " (NGL not provided - shown at +0.00)")
            cands_exc[label] = _r(v)
            cands_bf[label] = _r(v - buried_total)
    refs = [ws_ref, ngl_ref]
    r1 = rec(it_exc, rules=refs, candidates=cands_exc, missing=missing + ([] if ngl is not None else ["Natural ground level (survey) not provided"]),
             inputs={"T.O.F": fdn, "footings": len(fts), "blinding_t": blind_t, "natural_ground_level": ngl},
             evidence=[f"{len(fts)} footing(s) with schedule depths; formation = T.O.F - D - blinding"],
             formula="Sum((L + 0.2 + 2ws) x (W + 0.2 + 2ws) x (NGL - formation level))",
             notes=["Historical BOQ quantities are far larger than individual pits - Static Group may measure bulk excavation over the building footprint; method UNKNOWN"])
    r1["status"] = INPUT if ngl is None else REVIEW
    if ws_opt is not None and ngl is not None:
        r1["value"] = cands_exc.get(f"footing pits, NGL {ngl:+.2f}, working space {ws_opt} m")
        r1["status"] = ASSUMPTION
    r2 = rec(it_rem, rules=[rem_ref], formula="= bulk excavation (rule INFERRED from both historical BOQs)",
             evidence=["Rule removal_equals_excavation"], candidates=dict(cands_exc), missing=list(r1["missing"]))
    r2["value"] = r1["value"] if rem_opt == "equal" else None
    r2["status"] = r1["status"] if r2["value"] is not None else r1["status"]
    r3 = rec(it_bf, rules=[bf_ref, ws_ref, ngl_ref], candidates=cands_bf,
             inputs={"buried_volume_m3": _r(buried_total)}, evidence=["Excavation - (footings + blinding + ground beams)"],
             formula="Excavation - buried concrete", missing=list(r1["missing"]))
    r3["status"] = r1["status"] if bf_opt else REVIEW
    if bf_opt and r1["value"] is not None:
        r3["value"] = _r(r1["value"] - buried_total)
    return [r1, r2, r3]


def waterproofing_items(c: Ctx, it_h, it_v):
    opt, ref = c.rule("substructure_waterproofing_surfaces")
    fts = [e for e in c.els if e["element_type"] in ("footing",)]
    gbs = [e for e in c.els if e["element_type"] == "beam" and e["floor"] == "GR"]
    top_f = sum((e["dims"].get("plan_area", {}).get("value") or 0) for e in fts)
    side_f = 0.0
    for e in fts:
        D = e["dims"].get("depth", {}).get("value")
        if D:
            side_f += Polygon(e["geometry"]).length * D if len(e["geometry"]) > 2 else 0
    top_gb = sum((e["dims"].get("length", {}).get("value") or 0) * (e["dims"].get("width", {}).get("value") or 0) for e in gbs)
    side_gb = sum(2 * (e["dims"].get("length", {}).get("value") or 0) * (e["dims"].get("depth", {}).get("value") or 0) for e in gbs)
    h = rec(it_h, rules=[ref], candidates={"sides_and_tops": _r(top_f + top_gb), "sides_only": 0.0},
            inputs={"footing_tops_m2": _r(top_f), "ground_beam_tops_m2": _r(top_gb)},
            evidence=[f"{len(fts)} footing(s), {len(gbs)} ground/tie beam(s)"], formula="Footing plan areas + ground-beam L x W",
            notes=["Neck columns and fillet block faces not included"])
    v = rec(it_v, rules=[ref], candidates={"sides_and_tops": _r(side_f + side_gb), "sides_only": _r(side_f + side_gb)},
            inputs={"footing_sides_m2": _r(side_f), "ground_beam_sides_m2": _r(side_gb)},
            evidence=[f"Footing perimeters x depth; ground beams 2 x L x D"], formula="Sum(perimeter x depth) + Sum(2 x L x D)",
            notes=["Neck-column sides are excluded until the neck height rule is decided"])
    for r in (h, v):
        if opt:
            r["value"] = r["candidates"].get(opt)
            r["status"] = _status_from_rules([ref], [])
    return [h, v]


# ---------------------------------------------------------------------------- services
def manhole_items(c: Ctx, items):
    out = []
    drain = c.facts("site_drainage")
    elec = c.facts("site_electrical")
    def count(ds, key, kind):
        n = 0
        for d in ds:
            sc = (d["facts"].get("symbol_counts") or {}).get(key) or {}
            n += sc.get(kind, 0)
        return n
    spec = {"SRV-MH-DR": (drain, "drainage_manhole", "blocks", None), "SRV-MH-RW": (drain, "rainwater_manhole", "blocks", None),
            "SRV-SOAK": (drain, "soakaway", "blocks", None), "SRV-MH-EL": (elec, "power_manhole_label", "labels", "electrical_manhole_source")}
    for iid, (ds, key, kind, rid) in spec.items():
        it = items[iid]
        n = count(ds, key, kind)
        refs = [c.rule(rid)[1]] if rid else []
        r = rec(it, rules=refs, candidates={f"{kind} matching '{key}'": float(n)} if ds else {},
                evidence=[f"{n} {kind} on {', '.join(d['file'] for d in ds) or 'no site plan found'}"], formula="Count")
        if not ds:
            r.update(status=NA_DRAWING, missing=["Site services drawing not found"])
        elif rid and c.rule(rid)[0]:
            r.update(value=float(n), status=ASSUMPTION)
        else:
            r["status"] = REVIEW
            r["notes"].append("Symbols inside nested xrefs are counted; count method not yet confirmed")
        out.append(r)
    return out


# ---------------------------------------------------------------------------- inputs-driven
def tank_items(c: Ctx, items):
    opt, ref = c.rule("tank_geometry_source")
    tanks = c.inputs.get("tanks") or []
    ids = ["TANK-BLD", "TANK-FTG", "TANK-WALL", "TANK-SLAB", "WP-TANK-H", "WP-TANK-V"]
    need = ["L", "W", "H", "wall_t", "base_t", "slab_t"]
    if not tanks:
        return [rec(items[i], rules=[ref], status=INPUT, missing=["Tank internal L, W, H and wall/base/cover thicknesses (from the tank drawings) are required"],
                    evidence=["Tank drawings (A-007 / A-009) are not yet read automatically"]) for i in ids]
    acc = defaultdict(float)
    miss = []
    for t in tanks:
        if any(t.get(k) in (None, "") for k in need):
            miss.append(f"Tank '{t.get('name', '?')}' is missing {[k for k in need if t.get(k) in (None, '')]}")
            continue
        L, W, H = float(t["L"]), float(t["W"]), float(t["H"])
        tw, tb, ts = float(t["wall_t"]), float(t["base_t"]), float(t["slab_t"])
        bl = float(t.get("blinding_t", 0.1))
        pr = float(t.get("blinding_projection", 0.1))
        Lo, Wo = L + 2 * tw, W + 2 * tw
        acc["TANK-BLD"] += (Lo + 2 * pr) * (Wo + 2 * pr) * bl
        acc["TANK-FTG"] += Lo * Wo * tb
        acc["TANK-WALL"] += 2 * (L + W + 2 * tw) * tw * H
        acc["TANK-SLAB"] += Lo * Wo * ts
        acc["WP-TANK-H"] += Lo * Wo
        acc["WP-TANK-V"] += 2 * (Lo + Wo) * (H + tb + ts)
    out = []
    for i in ids:
        r = rec(items[i], rules=[ref], value=_r(acc[i]) if not miss else None, missing=miss,
                inputs={"tanks": tanks}, evidence=["Tank sizes entered by estimator"],
                formula={"TANK-BLD": "(Lo + 2p) x (Wo + 2p) x t_blinding", "TANK-FTG": "Lo x Wo x t_base", "TANK-WALL": "2 x (L + W + 2tw) x tw x H",
                         "TANK-SLAB": "Lo x Wo x t_slab", "WP-TANK-H": "Lo x Wo", "WP-TANK-V": "2 x (Lo + Wo) x (H + t_base + t_slab)"}[i])
        r["status"] = INPUT if miss else (ASSUMPTION if opt else REVIEW)
        out.append(r)
    return out


def boundary_items(c: Ctx, items):
    opt, ref = c.rule("boundary_wall_source")
    bw = c.inputs.get("boundary_wall") or {}
    plot = []
    for d in c.facts("site_plan"):
        plot += d["facts"].get("plot_boundary_candidates", [])
    cand_len = plot[0]["perimeter"] if plot else None
    ids = ["BW-EXC", "BW-REM", "BW-BF", "BW-BLD", "BW-FTG", "BW-NECK", "BW-GB", "BW-FILLET", "BW-WP", "BW-COL", "BW-STIFF", "BW-BLK", "PL-EXT-BW"]
    need = ["length", "height", "footing_w", "footing_t", "exc_depth", "gb_w", "gb_d", "col_w", "col_d", "col_spacing", "neck_h", "stiff_w", "stiff_d", "block_t"]
    miss = [k for k in need if bw.get(k) in (None, "")]
    if miss:
        return [rec(items[i], rules=[ref], status=INPUT, inputs={"plot_boundary_length_candidate_m": cand_len},
                    missing=[f"Boundary-wall inputs required: {', '.join(miss)}"],
                    evidence=[f"Plot boundary on site plan: {cand_len} m" if cand_len else "No plot boundary polyline found on the site plan"]) for i in ids]
    v = {k: float(bw[k]) for k in need}
    Lw, H = v["length"], v["height"]
    ncol = math.floor(Lw / v["col_spacing"]) + 1
    q = {
        "BW-EXC": Lw * (v["footing_w"] + 0.2) * v["exc_depth"],
        "BW-BLD": Lw * (v["footing_w"] + 0.2) * 0.1,
        "BW-FTG": Lw * v["footing_w"] * v["footing_t"],
        "BW-NECK": ncol * v["col_w"] * v["col_d"] * v["neck_h"],
        "BW-GB": Lw * v["gb_w"] * v["gb_d"],
        "BW-FILLET": Lw * v["gb_d"],
        "BW-WP": Lw * (2 * v["footing_t"] + v["footing_w"] + 2 * v["gb_d"]),
        "BW-COL": ncol * v["col_w"] * v["col_d"] * H,
        "BW-STIFF": Lw * v["stiff_w"] * v["stiff_d"],
        "BW-BLK": (Lw - ncol * v["col_w"]) * (H - v["stiff_d"]),
        "PL-EXT-BW": Lw * H,
    }
    q["BW-REM"] = q["BW-EXC"]
    q["BW-BF"] = q["BW-EXC"] - q["BW-BLD"] - q["BW-FTG"] - q["BW-GB"] - q["BW-NECK"]
    return [rec(items[i], rules=[ref], value=_r(q[i]), status=ASSUMPTION if opt else REVIEW, inputs=bw,
                evidence=["Boundary-wall length and typical section entered by estimator" + (f"; site plan boundary {cand_len} m" if cand_len else "")],
                formula="Typical section x length (see methodology rule)", notes=["Formulas for the typical section are development assumptions until confirmed"])
            for i in ids]


# ---------------------------------------------------------------------------- main
def compute_items(results, variants, drawings, design, rules, inputs, model) -> list:
    c = Ctx(results, variants, drawings, design, rules, inputs, model)
    items = model["by_id"]
    out = []
    out.append(element_item(c, items["SUB-FTG"], ["footing", "raft"], rule_ids=["footing_volume_method"]))
    out.append(blinding_item(c, items["SUB-BLD"]))
    out.append(neck_item(c, items["SUB-NECK"]))
    out.append(element_item(c, items["SUB-GB"], ["beam"], ["GR"], rule_ids=["ground_beam_method"]))
    out.append(element_item(c, items["SUB-SOG"], ["slab"], ["GR"], rule_ids=["slab_on_grade_extent"]))
    out.append(variant_item(c, items["SUP-COLW"], ["column", "wall"], None, "column_height_method"))
    out.append(variant_item(c, items["SUP-BEAM"], ["beam"], ["L1", "PH", "TOR"], "beam_depth_method"))
    out.append(element_item(c, items["SUP-SLAB"], ["slab"], ["L1", "PH", "TOR"]))
    out += earthworks_items(c, items["EW-EXC"], items["EW-REM"], items["EW-BF"])
    out += waterproofing_items(c, items["WP-SUB-H"], items["WP-SUB-V"])
    blk, walls, heights, ops = blockwork_items(c, items["BLK-EXT"], items["BLK-INT"])
    out += blk
    out += plaster_items(c, items["PL-EXT"], items["PL-INT"], walls, heights, ops)
    out.append(lintel_item(c, items["LINTEL"], ops))
    out += manhole_items(c, items)
    out += tank_items(c, items)
    out += boundary_items(c, items)
    done = {r["item_id"] for r in out}
    for it in model["items"]:
        if it["id"] in done:
            continue
        if it.get("kind") == "lump_sum" or it["automation"] == "Lump Sum":
            out.append(rec(it, status=LUMP, value=1.0, notes=["Lump sum - priced, not measured"]))
        elif it.get("kind") == "excluded" or it["automation"] == "Not Applicable":
            out.append(rec(it, status=NA, notes=["Excluded in Static Group proposals"]))
        else:
            out.append(rec(it, status=REVIEW if it["automation"] == "Requires Engineer Review" else NA_DRAWING,
                           missing=[it.get("review") or f"No automated extraction yet for this item ({it.get('method', '')})"]))
    for r in out:
        if r["value"] is not None and r["candidates"] and not r["confidence"]:
            r["confidence"] = 0.7
    return out
