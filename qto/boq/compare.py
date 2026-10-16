"""Layer 7 - BOQ comparison and variance analysis.

Pure functions; tolerance bands come from settings, never from code.
    Variance   = Drawing quantity - BOQ quantity
    Variance % = Variance / BOQ quantity x 100   (undefined when BOQ quantity is 0 or missing)
"""
from __future__ import annotations

import difflib
import re
from collections import defaultdict

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
DESCRIPTION_ALIASES = {
    "reinforced concrete": "rc concrete",
    "reinforced cement concrete": "rc concrete",
    "plain cement concrete": "plain concrete",
    "pcc": "plain concrete",
    "ground floor": "ground",
    "first floor": "first",
}


def norm_unit(u: str) -> str | None:
    u = (u or "").strip().lower()
    if not u:
        return None
    for k, al in UNIT_ALIASES.items():
        if u in al:
            return k
    return u


def norm_code(code) -> str:
    """Normalise formatting in codes without changing their alphanumeric identity."""
    return re.sub(r"[^A-Z0-9]", "", str(code or "").upper())


def norm_description(text) -> str:
    s = re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()
    for src, dst in DESCRIPTION_ALIASES.items():
        s = re.sub(rf"\b{re.escape(src)}\b", dst, s)
    return re.sub(r"\s+", " ", s)


def _description_score(a, b) -> float:
    left, right = norm_description(a), norm_description(b)
    if not left or not right:
        return 0.0
    seq = difflib.SequenceMatcher(None, left, right).ratio()
    la, lb = set(left.split()), set(right.split())
    token = len(la & lb) / len(la | lb) if la or lb else 0.0
    return max(seq, token)


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


def match_rows(boq_rows: list, lines: list, details: bool = False) -> list:
    """Return row matches. Fuzzy results remain suggestions and ambiguous candidates stay unmatched."""
    by_mark, by_item = {}, {}
    for i, l in enumerate(lines):
        if l["mark_norm"]:
            by_mark.setdefault(l["mark_norm"], []).append(i)
        code = norm_code(l.get("item_no"))
        if code:
            by_item.setdefault(code, []).append(i)
    out = []
    for r in boq_rows:
        m = norm_mark(r.get("element"))
        floor = parse_floor(r.get("floor"), r.get("description")) if (r.get("floor") or r.get("description")) else None
        idx, method, match_class, candidates = [], "", "unmatched", []
        if m and m in by_mark:
            idx = by_mark[m]
            method = "Element ID"
            match_class = "exact"
            candidates = idx[:]
            types = {lines[i]["element_type"] for i in idx}
            if len(types) > 1:  # same mark used by several element types: use description keywords
                desc = norm_description(r.get("description"))
                kw = [i for i in idx if any(k in desc for k in TYPE_KEYWORDS.get(lines[i]["element_type"], []))]
                if kw:
                    idx, method = kw, "Element ID + element type from description"
                    candidates = idx[:]
                else:
                    idx, match_class, method = [], "ambiguous", "Ambiguous element ID (multiple element types)"
            if floor:
                f_idx = [i for i in idx if lines[i]["floor"] == floor]
                if f_idx:
                    idx, method = f_idx, f"Element ID + floor ({floor})"
                    candidates = idx[:]
                elif idx:
                    candidates = idx[:]
                    idx, match_class, method = [], "ambiguous", f"Element ID does not occur on floor {floor}"
        elif r.get("item_no") and norm_code(r.get("item_no")) in by_item:
            candidate_idx = by_item[norm_code(r.get("item_no"))]
            if len(candidate_idx) == 1:
                idx, candidates, method, match_class = candidate_idx, candidate_idx[:], "BOQ item code", "exact"
            else:
                candidates, match_class = candidate_idx, "ambiguous"
                method = "Ambiguous BOQ item code"
        elif r.get("description"):
            ranked = sorted(((_description_score(r["description"], l["description"]), i) for i, l in enumerate(lines)),
                            reverse=True)
            if ranked and ranked[0][0] >= 0.65:
                best = ranked[0][0]
                candidates = [i for score, i in ranked if score >= 0.65 and best - score < 0.08]
                if len(candidates) == 1:
                    idx, method, match_class = candidates, f"Suggested by description similarity ({best:.0%}) - confirm", "suggested"
                else:
                    method, match_class = "Ambiguous description candidates", "ambiguous"
        detail = {"match_class": match_class, "candidate_indices": candidates,
                  "candidate_scores": [{"item_no": lines[i].get("item_no", ""), "score": round(_description_score(r.get("description"), lines[i].get("description")), 3)}
                                       for i in candidates]}
        out.append((r, idx, method, detail) if details else (r, idx, method))
    return out


def compare(boq_rows: list, lines: list, elements_by_uid: dict, settings: dict,
            approved_mappings: dict | None = None, mapping_issues: dict | None = None) -> dict:
    approved_mappings = approved_mappings or {}
    mapping_issues = mapping_issues or {}
    results = []
    used = set()
    codes = defaultdict(list)
    for r in boq_rows:
        code = norm_code(r.get("item_no"))
        if code:
            codes[code].append(r)
    duplicate_rows, reused_rows = set(), set()
    for code_rows in codes.values():
        if len(code_rows) < 2:
            continue
        if any(r.get("section") for r in code_rows):
            scopes = defaultdict(list)
            for r in code_rows:
                scopes[norm_description(r.get("section"))].append(r)
            duplicate_groups = [group for group in scopes.values() if len(group) > 1]
        else:
            descriptions = defaultdict(list)
            for r in code_rows:
                descriptions[(norm_description(r.get("description")), norm_unit(r.get("unit")),
                              norm_code(r.get("floor")))].append(r)
            duplicate_groups = [group for group in descriptions.values() if len(group) > 1]
            duplicate_records = {id(r) for group in duplicate_groups for r in group}
            reused_rows.update(r.get("source_row", r.get("row")) for r in code_rows if id(r) not in duplicate_records)
        duplicate_rows.update(r.get("source_row", r.get("row")) for group in duplicate_groups for r in group)
    matches = match_rows(boq_rows, lines, details=True)
    adjusted = []
    for r, idx, method, match in matches:
        key = r.get("mapping_key")
        if key in mapping_issues:
            match = {**match, "match_class": "stale"}
            idx, method = [], "Previously approved mapping requires review"
        elif key in approved_mappings:
            mapping = approved_mappings[key]
            idx = [mapping["target_index"]]
            method = f"Estimator-approved mapping v{mapping['version']}"
            match = {**match, "match_class": "approved"}
        elif (r.get("mapping_record", {}).get("status") == "approved"
              and r.get("mapping_record", {}).get("target_type") == "canonical"
              and match["match_class"] == "suggested"):
            idx = []
            method = "Canonical BOQ item approved; calculated-line suggestion remains unapproved"
        elif r.get("mapping_record", {}).get("status") == "rejected":
            idx, method = [], "Candidate rejected by estimator"
            match = {**match, "match_class": "rejected"}
        elif r.get("mapping_record", {}).get("status") == "unresolved":
            idx, method = [], "Left unresolved by estimator"
            match = {**match, "match_class": "unresolved"}
        adjusted.append((r, idx, method, match))
    matches = adjusted
    mapping_owners = defaultdict(list)
    for r, idx, _, _ in matches:
        for line_idx in idx:
            mapping_owners[line_idx].append(r.get("source_row", r.get("row")))
    duplicate_mapping_rows = {row for owners in mapping_owners.values() if len(set(owners)) > 1 for row in owners}
    for r, idx, method, match in matches:
        matched = [lines[i] for i in idx]
        used.update(idx or match["candidate_indices"])
        source_row = r.get("source_row", r.get("row"))
        decision = "review duplicate code" if source_row in duplicate_rows else (
            "review reused display code" if source_row in reused_rows else
            "review duplicate drawing mapping" if source_row in duplicate_mapping_rows else
            "exact" if match["match_class"] == "exact" else
            "suggestion pending confirmation" if match["match_class"] == "suggested" else match["match_class"])
        row_flags = []
        if source_row in duplicate_rows:
            row_flags.append("DUPLICATE_BOQ_CODE")
        if source_row in reused_rows:
            row_flags.append("REUSED_BOQ_CODE")
        if source_row in duplicate_mapping_rows:
            row_flags.append("DUPLICATE_DRAWING_MAPPING")
        res = {"boq_row": source_row, "boq_source_row": source_row,
               "boq_sheet": r.get("source_sheet"), "boq_item_no": r["item_no"], "boq_description": r["description"],
               "boq_original": {k: r.get(k) for k in ("source_item_no", "source_description", "source_unit", "source_quantity")},
               "boq_element": r["element"], "boq_floor": r.get("floor", ""), "boq_unit": r["unit"], "boq_quantity": r["quantity"],
               "match_method": method, "match_class": match["match_class"],
               "mapping_decision": decision,
               "mapping_status": r.get("mapping_record", {}).get("status"),
               "mapping_id": r.get("mapping_key"),
               "mapping_target_key": r.get("mapping_record", {}).get("target_key"),
               "mapping_target_type": r.get("mapping_record", {}).get("target_type"),
               "mapping_target_code": r.get("mapping_record", {}).get("target_code"),
               "mapping_target_description": r.get("mapping_record", {}).get("target_description"),
               "mapping_target_category": r.get("mapping_record", {}).get("target_category"),
               "mapping_target_unit": r.get("mapping_record", {}).get("target_unit"),
               "mapping_version": r.get("mapping_record", {}).get("version"),
               "mapping_reviewer": r.get("mapping_record", {}).get("reviewer"),
               "mapping_timestamp": r.get("mapping_record", {}).get("timestamp"),
               "mapping_comment": r.get("mapping_record", {}).get("comment"),
               "mapping_source_identity": r.get("mapping_record", {}).get("source_identity"),
               "mapping_history": r.get("mapping_record", {}).get("history", []),
               "candidate_items": [lines[i].get("item_no", "") for i in match["candidate_indices"]],
               "candidate_scores": match["candidate_scores"], "matched_items": [l.get("item_no", "") for l in matched],
               "candidate_refs": [{"match_key": lines[i].get("match_key"), "item_no": lines[i].get("item_no", ""), "qids": lines[i].get("qids", []),
                                   "element_uids": lines[i].get("element_uids", []),
                                   "evidence": lines[i].get("calculation_evidence", [])}
                                  for i in match["candidate_indices"]],
               "element_uids": [u for l in matched for u in l["element_uids"]],
               "calculation_refs": [{"item_no": l.get("item_no", ""), "qids": l.get("qids", []),
                                     "element_uids": l.get("element_uids", []),
                                     "evidence": l.get("calculation_evidence", [])}
                                    for l in matched],
               "drawing_quantity": None, "drawing_unit": "m3", "variance": None, "variance_pct": None,
               "absolute_variance": None,
               "status": ST_REVIEW, "reasons": [], "flags": row_flags,
               "category": matched[0]["category"] if matched else "Unmatched BOQ items",
               "element_type": matched[0]["element_type"] if matched else ""}
        if r.get("issues"):
            res["reasons"].extend(r["issues"])
        if (res.get("mapping_status") == "approved" and res.get("mapping_target_type") == "canonical"):
            res["reasons"].append(
                f"BOQ item is linked to canonical item {res.get('mapping_target_code')}: "
                f"{res.get('mapping_target_description')}. Canonical items are not measured quantities."
            )
        if r.get("source_row", r.get("row")) in duplicate_rows:
            res["flag"] = "DUPLICATE_BOQ_CODE"
            res["status"] = ST_REVIEW
            res["reasons"].append(f"BOQ item code '{r.get('item_no')}' occurs on multiple source rows.")
        elif source_row in reused_rows:
            res["flag"] = "REUSED_BOQ_CODE"
            res["status"] = ST_REVIEW
            res["reasons"].append(f"BOQ display code '{r.get('item_no')}' is reused; no section field was available to verify scope.")
        if source_row in duplicate_mapping_rows:
            res["flag"] = res.get("flag") or "DUPLICATE_DRAWING_MAPPING"
            res["status"] = ST_REVIEW
            res["reasons"].append("This calculated drawing line is mapped to multiple BOQ rows; check for double counting.")
        if r.get("mapping_key") in mapping_issues:
            row_flags.append("STALE_BOQ_MAPPING")
            res["flags"].append("STALE_BOQ_MAPPING")
            res["mapping_decision"] = "review stale mapping"
            res["reasons"].extend(mapping_issues[r["mapping_key"]])
        if not matched:
            if match["match_class"] == "stale":
                res["flag"] = res.get("flag") or "STALE_BOQ_MAPPING"
                res["mapping_decision"] = "review stale mapping"
            elif match["match_class"] == "ambiguous":
                res["reasons"].append("Multiple plausible calculated items; no quantity was selected automatically.")
                res["flags"].append("AMBIGUOUS_MATCH")
                res["flag"] = res.get("flag") or "AMBIGUOUS_MATCH"
            elif match["match_class"] != "suggested":
                res["reasons"].append("BOQ item not found in drawings: no drawing element with this ID"
                                      + (f" ('{r['element']}')" if r["element"] else " (no element ID in BOQ row)"))
                res["flags"].append("BOQ_ITEM_NOT_IN_DRAWINGS")
                res["flag"] = res.get("flag") or "BOQ_ITEM_NOT_IN_DRAWINGS"
            if not res.get("flag"):
                res["flags"].append("BOQ_ITEM_NOT_IN_DRAWINGS")
                res["flag"] = "BOQ_ITEM_NOT_IN_DRAWINGS"
            res["status"] = ST_REVIEW
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
            res["flags"].append("UNIT_MISMATCH")
            res["reasons"].append(f"Unit mismatch: BOQ '{r['unit']}' vs drawing 'm3' - quantities not comparable")
            results.append(res)
            continue
        if not bu:
            res["status"], res["flag"] = ST_REVIEW, "BOQ_UNIT_MISSING"
            res["flags"].append("BOQ_UNIT_MISSING")
            res["reasons"].append("BOQ unit is blank or unsupported - quantities were not compared.")
            results.append(res)
            continue
        v, pct, note = variance(dq, r["quantity"])
        res["variance"] = None if v is None else round(v, 4)
        res["absolute_variance"] = None if v is None else round(abs(v), 4)
        res["variance_pct"] = None if pct is None else round(pct, 2)
        evidence = _worst(*[l["status"] for l in matched])
        if dq is None:
            res["status"], res["flag"] = ST_MISSING, "MISSING_DRAWING_DATA"
            res["flags"].append("MISSING_DRAWING_DATA")
            res["reasons"].append(note + " - see review flags on the elements")
        elif r["quantity"] is None:
            res["status"], res["flag"] = ST_MISSING, "BOQ_QTY_MISSING"
            res["flags"].append("BOQ_QTY_MISSING")
            res["reasons"].append(note)
        elif pct is None:
            res["status"], res["flag"] = ST_REVIEW, "BOQ_QTY_ZERO"
            res["flags"].append("BOQ_QTY_ZERO")
            res["reasons"].append(note)
        else:
            tol = tolerance_status(pct, settings)
            res["tolerance_status"] = tol
            if tol != ST_OK:
                res["flag"] = "LARGE_VARIANCE" if tol == ST_REVIEW else "VARIANCE_CHECK"
                res["flags"].append(res["flag"])
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
        if match["match_class"] == "suggested":
            res["status"] = _worst(res["status"], ST_CHECK)
            res["reasons"].append("Match was suggested from the description - confirm it is the right item")
        elif match["match_class"] == "approved":
            res["mapping_decision"] = "estimator approved"
        if {"DUPLICATE_BOQ_CODE", "REUSED_BOQ_CODE", "DUPLICATE_DRAWING_MAPPING"} & set(res["flags"]):
            res["status"] = _worst(res["status"], ST_REVIEW)
        results.append(res)
    for i, l in enumerate(lines):
        if i in used:
            continue
        results.append({"boq_row": None, "boq_item_no": "", "boq_description": "", "boq_element": "", "boq_floor": "",
                        "boq_unit": "", "boq_quantity": None, "match_method": "", "matched_items": [l.get("item_no", "")],
                        "element_uids": l["element_uids"], "drawing_quantity": l["quantity"], "drawing_unit": "m3",
                        "variance": None, "variance_pct": None, "status": ST_REVIEW, "flag": "DRAWING_ITEM_NOT_IN_BOQ",
                        "flags": ["DRAWING_ITEM_NOT_IN_BOQ"], "match_class": "unmatched",
                        "mapping_decision": "unmatched",
                        "reasons": [f"Drawing item {l.get('item_no', '')} ({l['description']}) has no BOQ row"],
                        "category": l["category"], "element_type": l["element_type"], "drawing_description": l["description"]})
    for res in results:
        if res["matched_items"] and "drawing_description" not in res:
            res["drawing_description"] = "; ".join(l["description"] for l in lines if l.get("item_no", "") in res["matched_items"])
    return {"rows": results, "summary": summarise(results)}


def summarise(results: list) -> dict:
    from collections import Counter, defaultdict
    st = Counter(r["status"] for r in results)
    cat = defaultdict(lambda: {"drawing": 0.0, "boq": 0.0, "rows": 0})
    for r in results:
        c = cat[r["category"]]
        c["rows"] += 1
        if (r.get("mapping_decision") in ("exact", "estimator approved") and not ({"DUPLICATE_BOQ_CODE", "REUSED_BOQ_CODE", "DUPLICATE_DRAWING_MAPPING", "STALE_BOQ_MAPPING"} & set(r.get("flags", [])))
                and r["drawing_quantity"] is not None and r["boq_quantity"] is not None and r.get("variance") is not None):
            c["drawing"] += r["drawing_quantity"]
            c["boq"] += r["boq_quantity"]
    for c in cat.values():
        c["variance"] = round(c["drawing"] - c["boq"], 3)
        c["variance_pct"] = round(c["variance"] / c["boq"] * 100, 2) if c["boq"] else None
        c["drawing"], c["boq"] = round(c["drawing"], 3), round(c["boq"], 3)
    return {"by_status": dict(st), "by_category": dict(cat), "total_rows": len(results),
            "flags": dict(Counter(r.get("flag") for r in results if r.get("flag")))}
