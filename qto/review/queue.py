"""Layer 8 - review queue.

Collects every questionable item - element flags, comparison flags, orphan
labels/outlines - into one list an engineer can work through. Flags that apply
identically to many elements (e.g. 'height derived from level tags') are grouped
per floor so the queue stays readable.
"""
from __future__ import annotations

from collections import OrderedDict

from ..models import ST_CHECK, ST_MISSING, ST_OK, ST_REVIEW, STATUS_ORDER

GROUPED = {"HEIGHT_DERIVED", "WALL_HEIGHT_STOREY", "LABEL_INTERPRETATION", "ZONE_SPLIT_ALONG_BEAMS"}
SKIP = {"USER_INPUT"}
PRIORITY = {ST_REVIEW: 0, ST_MISSING: 1, ST_CHECK: 2, ST_OK: 3}


def build_queue(elements: list, comparison: dict | None, orphans: dict, decisions: dict) -> list:
    items = OrderedDict()
    for e in elements:
        for f in e["flags"]:
            if f["code"] in SKIP or f["status_impact"] == ST_OK:
                continue
            if f["code"] in GROUPED:
                key = f"GRP:{f['code']}:{e['element_type']}:{e['floor']}"
                it = items.get(key)
                if not it:
                    it = items[key] = _item(key, "element-group", f, e)
                    it["title"] = f"{f['title']} ({e['element_type']}s, {e['floor']})"
                    it["element_uids"] = []
                it["element_uids"].append(e["uid"])
                it["count"] = len(it["element_uids"])
                continue
            key = f"{e['uid']}:{f['code']}"
            it = _item(key, "element", f, e)
            it["element_uids"] = [e["uid"]]
            if f["code"] == "SUGGESTION" and e["attributes"].get("suggested_thickness_mm"):
                it["action"] = {"type": "slab_thickness", "uid": e["uid"], "value": e["attributes"]["suggested_thickness_mm"],
                                "label": f"Accept {e['attributes']['suggested_thickness_mm']} mm"}
            if f["code"] in ("MISSING_THICKNESS", "AMBIGUOUS_THICKNESS") and e["element_type"] == "slab":
                it["action"] = it.get("action") or {"type": "slab_thickness", "uid": e["uid"], "value": "", "label": "Enter thickness"}
            if f["code"] == "MISSING_HEIGHT":
                it["action"] = {"type": "storey_height", "floor": e["floor"], "label": "Enter storey height"}
            items[key] = it
    if comparison:
        for r in comparison["rows"]:
            flags = r.get("flags") or ([r["flag"]] if r.get("flag") else [])
            if r["status"] in (ST_OK, "Verified") and not flags:
                continue
            for code in flags:
                key = f"CMP:{r.get('boq_row') or ','.join(r.get('matched_items') or ['unmatched'])}:{code}"
                items[key] = {
                    "id": key, "source": "comparison", "code": code, "title": _cmp_title(code),
                    "detail": "; ".join(r["reasons"]), "severity": "warning", "status_impact": r["status"],
                    "element_uids": r["element_uids"], "mark": r.get("boq_element") or "", "element_type": r.get("element_type", ""),
                    "floor": "", "drawing": "", "drawing_id": "", "boq_row": r.get("boq_row"),
                    "boq_item_no": r.get("boq_item_no", ""), "boq_unit": r.get("boq_unit", ""),
                    "boq_source_file": r.get("boq_source_file", ""), "boq_sheet": r.get("boq_sheet", ""),
                    "boq_source_import_id": r.get("boq_source_import_id", ""),
                    "boq_source_fingerprint": r.get("boq_source_fingerprint", ""),
                    "variance_pct": r.get("variance_pct"), "match_class": r.get("match_class"),
                    "mapping_status": r.get("mapping_status"), "mapping_id": r.get("mapping_id"),
                    "mapping_version": r.get("mapping_version"), "mapping_reviewer": r.get("mapping_reviewer"),
                    "mapping_timestamp": r.get("mapping_timestamp"), "mapping_target_type": r.get("mapping_target_type"),
                    "mapping_target_key": r.get("mapping_target_key"), "mapping_target_code": r.get("mapping_target_code"),
                    "mapping_target_category": r.get("mapping_target_category"), "mapping_target_unit": r.get("mapping_target_unit"),
                    "mapping_history": r.get("mapping_history", []),
                    "match_method": r.get("match_method"), "candidate_items": r.get("candidate_items", []),
                    "calculation_refs": r.get("calculation_refs", []), "candidate_refs": r.get("candidate_refs", []),
                    "count": len(r["element_uids"]),
                }
    for t in orphans.get("labels", []):
        key = f"ORPHAN:{t['drawing_id']}:{t['handle']}"
        items[key] = {"id": key, "source": "drawing", "code": "LABEL_NOT_ATTACHED", "title": f"Label '{t['text']}' not attached to geometry",
                      "detail": f"Text '{t['text']}' ({t['handle']}, layer {t['layer']}) on {t['drawing']} could not be paired with a drawn element. "
                                "The element may be drawn with unsupported geometry, or the label may be misplaced.",
                      "severity": "warning", "status_impact": ST_REVIEW, "element_uids": [], "mark": t["text"], "element_type": "",
                      "floor": "", "drawing": t["drawing"], "drawing_id": t["drawing_id"], "handle": t["handle"], "point": t["insert"], "count": 1}
    for o in orphans.get("outlines", []):
        key = f"ORPHAN:{o['drawing_id']}:{o['handle']}"
        items[key] = {"id": key, "source": "drawing", "code": "UNCLASSIFIED_GEOMETRY", "title": "Outline on structural layer not classified",
                      "detail": f"Closed outline {o['handle']} on {o['layer']} ({o['drawing']}) did not match any element rule.",
                      "severity": "info", "status_impact": ST_CHECK, "element_uids": [], "mark": "", "element_type": "",
                      "floor": "", "drawing": o["drawing"], "drawing_id": o["drawing_id"], "handle": o["handle"],
                      "bbox": o.get("bbox"), "count": 1}
    out = list(items.values())
    for it in out:
        d = decisions.get(it["id"])
        it["decision"] = d or {"state": "Open"}
    out.sort(key=lambda i: (i["decision"]["state"] != "Open", PRIORITY.get(i["status_impact"], 9), i["code"], i["id"]))
    return out


def _item(key, source, f, e):
    return {"id": key, "source": source, "code": f["code"], "title": f["title"], "detail": f["detail"],
            "severity": f["severity"], "status_impact": f["status_impact"], "mark": e["mark"],
            "element_type": e["element_type"], "floor": e["floor"], "drawing": e["drawing"], "drawing_id": e["drawing_id"], "count": 1}


def _cmp_title(code):
    return {"BOQ_ITEM_NOT_IN_DRAWINGS": "BOQ item not found in drawings",
            "DRAWING_ITEM_NOT_IN_BOQ": "Drawing item missing from BOQ",
            "UNIT_MISMATCH": "Unit mismatch", "BOQ_UNIT_MISSING": "BOQ unit missing",
            "DUPLICATE_BOQ_CODE": "Duplicate BOQ item code", "AMBIGUOUS_MATCH": "Ambiguous BOQ match",
            "REUSED_BOQ_CODE": "Reused BOQ display code", "DUPLICATE_DRAWING_MAPPING": "Calculated line mapped more than once",
            "STALE_BOQ_MAPPING": "Approved BOQ mapping needs review",
            "LARGE_VARIANCE": "Large quantity variance",
            "VARIANCE_CHECK": "Variance to check", "BOQ_QTY_ZERO": "BOQ quantity is zero",
            "BOQ_QTY_MISSING": "BOQ quantity missing", "MISSING_DRAWING_DATA": "Drawing data missing for BOQ item"}.get(code, code)
