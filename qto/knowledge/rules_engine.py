"""Methodology rule configuration engine.

Seed definitions: config/knowledge/methodology_rules.json (never edited by the app).
State (approvals, edits, versions, notes): data/knowledge/rule_state.json.
Every change is versioned and written to the audit log of a 'platform' pseudo-project.

Effective use by the calculators:
  CONFIRMED / INFERRED / ASSUMED -> the selected option is used (status shown on every quantity)
  UNKNOWN                        -> no option is used; quantities are given as candidates per option
"""
from __future__ import annotations

import copy
import json
import os

from .. import store

SEED = os.path.join(store.CONFIG, "knowledge", "methodology_rules.json")
STATE = os.path.join(store.DATA, "knowledge", "rule_state.json")
STATUSES = ["CONFIRMED", "INFERRED", "ASSUMED", "UNKNOWN"]


def _seed():
    with open(SEED, encoding="utf-8") as fh:
        return json.load(fh)


def load_rules() -> dict:
    """Seed rules overlaid with the stored state. Returns {rule_id: rule}."""
    seed = _seed()
    state = store.read_json(STATE, {}) or {}
    out = {}
    for r in seed["rules"]:
        rr = copy.deepcopy(r)
        st = state.get(r["rule_id"])
        rr["version"] = 1
        rr["history"] = []
        rr["notes"] = []
        if st:
            for k in ("status", "selected", "options", "description", "custom_value"):
                if k in st:
                    rr[k] = st[k]
            rr["version"] = st.get("version", 1)
            rr["history"] = st.get("history", [])
            rr["notes"] = st.get("notes", [])
            rr["approved_by"] = st.get("approved_by")
            rr["approved_at"] = st.get("approved_at")
        out[r["rule_id"]] = rr
    return out


def effective(rules: dict, rule_id: str):
    """(option or None, status). None means UNKNOWN or rejected - callers must produce candidates."""
    r = rules.get(rule_id)
    if not r:
        return None, "UNKNOWN"
    if r["status"] == "UNKNOWN" or r.get("selected") in (None, ""):
        return None, r["status"] if r.get("selected") else "UNKNOWN"
    return r["selected"], r["status"]


def _save_state(state):
    store.write_json(STATE, state)


def _snapshot(r):
    return {k: r.get(k) for k in ("status", "selected", "options", "description", "custom_value")}


def update_rule(rule_id: str, action: str, user: str = None, option: str = None, note: str = "",
                options: dict | None = None, description: str | None = None, custom_value=None, status: str | None = None) -> dict:
    """action: approve (option -> CONFIRMED) | reject (back to UNKNOWN) | edit (options/description/status) | note."""
    rules = load_rules()
    if rule_id not in rules:
        raise KeyError(rule_id)
    r = rules[rule_id]
    state = store.read_json(STATE, {}) or {}
    st = state.get(rule_id) or {"version": 1, "history": [], "notes": []}
    user = user or store.user()
    before = _snapshot(r)
    if action == "approve":
        if option not in (r["options"] or {}):
            raise ValueError(f"Unknown option '{option}' for {rule_id}")
        st.update(status="CONFIRMED", selected=option, approved_by=user, approved_at=store.now())
        if custom_value is not None:
            st["custom_value"] = custom_value
    elif action == "reject":
        st.update(status="UNKNOWN", selected=None, approved_by=None, approved_at=None)
    elif action == "edit":
        if options:
            st["options"] = options
        if description:
            st["description"] = description
        if status:
            if status not in STATUSES:
                raise ValueError("invalid status")
            if status == "CONFIRMED":
                raise ValueError("Rules can only be CONFIRMED through the explicit approve action")
            st["status"] = status
        if option is not None:
            available_options = st.get("options", r["options"])
            if option and option not in available_options:
                raise ValueError(f"Unknown option '{option}' for {rule_id}")
            st["selected"] = option or None
        if custom_value is not None:
            st["custom_value"] = custom_value
    elif action == "note":
        pass
    else:
        raise ValueError("action must be approve, reject, edit or note")
    if note:
        st.setdefault("notes", []).append({"at": store.now(), "user": user, "text": note})
    if action != "note":
        st["version"] = st.get("version", 1) + 1
        st.setdefault("history", []).append({"version": st["version"], "at": store.now(), "user": user, "action": action,
                                             "before": before, "after": {k: st.get(k, before.get(k)) for k in before}, "note": note})
    state[rule_id] = st
    _save_state(state)
    store.audit("platform", "rule_" + action, rule_id=rule_id, option=option, note=note, version=st.get("version"),
                previous_status=before["status"], new_status=st.get("status", before["status"]),
                previous_option=before["selected"], new_option=st.get("selected", before["selected"]))
    return load_rules()[rule_id]


def settings_for(rules: dict, base_settings: dict) -> dict:
    """Settings used for the element calculation: decided options override the development defaults."""
    s = copy.deepcopy(base_settings)
    for r in rules.values():
        opt, _ = effective(rules, r["rule_id"])
        var = (r.get("variants") or {}).get(opt) if opt else None
        if var and var.get("measurement"):
            s["measurement"].update(var["measurement"])
    return s
