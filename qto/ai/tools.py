"""Data tools for the AI assistant and the management chat.

Every tool reads stored application data (runs, item calculations, benchmarks, reviews,
rules, audit) and returns {"data": ..., "citations": [...]}. Citations name the record the
answer comes from so every statement can be checked in the application. No tool measures CAD.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter

from .. import service, store
from ..knowledge.rules_engine import load_rules

ITEM_DONE = ("Automatically Calculated", "Calculated With Assumption", "Lump Sum", "Not Applicable")


def _cite(kind, project=None, ref=None, url=None):
    return {"type": kind, "project": project, "ref": ref, "url": url}


def _results(pid):
    rid = store.latest_run_id(pid)
    if not rid:
        return None, None
    try:
        return rid, store.read_project_run(pid, rid, "results.json")
    except KeyError:
        return rid, None


def list_projects():
    out, cites = [], []
    for p in store.projects():
        rid = store.latest_run_id(p["id"])
        try:
            run = store.run_metadata(p["id"], rid) if rid else None
        except KeyError:
            run = None
        out.append({"id": p["id"], "name": p["name"], "role": p.get("role", ""), "processed": bool(run and run.get("status") in ("completed", "completed with errors")),
                    "last_run": rid, "finished": run["finished"] if run else None})
        cites.append(_cite("project", p["id"], rid, "#/dashboard"))
    return {"data": out, "citations": cites}


def project_status(pid):
    p = store.project(pid)
    rid, res = _results(pid)
    if not res:
        return {"data": {"project": p["name"], "processed": False}, "citations": [_cite("project", pid)]}
    items = res.get("items") or []
    st = Counter(i["status"] for i in items)
    try:
        run = store.run_metadata(pid, rid)
    except KeyError:
        return {"data": {"project": p["name"], "processed": False, "data_error": "The latest run is missing or belongs to another project."},
                "citations": [_cite("project", pid, rid, "#/processing")]}
    q = service.queue(pid) if service.results(pid) else []
    open_q = [x for x in q if x["decision"]["state"] == "Open"]
    crit = [x for x in open_q if x["status_impact"] == "Review Required"]
    concrete = sum(i["value"] for i in items if i["value"] is not None and i["unit"] == "m3" and i["category"] in ("Concrete",))
    data = {"project": p["name"], "processed": True, "run": rid, "finished": run["finished"],
            "drawings": run["counts"]["drawings"], "drawings_failed": run["counts"]["failed"],
            "boq_items": len(items), "items_by_status": dict(st),
            "items_complete": sum(st[s] for s in ITEM_DONE), "items_with_value": sum(1 for i in items if i["value"] is not None),
            "items_needing_review": st.get("Requires Engineer Review", 0), "items_missing_input": st.get("Requires Input", 0) + st.get("Not Available From Drawing", 0),
            "open_review_items": len(open_q), "critical_review_items": len(crit),
            "concrete_calculated_m3": round(concrete, 1),
            "schedule_conflicts": sum(1 for e in res["elements"] for f in e["flags"] if f["code"] in ("SCHEDULE_MISMATCH", "LABEL_SCHEDULE_CONFLICT"))}
    return {"data": data, "citations": [_cite("run", pid, rid, "#/processing"), _cite("static_boq", pid, rid, "#/sboq"), _cite("review_queue", pid, None, "#/review")]}


def boq_items(pid, status=None):
    rid, res = _results(pid)
    items = (res or {}).get("items") or []
    rows = [{"item_id": i["item_id"], "variant": i["variant"], "description": i["description"], "unit": i["unit"], "value": i["value"],
             "status": i["status"], "open_rules": [r["rule_id"] for r in i["rules"] if r["selected"] is None], "missing": i["missing"]}
            for i in items if not status or i["status"] == status]
    return {"data": rows, "citations": [_cite("static_boq", pid, rid, "#/sboq")]}


def item_detail(pid, item_id):
    rid, res = _results(pid)
    items = [i for i in (res or {}).get("items") or [] if i["item_id"] == item_id]
    b = store.read_json(store.pdir(pid, "benchmark.json")) or {}
    bench = [r for r in b.get("rows", []) if r.get("item_id") == item_id and r["kind"] == "measured"]
    return {"data": {"calculations": items, "benchmark": bench},
            "citations": [_cite("item", pid, item_id, "#/sboq")] + ([_cite("benchmark", pid, f"{r['sheet']} row {r['row']}", "#/benchmark") for r in bench])}


def benchmark_lines(pid, min_abs_pct=None):
    b = store.read_json(store.pdir(pid, "benchmark.json"))
    if not b:
        return {"data": None, "citations": []}
    rows = [r for r in b["rows"] if r["kind"] == "measured" and (min_abs_pct is None or (r["diff_pct"] is not None and abs(r["diff_pct"]) >= min_abs_pct))]
    return {"data": {"summary": b["summary"], "rows": rows, "run": b["run_id"], "boq_ref": b["boq_meta"].get("ref")},
            "citations": [_cite("benchmark", pid, b["run_id"], "#/benchmark")]}


def review_items(pid, impact=None):
    q = service.queue(pid) if service.results(pid) else []
    rows = [{"id": x["id"], "title": x["title"], "impact": x["status_impact"], "element": f"{x.get('element_type', '')} {x.get('mark', '')}".strip(),
             "floor": x.get("floor", ""), "count": x.get("count", 1), "detail": x["detail"][:200]}
            for x in q if x["decision"]["state"] == "Open" and (not impact or x["status_impact"] == impact)]
    return {"data": rows, "citations": [_cite("review_queue", pid, None, "#/review")]}


def unknown_rules():
    rs = load_rules()
    rows = [{"rule_id": r["rule_id"], "title": r["title"], "status": r["status"], "items": r.get("items", []), "evidence": r.get("evidence", "")}
            for r in rs.values() if r["status"] != "CONFIRMED"]
    return {"data": rows, "citations": [_cite("rules", None, None, "#/rules")]}


def concrete_all():
    rows = []
    for p in store.projects():
        s = project_status(p["id"])["data"]
        if s.get("processed"):
            rows.append({"project": p["name"], "concrete_calculated_m3": s["concrete_calculated_m3"],
                         "items_needing_review": s["items_needing_review"]})
    return {"data": rows, "citations": [_cite("static_boq", p["id"], None, "#/sboq") for p in store.projects()]}


def compare_projects(a, b):
    def summary(pid):
        rid, res = _results(pid)
        d = {}
        for i in (res or {}).get("items") or []:
            k = i["item_id"] + (f" {i['variant']}" if i["variant"] else "")
            d[k] = {"value": i["value"], "unit": i["unit"], "status": i["status"]}
        return d
    sa, sb = summary(a), summary(b)
    rows = [{"item": k, "a": sa.get(k, {}).get("value"), "b": sb.get(k, {}).get("value"), "unit": (sa.get(k) or sb.get(k))["unit"],
             "a_status": sa.get(k, {}).get("status"), "b_status": sb.get(k, {}).get("status")} for k in sorted(set(sa) | set(sb))]
    return {"data": {"a": store.project(a)["name"], "b": store.project(b)["name"], "rows": rows},
            "citations": [_cite("static_boq", a, None, "#/sboq"), _cite("static_boq", b, None, "#/sboq")]}


def recent_activity(hours=24):
    since = (dt.datetime.now() - dt.timedelta(hours=hours)).isoformat(timespec="seconds")
    ev = []
    for pid in [p["id"] for p in store.projects()] + ["platform"]:
        for a in store.audit_log(pid, 500):
            if a["at"] >= since and a.get("event") != "chat_question":
                ev.append({k: a.get(k) for k in ("at", "user", "event", "project", "rule_id", "item", "state", "run_id", "kind")})
    ev.sort(key=lambda a: a["at"], reverse=True)
    return {"data": ev, "citations": [_cite("audit", None, f"last {hours} h", "#/reports")]}


def run_changes(pid):
    from ..changes import compare_runs
    c = compare_runs(pid)
    if not c.get("available"):
        return {"data": c, "citations": [_cite("changes", pid, None, "#/project/changes")]}
    data = {"old": c["old"], "new": c["new"], "summary": c["summary"],
            "items": [i for i in c["items"]][:30], "drawings": c["drawings"][:20]}
    return {"data": data, "citations": [_cite("changes", pid, f"{c['old']} → {c['new']}", "#/project/changes")]}


def search(pid, q):
    from .explain import search as _s
    data = service.results(pid)
    return {"data": _s(data, q) if data else [], "citations": [_cite("search", pid, q)]}


TOOLS = {
    "list_projects": (list_projects, "List all projects with processing status.", {}),
    "project_status": (project_status, "Status of one project: BOQ items by status, review items, concrete, conflicts.", {"pid": "project id"}),
    "boq_items": (boq_items, "Static Group BOQ item calculations of a project, optionally filtered by status.", {"pid": "project id", "status": "optional status"}),
    "item_detail": (item_detail, "Calculation, candidates, rules and benchmark lines for one knowledge-model item.", {"pid": "project id", "item_id": "e.g. SUP-BEAM"}),
    "benchmark_lines": (benchmark_lines, "Historical-benchmark lines of a project, optionally only those above a variance %.", {"pid": "project id", "min_abs_pct": "optional number"}),
    "review_items": (review_items, "Open review-queue items of a project.", {"pid": "project id", "impact": "optional: Review Required / Missing Data / Check"}),
    "unknown_rules": (unknown_rules, "Methodology rules that are not yet CONFIRMED.", {}),
    "concrete_all": (concrete_all, "Calculated concrete per project.", {}),
    "compare_projects": (compare_projects, "Compare BOQ item quantities of two projects.", {"a": "project id", "b": "project id"}),
    "recent_activity": (recent_activity, "Audit-log activity in the last N hours.", {"hours": "number, default 24"}),
    "run_changes": (run_changes, "Changes between the latest two processing runs of a project: drawings, elements, BOQ lines.", {"pid": "project id"}),
    "search": (search, "Search elements, BOQ lines and drawings of a project.", {"pid": "project id", "q": "text"}),
}
