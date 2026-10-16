"""BOQ knowledge model: load canonical items, match BOQ lines to them, evaluate engine rules."""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(ROOT, "config", "knowledge", "static_boq_model.json")


def load_model(path: str = MODEL_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        m = json.load(fh)
    m["by_id"] = {i["id"]: i for i in m["items"]}
    return m


def context_of(row: dict) -> set:
    """Section context tags derived from the BOQ position (sheet + section headings)."""
    txt = " ".join([row.get("sheet", "")] + row.get("section_names", [])).lower()
    ctx = set()
    if "boundary" in txt:
        ctx.add("boundary")
    if "tank" in txt and "plinth" not in txt:
        ctx.add("tanks")
    if "external block" in txt:
        ctx.add("external block")
    if "internal block" in txt:
        ctx.add("internal block")
    if "earth works" in txt:
        ctx.add("b.1")
    if "sub-structure" in txt or "sub structure" in txt:
        ctx.add("b.2.1")
    return ctx


def match_row(row: dict, model: dict):
    """Return (item, score) or (None, 0). Items with a section_hint only match inside that context."""
    desc = row["description"].lower()
    ctx = context_of(row)
    best, best_score = None, 0
    for it in model["items"]:
        hint = it.get("section_hint")
        if "boundary" in ctx and not it["id"].startswith(("BW-", "PL-")):
            continue  # boundary-wall section lines only map to boundary-wall items
        if hint and hint not in ctx:
            continue
        for pat in it.get("match", []):
            if re.search(pat, desc):
                score = len(pat) + (20 if hint else 0)
                if score > best_score:
                    best, best_score = it, score
    return best, best_score


def variant_of(row: dict) -> str:
    """Thickness / type variant for items measured per wall type (e.g. '200mm Insulated hollow')."""
    m = re.search(r"(\d{3})\s*mm", row["description"])
    t = re.search(r"\(([^)]*)\)", row["description"])
    return " ".join(x for x in [(m.group(1) + "mm") if m else "", (t.group(1).strip() if t else "")] if x)


def evaluate_engine(item: dict, results: dict, project_files: list | None = None, computed: dict | None = None):
    """Compute an item's quantity from engine results. Returns dict or None when not automated.

    results: {'elements': [...dict], 'quantities': [...dict]}
    """
    rule = item.get("engine")
    if not rule:
        return None
    computed = computed or {}
    if "derived" in rule:
        src = computed.get(rule["of"])
        if not src or src.get("value") is None:
            return {"value": None, "detail": f"depends on {rule['of']} which is not calculated", "uids": []}
        return {"value": src["value"], "detail": f"= {rule['of']}", "uids": src.get("uids", [])}
    if "elements" in rule:
        els = {e["uid"]: e for e in results["elements"] if e["element_type"] in rule["elements"]
               and (not rule.get("floors") or e["floor"] in rule["floors"])}
        total, missing, uids = 0.0, 0, []
        by_floor = defaultdict(float)
        for q in results["quantities"]:
            if q["element_uid"] in els and q["quantity_type"] == rule["quantity"]:
                uids.append(q["element_uid"])
                if q["value"] is None:
                    missing += 1
                else:
                    total += q["value"]
                    by_floor[els[q["element_uid"]]["floor"]] += q["value"]
        return {"value": round(total, 3) if uids else None, "missing": missing, "count": len(uids), "uids": uids,
                "by_floor": {k: round(v, 3) for k, v in by_floor.items()},
                "detail": f"{len(uids)} {'/'.join(rule['elements'])} element(s)" + (f", {missing} without data" if missing else "")}
    if "text_count" in rule:
        tc = rule["text_count"]
        hits = []
        for d in project_files or []:
            if re.search(tc["drawing_regex"], d.get("file", "")):
                for t in (d.get("facts") or {}).get("all_texts", []) or d.get("_texts", []):
                    if re.search(tc["regex"], t["text"], re.I):
                        hits.append(t)
        return {"value": float(len(hits)) if hits else None, "detail": f"{len(hits)} label(s) matching '{tc['regex']}'", "uids": []}
    return None
