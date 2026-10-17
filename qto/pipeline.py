"""End-to-end processing pipeline with real, observable progress.

Stages (each reported to the UI as it actually happens):
 1 Select project      2 Load drawings        3 Scan DXF files
 4 Detect layers & elements                   5 Extract dimensions
 6 Calculate quantities 7 Generate BOQ         8 Run validation   9 Results
"""
from __future__ import annotations

import os
import time
import traceback
import uuid
from collections import Counter

from . import store
from .boq.generate import generate_boq
from .build import build_all
from .calc.validation import validate_calculations
from .scan import list_files, scan_drawing
from .knowledge.model import load_model
from .knowledge.rules_engine import load_rules as load_method_rules, settings_for
from .takeoff.items import compute_items
import copy

STAGES = ["Select project", "Load drawings", "Scan DXF files", "Detect layers and elements", "Extract dimensions",
          "Calculate quantities", "Generate BOQ", "Run validation", "Results"]


class Progress:
    def __init__(self):
        self.state = {"running": False, "stages": [{"name": s, "status": "pending", "detail": ""} for s in STAGES],
                      "current_file": None, "file_index": 0, "file_total": 0, "log": [], "run_id": None, "error": None}

    def stage(self, i, status, detail=""):
        st = self.state["stages"][i]
        st["status"], st["detail"] = status, detail
        if status == "running":
            st["started"] = time.time()
        if status in ("done", "error"):
            st["seconds"] = round(time.time() - st.get("started", time.time()), 1)
        self.log(f"[{STAGES[i]}] {status}{': ' + detail if detail else ''}")

    def log(self, msg):
        self.state["log"].append({"t": store.now(), "msg": msg})
        self.state["log"] = self.state["log"][-400:]


def assumptions_list(design: dict, settings: dict, rules: dict) -> list:
    a = ["Drawing units: $INSUNITS = 6 (metres) in every structural file; confirmed against dimension values (e.g. 0.20 = 200 mm column)."]
    for fid, s in design.get("storey_heights", {}).items():
        a.append(f"Storey height {fid}: {s.get('explanation')}" + ("" if s.get("confirmed") else " - NOT YET CONFIRMED by user"))
    for fid, lv in design.get("levels", {}).items():
        if lv.get("tie"):
            a.append(f"Level {fid}: several {lv.get('kind')} values are equally frequent ({lv.get('tied_values')}); the lowest was used.")
    a.append(f"Column height basis: {settings['measurement']['column_height_basis']} (configurable in Settings).")
    a.append(f"Beam depth basis: {settings['measurement']['beam_depth_basis']}; families whose schedule depth excludes the slab: "
             + ", ".join(f["name"] for f in rules["beam_families"] if not f.get("depth_includes_slab", True)) + ".")
    a.append("Slabs measured over beams (gross zone area less shafts/openings); beams measured below the slab to avoid double counting.")
    a.append("Footing and column volumes use the drawn geometry; schedule sizes are used as an independent cross-check.")
    b = design.get("blinding")
    if b:
        a.append(f"Blinding thickness {b['value']*1000:.0f} mm from drawing note ({b['occurrences']} occurrences on {b['source']['drawing']}).")
    a.append("Tie-beam depth = largest vertical dimension on the 'TYPICAL SECTION THROUGH T.B.n' detail; width from the plan.")
    a.append("Pedestal size note '500X500X500 MM' interpreted as length x width x height.")
    a.append("RC wall height = storey height of the floor; door/window openings in walls are not deducted.")
    a.append("Slab IDs, raft IDs and residual-zone IDs are system-generated - the drawings do not number them.")
    return a


def run_full(pid: str, progress: Progress, scope: str = "all") -> str:
    P = progress
    st = P.state
    st["running"] = True
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    st["run_id"] = run_id
    started = store.now()
    errors, warnings = [], []
    try:
        P.stage(0, "running")
        proj = store.project(pid)
        rules, settings, ov = store.rules(pid), store.settings(pid), store.overrides(pid)
        root = proj["source_folder"]
        if not os.path.isdir(root):
            raise FileNotFoundError(f"Source folder not found: {root}")
        P.stage(0, "done", proj["name"])

        P.stage(1, "running")
        dxf, other = list_files(root)
        if scope == "structural":
            dxf = [p for p in dxf if "structural" in p.lower()]
        P.stage(1, "done", f"{len(dxf)} DXF files, {len(other)} other files")

        if not dxf:
            message = "No DXF or DWG drawings were found; other documents are stored as references and are not measured."
            st["error"] = message
            P.stage(1, "error", message)
            store.write_json(store.run_path(pid, run_id, "drawings.json"), [])
            store.write_json(store.run_path(pid, run_id, "run.json"), _incomplete_run_meta(
                pid, run_id, "no drawings", started, proj, root, other, [], warnings, message))
            store.audit(pid, "processing_incomplete", run_id=run_id, status="no drawings", message=message)
            return run_id

        P.stage(2, "running")
        st["file_total"] = len(dxf)
        drawings = []
        cache = store.pdir(pid, "cache", "geom")
        for i, p in enumerate(dxf, start=1):
            st["file_index"], st["current_file"] = i, os.path.relpath(p, root)
            P.state["stages"][2]["detail"] = f"{i}/{len(dxf)} {os.path.basename(p)}"
            try:
                d = scan_drawing(p, root, rules, cache)
            except Exception as exc:  # never stop the run for one file
                d = {"file": os.path.basename(p), "rel_path": os.path.relpath(p, root), "status": "error", "drawing_id": None,
                     "log": [{"level": "error", "message": f"{exc}"}], "role": None}
            drawings.append(d)
            for l in d.get("log", []):
                if l["level"] == "error":
                    errors.append(f"{d['file']}: {l['message']}")
                elif l["level"] == "warning":
                    warnings.append(f"{d['file']}: {l['message']}")
            P.log(f"Scanned {d['file']} ({d['status']}, {d.get('seconds', '?')} s)")
        P.stage(2, "done", f"{sum(1 for d in drawings if d['status'] != 'error')}/{len(dxf)} opened")

        if drawings and all(d.get("status") == "error" for d in drawings):
            message = "Every DXF/DWG drawing failed to open; no results were generated and the previous successful run remains active."
            st["error"] = message
            P.stage(2, "error", message)
            store.write_json(store.run_path(pid, run_id, "drawings.json"), drawings)
            store.write_json(store.run_path(pid, run_id, "run.json"), _incomplete_run_meta(
                pid, run_id, "failed", started, proj, root, other, drawings, warnings, message, errors))
            store.audit(pid, "processing_failed", run_id=run_id, status="failed", message=message, errors=errors)
            return run_id

        role_d = [d for d in drawings if d.get("role")]
        if not role_d:
            message = "No drawing matched a supported quantity rule; files were inventoried only and no results were generated."
            st["error"] = message
            P.stage(3, "error", message)
            store.write_json(store.run_path(pid, run_id, "drawings.json"), drawings)
            store.write_json(store.run_path(pid, run_id, "run.json"), _incomplete_run_meta(
                pid, run_id, "unsupported drawings", started, proj, root, other, drawings, warnings, message, errors))
            store.audit(pid, "processing_incomplete", run_id=run_id, status="unsupported drawings", message=message)
            return run_id

        P.stage(3, "running")
        hits = Counter()
        for d in role_d:
            hits.update(d["facts"]["rule_hits"])
        P.stage(3, "done", f"{len(role_d)} drawings matched a quantity rule; " +
                ", ".join(f"{k.split(':')[1]} {v}" for k, v in sorted(hits.items()) if k.startswith(("layer", "text")))[:300])

        facts = {d["drawing_id"]: {"facts": d.pop("facts"), "tables": d.pop("tables")} for d in drawings if d.get("role") and "facts" in d}
        store.write_json(store.run_path(pid, run_id, "facts.json"), facts)
        store.write_json(store.run_path(pid, run_id, "drawings.json"), drawings)
        result = _compute(pid, run_id, drawings, facts, rules, settings, ov, P)
        warnings += result.pop("_warnings")
        P.stage(8, "running")
        meta = _run_meta(pid, run_id, "full", started, proj, drawings, other, result, warnings, errors, root)
        store.write_json(store.run_path(pid, run_id, "run.json"), meta)
        store.set_latest(pid, run_id)
        store.audit(pid, "processing_run", run_id=run_id, kind="full", counts=meta["counts"],
                    files=len(drawings), errors=len(errors), warnings=len(warnings))
        P.stage(8, "done", f"Run {run_id} saved")
    except Exception as exc:
        st["error"] = f"{exc}"
        P.log("ERROR: " + traceback.format_exc())
        for s in st["stages"]:
            if s["status"] == "running":
                s["status"] = "error"
        store.audit(pid, "processing_error", run_id=run_id, error=str(exc))
    finally:
        st["running"] = False
    return run_id


def _incomplete_run_meta(pid, run_id, status, started, project, root, other, drawings, warnings, message, errors=None):
    return {"run_id": run_id, "kind": "full", "project": pid, "project_name": project["name"],
            "source_folder": root, "started": started, "finished": store.now(), "status": status,
            "previous_run": store.latest_run_id(pid),
            "files": [{"file": d.get("file"), "rel_path": d.get("rel_path"), "status": d.get("status"),
                       "drawing_id": d.get("drawing_id")} for d in drawings],
            "other_files": [os.path.relpath(path, root) for path in other],
            "counts": {"drawings": len(drawings), "processed": 0, "inventoried": 0,
                       "failed": sum(d.get("status") == "error" for d in drawings), "elements": 0,
                       "by_type": {}, "elements_skipped": 0, "quantity_records": 0, "quantified": 0,
                       "not_quantified": 0, "boq_lines": 0, "validation_issues": 0,
                       "total_concrete_m3": 0, "total_blinding_m3": 0},
            "warnings": warnings, "errors": errors or [], "incomplete_reason": message}


def _compute(pid, run_id, drawings, facts, rules, settings, ov, P=None):
    def stage(i, s, d=""):
        if P:
            P.stage(i, s, d)
    stage(4, "running")
    dd = []
    for d in drawings:
        if d.get("drawing_id") in facts:
            x = dict(d)
            x.update(facts[d["drawing_id"]])
            dd.append(x)
    logs = []
    mrules = load_method_rules(pid)
    settings = settings_for(mrules, settings)   # approved methodology rules override development defaults
    res = build_all(dd, rules, settings, ov, logs.append)
    stage(4, "done", "; ".join(logs[:3]))
    stage(5, "running")
    validation_issues = validate_calculations(res["elements"], res["quantities"])
    elements = [e.to_dict() for e in res["elements"]]
    quantities = [q.to_dict() for q in res["quantities"]]
    # engine variants for rules that change element measurement (heights, depths): used for candidates/impact
    variants = {}
    for r in mrules.values():
        if not r.get("variants"):
            continue
        variants[r["rule_id"]] = {}
        for opt, var in r["variants"].items():
            if not var.get("measurement"):
                continue
            s2 = copy.deepcopy(settings)
            s2["measurement"].update(var["measurement"])
            vr = build_all(dd, rules, s2, ov, lambda m: None)
            variants[r["rule_id"]][opt] = {"elements": [{k: e.to_dict()[k] for k in ("uid", "element_type", "floor")} for e in vr["elements"]],
                                           "quantities": [{k: q.to_dict()[k] for k in ("element_uid", "quantity_type", "value")} for q in vr["quantities"]]}
    items = compute_items({"elements": elements, "quantities": quantities}, variants, dd, res["design"], mrules,
                          store.project_inputs(pid), load_model())
    rules_by_element = {}
    for item in items:
        for uid in item.get("element_uids", []):
            linked = rules_by_element.setdefault(uid, [])
            for rule in item.get("rules", []):
                if not any(existing.get("rule_id") == rule.get("rule_id") for existing in linked):
                    linked.append(rule)
    for quantity in quantities:
        quantity["methodology_rules"] = rules_by_element.get(quantity["element_uid"], [])
    stage(5, "done", f"{len(quantities)} quantity records, {sum(1 for q in quantities if q['value'] is None)} not calculable; "
                     f"{len(items)} BOQ item calculations ({sum(1 for i in items if i['value'] is not None)} with a value)")
    stage(6, "running")
    boq = generate_boq(elements, quantities)
    stage(6, "done", f"{len(boq)} BOQ lines")
    stage(7, "running")
    flags = Counter(f["code"] for e in elements for f in e["flags"])
    stage(7, "done", f"{sum(flags.values())} element flags; {len(validation_issues)} calculation validation issues")
    out = {"run_id": run_id, "elements": elements, "quantities": quantities, "boq": boq, "design": res["design"],
           "items": items, "validation_issues": validation_issues,
           "rule_snapshot": {k: {"status": v["status"], "selected": v.get("selected"), "version": v.get("version"),
                                  "source": v.get("source", "Shared default")} for k, v in mrules.items()},
           "warnings": res["warnings"], "orphans": res["orphans"], "build_log": logs,
           "assumptions": assumptions_list(res["design"], settings, rules), "settings_used": settings, "overrides_used": ov}
    store.write_json(store.run_path(pid, run_id, "results.json"), out)
    out["_warnings"] = res["warnings"]
    return out


def _run_meta(pid, run_id, kind, started, proj, drawings, other, result, warnings, errors, root):
    els = result["elements"]
    qs = result["quantities"]
    vol = [q for q in qs if q["quantity_type"] in ("concrete_volume", "blinding_volume")]
    prev = store.latest_run_id(pid)
    corrections = [a for a in store.audit_log(pid, 2000) if a["event"] in ("override_changed", "review_decision", "slab_thickness_entered")]
    return {
        "run_id": run_id, "kind": kind, "project": pid, "project_name": proj["name"], "source_folder": root,
        "started": started, "finished": store.now(), "status": "completed" if not errors else "completed with errors",
        "previous_run": prev,
        "files": [{k: d.get(k) for k in ("file", "rel_path", "discipline", "role", "role_title", "status", "seconds", "drawing_id",
                                         "flattened_entities", "unsupported")} | {
                      "entities": (d.get("meta") or {}).get("modelspace_entities"),
                      "units": (d.get("meta") or {}).get("units"),
                      "warnings": sum(1 for l in d.get("log", []) if l["level"] == "warning"),
                      "errors": sum(1 for l in d.get("log", []) if l["level"] == "error")} for d in drawings],
        "other_files": [os.path.relpath(o, root) for o in other],
        "counts": {
            "drawings": len(drawings), "processed": sum(1 for d in drawings if d["status"] == "processed"),
            "inventoried": sum(1 for d in drawings if d["status"] == "inventoried"),
            "failed": sum(1 for d in drawings if d["status"] == "error"),
            "elements": len(els), "by_type": dict(Counter(e["element_type"] for e in els)),
            "elements_skipped": len(result["orphans"]["labels"]) + len(result["orphans"]["outlines"]),
            "quantity_records": len(vol), "quantified": sum(1 for q in vol if q["value"] is not None),
            "not_quantified": sum(1 for q in vol if q["value"] is None),
            "boq_lines": len(result["boq"]),
            "validation_issues": len(result.get("validation_issues", [])),
            "total_concrete_m3": round(sum(q["value"] for q in vol if q["value"] and q["quantity_type"] == "concrete_volume"), 3),
            "total_blinding_m3": round(sum(q["value"] for q in vol if q["value"] and q["quantity_type"] == "blinding_volume"), 3),
        },
        "unsupported_entities": dict(sum((Counter(d.get("unsupported") or {}) for d in drawings), Counter())),
        "warnings": warnings, "errors": errors, "assumptions": result["assumptions"],
        "user_corrections": corrections[:200],
    }


def recalc(pid: str) -> str:
    """Recompute elements/quantities from the latest run's stored facts (after user corrections)."""
    base = store.latest_run_id(pid)
    if not base:
        raise RuntimeError("No processing run yet")
    drawings = store.read_json(store.run_path(pid, base, "drawings.json"))
    facts = store.read_json(store.run_path(pid, base, "facts.json"))
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-r" + uuid.uuid4().hex[:3]
    started = store.now()
    store.write_json(store.run_path(pid, run_id, "facts.json"), facts)
    store.write_json(store.run_path(pid, run_id, "drawings.json"), drawings)
    proj = store.project(pid)
    res = _compute(pid, run_id, drawings, facts, store.rules(pid), store.settings(pid), store.overrides(pid))
    w = res.pop("_warnings")
    old = store.read_json(store.run_path(pid, base, "run.json")) or {}
    meta = _run_meta(pid, run_id, "recalculation", started, proj, drawings, [os.path.join(proj["source_folder"], o) for o in old.get("other_files", [])],
                     res, w, old.get("errors", []), proj["source_folder"])
    meta["based_on_scan"] = old.get("based_on_scan") or base
    store.write_json(store.run_path(pid, run_id, "run.json"), meta)
    store.set_latest(pid, run_id)
    store.audit(pid, "processing_run", run_id=run_id, kind="recalculation", based_on=base, counts=meta["counts"])
    return run_id
