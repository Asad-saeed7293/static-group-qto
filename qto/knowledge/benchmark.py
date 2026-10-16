"""Validation of the engine against Static Group's own historical BOQs.

For every line of a historical BOQ: canonical item, engine value (or candidates when a methodology
rule is UNKNOWN), historical value, variance, rules used and their status, missing information,
and a diagnosis listing *possible* causes with the data that supports each one. A cause is only
listed when the data shows it; nothing is concluded automatically.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .model import evaluate_engine, match_row, variant_of

EXACT_PCT = 0.5
TOL_PCT = 5.0


def classify(engine_v, hist_v):
    if hist_v is None:
        return "Not Measured", None
    if engine_v is None:
        return "Unable to Calculate", None
    if hist_v == 0:
        return ("Exact Match" if engine_v == 0 else "Difference"), None
    pct = (engine_v - hist_v) / hist_v * 100
    a = abs(pct)
    return ("Exact Match" if a <= EXACT_PCT else "Within Tolerance" if a <= TOL_PCT else "Difference"), round(pct, 2)


def _wall_key(row):
    m = re.search(r"(\d{3})\s*mm", row["description"])
    th = m.group(1) + "mm" if m else None
    ctx = " ".join(row.get("section_names", [])).lower()
    if "parepet" in row["description"].lower() or "parapet" in row["description"].lower():
        side = "parapet"
    elif "internal" in ctx:
        side = "internal"
    else:
        side = "external"
    return f"{th} {side}" if th else None


def find_records(row, it, items):
    recs = [r for r in items if r["item_id"] == it["id"]]
    if it["id"] in ("BLK-EXT", "BLK-INT"):
        k = _wall_key(row)
        recs = [r for r in recs if r["variant"] == k]
    return recs


def diagnose(row, recs, elements_by_uid, hist):
    """Possible causes of a difference, each with its evidence. Never a conclusion."""
    causes = []
    for r in recs:
        for ref in r["rules"]:
            if ref["selected"] is None:
                causes.append({"cause": "Unknown Static Group convention", "evidence":
                               f"Rule '{ref['title']}' ({ref['rule_id']}) is {ref['status']} - no option is approved."})
        if r["candidates"] and hist:
            best = min(((k, v) for k, v in r["candidates"].items() if v is not None), key=lambda kv: abs(kv[1] - hist), default=None)
            if best:
                causes.append({"cause": "Candidate comparison (not a conclusion)", "evidence":
                               f"Closest candidate to the historical {hist:.2f}: '{best[0]}' = {best[1]:.2f} "
                               f"({(best[1] - hist) / hist * 100:+.1f} %). Other candidates: "
                               + "; ".join(f"{k} = {v:.2f}" for k, v in r["candidates"].items() if v is not None and k != best[0])})
        for m in r["missing"]:
            causes.append({"cause": "Missing information", "evidence": m})
        flags = Counter(f["code"] for u in r["element_uids"] for f in elements_by_uid.get(u, {}).get("flags", []))
        if flags.get("UNIDENTIFIED_ELEMENT"):
            causes.append({"cause": "Unidentified elements", "evidence": f"{flags['UNIDENTIFIED_ELEMENT']} element(s) have no mark, so schedule data could not be linked"})
        if flags.get("MISSING_DEPTH") or flags.get("MISSING_THICKNESS") or flags.get("MISSING_HEIGHT"):
            n = flags.get("MISSING_DEPTH", 0) + flags.get("MISSING_THICKNESS", 0) + flags.get("MISSING_HEIGHT", 0)
            causes.append({"cause": "Elements without a quantity", "evidence": f"{n} element(s) lack depth/thickness/height and are excluded from the engine total"})
        if flags.get("SCHEDULE_MISMATCH"):
            causes.append({"cause": "Drawing / schedule mismatch", "evidence": f"{flags['SCHEDULE_MISMATCH']} element(s) are drawn differently from their schedule"})
        if flags.get("OVERLAPPING_GEOMETRY"):
            causes.append({"cause": "Overlapping geometry", "evidence": f"{flags['OVERLAPPING_GEOMETRY']} overlap flag(s) - shared volume counted twice"})
        if flags.get("AMBIGUOUS_THICKNESS"):
            causes.append({"cause": "Ambiguous slab zones", "evidence": f"{flags['AMBIGUOUS_THICKNESS']} zone(s) with conflicting thickness tags are excluded"})
        for n in r.get("notes", []):
            if "Historical" in n or "UNKNOWN" in n:
                causes.append({"cause": "Method note", "evidence": n})
    if not recs:
        causes.append({"cause": "Not automated", "evidence": "No calculator exists yet for this BOQ line (see the knowledge model / roadmap)."})
    return causes


def run_benchmark(boq: dict, results: dict, model: dict, files: list | None = None) -> dict:
    items = results.get("items")
    els = {e["uid"]: e for e in results.get("elements", [])}
    rows = []
    legacy = {}
    shared = Counter()
    matched = []
    for r in boq["rows"]:
        it, _ = match_row(r, model)
        recs = find_records(r, it, items) if (it and items is not None) else []
        if it and it["id"] in ("BLK-EXT", "BLK-INT") and recs:
            shared[recs[0]["variant"]] += 1
        matched.append((r, it, recs))
    for r, it, recs in matched:
        hist = r["quantity"] if r["kind"] == "measured" else None
        if items is None and it:   # results from older runs without item calculations
            if it["id"] not in legacy:
                legacy[it["id"]] = evaluate_engine(it, results, files, legacy) or {}
            ev = legacy[it["id"]]
            eng, cands, refs, missing, detail = ev.get("value"), {}, [], [], ev.get("detail", "Not automated yet")
        else:
            eng = recs[0]["value"] if len(recs) == 1 else (sum(x["value"] for x in recs) if recs and all(x["value"] is not None for x in recs) else None)
            cands = recs[0]["candidates"] if len(recs) == 1 else {}
            refs = [ref for x in recs for ref in x["rules"]]
            missing = [m for x in recs for m in x["missing"]]
            detail = "; ".join(e for x in recs for e in x["evidence"])[:300] if recs else ("Not automated yet" if it else "No knowledge-model item matches this line")
        status, pct = classify(eng, hist) if r["kind"] == "measured" else ("Not Measured", None)
        if status == "Unable to Calculate" and cands:
            status = "Candidates Only"
        diag = diagnose(r, recs, els, hist) if (r["kind"] == "measured" and status not in ("Exact Match",)) else []
        if recs and recs[0]["item_id"] in ("BLK-EXT", "BLK-INT") and shared[recs[0]["variant"]] > 1:
            diag.insert(0, {"cause": "Wall type split", "evidence": f"The historical BOQ splits {recs[0]['variant']} walls into {shared[recs[0]['variant']]} lines (block make-up); the engine measures the thickness only, so each line is compared with the same engine total."})
        rows.append({
            "sheet": r["sheet"], "row": r["row"], "item": r["item"], "description": r["description"], "unit": r["unit"],
            "kind": r["kind"], "historical_qty": hist, "item_id": it["id"] if it else None,
            "category": it["category"] if it else "Unmapped", "variant": recs[0]["variant"] if len(recs) == 1 else variant_of(r),
            "automation": it["automation"] if it else "Unmapped", "engine_qty": eng, "candidates": cands,
            "engine_status": recs[0]["status"] if len(recs) == 1 else ("Not automated" if not recs else "Multiple"),
            "rules": refs, "missing": missing, "engine_detail": detail,
            "element_uids": [u for x in recs for u in x["element_uids"]][:400],
            "formula": recs[0]["formula"] if recs else "",
            "status": status, "diff_pct": pct, "diagnosis": diag,
            "diff": round(eng - hist, 3) if (eng is not None and hist is not None) else None,
        })
    measured = [x for x in rows if x["kind"] == "measured"]
    summary = {
        "boq_lines": len(rows), "measured_lines": len(measured),
        "mapped_to_model": sum(1 for x in rows if x["item_id"]),
        "by_status": dict(Counter(x["status"] for x in measured)),
        "by_category": {},
        "unknown_rules_involved": sorted({ref["rule_id"] for x in measured for ref in x["rules"] if ref["selected"] is None}),
    }
    cats = defaultdict(Counter)
    for x in measured:
        cats[x["category"]][x["status"]] += 1
    summary["by_category"] = {k: dict(v) for k, v in cats.items()}
    return {"rows": rows, "summary": summary}
