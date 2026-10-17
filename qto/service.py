"""Read-side services shared by the web API and the exporters."""
from __future__ import annotations

from collections import Counter, defaultdict

from . import store
from .boq.compare import compare
from .boq import mappings
from .models import ST_NO_BOQ
from .review.queue import build_queue

_cache = {}


def results(pid):
    rid = store.latest_run_id(pid)
    if not rid:
        return None
    key = (pid, rid)
    if key not in _cache:
        meta = store.run_metadata(pid, rid)
        result = store.read_project_run(pid, rid, "results.json")
        if result is None or meta.get("status") not in ("completed", "completed with errors"):
            return None
        _cache.clear()
        _cache[key] = {"results": result, "run": meta,
                       "drawings": store.read_project_run(pid, rid, "drawings.json") or []}
    return _cache[key]


def invalidate():
    _cache.clear()


def comparison(pid):
    r = results(pid)
    boq = store.active_boq(pid)
    if not r:
        return None
    if not boq:
        rows = [{"boq_row": None, "boq_item_no": "", "boq_description": "", "boq_element": "", "boq_unit": "", "boq_quantity": None,
                 "matched_items": [l["item_no"]], "element_uids": l["element_uids"], "drawing_quantity": l["quantity"],
                 "drawing_unit": "m3", "variance": None, "variance_pct": None, "status": ST_NO_BOQ, "reasons": ["BOQ not provided"],
                 "category": l["category"], "element_type": l["element_type"], "drawing_description": l["description"],
                 "match_method": ""} for l in r["results"]["boq"]]
        return {"boq": None, "rows": rows, "summary": {"by_status": {ST_NO_BOQ: len(rows)}, "by_category": {}, "total_rows": len(rows), "flags": {}}}
    els = {e["uid"]: e for e in r["results"]["elements"]}
    rows = [dict(row) for row in boq["rows"]]
    applied, issues = mappings.applicable(pid, boq, rows, r["results"]["boq"])
    c = compare(rows, r["results"]["boq"], els, store.settings(pid), applied, issues)
    c["boq"] = {k: boq.get(k) for k in ("import_id", "name", "is_test", "imported", "source_file",
                                         "source_fingerprint", "row_count", "mapping")}
    c["run_id"] = r["run"]["run_id"]
    c["historical_comparison_snapshot"] = None
    for row in c["rows"]:
        if row.get("boq_source_row") is not None:
            row["boq_source_file"] = boq.get("source_file")
            row["boq_source_import_id"] = boq.get("import_id")
            row["boq_source_fingerprint"] = boq.get("source_fingerprint")
    return c


def queue(pid):
    r = results(pid)
    if not r:
        return []
    cmp = comparison(pid)
    return build_queue(r["results"]["elements"], cmp if cmp and cmp.get("boq") else None, r["results"]["orphans"], store.decisions(pid))


def dashboard(pid):
    r = results(pid)
    if not r:
        return None
    res, run = r["results"], r["run"]
    els = res["elements"]
    vol = [q for q in res["quantities"] if q["quantity_type"] in ("concrete_volume", "blinding_volume")]
    by_type = defaultdict(lambda: {"count": 0, "quantity": 0.0, "missing": 0})
    for q in vol:
        t = by_type[q["element_type"]]
        t["count"] += 1
        if q["value"] is None:
            t["missing"] += 1
        else:
            t["quantity"] += q["value"]
    for t in by_type.values():
        t["quantity"] = round(t["quantity"], 3)
    cmp = comparison(pid)
    q = queue(pid)
    return {
        "project": store.project(pid), "run": {k: run.get(k) for k in ("run_id", "kind", "started", "finished", "status", "counts")},
        "drawings": {"total": run["counts"]["drawings"], "processed": run["counts"]["processed"],
                     "inventoried": run["counts"]["inventoried"], "failed": run["counts"]["failed"],
                     "by_discipline": dict(Counter(f["discipline"] for f in run["files"]))},
        "elements": {"total": len(els), "by_type": dict(Counter(e["element_type"] for e in els))},
        "quantities": {"by_type": by_type, "total_concrete_m3": run["counts"]["total_concrete_m3"],
                       "total_blinding_m3": run["counts"]["total_blinding_m3"],
                       "quantified": run["counts"]["quantified"], "not_quantified": run["counts"]["not_quantified"]},
        "boq": {"lines": len(res["boq"]), "active": cmp["boq"] if cmp else None,
                "by_status": cmp["summary"]["by_status"] if cmp else {}, "by_category": cmp["summary"]["by_category"] if cmp else {}},
        "review": {"open": sum(1 for i in q if i["decision"]["state"] == "Open"), "total": len(q),
                   "by_impact": dict(Counter(i["status_impact"] for i in q if i["decision"]["state"] == "Open")),
                   "by_code": dict(Counter(i["code"] for i in q if i["decision"]["state"] == "Open"))},
        "element_status": dict(Counter(_el_status(e) for e in els)),
        "storey_heights": res["design"]["storey_heights"],
    }


def _el_status(e):
    from .models import STATUS_ORDER
    order = {s: i for i, s in enumerate(STATUS_ORDER)}
    st = [f["status_impact"] for f in e["flags"]] or ["OK"]
    w = max(st, key=lambda s: order.get(s, 0))
    if w == "OK" and e["cross_checks"] and all(c["passed"] for c in e["cross_checks"]):
        return "Verified"
    return w
