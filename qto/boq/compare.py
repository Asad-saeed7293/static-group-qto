"""Layer 7 - BOQ comparison and variance analysis.

Pure functions; tolerance bands come from settings, never from code.
    Variance   = Drawing quantity - BOQ quantity
    Variance % = Variance / BOQ quantity x 100   (undefined when BOQ quantity is 0 or missing)
"""
from __future__ import annotations

import difflib
import re

from ..models import ST_CHECK, ST_MISSING, ST_OK, ST_REVIEW, ST_VERIFIED, STATUS_ORDER
from .generate import norm_mark

UNIT_ALIASES = {
    "m3": ["m3", "m³", "cum", "cu.m", "cu m", "cu.m.", "cubic metre", "cubic meter", "m^3"],
    "m2": ["m2", "m²", "sqm", "sq.m", "sq m", "square metre", "square meter", "m^2"],
    "m": ["m", "lm", "rm", "rmt", "metre", "meter", "l.m"],
    "nr": ["nr", "no", "nos", "no.", "each", "ea", "pcs", "number"],
}
FLOOR_TOKENS = {
    "FDN": ["fdn", "foundation", "foundations", "substructure"],
    "BS": ["bs", "basement", "b1", "bf"],
    "GR": ["gr", "gf", "ground", "ground floor", "g.f"],
    "L1": ["l1", "ff", "first", "first floor", "1st"],
    "PH": ["ph", "penthouse"],
    "TOR": ["tor", "roof", "top of roof"],
}


TYPE_KEYWORDS = {
    "footing": ["footing", "foundation", "base"], "raft": ["raft", "mat "], "blinding": ["blinding", "plain concrete", "pcc"],
    "column": ["column"], "wall": ["wall"], "beam": ["beam"], "slab": ["slab"], "pedestal": ["pedestal"],
}


def norm_unit(u: str) -> str | None:
    u = (u or "").strip().lower()
    if not u:
        return None
    for k, al in UNIT_ALIASES.items():
        if u in al:
            return k
    return u


def parse_floor(*texts) -> str | None:
    s = " ".join(t or "" for t in texts).lower()
    for fid, toks in FLOOR_TOKENS.items():
        for t in toks:
            if re.search(rf"(^|[^a-z0-9]){re.escape(t)}($|[^a-z0-9])", s):
                return fid
    return None


def tolerance_status(pct: float, settings: dict) -> str:
    a = abs(pct)
    for band in settings["tolerances"]:
        if a <= band["max_abs_pct"] + 1e-9:
            return band["status"]
    return settings.get("tolerance_above_status", ST_REVIEW)


def _worst(*s):
    order = {x: i for i, x in enumerate(STATUS_ORDER)}
    return max(s, key=lambda x: order.get(x, 0))


def variance(drawing_qty, boq_qty):
    """Returns (variance, variance_pct, note). Safe for zero / missing values."""
    if drawing_qty is None:
        return None, None, "Drawing quantity not available"
    if boq_qty is None:
        return None, None, "BOQ quantity missing"
    v = drawing_qty - boq_qty
    if boq_qty == 0:
        return v, None, "BOQ quantity is zero - percentage undefined"
    return v, v / boq_qty * 100.0, ""


def match_rows(boq_rows: list, lines: list) -> list:
    """Returns [(row, [line indices], method)]."""
    by_mark = {}
    for i, l in enumerate(lines):
        if l["mark_norm"]:
            by_mark.setdefault(l["mark_norm"], []).append(i)
    out = []
    for r in boq_rows:
        m = norm_mark(r.get("element"))
        floor = parse_floor(r.get("floor"), r.get("description")) if (r.get("floor") or r.get("description")) else None
        idx, method = [], ""
        if m and m in by_mark:
            idx = by_mark[m]
            method = "Element ID"
            types = {lines[i]["element_type"] for i in idx}
            if len(types) > 1:  # same mark used by several element types: use description keywords
                desc = (r.get("description") or "").lower()
                kw = [i for i in idx if any(k in desc for k in TYPE_KEYWORDS.get(lines[i]["element_type"], []))]
                if kw:
                    idx, method = kw, "Element ID + element type from description"
            if floor:
                f_idx = [i for i in idx if lines[i]["floor"] == floor]
                if f_idx:
                    idx, method = f_idx, f"Element ID + floor ({floor})"
        elif not m and r.get("description"):
            # suggestion only: best description similarity
            best = max(((difflib.SequenceMatcher(None, r["description"].lower(), l["description"].lower()).ratio(), i)
                        for i, l in enumerate(lines)), default=(0, None))
            if best[0] >= 0.8:
                idx, method = [best[1]], f"Suggested by description similarity ({best[0]:.0%}) - confirm"
        out.append((r, idx, method))
    return out


def compare(boq_rows: list, lines: list, elements_by_uid: dict, settings: dict) -> dict:
    results = []
    used = set()
    for r, idx, method in match_rows(boq_rows, lines):
        matched = [lines[i] for i in idx]
        used.update(idx)
        res = {"boq_row": r["row"], "boq_item_no": r["item_no"], "boq_description": r["description"],
               "boq_element": r["element"], "boq_floor": r.get("floor", ""), "boq_unit": r["unit"], "boq_quantity": r["quantity"],
               "match_method": method, "matched_items": [l["item_no"] for l in matched],
               "element_uids": [u for l in matched for u in l["element_uids"]],
               "drawing_quantity": None, "drawing_unit": "m3", "variance": None, "variance_pct": None,
               "status": ST_REVIEW, "reasons": [], "category": matched[0]["category"] if matched else "Unmatched BOQ items",
               "element_type": matched[0]["element_type"] if matched else ""}
        if not matched:
            res["reasons"].append("BOQ item not found in drawings: no drawing element with this ID"
                                  + (f" ('{r['element']}')" if r["element"] else " (no element ID in BOQ row)"))
            res["status"] = ST_REVIEW
            res["flag"] = "BOQ_ITEM_NOT_IN_DRAWINGS"
            results.append(res)
            continue
        qs = [l["quantity"] for l in matched]
        dq = None if any(q is None for q in qs) else round(sum(qs), 4)
        if any(q is None for q in qs) and any(q is not None for q in qs):
            res["reasons"].append("Some drawing instances lack data; drawing quantity not complete")
        res["drawing_quantity"] = dq
        if len(matched) > 1:
            res["reasons"].append(f"BOQ row covers {len(matched)} drawing lines ({', '.join(l['floor'] for l in matched)}) - compared against their sum")
        bu, du = norm_unit(r["unit"]), "m3"
        if bu and bu != du:
            res["status"] = ST_REVIEW
            res["flag"] = "UNIT_MISMATCH"
            res["reasons"].append(f"Unit mismatch: BOQ '{r['unit']}' vs drawing 'm3' - quantities not comparable")
            results.append(res)
            continue
        if not bu:
            res["reasons"].append("BOQ unit blank - assumed m3")
        v, pct, note = variance(dq, r["quantity"])
        res["variance"] = None if v is None else round(v, 4)
        res["variance_pct"] = None if pct is None else round(pct, 2)
        evidence = _worst(*[l["status"] for l in matched])
        if dq is None:
            res["status"], res["flag"] = ST_MISSING, "MISSING_DRAWING_DATA"
            res["reasons"].append(note + " - see review flags on the elements")
        elif r["quantity"] is None:
            res["status"], res["flag"] = ST_MISSING, "BOQ_QTY_MISSING"
            res["reasons"].append(note)
        elif pct is None:
            res["status"], res["flag"] = ST_REVIEW, "BOQ_QTY_ZERO"
            res["reasons"].append(note)
        else:
            tol = tolerance_status(pct, settings)
            res["tolerance_status"] = tol
            if tol != ST_OK:
                res["flag"] = "LARGE_VARIANCE" if tol == ST_REVIEW else "VARIANCE_CHECK"
                res["reasons"].append(f"Variance {pct:+.2f}% is outside the OK band (±{settings['tolerances'][0]['max_abs_pct']}%)")
            status = _worst(tol, evidence)
            if status == ST_OK and settings.get("verified_requires_cross_checks", True):
                ccs = [c for u in res["element_uids"] for c in elements_by_uid.get(u, {}).get("cross_checks", [])]
                if ccs and all(c["passed"] for c in ccs):
                    status = ST_VERIFIED
                    res["reasons"].append(f"Within tolerance and all {len(ccs)} drawing cross-checks passed")
            elif evidence != ST_OK and tol == ST_OK:
                res["reasons"].append(f"Within tolerance, but drawing evidence is '{evidence}' - see element flags")
            res["status"] = status
        if "Suggested" in method:
            res["status"] = _worst(res["status"], ST_CHECK)
            res["reasons"].append("Match was suggested from the description - confirm it is the right item")
        results.append(res)
    for i, l in enumerate(lines):
        if i in used:
            continue
        results.append({"boq_row": None, "boq_item_no": "", "boq_description": "", "boq_element": "", "boq_floor": "",
                        "boq_unit": "", "boq_quantity": None, "match_method": "", "matched_items": [l["item_no"]],
                        "element_uids": l["element_uids"], "drawing_quantity": l["quantity"], "drawing_unit": "m3",
                        "variance": None, "variance_pct": None, "status": ST_REVIEW, "flag": "DRAWING_ITEM_NOT_IN_BOQ",
                        "reasons": [f"Drawing item {l['item_no']} ({l['description']}) has no BOQ row"],
                        "category": l["category"], "element_type": l["element_type"], "drawing_description": l["description"]})
    for res in results:
        if res["matched_items"] and "drawing_description" not in res:
            res["drawing_description"] = "; ".join(l["description"] for l in lines if l["item_no"] in res["matched_items"])
    return {"rows": results, "summary": summarise(results)}


def summarise(results: list) -> dict:
    from collections import Counter, defaultdict
    st = Counter(r["status"] for r in results)
    cat = defaultdict(lambda: {"drawing": 0.0, "boq": 0.0, "rows": 0})
    for r in results:
        c = cat[r["category"]]
        c["rows"] += 1
        if r["drawing_quantity"] is not None and r["boq_quantity"] is not None and r.get("variance") is not None:
            c["drawing"] += r["drawing_quantity"]
            c["boq"] += r["boq_quantity"]
    for c in cat.values():
        c["variance"] = round(c["drawing"] - c["boq"], 3)
        c["variance_pct"] = round(c["variance"] / c["boq"] * 100, 2) if c["boq"] else None
        c["drawing"], c["boq"] = round(c["drawing"], 3), round(c["boq"], 3)
    return {"by_status": dict(st), "by_category": dict(cat), "total_rows": len(results),
            "flags": dict(Counter(r.get("flag") for r in results if r.get("flag")))}
