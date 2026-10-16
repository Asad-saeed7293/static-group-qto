"""Daily automation report (management summary) built only from stored application data.

Snapshots of open issues are kept in data/reports/snapshots/<date>.json so new / resolved issues
can be computed day over day. No external delivery (email, Teams) is configured.
"""
from __future__ import annotations

import datetime as dt
import os

from .. import service, store
from ..changes import compare_runs
from ..knowledge.rules_engine import load_rules

REPORTS = os.path.join(store.DATA, "reports")
LARGE_VARIANCE_PCT = 20


def _open_issues(pid):
    if not service.results(pid):
        return {}
    return {x["id"]: {"title": x["title"], "impact": x["status_impact"]} for x in service.queue(pid) if x["decision"]["state"] == "Open"}


def _previous_snapshot(today):
    d = os.path.join(REPORTS, "snapshots")
    if not os.path.isdir(d):
        return None, {}
    older = sorted(f for f in os.listdir(d) if f.endswith(".json") and f[:-5] < today)
    if not older:
        return None, {}
    return older[-1][:-5], store.read_json(os.path.join(d, older[-1])) or {}


def build_daily_report(save=True, date=None):
    from ..ai.tools import project_status
    today = date or dt.date.today().isoformat()
    prev_date, prev = _previous_snapshot(today)
    pending = [r for r in load_rules().values() if r["status"] != "CONFIRMED"]
    projects, snapshot, actions = [], {}, []
    for p in store.projects():
        pid = p["id"]
        s = project_status(pid)["data"]
        if not s.get("processed"):
            projects.append({"id": pid, "name": p["name"], "processed": False})
            actions.append(f"Process drawings for {p['name']}.")
            continue
        issues = _open_issues(pid)
        snapshot[pid] = issues
        before = prev.get(pid)
        b = store.read_json(store.pdir(pid, "benchmark.json"))
        large = []
        if b:
            large = [{"description": r["description"], "engine": r["engine_qty"], "historical": round(r["historical_qty"], 3), "unit": r["unit"], "diff_pct": r["diff_pct"]}
                     for r in b["rows"] if r["kind"] == "measured" and r["diff_pct"] is not None and abs(r["diff_pct"]) >= LARGE_VARIANCE_PCT]
        res = service.results(pid)
        missing = sorted({m for i in res.get("items", []) for m in i["missing"]})
        ch = compare_runs(pid)
        done = s["items_complete"]
        projects.append({"id": pid, "name": p["name"], "processed": True, "run": s["run"], "finished": s["finished"],
                         "boq_items": s["boq_items"], "items_complete": done,
                         "items_final": sum(s["items_by_status"].get(k, 0) for k in ("Automatically Calculated", "Calculated With Assumption")),
                         "items_lump_excluded": sum(s["items_by_status"].get(k, 0) for k in ("Lump Sum", "Not Applicable")),
                         "completion_pct": round(100 * done / s["boq_items"], 1) if s["boq_items"] else None,
                         "items_needing_review": s["items_needing_review"], "items_missing_input": s["items_missing_input"],
                         "open_issues": len(issues), "critical_issues": s["critical_review_items"],
                         "new_issues": [v["title"] for k, v in issues.items() if k not in before] if before is not None else None,
                         "resolved_issues": [v["title"] for k, v in before.items() if k not in issues] if before is not None else None,
                         "large_variances": large, "missing_information": missing[:25],
                         "drawing_changes": ch.get("summary") if ch.get("available") else None,
                         "drawing_change_runs": [ch.get("old"), ch.get("new")]})
        if s["items_missing_input"]:
            actions.append(f"{p['name']}: provide {s['items_missing_input']} missing inputs (Project Inputs page).")
        if s["critical_review_items"]:
            actions.append(f"{p['name']}: resolve {s['critical_review_items']} critical review items.")
        if large:
            actions.append(f"{p['name']}: reconcile {len(large)} benchmark lines differing by {LARGE_VARIANCE_PCT} % or more.")
    if pending:
        n_unknown = sum(r["status"] == "UNKNOWN" for r in pending)
        actions.insert(0, f"Estimator decision needed on {len(pending)} methodology rules ({n_unknown} UNKNOWN) - Rule Approval page.")
    rep = {"date": today, "generated": store.now(), "compared_with": prev_date, "projects": projects,
           "pending_approvals": [{"rule_id": r["rule_id"], "title": r["title"], "status": r["status"]} for r in pending],
           "recommended_actions": actions,
           "not_measured": ["Time saved and cost savings are not reported: no measured baseline of manual take-off effort exists in the application."]}
    rep["text"] = report_text(rep)
    if save:
        os.makedirs(os.path.join(REPORTS, "snapshots"), exist_ok=True)
        store.write_json(os.path.join(REPORTS, "snapshots", today + ".json"), snapshot)
        store.write_json(os.path.join(REPORTS, f"daily_{today}.json"), rep)
        with open(os.path.join(REPORTS, f"daily_{today}.md"), "w", encoding="utf-8") as fh:
            fh.write(rep["text"])
        store.audit("platform", "daily_report", date=today)
    return rep


def report_text(rep):
    L = [f"# Static Group daily project report - {rep['date']}", ""]
    L.append(f"Compared with snapshot: {rep['compared_with'] or 'none (first report - new/resolved issues not available yet)'}")
    for p in rep["projects"]:
        L += ["", f"## {p['name']}"]
        if not p["processed"]:
            L.append("Not processed.")
            continue
        L.append(f"- Last run {p['run']} ({p['finished']})")
        L.append(f"- BOQ lines ({p['boq_items']}): {p['items_final']} calculated/estimated, {p['items_lump_excluded']} lump sum/excluded (no measurement needed); "
                 f"{p['items_needing_review']} need methodology review; {p['items_missing_input']} missing data")
        L.append(f"- Open review items: {p['open_issues']} ({p['critical_issues']} critical)")
        if p["new_issues"] is not None:
            L.append(f"- New issues since last report: {len(p['new_issues'])}; resolved: {len(p['resolved_issues'])}")
        if p["large_variances"]:
            L.append(f"- Benchmark lines {LARGE_VARIANCE_PCT} % or more from the historical BOQ: {len(p['large_variances'])}")
            for v in p["large_variances"][:5]:
                L.append(f"  - {v['description'][:70]}: {v['engine']} vs {v['historical']} {v['unit']} ({v['diff_pct']:+.1f} %)")
        dc = p["drawing_changes"]
        if dc:
            L.append(f"- Changes vs previous run {p['drawing_change_runs'][0]}: {dc['drawings_changed']} drawings, "
                     f"+{dc['elements_added']}/-{dc['elements_removed']}/~{dc['elements_modified']} elements, {dc['boq_items_changed']} BOQ items changed")
        if p["missing_information"]:
            L.append("- Missing information: " + "; ".join(p["missing_information"][:8]))
    L += ["", f"## Pending methodology approvals ({len(rep['pending_approvals'])})"]
    L += [f"- [{r['status']}] {r['title']}" for r in rep["pending_approvals"]]
    L += ["", "## Recommended actions"] + [f"- {a}" for a in rep["recommended_actions"]]
    L += ["", "## Not reported"] + [f"- {n}" for n in rep["not_measured"]]
    return "\n".join(L) + "\n"
