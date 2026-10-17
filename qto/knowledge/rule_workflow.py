"""Methodology-rule decision workflow.

decide() = save + version the rule (rules_engine.update_rule) -> recalculate every project whose
BOQ items use the rule -> refresh their historical benchmarks -> audit the quantity impact
(before / after value and status of every affected BOQ line, benchmark summary before / after).
Review items are derived from the results, so they update with the recalculation.
Every decision (including notes) is recorded as a 'rule_decision' audit event tagged with the open
estimator validation session, if any. The estimator decides; nothing here chooses an option.
"""
from __future__ import annotations

from .. import service, store
from .rules_engine import load_rules, update_rule

RECALC_ACTIONS = ("approve", "reject", "edit")


def _rule_lines(pid, rule_id, rules=None):
    rid = store.latest_run_id(pid)
    res = store.read_json(store.run_path(pid, rid, "results.json")) if rid else None
    return {(i["item_id"], i["variant"]): i for i in (res or {}).get("items") or []
            if any(r["rule_id"] == rule_id for r in i["rules"])}


def _bench_summary(pid):
    b = store.read_json(store.pdir(pid, "benchmark.json"))
    return (b or {}).get("summary", {}).get("by_status")


def decide(rule_id, action, option=None, note="", options=None, description=None, status=None, custom_value=None,
           recalculate=True, user=None, session_id=None, project_id=None):
    from ..pipeline import recalc
    from .historical import benchmark_project
    from .validation import active
    if session_id is None:
        s = active()
        session_id = s["id"] if s else None
    prev = load_rules(project_id).get(rule_id)
    rule = update_rule(rule_id, action, user=user, option=option, note=note, options=options, description=description,
                       status=status, custom_value=custom_value, project_id=project_id)
    audit_pid = project_id or "platform"
    store.audit(audit_pid, "rule_decision", rule_id=rule_id, action=action, session_id=session_id, user_name=user or store.user(),
                previous_status=prev["status"], new_status=rule["status"], previous_option=prev.get("selected"),
                new_option=rule.get("selected"), note=note, version=rule["version"])
    if project_id and session_id:
        store.audit("platform", "rule_decision", project=project_id, rule_id=rule_id, action=action, session_id=session_id,
                    user_name=user or store.user(), previous_status=prev["status"], new_status=rule["status"],
                    previous_option=prev.get("selected"), new_option=rule.get("selected"), note=note, version=rule["version"])
    recalculated, impact, benchmarks = [], [], {}
    if recalculate and action in RECALC_ACTIONS:
        projects = [store.project(project_id)] if project_id else store.projects()
        for p in projects:
            before = _rule_lines(p["id"], rule_id)
            if not before:          # project not processed, or the rule drives none of its lines
                continue
            b_before = _bench_summary(p["id"]) if p.get("historical_boq") else None
            try:
                run_id = recalc(p["id"])
                if p.get("historical_boq"):
                    benchmark_project(p["id"])
                    benchmarks[p["id"]] = {"before": b_before, "after": _bench_summary(p["id"])}
            except Exception as exc:
                store.audit(p["id"], "recalc_error", error=str(exc), rule_id=rule_id)
                continue
            recalculated.append(p["id"])
            after = _rule_lines(p["id"], rule_id)
            for k in sorted(set(before) | set(after)):
                b, a = before.get(k) or {}, after.get(k) or {}
                impact.append({"project": p["id"], "run_id": run_id, "item_id": k[0], "variant": k[1],
                               "old_value": b.get("value"), "new_value": a.get("value"),
                               "old_status": b.get("status"), "new_status": a.get("status")})
        service.invalidate()
        store.audit(audit_pid, "rule_decision_impact", rule_id=rule_id, action=action, option=option, note=note,
                    new_status=rule["status"], version=rule["version"], projects=recalculated, lines=impact,
                    benchmarks=benchmarks, session_id=session_id)
    return {"rule": rule, "recalculated": recalculated, "impact": impact, "benchmarks": benchmarks, "session_id": session_id}
