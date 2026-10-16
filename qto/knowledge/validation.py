"""Estimator validation sessions - traceability for methodology-rule validation.

A session records who validated, when, and (derived from the session-tagged audit trail) which rules were
reviewed, confirmed, rejected or kept unconfirmed, and the resulting recalculations, BOQ-line changes and
benchmark changes. Sessions never decide anything themselves.
Stored in data/knowledge/validation_sessions.json.
"""
from __future__ import annotations

import os
import uuid

from .. import store
from .rules_engine import load_rules


def _path():
    return os.path.join(store.DATA, "knowledge", "validation_sessions.json")


def sessions():
    return store.read_json(_path(), []) or []


def _save(ss):
    store.write_json(_path(), ss)


def active():
    return next((s for s in sessions() if not s.get("finished")), None)


def start(estimator=None, scope="All reference projects", note=""):
    if active():
        raise ValueError("A validation session is already open - finish it first")
    rules = load_rules()
    s = {"id": uuid.uuid4().hex[:8], "estimator": estimator or store.user(), "scope": scope, "note": note,
         "started": store.now(), "finished": None,
         "start_state": {rid: {"status": r["status"], "selected": r.get("selected")} for rid, r in rules.items()}}
    ss = sessions()
    ss.append(s)
    _save(ss)
    store.audit("platform", "validation_session_started", session_id=s["id"], estimator=s["estimator"], scope=scope, note=note)
    return s


def summarize(s):
    ev = [a for a in store.audit_log("platform", 1_000_000) if a.get("session_id") == s["id"]]
    decisions = sorted([a for a in ev if a["event"] == "rule_decision"], key=lambda a: a["at"])
    last = {}
    for a in decisions:
        last[a["rule_id"]] = a
    rules = load_rules()
    impacts = [a for a in ev if a["event"] == "rule_decision_impact"]
    lines = [l for a in impacts for l in a.get("lines", [])]
    changed = [l for l in lines if l["old_value"] != l["new_value"] or l["old_status"] != l["new_status"]]
    bench = {}
    for a in impacts:
        for pid, b in (a.get("benchmarks") or {}).items():
            bench.setdefault(pid, {"before": b["before"]})["after"] = b["after"]
    lines_dec = [a for p in store.projects() for a in store.audit_log(p["id"], 1_000_000)
                 if a.get("event") == "line_decision" and a.get("session_id") == s["id"]]
    by_action = {}
    for a in lines_dec:
        by_action[a["action"]] = by_action.get(a["action"], 0) + 1
    return {
        "line_decisions": len(lines_dec), "line_decisions_by_action": by_action,
        "line_decision_projects": sorted({a["project"] for a in lines_dec}),
        "rules_total": len(rules),
        "reviewed": sorted(last),
        "confirmed": sorted(r for r, a in last.items() if a["action"] == "approve"),
        "rejected": sorted(r for r, a in last.items() if a["action"] == "reject"),
        "kept_unconfirmed": sorted(r for r, a in last.items() if a["action"] == "note"),
        "unresolved": sorted(rid for rid, r in rules.items() if r["status"] != "CONFIRMED"),
        "notes": [{"rule_id": a["rule_id"], "at": a["at"], "text": a.get("note", "")} for a in decisions if a.get("note")],
        "recalculations": sorted({p for a in impacts for p in a.get("projects", [])}),
        "boq_lines_affected": len(lines), "boq_lines_changed": len(changed), "changes": changed[:200],
        "benchmark_changes": bench,
    }


def finish(session_id, note="", cancelled=False):
    """Close a session. cancelled=True records it as cancelled (e.g. started by mistake); any decisions already made
    in it stay recorded in the audit trail - nothing is undone or deleted."""
    ss = sessions()
    s = next((x for x in ss if x["id"] == session_id), None)
    if not s:
        raise KeyError(session_id)
    if s.get("finished"):
        raise ValueError("Session already finished")
    s["finished"] = store.now()
    s["finish_note"] = note
    s["outcome"] = "cancelled" if cancelled else "completed"
    s["summary"] = summarize(s)
    _save(ss)
    store.audit("platform", "validation_session_cancelled" if cancelled else "validation_session_finished", session_id=s["id"],
                estimator=s["estimator"], reviewed=len(s["summary"]["reviewed"]), confirmed=len(s["summary"]["confirmed"]),
                line_decisions=s["summary"]["line_decisions"], note=note)
    return s


def with_summary(s):
    return s if s.get("finished") else {**s, "summary": summarize(s)}
