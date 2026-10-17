"""Live-pilot measurement record: manual take-off vs the automated system on a real project.

Manual figures are entered by Static Group (never estimated here). Automated figures are read from the
application (run durations, BOQ statuses, audit trail). A difference is computed only when both sides
exist; no overall accuracy percentage or time-saving figure is produced.
Stored in data/projects/<pid>/pilot.json.
"""
from __future__ import annotations

import datetime as dt
import time

from . import store

REVISION_STATE = "Implemented — Real Revised Drawing Validation Pending"
EMPTY = {"manual": {"takeoff_hours": None, "boq_hours": None, "review_hours": None, "missing_items_found": None, "corrections": None},
         "automated": {"estimator_review_hours": None, "accepted_quantities": None, "rejected_quantities": None},
         "quantities": [],      # [{item_id, variant, manual_qty, unit, note}]
         "revision": {"real_revision_received": False, "manual_review_required": None, "notes": ""},
         "notes": ""}
NUM = {("manual", k) for k in EMPTY["manual"]} | {("automated", k) for k in EMPTY["automated"]}


def load(pid):
    rec = store.read_json(store.pdir(pid, "pilot.json"))
    out = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in EMPTY.items()}
    for k, v in (rec or {}).items():
        out[k] = {**out[k], **v} if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out


def _num(v):
    if v in (None, ""):
        return None
    v = float(v)
    if v < 0:
        raise ValueError("Values cannot be negative")
    return v


def save(pid, body):
    rec = load(pid)
    for sec in ("manual", "automated", "revision"):
        for k, v in (body.get(sec) or {}).items():
            if k in rec[sec]:
                rec[sec][k] = _num(v) if (sec, k) in NUM else v
    if "quantities" in body:
        qs = []
        for q in body["quantities"] or []:
            if q.get("item_id"):
                qs.append({"item_id": q["item_id"], "variant": q.get("variant", ""), "manual_qty": _num(q.get("manual_qty")),
                           "unit": q.get("unit", ""), "note": q.get("note", "")})
        rec["quantities"] = qs
    if "notes" in body:
        rec["notes"] = body["notes"]
    rec["updated"], rec["updated_by"] = store.now(), store.user()
    store.write_json(store.pdir(pid, "pilot.json"), rec)
    store.audit(pid, "pilot_record_updated", sections=sorted(k for k in body))
    return rec


def _dur(meta):
    try:
        return (dt.datetime.fromisoformat(meta["finished"]) - dt.datetime.fromisoformat(meta["started"])).total_seconds()
    except Exception:
        return None


def automated_facts(pid):
    from .boq.static_template import generate_static_boq
    from .knowledge.rules_engine import load_rules
    runs = store.list_runs(pid)
    full = next((r for r in runs if r.get("kind") != "recalculation"), None)
    calc = next((r for r in runs if r.get("kind") == "recalculation"), None) or full
    rid = store.latest_run_id(pid)
    res = store.read_json(store.run_path(pid, rid, "results.json")) if rid else None
    items = (res or {}).get("items") or []
    t0 = time.perf_counter()
    boq = generate_static_boq(items) if items else None
    gen = time.perf_counter() - t0 if boq else None
    audit = store.audit_log(pid, 1_000_000)
    rules = load_rules(pid).values()
    return {"processing_seconds": _dur(full) if full else None, "processing_run": full["run_id"] if full else None,
            "calculation_seconds": _dur(calc) if calc else None, "calculation_run": calc["run_id"] if calc else None,
            "boq_generation_seconds": round(gen, 3) if gen is not None else None,
            "boq_lines": len(items), "boq_status": (boq or {}).get("summary", {}),
            "missing_lines": sum(1 for i in items if i["status"] in ("Requires Input", "Not Available From Drawing")),
            "corrections": sum(1 for a in audit if a["event"] in ("override_changed", "inputs_changed")),
            "review_decisions": sum(1 for a in audit if a["event"] == "review_decision"),
            "rules_confirmed": sum(1 for r in rules if r["status"] == "CONFIRMED"),
            "rules_unconfirmed": sum(1 for r in rules if r["status"] != "CONFIRMED"),
            "items": items}


def report(pid):
    from .changes import compare_runs
    rec, auto = load(pid), automated_facts(pid)
    items = auto.pop("items")
    by = {(i["item_id"], i["variant"]): i for i in items}

    def diff(a, b):
        return round(b - a, 3) if a is not None and b is not None else None
    h = lambda s: round(s / 3600, 3) if s is not None else None
    rows = [
        {"category": "Takeoff time (h)", "manual": rec["manual"]["takeoff_hours"], "automated": h(auto["processing_seconds"]),
         "note": "Automated = drawing processing run duration"},
        {"category": "BOQ preparation (h)", "manual": rec["manual"]["boq_hours"], "automated": h((auto["calculation_seconds"] or 0) + (auto["boq_generation_seconds"] or 0)) if auto["calculation_seconds"] is not None else None,
         "note": "Automated = latest calculation run + BOQ generation"},
        {"category": "Review time (h)", "manual": rec["manual"]["review_hours"], "automated": rec["automated"]["estimator_review_hours"],
         "note": "Automated = estimator review hours entered for the pilot"},
        {"category": "Missing information (lines)", "manual": rec["manual"]["missing_items_found"], "automated": auto["missing_lines"], "note": ""},
        {"category": "Corrections", "manual": rec["manual"]["corrections"], "automated": auto["corrections"], "note": "Automated = audited input / override changes"},
    ]
    for r in rows:
        r["difference"] = diff(r["manual"], r["automated"])
    qrows = []
    for q in rec["quantities"]:
        it = by.get((q["item_id"], q["variant"])) or {}
        val = it.get("value")
        status = it.get("status")
        final = status in ("Automatically Calculated", "Calculated With Assumption")
        qrows.append({**q, "automated_qty": val, "automated_status": status, "automated_final": final,
                      "candidates": it.get("candidates") or {}, "difference": diff(q["manual_qty"], val),
                      "variance_pct": round((val - q["manual_qty"]) / q["manual_qty"] * 100, 2) if val is not None and q["manual_qty"] else None})
    ch = compare_runs(pid) if store.latest_run_id(pid) else {"available": False}
    rev = {"state": REVISION_STATE, **rec["revision"],
           "latest_comparison": {k: ch.get(k) for k in ("old", "new", "summary")} if ch.get("available") else None}
    return {"record": rec, "automated": auto, "comparison": rows, "quantities": qrows, "revision": rev,
            "note": "No accuracy percentage or time-saving figure is produced. Differences appear only where both values exist; "
                    "quantity variances against non-final (Needs Review) values are not accuracy measures."}
