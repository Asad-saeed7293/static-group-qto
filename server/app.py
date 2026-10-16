"""FastAPI backend + static web UI.

Run:  python -m uvicorn server.app:app --port 8000   (or run.bat)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi import Body, FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from qto import service, store  # noqa: E402
from qto.ai.explain import explain_element, explain_comparison_row, search  # noqa: E402
from qto.boq import importer  # noqa: E402
from qto.export import excel  # noqa: E402
from qto.pipeline import Progress, recalc, run_full  # noqa: E402

app = FastAPI(title="Static Group QTO & BOQ Verification", version="0.9")
WEB = os.path.join(ROOT, "web")
app.mount("/static", StaticFiles(directory=WEB), name="static")

PROGRESS: dict[str, Progress] = {}
UPLOADS = os.path.join(tempfile.gettempdir(), "static_qto_uploads")


def _need(pid):
    try:
        store.project(pid)
    except KeyError:
        raise HTTPException(404, f"Unknown project {pid}")
    r = service.results(pid)
    return r


def _results(pid):
    r = _need(pid)
    if not r:
        raise HTTPException(409, "Project has not been processed yet - run processing first")
    return r


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB, "index.html"))


# --- projects --------------------------------------------------------------------
@app.get("/api/projects")
def projects():
    out = []
    for p in store.projects():
        rid = store.latest_run_id(p["id"])
        run = store.read_json(store.run_path(p["id"], rid, "run.json")) if rid else None
        out.append({**p, "latest_run": rid, "counts": run["counts"] if run else None,
                    "folder_exists": os.path.isdir(p["source_folder"])})
    return out


@app.post("/api/projects")
def add_project(body: dict = Body(...)):
    name, folder = body.get("name", "").strip(), body.get("source_folder", "").strip()
    pid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or uuid.uuid4().hex[:8]
    if not name:
        raise HTTPException(400, "name is required")
    if body.get("mode") == "upload" or not folder:
        folder = store.pdir(pid, "files", "drawings")   # drawings will be uploaded into the project
        os.makedirs(folder, exist_ok=True)
    elif not os.path.isdir(folder):
        raise HTTPException(400, f"Folder not found: {folder}")
    rec = {"id": pid, "name": name, "client": body.get("client", ""), "location": body.get("location", ""),
           "source_folder": folder, "rules_file": body.get("rules_file") or "rules_villa_std.json", "historical_boq": None,
           "role": "new project", "created": store.now()[:10]}
    try:
        store.add_project(rec)
    except ValueError as e:
        raise HTTPException(400, str(e))
    store.audit(pid, "project_created", name=name, folder=folder)
    return rec


UPLOAD_KINDS = {"drawings": (".dxf", ".dwg", ".pdf", ".zip"), "schedules": (".dxf", ".pdf", ".xlsx", ".csv", ".zip"),
                "specifications": (".pdf", ".docx", ".zip"), "client_boq": (".xlsx", ".csv")}


def _safe_rel_path(raw: str) -> str | None:
    """Normalises a browser-supplied relative path (folder upload sends 'Sub/Folder/file.dxf' as the
    filename) into a safe, OS-correct relative path under the destination folder. Returns None for
    anything that tries to escape the destination - a '..' component, or a part containing ':' (a
    Windows drive letter such as 'C:', which os.path.join silently lets override the destination
    entirely and must never reach it as a path component). Nothing with any of these is silently written
    outside the project folder - the caller's final abspath check below is the second, independent layer
    of the same defense."""
    rel = (raw or "").replace("\\", "/").lstrip("/")
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." or ":" in p for p in parts):
        return None
    return os.path.join(*parts)


def _within(base: str, target: str) -> bool:
    base_abs = os.path.abspath(base)
    return os.path.abspath(target).startswith(base_abs + os.sep)


@app.post("/api/projects/{pid}/upload/{kind}")
async def upload_files(pid: str, kind: str, files: list[UploadFile] = File(...)):
    """Upload project documents - individual files, or every file from a chosen folder (and its
    subfolders) at once. A folder upload's relative path (e.g. 'Structural/Plans/S-FP.dxf') is preserved
    on disk, not flattened to a basename, so files with the same name in different subfolders never
    silently overwrite each other and nothing picked in the folder dialog is dropped. Zip files are still
    extracted, keeping their own internal folder structure the same way."""
    import zipfile
    store.project(pid)
    if kind not in UPLOAD_KINDS:
        raise HTTPException(400, f"kind must be one of {list(UPLOAD_KINDS)}")
    dest = store.project(pid)["source_folder"] if kind == "drawings" else store.pdir(pid, "files", kind)
    os.makedirs(dest, exist_ok=True)
    saved, skipped = [], []
    for f in files:
        raw_name = f.filename or ""
        rel = _safe_rel_path(raw_name)
        if rel is None:
            skipped.append({"file": raw_name, "reason": "unsafe path"})
            continue
        ext = os.path.splitext(rel)[1].lower()
        if ext not in UPLOAD_KINDS[kind]:
            skipped.append({"file": rel, "reason": f"type {ext} not accepted for {kind}"})
            continue
        target = os.path.join(dest, rel)
        if not _within(dest, target):
            skipped.append({"file": rel, "reason": "unsafe path"})
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as fh:
            shutil.copyfileobj(f.file, fh)
        if ext == ".zip":
            with zipfile.ZipFile(target) as z:
                for m in z.namelist():
                    if m.endswith("/"):
                        continue
                    mrel = _safe_rel_path(m)
                    if mrel is None or not _within(dest, os.path.join(dest, mrel)):
                        skipped.append({"file": f"{rel}:{m}", "reason": "unsafe path in zip"})
                        continue
                    z.extract(m, dest)
                    saved.append(mrel)
            os.remove(target)
        else:
            saved.append(rel)
    if saved:
        from qto import live
        live.record_uploads(pid, kind, [os.path.join(dest, s) for s in saved])
    notes = []
    if kind == "drawings" and any(s.lower().endswith(".pdf") for s in saved):
        notes.append("PDF drawings are stored but not measured - they are reference only.")
    if kind in ("specifications", "schedules"):
        notes.append("Stored with the project; PDF/Word content is not parsed yet. DXF schedules are read automatically when placed with the drawings.")
    store.audit(pid, "files_uploaded", kind=kind, files=saved[:200], skipped=skipped[:50])
    return {"saved": saved, "skipped": skipped, "notes": notes}


@app.get("/api/projects/{pid}/files")
def list_project_files(pid: str):
    proj = store.project(pid)
    out = {}
    for kind in UPLOAD_KINDS:
        d = proj["source_folder"] if kind == "drawings" else store.pdir(pid, "files", kind)
        lst = []
        if os.path.isdir(d):
            for dp, dn, fn in os.walk(d):
                for f in fn:
                    lst.append({"file": os.path.relpath(os.path.join(dp, f), d), "size": os.path.getsize(os.path.join(dp, f))})
        out[kind] = lst
    return out


# --- processing ------------------------------------------------------------------
@app.post("/api/projects/{pid}/run")
def start_run(pid: str, body: dict = Body(default={})):
    _need(pid)
    p = PROGRESS.get(pid)
    if p and p.state["running"]:
        raise HTTPException(409, "A run is already in progress")
    p = PROGRESS[pid] = Progress()
    p.state["running"] = True

    def work():
        run_full(pid, p, body.get("scope", "all"))
        service.invalidate()
    threading.Thread(target=work, daemon=True).start()
    return {"started": True}


@app.get("/api/projects/{pid}/progress")
def progress(pid: str):
    p = PROGRESS.get(pid)
    return p.state if p else {"running": False, "stages": [], "log": []}


@app.post("/api/projects/{pid}/recalc")
def do_recalc(pid: str):
    _results(pid)
    rid = recalc(pid)
    service.invalidate()
    return {"run_id": rid}


@app.get("/api/projects/{pid}/runs")
def runs(pid: str):
    return store.list_runs(pid)


@app.get("/api/projects/{pid}/dashboard")
def dashboard(pid: str):
    _results(pid)
    return service.dashboard(pid)


# --- drawings --------------------------------------------------------------------
@app.get("/api/projects/{pid}/drawings")
def drawings(pid: str):
    r = _results(pid)
    els = r["results"]["elements"]
    per = {}
    for e in els:
        per.setdefault(e["drawing_id"], {}).setdefault(e["element_type"], 0)
        per[e["drawing_id"]][e["element_type"]] += 1
    out = []
    for d in r["drawings"]:
        m = d.get("meta") or {}
        inv = d.get("inventory") or {}
        out.append({"drawing_id": d.get("drawing_id"), "file": d["file"], "rel_path": d["rel_path"], "discipline": d["discipline"],
                    "role": d.get("role"), "role_title": d.get("role_title"), "status": d["status"], "units": m.get("units"),
                    "dxf_version": m.get("acad_release"), "entities": m.get("modelspace_entities"),
                    "layers": len(inv.get("layers_used", {})), "blocks": len(inv.get("blocks_inserted", {})),
                    "seconds": d.get("seconds"), "elements": per.get(d.get("drawing_id"), {}),
                    "warnings": sum(1 for l in d.get("log", []) if l["level"] == "warning")})
    return out


@app.get("/api/projects/{pid}/drawings/{did}")
def drawing(pid: str, did: str):
    r = _results(pid)
    d = next((x for x in r["drawings"] if x.get("drawing_id") == did), None)
    if not d:
        raise HTTPException(404, "drawing not found")
    els = [{"uid": e["uid"], "element_type": e["element_type"], "mark": e["mark"], "floor": e["floor"]}
           for e in r["results"]["elements"] if e["drawing_id"] == did]
    return {**d, "elements": els}


@app.get("/api/projects/{pid}/drawings/{did}/geometry")
def geometry(pid: str, did: str):
    path = store.pdir(pid, "cache", "geom", f"{did}.json")
    if not os.path.exists(path):
        r = _results(pid)
        d = next((x for x in r["drawings"] if x.get("drawing_id") == did), None)
        if not d:
            raise HTTPException(404, "drawing not found")
        from qto.ingest.dxf_reader import load_dxf, viewer_geometry
        root = store.project(pid)["source_folder"]
        dwg = load_dxf(os.path.join(root, d["rel_path"]), root)
        store.write_json(path, viewer_geometry(dwg))
    return FileResponse(path, media_type="application/json")


# --- elements ---------------------------------------------------------------------
@app.get("/api/projects/{pid}/elements")
def elements(pid: str, type: str | None = None, floor: str | None = None, drawing_id: str | None = None, full: bool = False):
    r = _results(pid)
    qs = {}
    for q in r["results"]["quantities"]:
        if q["quantity_type"] in ("concrete_volume", "blinding_volume"):
            qs[q["element_uid"]] = q
    out = []
    for e in r["results"]["elements"]:
        if (type and e["element_type"] != type) or (floor and e["floor"] != floor) or (drawing_id and e["drawing_id"] != drawing_id):
            continue
        q = qs.get(e["uid"])
        base = e if full else {k: e[k] for k in ("uid", "element_type", "mark", "floor", "description", "drawing", "drawing_id", "layer", "confidence")}
        out.append({**base, "dims": {k: v["value"] for k, v in e["dims"].items()},
                    "geometry": e["geometry"] if (full or drawing_id) else None,
                    "extra_rings": e["attributes"].get("extra_rings") if (full or drawing_id) else None,
                    "quantity": q["value"] if q else None, "unit": q["unit"] if q else "", "formula": q["formula"] if q else "",
                    "status": service._el_status(e), "flags": [f["code"] for f in e["flags"]],
                    "cross_checks_passed": sum(1 for c in e["cross_checks"] if c["passed"]), "cross_checks": len(e["cross_checks"])})
    return out


@app.get("/api/projects/{pid}/elements/{uid}")
def element(pid: str, uid: str):
    r = _results(pid)
    e = next((x for x in r["results"]["elements"] if x["uid"] == uid), None)
    if not e:
        raise HTTPException(404, "element not found")
    qs = [q for q in r["results"]["quantities"] if q["element_uid"] == uid]
    line = next((l for l in r["results"]["boq"] if uid in l["element_uids"]), None)
    cmp = service.comparison(pid)
    row = next((x for x in cmp["rows"] if uid in x["element_uids"]), None) if cmp else None
    return {"element": e, "quantities": qs, "boq_line": line, "comparison": row, "status": service._el_status(e),
            "explanation": explain_element(e, qs, line, row, store.settings(pid))}


# --- BOQ ---------------------------------------------------------------------------
@app.get("/api/projects/{pid}/boq")
def boq(pid: str):
    return _results(pid)["results"]["boq"]


@app.get("/api/projects/{pid}/comparison")
def comparison(pid: str):
    _results(pid)
    c = service.comparison(pid)
    return c


@app.get("/api/projects/{pid}/comparison/{idx}/explain")
def explain_row(pid: str, idx: int):
    c = service.comparison(pid)
    if not c or idx >= len(c["rows"]):
        raise HTTPException(404)
    return {"explanation": explain_comparison_row(c["rows"][idx], store.settings(pid))}


@app.post("/api/projects/{pid}/boq/preview")
async def boq_preview(pid: str, file: UploadFile = File(...), sheet: str | None = None):
    _need(pid)
    os.makedirs(UPLOADS, exist_ok=True)
    token = uuid.uuid4().hex
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".xlsx", ".xlsm", ".csv", ".txt"):
        raise HTTPException(400, "Only .xlsx and .csv files are supported")
    path = os.path.join(UPLOADS, token + ext)
    with open(path, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    try:
        pv = importer.preview(path, sheet)
    except Exception as exc:
        raise HTTPException(400, f"Could not read file: {exc}")
    looks_test = bool(re.search(r"test|synthetic|sample|demo", file.filename + " ".join(pv["title_rows"]), re.I))
    return {"token": token + ext, "filename": file.filename, "looks_like_test": looks_test, "fields": importer.FIELDS, **pv}


@app.post("/api/projects/{pid}/boq/import")
def boq_import(pid: str, body: dict = Body(...)):
    _need(pid)
    token = os.path.basename(body["token"])
    src = os.path.join(UPLOADS, token)
    if not os.path.exists(src):
        raise HTTPException(400, "Upload expired - please upload again")
    mapping = {k: int(v) for k, v in body.get("mapping", {}).items() if v not in (None, "", -1, "-1")}
    try:
        rows, warnings = importer.import_rows(src, mapping, int(body.get("header_row", 0)), body.get("sheet"))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    iid = time.strftime("%Y%m%d-%H%M%S")
    d = store.pdir(pid, "boq")
    os.makedirs(d, exist_ok=True)
    shutil.copy(src, os.path.join(d, f"{iid}{os.path.splitext(token)[1]}"))
    rec = {"import_id": iid, "name": body.get("name") or body.get("filename") or token, "source_file": body.get("filename"),
           "imported": store.now(), "is_test": bool(body.get("is_test")), "mapping": mapping, "header_row": body.get("header_row"),
           "row_count": len(rows), "rows": rows, "warnings": warnings}
    store.write_json(os.path.join(d, f"{iid}.json"), rec)
    store.write_json(store.pdir(pid, "active_boq.json"), {"import_id": iid})
    rates_recorded = 0
    if "rate" in mapping and not rec["is_test"]:
        from qto.knowledge.rates import record_from_import
        rates_recorded = record_from_import(pid, store.project(pid)["name"], rec["source_file"], rows)
    store.audit(pid, "boq_imported", import_id=iid, name=rec["name"], is_test=rec["is_test"], rows=len(rows), mapping=mapping,
                rates_recorded=rates_recorded)
    service.invalidate()
    return {**{k: v for k, v in rec.items() if k != "rows"}, "rates_recorded": rates_recorded}


@app.get("/api/projects/{pid}/boq/imports")
def boq_imports(pid: str):
    act = (store.read_json(store.pdir(pid, "active_boq.json"), {}) or {}).get("import_id")
    return [{**b, "active": b["import_id"] == act} for b in store.boq_imports(pid)]


@app.post("/api/projects/{pid}/boq/activate")
def boq_activate(pid: str, body: dict = Body(...)):
    store.write_json(store.pdir(pid, "active_boq.json"), {"import_id": body.get("import_id")})
    store.audit(pid, "boq_activated", import_id=body.get("import_id"))
    service.invalidate()
    return {"ok": True}


# --- review -------------------------------------------------------------------------
@app.get("/api/projects/{pid}/review")
def review(pid: str):
    _results(pid)
    return service.queue(pid)


@app.post("/api/projects/{pid}/review/{item_id:path}")
def review_decide(pid: str, item_id: str, body: dict = Body(...)):
    d = store.decisions(pid)
    state = body.get("state", "Open")
    if state not in ("Open", "Accepted", "Resolved", "Rejected"):
        raise HTTPException(400, "invalid state")
    d[item_id] = {"state": state, "comment": body.get("comment", ""), "user": store.user(), "at": store.now()}
    store.save_decisions(pid, d)
    store.audit(pid, "review_decision", item=item_id, state=state, comment=body.get("comment", ""))
    return d[item_id]


# --- settings & corrections ------------------------------------------------------------
@app.get("/api/projects/{pid}/settings")
def get_settings(pid: str):
    r = _results(pid)
    return {"settings": store.settings(pid), "overrides": store.overrides(pid), "design": {
        k: r["results"]["design"][k] for k in ("levels", "storey_heights", "slab_thickness_by_floor")},
        "rules_file": store.project(pid).get("rules_file")}


@app.post("/api/projects/{pid}/settings")
def set_settings(pid: str, body: dict = Body(...)):
    ov = store.overrides(pid)
    before = json.loads(json.dumps(ov))
    for key in ("tolerances", "measurement", "storey_heights", "storey_heights_confirmed", "levels", "slab_thickness"):
        if key in body:
            if isinstance(body[key], dict) and isinstance(ov.get(key), dict):
                ov[key].update(body[key])
                ov[key] = {k: v for k, v in ov[key].items() if v not in (None, "")}
            else:
                ov[key] = body[key]
    store.save_overrides(pid, ov)
    changed = {k: {"from": before.get(k), "to": ov.get(k)} for k in ov if before.get(k) != ov.get(k)}
    store.audit(pid, "override_changed", changes=changed, reason=body.get("reason", ""))
    rid = recalc(pid)
    service.invalidate()
    return {"run_id": rid, "changes": changed}


# --- audit / export / inspection / search ----------------------------------------------
@app.get("/api/projects/{pid}/audit")
def audit(pid: str):
    return store.audit_log(pid)


@app.get("/api/projects/{pid}/export/tender-pdf")
def export_tender_pdf_route(pid: str):
    """Client-ready tender BOQ as a single PDF - same sheets/numbering as the Excel export and the in-app
    preview, with Rate/Amount left for Static Group Estimating to fill in. Registered before the generic
    /export/{kind} route below - FastAPI matches path routes in registration order, and {kind} would
    otherwise swallow "tender-pdf" as an unknown export kind and 404 before this handler ever runs."""
    from qto.export.pdf import export_tender_pdf
    _results(pid)
    out = os.path.join(tempfile.gettempdir(), f"Tender_BOQ_{excel.safe(pid)}_{store.latest_run_id(pid)}.pdf")
    export_tender_pdf(pid, out)
    store.audit(pid, "export", kind="tender-pdf", run_id=store.latest_run_id(pid))
    return FileResponse(out, filename=os.path.basename(out), media_type="application/pdf")


@app.get("/api/projects/{pid}/export/{kind}")
def export(pid: str, kind: str, old: str | None = None, new: str | None = None):
    _results(pid)
    if kind not in excel.EXPORTERS:
        raise HTTPException(404)
    name, fn = excel.EXPORTERS[kind]
    out = os.path.join(tempfile.gettempdir(), f"{name}_{excel.safe(pid)}_{store.latest_run_id(pid)}.xlsx")
    if kind == "changes":
        fn(pid, out, old, new)
    else:
        fn(pid, out)
    store.audit(pid, "export", kind=kind, run_id=store.latest_run_id(pid))
    return FileResponse(out, filename=os.path.basename(out),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/projects/{pid}/inspection")
def inspection(pid: str):
    from qto.inspection import inspection_summary
    return inspection_summary(_results(pid))


@app.get("/api/rates/suggestions")
def rate_suggestions():
    """Rate memory: the most recent real rate Static Group has entered for each BOQ item, captured only
    from priced BOQs imported back into the app. Empty until at least one priced BOQ has been imported -
    see qto/knowledge/rates.py."""
    from qto.knowledge.rates import suggestions
    return suggestions()


@app.get("/api/costs/benchmark")
def cost_benchmark():
    """Cost benchmarking dashboard data: one indicative-cost summary per processed project, built only
    from rate memory (qto/knowledge/rates.py). Every project starts at 0% coverage until priced BOQs are
    imported - this is not pre-populated or estimated from anything external."""
    from qto.knowledge.rates import cost_benchmark as _cb
    return _cb()


@app.get("/api/rules")
def rules_list():
    """Methodology rules with status, options, history and quantity impact on every processed project."""
    from qto.knowledge.rules_engine import load_rules
    rules = load_rules()
    impact = {}
    for p in store.projects():
        rid = store.latest_run_id(p["id"])
        res = store.read_json(store.run_path(p["id"], rid, "results.json")) if rid else None
        if not res or not res.get("items"):
            continue
        b = store.read_json(store.pdir(p["id"], "benchmark.json")) or {}
        hist = {}
        for row in b.get("rows", []):
            if row.get("item_id") and row.get("historical_qty") is not None:
                hist.setdefault(row["item_id"], 0)
                hist[row["item_id"]] += row["historical_qty"]
        for it in res["items"]:
            for ref in it["rules"]:
                impact.setdefault(ref["rule_id"], []).append({
                    "project": p["id"], "project_name": p["name"], "item_id": it["item_id"], "variant": it["variant"],
                    "unit": it["unit"], "value": it["value"], "candidates": it["candidates"], "historical": hist.get(it["item_id"]) if not it["variant"] else None})
    # options that give identical quantities on a project: explain why from the project's own data
    slab_missing = {}
    for p in store.projects():
        rid = store.latest_run_id(p["id"])
        res = store.read_json(store.run_path(p["id"], rid, "results.json")) if rid else None
        sl = [i for i in (res or {}).get("items") or [] if i["item_id"] == "SUP-SLAB"]
        slab_missing[p["id"]] = bool(sl) and sl[0]["value"] is None and not sl[0]["candidates"]
    out = []
    for r in rules.values():
        imp = impact.get(r["rule_id"], [])
        ties = []
        for m in imp:
            vals = [v for v in (m["candidates"] or {}).values() if v is not None]
            if len(vals) >= 2 and len(set(vals)) == 1 and not m["variant"]:
                if r["rule_id"] == "beam_depth_method" and slab_missing.get(m["project"]):
                    why = "slab geometry has not yet been detected for this project, so no slab thickness deduction is available"
                elif r["rule_id"] == "substructure_waterproofing_surfaces" and m["item_id"].endswith("-V"):
                    why = "both options include the same vertical side faces; they differ only in horizontal top faces (WP-SUB-H)"
                else:
                    why = "the options produce the same quantity for this line on this project; no specific cause has been identified"
                ties.append({"project": m["project"], "project_name": m["project_name"], "item_id": m["item_id"], "value": vals[0], "reason": why})
        out.append({**r, "impact": imp, "identical_options": ties})
    return out


@app.post("/api/rules/{rule_id}")
def rules_update(rule_id: str, body: dict = Body(...)):
    from qto.knowledge.rule_workflow import decide
    try:
        return decide(rule_id, body.get("action"), option=body.get("option"), note=body.get("note", ""),
                      options=body.get("options"), description=body.get("description"), status=body.get("status"),
                      custom_value=body.get("custom_value"), recalculate=body.get("recalculate", True))
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/projects/{pid}/reconciliations")
def get_recon(pid: str):
    return [r for r in (store.read_json(os.path.join(store.DATA, "knowledge", "reconciliations.json"), []) or []) if r.get("project") == pid]


@app.post("/api/projects/{pid}/reconciliations")
def add_recon(pid: str, body: dict = Body(...)):
    path = os.path.join(store.DATA, "knowledge", "reconciliations.json")
    allr = store.read_json(path, []) or []
    rec = {**body, "project": pid, "user": store.user(), "at": store.now(), "id": uuid.uuid4().hex[:8]}
    allr.append(rec)
    store.write_json(path, allr)
    store.audit(pid, "reconciliation_note", **{k: rec.get(k) for k in ("item_id", "category", "rule_id", "text", "row")})
    return rec


@app.get("/api/projects/{pid}/inputs")
def get_inputs(pid: str):
    return store.project_inputs(pid)


@app.post("/api/projects/{pid}/inputs")
def set_inputs(pid: str, body: dict = Body(...)):
    before = store.project_inputs(pid)
    store.save_project_inputs(pid, body)
    store.audit(pid, "inputs_changed", before=before, after=body)
    rid = recalc(pid) if store.latest_run_id(pid) else None
    service.invalidate()
    return {"run_id": rid}


@app.get("/api/projects/{pid}/items")
def project_items(pid: str):
    r = _results(pid)
    return r["results"].get("items") or []


@app.get("/api/projects/{pid}/static-boq")
def static_boq(pid: str):
    from qto.boq.static_template import generate_static_boq
    r = _results(pid)
    items = r["results"].get("items")
    if items is None:
        return {"available": False, "reason": "This run predates the BOQ item engine - reprocess the project"}
    b = generate_static_boq(items)
    act = store.active_boq(pid)
    if act:
        from qto.boq.static_template import detect_new_items
        b["new_items"] = detect_new_items(act["rows"])
    return {"available": True, **b}


@app.get("/api/projects/{pid}/static-boq/preview")
def static_boq_preview(pid: str):
    from qto.export.excel import preview_static_boq
    r = _results(pid)
    if r["results"].get("items") is None:
        return {"available": False, "reason": "This run predates the BOQ item engine - reprocess the project"}
    return {"available": True, **preview_static_boq(pid)}


@app.get("/api/knowledge")
def knowledge():
    from qto.knowledge.model import load_model
    m = load_model()
    m.pop("by_id", None)
    return m


@app.get("/api/projects/{pid}/benchmark")
def benchmark(pid: str, refresh: bool = False):
    from qto.knowledge.historical import benchmark_project
    if not store.project(pid).get("historical_boq"):
        return {"available": False, "reason": "No historical Static Group BOQ is configured for this project"}
    b = None if refresh else store.read_json(store.pdir(pid, "benchmark.json"))
    if not b or b.get("run_id") != store.latest_run_id(pid):
        b = benchmark_project(pid)
    if not b:
        return {"available": False, "reason": "Project has not been processed yet"}
    return {"available": True, **b}


@app.get("/api/projects/{pid}/search")
def do_search(pid: str, q: str):
    return search(_results(pid), q)


@app.get("/api/projects/{pid}/changes")
def run_changes(pid: str, old: str | None = None, new: str | None = None):
    from qto.changes import compare_runs
    _need(pid)
    return compare_runs(pid, old, new)


@app.get("/api/projects/{pid}/runs")
def runs(pid: str):
    _need(pid)
    return store.list_runs(pid)


# --- management / AI -------------------------------------------------------------
CHAT_LOG = os.path.join(store.DATA, "knowledge", "chat_log.jsonl")


@app.post("/api/chat")
def chat(body: dict = Body(...)):
    from qto.ai.agent import answer
    msg = (body.get("message") or "").strip()
    if not msg:
        raise HTTPException(400, "Empty message")
    out = answer(msg, body.get("project"))
    rec = {"at": store.now(), "user": store.user(), "project": body.get("project"), "message": msg, "mode": out["mode"],
           "tools": out["tool_calls"], "answer": out["answer"]}
    os.makedirs(os.path.dirname(CHAT_LOG), exist_ok=True)
    with open(CHAT_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    store.audit("platform", "chat_question", message=msg[:200], mode=out["mode"], tools=[t["tool"] for t in out["tool_calls"]])
    return out


@app.get("/api/chat/history")
def chat_history(limit: int = 50):
    try:
        with open(CHAT_LOG, encoding="utf-8") as fh:
            lines = fh.readlines()[-limit:]
    except FileNotFoundError:
        return []
    return [json.loads(l) for l in lines]


@app.get("/api/ceo")
def ceo():
    """Multi-project management dashboard - every figure comes from stored runs, reviews, benchmarks and rules."""
    from qto.ai.tools import project_status
    from qto.knowledge.rules_engine import load_rules
    rows = []
    for p in store.projects():
        s = project_status(p["id"])["data"]
        b = store.read_json(store.pdir(p["id"], "benchmark.json")) if p.get("historical_boq") else None
        s.update({"id": p["id"], "name": p["name"], "role": p.get("role", ""),
                  "benchmark": b["summary"]["by_status"] if b else None})
        rows.append(s)
    rules = list(load_rules().values())
    pending = [r for r in rules if r["status"] != "CONFIRMED"]
    attention, merged = [], {}
    if pending:
        attention.append({"severity": "attention", "title": f"{len(pending)} methodology decisions pending",
                          "detail": f"{sum(r['status'] == 'UNKNOWN' for r in pending)} UNKNOWN, "
                                    f"{sum(r['status'] == 'INFERRED' for r in pending)} inferred, {sum(r['status'] == 'ASSUMED' for r in pending)} assumed - estimator approval needed",
                          "project": None, "url": "#/rules"})
    for p, s in zip(store.projects(), rows):
        if not s.get("processed"):
            attention.append({"severity": "info", "title": "Not processed yet", "detail": "Run processing to read the drawings",
                              "project": p["name"], "pid": p["id"], "url": "#/project/overview"})
            continue
        items = service.results(p["id"])["results"].get("items") or []
        # automation readiness: mutually exclusive buckets of BOQ lines (no percentages, no accuracy claim)
        rd = {"final": 0, "lump_excluded": 0, "measured_review": 0, "candidates": 0, "not_automated": 0, "missing": 0, "missing_with_candidates": 0}
        for it in items:
            st_ = it["status"]
            if st_ in ("Lump Sum", "Not Applicable"):
                rd["lump_excluded"] += 1
            elif st_ in ("Automatically Calculated", "Calculated With Assumption"):
                rd["final"] += 1
            elif st_ in ("Requires Input", "Not Available From Drawing"):
                rd["missing"] += 1
                rd["missing_with_candidates"] += bool(it["candidates"] and it["value"] is None)
            elif it["value"] is not None:
                rd["measured_review"] += 1
            elif it["candidates"]:
                rd["candidates"] += 1
            else:
                rd["not_automated"] += 1
        rd["lines_with_candidates"] = sum(1 for it in items if it["candidates"] and it["value"] is None)
        s["readiness"] = rd
        for it in items:   # structural concrete that could not be detected at all
            if it["category"] == "Concrete" and it["item_id"].startswith(("SUB-FTG", "SUB-GB", "SUB-SOG", "SUP-SLAB", "SUP-BEAM", "SUP-COLW")) \
                    and it["value"] is None and not it["candidates"]:
                attention.append({"severity": "critical", "title": f"{it['description'].split(' - ')[0]} not detected",
                                  "detail": "; ".join(it["missing"][:1]) or "No elements extracted from the drawings",
                                  "project": p["name"], "pid": p["id"], "url": "#/project/boq"})
        reasons = {}
        for it in items:
            if it["value"] is None and it["status"] != "Not Applicable":
                for m in it["missing"]:
                    if "element(s) have no quantity" in m or m.startswith(("No automated extraction yet", "Openings in these walls")):
                        continue
                    reasons.setdefault(m.split(":")[0].split(" (")[0].split(" - ")[0][:90], set()).add((it["item_id"], it["variant"]))
        for m, ids in reasons.items():   # the same gap on several projects is one attention item
            merged.setdefault(m, {"title": m, "lines": 0, "projects": []})
            merged[m]["lines"] += len(ids)
            merged[m]["projects"].append(p["name"])
        b = store.read_json(store.pdir(p["id"], "benchmark.json")) if p.get("historical_boq") else None
        for r in (b or {}).get("rows", []):
            if r["kind"] == "measured" and r["diff_pct"] is not None and abs(r["diff_pct"]) >= 20:
                attention.append({"severity": "critical" if abs(r["diff_pct"]) >= 50 else "attention",
                                  "title": f"{r['description'][:60]}: {r['diff_pct']:+.1f} % vs historical BOQ",
                                  "detail": f"Engine {r['engine_qty']:,.2f} vs Static Group {r['historical_qty']:,.2f} {r['unit']} - investigation required",
                                  "project": p["name"], "pid": p["id"], "url": "#/benchmark"})
        if s["critical_review_items"]:
            attention.append({"severity": "attention", "title": f"{s['critical_review_items']} review items need an engineer decision",
                              "detail": "Drawing conflicts, ambiguous marks and large variances", "project": p["name"], "pid": p["id"], "url": "#/project/reviews"})
    for m in sorted(merged.values(), key=lambda x: -x["lines"]):
        short = [n.replace("Mr. ", "").split(" Villa")[0] for n in m["projects"]]
        attention.append({"severity": "attention", "title": m["title"],
                          "detail": f"{m['lines']} BOQ lines · {', '.join(short)}",
                          "project": None, "url": "#/project/boq"})
    order = {"critical": 0, "attention": 1, "info": 2}
    attention.sort(key=lambda a: order[a["severity"]])
    return {"projects": rows, "attention": attention,
            "rules": {"total": len(rules), "by_status": {k: sum(r["status"] == k for r in rules) for k in ("CONFIRMED", "INFERRED", "ASSUMED", "UNKNOWN")},
                      "reviewed": sum(1 for r in rules if r.get("notes") or r.get("history"))},
            "not_measured": ["Time saved / cost savings: no measured manual-effort baseline exists, so none is shown."],
            "ai_mode": "llm" if store.base_settings().get("ai", {}).get("enabled") else "deterministic (offline, data only)"}


@app.post("/api/projects/{pid}/archive")
def archive_project(pid: str, body: dict = Body(...)):
    try:
        return store.set_archived(pid, bool(body.get("archived", True)), body.get("reason", ""))
    except KeyError:
        raise HTTPException(404, f"Unknown project {pid}")


@app.get("/api/projects-archived")
def archived_projects():
    return [p for p in store.projects(include_archived=True) if p.get("archived")]


@app.get("/api/validation/sessions")
def validation_sessions():
    from qto.knowledge import validation
    return [validation.with_summary(s) for s in validation.sessions()][::-1]


@app.post("/api/validation/sessions")
def validation_start(body: dict = Body(...)):
    from qto.knowledge import validation
    try:
        return validation.start(body.get("estimator") or None, body.get("scope") or "All reference projects", body.get("note", ""))
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.post("/api/validation/sessions/{sid}/finish")
def validation_finish(sid: str, body: dict = Body(...)):
    from qto.knowledge import validation
    try:
        return validation.finish(sid, body.get("note", ""), cancelled=bool(body.get("cancelled")))
    except KeyError:
        raise HTTPException(404, "Unknown session")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/projects/{pid}/live")
def live_overview(pid: str):
    """Controlled live validation: register, baselines, AI proposals with estimator decisions, metrics, dependencies."""
    from qto import live
    _need(pid)
    if store.project(pid).get("archived"):
        raise HTTPException(409, "Archived projects are excluded from validation")
    return {"register": live.register(pid) if store.latest_run_id(pid) else [], "baselines": live.baselines(pid),
            "proposals": live.proposals(pid) if store.latest_run_id(pid) else [], "metrics": live.metrics(pid) if store.latest_run_id(pid) else None,
            "dependencies": live.dependencies(pid)}


@app.post("/api/projects/{pid}/live/drawings/{did}")
def live_drawing(pid: str, did: str, body: dict = Body(...)):
    from qto import live
    try:
        return live.update_drawing(pid, did, body)
    except KeyError:
        raise HTTPException(404, "Unknown drawing")


@app.post("/api/projects/{pid}/live/baselines")
def live_baseline(pid: str, body: dict = Body(...)):
    from qto import live
    try:
        return live.create_baseline(pid, body.get("source"), body.get("label", ""), body.get("revision"), body.get("note", ""))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/projects/{pid}/live/baselines/{bid}/compare")
def live_compare(pid: str, bid: str):
    from qto import live
    try:
        return live.revision_comparison(pid, bid)
    except KeyError:
        raise HTTPException(404, "Unknown baseline")


@app.post("/api/projects/{pid}/live/lines")
def live_line(pid: str, body: dict = Body(...)):
    from qto import live
    try:
        return live.decide_line(pid, body.get("item_id"), body.get("variant", ""), body.get("action"), body.get("estimator_quantity"),
                                body.get("comment", ""), body.get("reason", ""))
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/projects/{pid}/pilot")
def pilot_get(pid: str):
    from qto import pilot
    _need(pid)
    return pilot.report(pid)


@app.post("/api/projects/{pid}/pilot")
def pilot_save(pid: str, body: dict = Body(...)):
    from qto import pilot
    _need(pid)
    try:
        pilot.save(pid, body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return pilot.report(pid)


@app.get("/api/me")
def me():
    return {"user": store.user()}


@app.get("/api/reports/daily")
def daily_report(save: bool = False):
    from qto.reports.daily import build_daily_report
    return build_daily_report(save=save)


@app.exception_handler(Exception)
async def on_error(request, exc):
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})
