"""Controlled live validation: drawing register, immutable baselines, AI proposals, estimator line decisions,
revision comparison and validation metrics.

Principles
* The engine (AI/automation) PROPOSES a quantity per BOQ line; only an estimator decision (ACCEPT / CORRECT)
  produces an estimator-confirmed quantity. REJECT and KEEP_UNCONFIRMED never produce a quantity.
* Estimator decisions never change methodology rules, never change engine results and never touch baselines.
* A baseline is written once (exclusive create) and never modified.
* Nothing is inferred: drawing numbers parsed from file names are labelled as such; revisions are 'Not recorded'
  until entered from the title block.
Storage (per project): drawing_register.json, uploads.json, baselines/<id>.json, line_decisions.json.
"""
from __future__ import annotations

import os
import re
import statistics
import uuid

from . import store

ACTIONS = ("ACCEPT", "CORRECT", "REJECT", "KEEP_UNCONFIRMED")
LINE_STATUS = {"ACCEPT": "Accepted by estimator", "CORRECT": "Corrected by estimator",
               "REJECT": "Rejected by estimator", "KEEP_UNCONFIRMED": "Kept unconfirmed"}
RAW2DS = {"Automatically Calculated": "Calculated", "Calculated With Assumption": "Estimated", "Requires Input": "Missing",
          "Not Available From Drawing": "Missing", "Requires Engineer Review": "Needs Review", "Lump Sum": "Lump Sum", "Not Applicable": "Excluded"}
NOT_MEASURED = ("Lump Sum", "Not Applicable")


def key(item_id, variant):
    return f"{item_id}|{variant or ''}"


# ------------------------------------------------------------------ drawing register
CODE_RE = re.compile(r"^([A-Z]{1,4}(?:-[A-Z0-9.]+)+)(?:\s+(.*))?$")              # S-FP, S-FR-S.O.G, DR-050 Site Plan …
SHEET_RE = re.compile(r"\b([A-Z]{1,3})\s*-\s*(\d{1,4}[A-Za-z]?)\s*-\s*(.+)$")        # A - 101-Ground Floor …, … Sheet - A - 101 - …


def parse_name(filename):
    """Drawing number / title from the file name. Returned values are labelled 'parsed from file name' by the caller
    and must be verified against the title block; (None, stem) when no number pattern is recognised."""
    stem = os.path.splitext(os.path.basename(filename))[0].strip()
    m = CODE_RE.match(re.sub(r"-\s+", "-", stem))
    if m:
        return m.group(1), (m.group(2) or "").strip() or None
    m = SHEET_RE.search(stem)
    if m:
        return f"{m.group(1)}-{m.group(2)}", m.group(3).strip(" -") or None
    return None, stem


def _uploads(pid):
    return store.read_json(store.pdir(pid, "uploads.json"), []) or []


def record_uploads(pid, kind, files):
    ups = _uploads(pid)
    for f in files:
        ups.append({"file": os.path.basename(f), "path": f, "kind": kind, "uploaded_at": store.now(), "user": store.user()})
    store.write_json(store.pdir(pid, "uploads.json"), ups)
    store.audit(pid, "files_uploaded", kind=kind, files=[os.path.basename(f) for f in files])


def register(pid, persist=False):
    """Drawing register synced with the latest processing run. Entered fields are never overwritten by a sync.
    Reading does not write (persist=False); the register is saved only when an estimator edits an entry."""
    reg = store.read_json(store.pdir(pid, "drawing_register.json"), {}) or {}
    rid = store.latest_run_id(pid)
    drawings = store.read_json(store.run_path(pid, rid, "drawings.json"), []) if rid else []
    uploaded = {}
    for u in _uploads(pid):
        uploaded.setdefault(u["file"].lower(), u["uploaded_at"])
    seen = set()
    for d in drawings or []:
        did = d["drawing_id"]
        seen.add(did)
        rec = reg.get(did)
        if rec is None:
            num, title = parse_name(d["file"])
            rec = {"project_id": pid, "drawing_id": did, "drawing_number": num, "drawing_number_source": "parsed from file name" if num else "not recorded",
                   "title": title, "title_source": "parsed from file name" if title else "not recorded",
                   "revision": None, "revision_source": "not recorded",
                   "source_file": d.get("rel_path") or d["file"], "discipline": d.get("discipline"),
                   "uploaded_at": uploaded.get(d["file"].lower()), "registered_at": store.now() if persist else None,
                   "registration": "uploaded" if d["file"].lower() in uploaded else "registered from project folder"}
            reg[did] = rec
        rec["status"] = d.get("status")
        rec["last_run"] = rid
    for did, rec in reg.items():
        if did not in seen:
            rec["status"] = "not in latest run"
    if persist:
        store.write_json(store.pdir(pid, "drawing_register.json"), reg)
    return sorted(reg.values(), key=lambda r: (r.get("drawing_number") or "~", r["source_file"]))


def update_drawing(pid, drawing_id, fields):
    register(pid, persist=True)
    reg = store.read_json(store.pdir(pid, "drawing_register.json"), {}) or {}
    rec = reg.get(drawing_id)
    if not rec:
        raise KeyError(drawing_id)
    before = {k: rec.get(k) for k in ("drawing_number", "revision", "title")}
    for k in ("drawing_number", "revision", "title"):
        if k in fields:
            v = (fields[k] or "").strip() or None
            rec[k] = v
            rec[k + "_source"] = "entered by estimator" if v else "not recorded"
    rec["updated_at"], rec["updated_by"] = store.now(), store.user()
    store.write_json(store.pdir(pid, "drawing_register.json"), reg)
    store.audit(pid, "drawing_register_updated", drawing_id=drawing_id, before=before, after={k: rec.get(k) for k in before})
    return rec


# ------------------------------------------------------------------ baselines (immutable)
def _bdir(pid):
    return store.pdir(pid, "baselines")


def baselines(pid):
    d = _bdir(pid)
    if not os.path.isdir(d):
        return []
    out = []
    for f in sorted(os.listdir(d)):
        b = store.read_json(os.path.join(d, f))
        if b:
            out.append({k: b[k] for k in ("baseline_id", "label", "source", "revision", "created", "created_by", "note")} | {"lines": len(b["lines"])})
    return out


def get_baseline(pid, baseline_id):
    b = store.read_json(os.path.join(_bdir(pid), f"{baseline_id}.json"))
    if not b:
        raise KeyError(baseline_id)
    return b


def create_baseline(pid, source, label="", revision=None, note=""):
    """source: historical_boq (Static Group's own BOQ of a reference project), estimator_decisions (accepted /
    corrected quantities) or client_boq (active imported BOQ, mapped to knowledge-model items)."""
    lines = {}

    def add(item_id, variant, desc, unit, qty, ref):
        if qty is None:
            return
        k = key(item_id, variant)
        ln = lines.setdefault(k, {"item_id": item_id, "variant": variant or "", "description": desc, "unit": unit, "quantity": 0.0, "refs": []})
        ln["quantity"] = round(ln["quantity"] + float(qty), 4)
        ln["refs"].append(ref)
    if source == "historical_boq":
        p = store.project(pid)
        b = store.read_json(store.pdir(pid, "benchmark.json"))
        if not p.get("historical_boq") or not b:
            raise ValueError("No historical Static Group BOQ is available for this project")
        for r in b["rows"]:
            if r["kind"] == "measured" and r.get("item_id"):
                add(r["item_id"], r.get("variant"), r["description"], r["unit"], r["historical_qty"], f"{b['boq_meta'].get('ref')} {r['sheet']} row {r['row']}")
        src_ref = f"Static Group BOQ {b['boq_meta'].get('ref')} ({os.path.basename(p['historical_boq'])})"
    elif source == "estimator_decisions":
        for k, d in latest_decisions(pid).items():
            if d["action"] in ("ACCEPT", "CORRECT"):
                add(d["item_id"], d["variant"], d["description"], d["unit"], d["final_quantity"], f"decision {d['decision_id']} ({d['action']}) by {d['user']}")
        src_ref = "Estimator-approved quantities (ACCEPT / CORRECT decisions)"
    elif source == "client_boq":
        from .knowledge.model import load_model, match_row
        act = store.active_boq(pid)
        if not act:
            raise ValueError("No client BOQ is imported / active for this project")
        model = load_model()
        for r in act["rows"]:
            it, _ = match_row({"description": r.get("description", ""), "sheet": r.get("sheet", ""), "section_names": r.get("section_names", [])}, model)
            if it and r.get("quantity") not in (None, ""):
                add(it["id"], "", r.get("description"), r.get("unit"), r["quantity"], f"client BOQ row {r.get('row')}")
        src_ref = f"Client BOQ '{act.get('name')}'" + (" (TEST / synthetic)" if act.get("is_test") else "")
    else:
        raise ValueError("source must be historical_boq, estimator_decisions or client_boq")
    if not lines:
        raise ValueError("The selected source contains no quantities to baseline")
    bid = store.now().replace(":", "").replace("-", "").replace("T", "-") + "-" + uuid.uuid4().hex[:4]
    rec = {"baseline_id": bid, "project_id": pid, "label": label or src_ref, "source": source, "source_ref": src_ref,
           "revision": (revision or "").strip() or None, "created": store.now(), "created_by": store.user(), "note": note,
           "run_id_at_creation": store.latest_run_id(pid), "lines": lines}
    os.makedirs(_bdir(pid), exist_ok=True)
    path = os.path.join(_bdir(pid), f"{bid}.json")
    import json
    with open(path, "x", encoding="utf-8") as fh:        # exclusive create: a baseline is never overwritten
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    store.audit(pid, "baseline_created", baseline_id=bid, source=source, revision=rec["revision"], lines=len(lines), label=rec["label"])
    return rec


# ------------------------------------------------------------------ AI proposals
def _results(pid, run_id=None):
    rid = run_id or store.latest_run_id(pid)
    return rid, (store.read_project_run(pid, rid, "results.json") if rid else None) or {}


def proposals(pid, run_id=None):
    from .knowledge.rules_engine import load_rules
    rid, res = _results(pid, run_id)
    rules = load_rules(pid)
    els = {e["uid"]: e for e in res.get("elements", [])}
    reg = {r["drawing_id"]: r for r in register(pid)} if rid else {}
    dec = latest_decisions(pid)
    out = []
    for it in res.get("items") or []:
        if it["status"] in NOT_MEASURED:
            continue
        dids = sorted({els[u]["drawing_id"] for u in it.get("element_uids", []) if u in els})
        rule_ctx = [{"rule_id": r["rule_id"], "title": r.get("title"), "status": rules.get(r["rule_id"], {}).get("status", r["status"]),
                     "option": rules.get(r["rule_id"], {}).get("selected")} for r in it["rules"]]
        k = key(it["item_id"], it["variant"])
        d = dec.get(k)
        stale = bool(d) and (d["run_id"] != rid and d.get("ai_quantity") != it["value"])
        out.append({"key": k, "item_id": it["item_id"], "variant": it["variant"], "description": it["description"], "unit": it["unit"],
                    "ai_quantity": it["value"], "candidates": it["candidates"], "ai_status": it["status"], "ai_display_status": RAW2DS.get(it["status"], it["status"]),
                    "ai_final": it["status"] in ("Automatically Calculated", "Calculated With Assumption"),
                    "confidence": it.get("confidence"), "rules": rule_ctx, "unknown_rules": [r["rule_id"] for r in rule_ctx if r["status"] == "UNKNOWN"],
                    "missing": it["missing"], "drawings": [{"drawing_id": x, "drawing_number": (reg.get(x) or {}).get("drawing_number"), "revision": (reg.get(x) or {}).get("revision"),
                                                              "file": (els_file(els, it, x))} for x in dids],
                    "evidence": {"formula": it.get("formula"), "evidence": it.get("evidence", []), "element_count": len(it.get("element_uids", []))},
                    "run_id": rid, "decision": d, "decision_stale": stale,
                    "estimator_quantity": d["final_quantity"] if d and not stale else None,
                    "line_status": (LINE_STATUS[d["action"]] + (" — stale, AI quantity changed" if stale else "")) if d else "Awaiting estimator"})
    return out


def els_file(els, it, did):
    for u in it.get("element_uids", []):
        e = els.get(u)
        if e and e["drawing_id"] == did:
            return e.get("drawing")
    return None


# ------------------------------------------------------------------ estimator line decisions
def _decisions(pid):
    return store.read_json(store.pdir(pid, "line_decisions.json"), {}) or {}


def latest_decisions(pid):
    return {k: v[-1] for k, v in _decisions(pid).items() if v}


def _bench(pid):
    return ((store.read_json(store.pdir(pid, "benchmark.json")) or {}).get("summary") or {}).get("by_status")


def decide_line(pid, item_id, variant, action, estimator_quantity=None, comment="", reason="", user=None, session_id=None):
    from .knowledge.validation import active
    action = (action or "").upper()
    if action not in ACTIONS:
        raise ValueError(f"action must be one of {ACTIONS}")
    k = key(item_id, variant)
    prop = next((p for p in proposals(pid) if p["key"] == k), None)
    if not prop:
        raise KeyError(f"No measurable BOQ line {k} in the latest run")
    ai = prop["ai_quantity"]
    est = None
    if action == "ACCEPT" and ai is None:
        raise ValueError("Nothing to accept: the engine has no quantity for this line (candidates only or missing data). "
                         "Use CORRECT with your own quantity, or KEEP_UNCONFIRMED.")
    if action == "CORRECT":
        if estimator_quantity in (None, ""):
            raise ValueError("CORRECT needs the estimator quantity")
        est = float(estimator_quantity)
        if est < 0:
            raise ValueError("Quantity cannot be negative")
        if not (comment or "").strip():
            raise ValueError("CORRECT needs a comment explaining the correction")
    if action == "REJECT" and not (reason or "").strip():
        raise ValueError("REJECT needs a reason")
    if session_id is None:
        s = active()
        session_id = s["id"] if s else None
    allh = _decisions(pid)
    hist = allh.setdefault(k, [])
    prev = hist[-1] if hist else None
    final = ai if action == "ACCEPT" else est if action == "CORRECT" else None
    variance = round(est - ai, 4) if action == "CORRECT" and ai is not None else None
    variance_pct = round((est - ai) / ai * 100, 3) if action == "CORRECT" and ai not in (None, 0) else None
    rec = {"decision_id": uuid.uuid4().hex[:10], "project_id": pid, "item_id": item_id, "variant": variant or "", "key": k,
           "description": prop["description"], "unit": prop["unit"], "action": action, "run_id": prop["run_id"],
           "ai_quantity": ai, "ai_status": prop["ai_status"], "candidates": prop["candidates"], "estimator_quantity": est,
           "final_quantity": final, "variance": variance, "variance_pct": variance_pct,
           "comment": comment or "", "reason": reason or "", "user": user or store.user(), "at": store.now(), "session_id": session_id,
           "version": len(hist) + 1, "rules": prop["rules"], "line_status": LINE_STATUS[action]}
    hist.append(rec)
    store.write_json(store.pdir(pid, "line_decisions.json"), allh)
    b = _bench(pid)     # line decisions never recalculate or re-benchmark: before == after by design
    store.audit(pid, "line_decision", decision_id=rec["decision_id"], session_id=session_id, user_name=rec["user"], version=rec["version"],
                project_affected=pid, boq_line=k, action=action, comment=rec["comment"], reason=rec["reason"],
                rules=[{"rule_id": r["rule_id"], "status": r["status"], "option": r["option"]} for r in prop["rules"]],
                rule_status_changed=False,
                previous_quantity=prev["final_quantity"] if prev else None, new_quantity=final,
                previous_line_status=prev["line_status"] if prev else f"Awaiting estimator (AI: {prop['ai_display_status']})",
                new_line_status=rec["line_status"], ai_quantity=ai, estimator_quantity=est, variance=variance, variance_pct=variance_pct,
                run_id=prop["run_id"], benchmark_before=b, benchmark_after=b)
    return rec


# ------------------------------------------------------------------ revision comparison
def revision_comparison(pid, baseline_id, run_id=None):
    base = get_baseline(pid, baseline_id)
    props = {p["key"]: p for p in proposals(pid, run_id)}
    revs = sorted({r.get("revision") or "Not recorded" for r in register(pid) if r.get("status") == "processed"})
    rows = []
    for k in sorted(set(base["lines"]) | set(props)):
        bl, p = base["lines"].get(k), props.get(k)
        bq = bl["quantity"] if bl else None
        aq = p["ai_quantity"] if p else None
        has_new = p is not None and (aq is not None or bool(p["candidates"]))
        if bl and not has_new:
            change = "omitted"
        elif not bl and has_new:
            change = "added"
        elif not bl:
            continue
        elif aq is None:
            change = "not comparable (no final AI quantity)"
        elif abs(aq - bq) > 0.0005:
            change = "changed"
        else:
            change = "unchanged"
        est = p["estimator_quantity"] if p else None
        rows.append({"key": k, "item_id": (bl or p)["item_id"], "variant": (bl or p)["variant"], "description": (p or bl)["description"],
                     "unit": (p or bl)["unit"], "baseline_quantity": bq, "new_ai_quantity": aq,
                     "candidates": p["candidates"] if p else {}, "delta": round(aq - bq, 4) if aq is not None and bq is not None else None,
                     "delta_pct": round((aq - bq) / bq * 100, 2) if aq is not None and bq else None,
                     "estimator_quantity": est, "variance": round(est - aq, 4) if est is not None and aq is not None else None,
                     "status": p["line_status"] if p else "Not in new run", "ai_status": p["ai_display_status"] if p else None,
                     "rules": p["rules"] if p else [], "evidence": p["evidence"] if p else None,
                     "drawing_revisions": sorted({(d.get("drawing_number") or d["drawing_id"]) + " rev " + (d.get("revision") or "not recorded") for d in (p["drawings"] if p else [])}),
                     "baseline_refs": bl["refs"] if bl else [], "change": change})
    cnt = {}
    for r in rows:
        cnt[r["change"]] = cnt.get(r["change"], 0) + 1
    return {"baseline": {k: base[k] for k in ("baseline_id", "label", "source", "source_ref", "revision", "created")},
            "new_run": run_id or store.latest_run_id(pid), "new_drawing_revisions": revs, "summary": cnt, "rows": rows,
            "note": "The baseline is read-only. Lines without a final AI quantity are not compared as quantities."}


# ------------------------------------------------------------------ metrics and dependencies
def metrics(pid):
    from . import pilot
    from .knowledge.rules_engine import load_rules
    props = proposals(pid)
    proposed = [p for p in props if p["ai_quantity"] is not None or p["candidates"]]
    dec = {p["key"]: p["decision"] for p in props if p["decision"] and not p["decision_stale"]}
    count = lambda a: sum(1 for d in dec.values() if d["action"] == a)
    var = [abs(d["variance_pct"]) for d in dec.values() if d["action"] == "CORRECT" and d["variance_pct"] is not None]
    rules = load_rules(pid).values()
    hours = pilot.load(pid)["automated"].get("estimator_review_hours")
    decided = count("ACCEPT") + count("CORRECT") + count("REJECT")
    return {"total_ai_proposed_lines": len(proposed), "measurable_lines": len(props), "accepted": count("ACCEPT"), "corrected": count("CORRECT"),
            "rejected": count("REJECT"), "kept_unconfirmed": count("KEEP_UNCONFIRMED"),
            "unconfirmed": len(props) - decided, "stale_decisions": sum(1 for p in props if p["decision_stale"]),
            "variance_basis": f"absolute % variance of {len(var)} CORRECT decision(s) against the AI quantity",
            "variance_n": len(var), "average_abs_variance_pct": round(sum(var) / len(var), 2) if var else None,
            "median_abs_variance_pct": round(statistics.median(var), 2) if var else None, "max_abs_variance_pct": round(max(var), 2) if var else None,
            "preliminary": True, "rules_validated": sum(1 for r in rules if r["status"] == "CONFIRMED"),
            "rules_unknown": sum(1 for r in rules if r["status"] == "UNKNOWN"), "rules_total": len(list(load_rules(pid))),
            "estimator_review_hours": hours,
            "note": "Preliminary: computed only from estimator decisions recorded so far. Not an accuracy, saving or ROI figure."}


def dependencies(pid):
    from . import pilot
    from .knowledge.rules_engine import load_rules
    p = store.project(pid)
    reg = register(pid) if store.latest_run_id(pid) else []
    used = [r for r in reg if r.get("status") == "processed"]
    inp = store.project_inputs(pid)
    bw = inp.get("boundary_wall") or {}
    pr = pilot.load(pid)
    rules = list(load_rules(pid).values())
    dep = lambda item, ok, detail: {"item": item, "ok": bool(ok), "detail": detail}
    return [
        dep("Real, unseen Static Group project", p.get("role") == "new project" and not p.get("historical_boq"),
            "This is a reference project used for methodology evidence" if p.get("historical_boq") or p.get("role", "").startswith("reference") else "Live project"),
        dep("Drawing set processed", bool(store.latest_run_id(pid)), f"{len(reg)} drawings registered, {len(used)} used for quantities" if reg else "Not processed"),
        dep("Drawing revisions recorded", used and all(r.get("revision") for r in used),
            f"{sum(1 for r in used if not r.get('revision'))} of {len(used)} measured drawings have no revision recorded (enter from the title block)"),
        dep("Baseline quantity set", bool(baselines(pid)), f"{len(baselines(pid))} baseline(s)" if baselines(pid) else "No baseline created (existing BOQ or approved quantities)"),
        dep("Natural ground level", inp.get("natural_ground_level") not in (None, ""), "Required for excavation / backfill"),
        dep("Tank sizes", bool(inp.get("tanks")), f"{len(inp.get('tanks') or [])} tank(s) entered"),
        dep("Boundary-wall section", bool(bw.get("length") and bw.get("height")), "Length, height and typical section"),
        dep("Methodology rules confirmed", all(r["status"] == "CONFIRMED" for r in rules), f"{sum(r['status'] != 'CONFIRMED' for r in rules)} of {len(rules)} not confirmed"),
        dep("Manual take-off recorded for comparison", pr["manual"].get("takeoff_hours") is not None or bool(pr["quantities"]), "Pilot tab"),
    ]
