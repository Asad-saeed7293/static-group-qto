"""Persistence: projects, runs, overrides, review decisions, BOQ imports and the audit log.

Everything is plain JSON on disk under data/ so results are inspectable and
version-controllable. One folder per project:

data/projects/<pid>/
    runs/<run_id>/{run.json, drawings.json, facts.json, results.json}
    latest_run.txt
    cache/geom/<drawing_id>.json
    boq/<import_id>.json  + uploaded source files
    overrides.json, review_decisions.json, audit_log.jsonl
"""
from __future__ import annotations

import datetime as dt
import getpass
import json
import os
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
DATA = os.path.join(ROOT, "data")
_lock = threading.Lock()


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def user():
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, default=str)
    os.replace(tmp, path)


# --- config ----------------------------------------------------------------------
def projects(include_archived=False):
    """Active projects. Archived projects (e.g. test data) are kept on disk but excluded from KPIs, reports and the assistant."""
    ps = read_json(os.path.join(CONFIG, "projects.json"), {"projects": []})["projects"]
    return ps if include_archived else [p for p in ps if not p.get("archived")]


def set_archived(pid, archived, reason=""):
    cfg = read_json(os.path.join(CONFIG, "projects.json"), {"projects": []})
    p = next((p for p in cfg["projects"] if p["id"] == pid), None)
    if not p:
        raise KeyError(pid)
    if archived:
        p.update(archived=True, archived_reason=reason, archived_at=now(), archived_by=user())
    else:
        for k in ("archived", "archived_reason", "archived_at", "archived_by"):
            p.pop(k, None)
    write_json(os.path.join(CONFIG, "projects.json"), cfg)
    audit(pid, "project_archived" if archived else "project_restored", reason=reason)
    return p


def project(pid):
    p = next((p for p in projects(include_archived=True) if p["id"] == pid), None)
    if not p:
        raise KeyError(pid)
    return p


def add_project(rec):
    cfg = read_json(os.path.join(CONFIG, "projects.json"), {"projects": []})
    if any(p["id"] == rec["id"] for p in cfg["projects"]):
        raise ValueError("Project id already exists")
    cfg["projects"].append(rec)
    write_json(os.path.join(CONFIG, "projects.json"), cfg)


def load_rules_file(name):
    """Load a rules file; a file may 'extends' another and override top-level keys."""
    r = read_json(os.path.join(CONFIG, name))
    if r and r.get("extends"):
        base = load_rules_file(r["extends"])
        for k, v in r.items():
            if k in ("extends", "_comment"):
                continue
            if k == "merge_lists" or k.startswith("add_"):
                continue
            base[k] = v
        # add_<key>: append list items to the base list (e.g. extra layer/text roles)
        for k, v in r.items():
            if k.startswith("add_") and isinstance(v, list):
                base.setdefault(k[4:], [])
                base[k[4:]] = v + base[k[4:]]
        r = base
    return r


def rules(pid):
    return load_rules_file(project(pid).get("rules_file", "rules_ramzi_villa.json"))


def base_settings():
    return read_json(os.path.join(CONFIG, "settings.json"))


def pdir(pid, *parts):
    return os.path.join(DATA, "projects", pid, *parts)


def overrides(pid):
    return read_json(pdir(pid, "overrides.json"), {})


def settings(pid):
    s = base_settings()
    ov = overrides(pid)
    if ov.get("tolerances"):
        s["tolerances"] = ov["tolerances"]
    if ov.get("measurement"):
        s["measurement"].update(ov["measurement"])
    return s


def save_overrides(pid, ov):
    write_json(pdir(pid, "overrides.json"), ov)


def project_inputs(pid):
    """Estimator-entered project data that the drawings do not provide (tank sizes, boundary wall section, NGL)."""
    return read_json(pdir(pid, "inputs.json"), {}) or {}


def save_project_inputs(pid, inputs):
    write_json(pdir(pid, "inputs.json"), inputs)


def decisions(pid):
    return read_json(pdir(pid, "review_decisions.json"), {})


def save_decisions(pid, d):
    write_json(pdir(pid, "review_decisions.json"), d)


# --- audit -----------------------------------------------------------------------
def audit(pid, event, **data):
    rec = {"at": now(), "user": user(), "project": pid, "event": event, **data}
    os.makedirs(pdir(pid), exist_ok=True)
    with _lock, open(pdir(pid, "audit_log.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    return rec


def audit_log(pid, limit=500):
    try:
        with open(pdir(pid, "audit_log.jsonl"), encoding="utf-8") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return []
    return [json.loads(l) for l in lines[-limit:]][::-1]


# --- runs ------------------------------------------------------------------------
def latest_run_id(pid):
    try:
        with open(pdir(pid, "latest_run.txt")) as fh:
            return fh.read().strip() or None
    except FileNotFoundError:
        return None


def set_latest(pid, run_id):
    os.makedirs(pdir(pid), exist_ok=True)
    with open(pdir(pid, "latest_run.txt"), "w") as fh:
        fh.write(run_id)


def run_path(pid, run_id, name):
    return pdir(pid, "runs", run_id, name)


def list_runs(pid):
    d = pdir(pid, "runs")
    if not os.path.isdir(d):
        return []
    out = []
    for r in sorted(os.listdir(d), reverse=True):
        meta = read_json(os.path.join(d, r, "run.json"))
        if meta:
            out.append({k: meta.get(k) for k in ("run_id", "started", "finished", "status", "counts", "kind")})
    return out


# --- BOQ imports ---------------------------------------------------------------------
def boq_imports(pid):
    d = pdir(pid, "boq")
    if not os.path.isdir(d):
        return []
    out = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".json"):
            b = read_json(os.path.join(d, f))
            out.append({k: b.get(k) for k in ("import_id", "name", "imported", "is_test", "row_count", "source_file", "active")})
    return out


def active_boq(pid):
    d = pdir(pid, "boq")
    if not os.path.isdir(d):
        return None
    act = read_json(pdir(pid, "active_boq.json"), {}).get("import_id")
    if act and os.path.exists(os.path.join(d, f"{act}.json")):
        return read_json(os.path.join(d, f"{act}.json"))
    return None
