"""Change detection between two runs of a project (drawing revisions -> BOQ impact).

Compares stored run outputs only: drawing files (size, entity count, extents, added/removed),
elements (added/removed/changed dimensions or quantities) and Static Group BOQ item values.
Nothing is inferred - every change listed is a difference between two stored records.
"""
from __future__ import annotations

from . import store


def _drawings(pid, rid):
    out = {}
    for d in store.read_project_run(pid, rid, "drawings.json") or []:
        m = d.get("meta") or {}
        out[d.get("rel_path") or d["file"]] = {"file": d["file"], "size": m.get("file_size"), "entities": m.get("modelspace_entities"),
                                                "extents": [round(v, 3) for v in (m.get("header_extents") or [])], "role": d.get("role")}
    return out


def _elem_qty(res):
    q = {}
    for r in res.get("quantities", []):
        q.setdefault(r["element_uid"], {})[r["quantity_type"]] = r["value"]
    return q


def compare_results(ro, rn, do=None, dn=None):
    do, dn = do or {}, dn or {}
    drawings = []
    for k in sorted(set(do) | set(dn)):
        a, b = do.get(k), dn.get(k)
        if a is None:
            drawings.append({"drawing": b["file"], "change": "added"})
        elif b is None:
            drawings.append({"drawing": a["file"], "change": "removed"})
        else:
            diff = [f for f in ("size", "entities", "extents") if a[f] != b[f]]
            if diff:
                drawings.append({"drawing": b["file"], "change": "modified", "fields": diff,
                                 "old": {f: a[f] for f in diff}, "new": {f: b[f] for f in diff}})
    eo = {e["uid"]: e for e in ro.get("elements", [])}
    en = {e["uid"]: e for e in rn.get("elements", [])}
    qo, qn = _elem_qty(ro), _elem_qty(rn)
    elements = []
    for u in sorted(set(eo) | set(en)):
        if u not in eo:
            elements.append({"uid": u, "type": en[u]["element_type"], "change": "added", "drawing": en[u].get("drawing")})
        elif u not in en:
            elements.append({"uid": u, "type": eo[u]["element_type"], "change": "removed", "drawing": eo[u].get("drawing")})
        else:
            a, b = eo[u].get("dims") or {}, en[u].get("dims") or {}
            dd = {k: [a.get(k), b.get(k)] for k in set(a) | set(b) if a.get(k) != b.get(k)}
            qa, qb = qo.get(u, {}), qn.get(u, {})
            qd = {k: [qa.get(k), qb.get(k)] for k in set(qa) | set(qb) if qa.get(k) != qb.get(k)}
            if dd or qd:
                elements.append({"uid": u, "type": en[u]["element_type"], "change": "modified", "dims": dd, "quantities": qd,
                                 "drawing": en[u].get("drawing")})
    key = lambda i: (i["item_id"], i["variant"])
    io = {key(i): i for i in ro.get("items", [])}
    inn = {key(i): i for i in rn.get("items", [])}
    items = []
    for k in sorted(set(io) | set(inn)):
        a, b = io.get(k) or {}, inn.get(k) or {}
        va, vb = a.get("value"), b.get("value")
        if va != vb or a.get("status") != b.get("status"):
            delta = round(vb - va, 3) if va is not None and vb is not None else None
            items.append({"item_id": k[0], "variant": k[1], "description": (b or a)["description"], "unit": (b or a)["unit"],
                          "old": va, "new": vb, "delta": delta,
                          "delta_pct": round(100 * delta / va, 1) if delta is not None and va else None,
                          "old_status": a.get("status"), "new_status": b.get("status")})
    tot = lambda r: sum(q["value"] or 0 for q in r.get("quantities", []) if q["quantity_type"] == "concrete_volume")
    return {"summary": {"drawings_changed": len(drawings), "elements_added": sum(e["change"] == "added" for e in elements),
                        "elements_removed": sum(e["change"] == "removed" for e in elements),
                        "elements_modified": sum(e["change"] == "modified" for e in elements),
                        "boq_items_changed": len(items),
                        "concrete_old_m3": round(tot(ro), 3), "concrete_new_m3": round(tot(rn), 3)},
            "drawings": drawings, "elements": elements, "items": items}


def compare_runs(pid, old=None, new=None):
    new = new or store.latest_run_id(pid)
    if new and old is None:
        meta = store.run_metadata(pid, new)
        old = meta.get("previous_run") or next((r["run_id"] for r in store.list_runs(pid) if r["run_id"] < new), None)
    if not (old and new):
        return {"project": pid, "old": old, "new": new, "available": False, "reason": "Two runs are needed for a comparison."}
    if not store.read_json(store.run_path(pid, old, "results.json")) or not store.read_json(store.run_path(pid, new, "results.json")):
        return {"project": pid, "old": old, "new": new, "available": False,
                "reason": "A referenced project-local run is unavailable; no comparison was generated."}
    ro = store.read_project_run(pid, old, "results.json")
    rn = store.read_project_run(pid, new, "results.json")
    if ro is None or rn is None:
        raise KeyError(f"Run results are missing for project {pid}")
    out = compare_results(ro, rn, _drawings(pid, old), _drawings(pid, new))
    return {"project": pid, "old": old, "new": new, "available": True, **out}
