"""Stages 2-4: enumerate, load and classify every DXF in a project folder.

Each drawing becomes a dict with metadata, an inventory (layers, entity types,
blocks, unsupported entities) and - for drawings whose role is recognised by the
rules - the classified *facts* used by the element builders.
"""
from __future__ import annotations

import os
import time
from collections import Counter

from .classify.rules import classify, detect_discipline, detect_role
from .extract.tables import decode_tables
from .ingest.dxf_reader import flatten, load_dxf, viewer_geometry

NON_DXF_NOTE = "Not a DXF drawing - listed but not processed"


def list_files(root: str) -> tuple[list, list]:
    """CAD drawings (.dxf, native .dwg) go to the first list for processing; everything else is listed
    but not processed. A .dwg needs the ODA File Converter on this machine - see ingest/dwg_convert.py -
    but it is still classified as a drawing here so a missing converter shows up as a clear per-file error
    in the processing log, not as a silently-skipped file."""
    dxf, other = [], []
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for f in sorted(fn):
            p = os.path.join(dp, f)
            (dxf if f.lower().endswith((".dxf", ".dwg")) else other).append(p)
    return dxf, other


def inventory(dwg) -> dict:
    msp = dwg.doc.modelspace()
    types, layers, blocks = Counter(), Counter(), Counter()
    texts = []
    for e in msp:
        t = e.dxftype()
        types[t] += 1
        layers[e.dxf.get("layer", "0")] += 1
        if t == "INSERT":
            blocks[e.dxf.name] += 1
        elif t in ("TEXT", "MTEXT") and len(texts) < 400:
            try:
                s = (e.plain_text() if t == "MTEXT" else e.dxf.text or "").strip()
                if s:
                    texts.append(s[:80])
            except Exception:
                pass
    layer_table = []
    for l in dwg.doc.layers:
        layer_table.append({"name": l.dxf.name, "color": l.dxf.get("color", 7), "on": l.is_on(), "frozen": l.is_frozen(),
                            "entities": layers.get(l.dxf.name, 0)})
    return {
        "entity_types": dict(types.most_common()),
        "layers_used": dict(layers.most_common()),
        "layer_table": layer_table,
        "blocks_inserted": dict(blocks.most_common(60)),
        "text_sample": texts[:60],
    }


def _symbol_counts(dwg, patterns: dict, max_depth=4) -> dict:
    """Count block references (also inside xrefs/nested blocks) and labels matching symbol patterns."""
    import re
    counts = {k: {"blocks": 0, "labels": 0, "block_names": Counter(), "label_samples": []} for k in patterns}

    def walk(ents, depth):
        for e in ents:
            t = e.dxftype()
            if t == "INSERT":
                for k, pat in patterns.items():
                    if re.search(pat, e.dxf.name):
                        counts[k]["blocks"] += 1
                        counts[k]["block_names"][e.dxf.name] += 1
                if depth < max_depth:
                    try:
                        walk(e.virtual_entities(), depth + 1)
                    except Exception:
                        pass
            elif t in ("TEXT", "MTEXT"):
                s = (e.plain_text() if t == "MTEXT" else e.dxf.text or "").strip()
                for k, pat in patterns.items():
                    if re.search(pat, s):
                        counts[k]["labels"] += 1
                        if len(counts[k]["label_samples"]) < 5:
                            counts[k]["label_samples"].append(s[:60])
    walk(dwg.doc.modelspace(), 0)
    for v in counts.values():
        v["block_names"] = dict(v["block_names"])
    return counts


def role_extras(dwg, role: str, rules: dict) -> dict:
    """Role-specific extraction that needs the open document (walls, symbols, plot boundary)."""
    if role == "arch_floor_plan":
        from .extract.architecture import extract_walls_openings
        return extract_walls_openings(dwg, rules)
    if role in ("site_drainage", "site_electrical"):
        return {"symbol_counts": _symbol_counts(dwg, rules.get("symbols", {}))}
    if role == "site_plan":
        import math
        cands = []
        for e in dwg.doc.modelspace().query("LWPOLYLINE"):
            L = e.dxf.layer.split("$")[-1].upper()
            if e.closed and any(k in L for k in ("PROP", "BOUND", "PLOT")):
                pts = [(p[0] * dwg.unit_factor, p[1] * dwg.unit_factor) for p in e.get_points("xy")]
                per = sum(math.dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))
                cands.append({"handle": e.dxf.handle, "layer": e.dxf.layer, "perimeter": round(per, 2), "vertices": len(pts)})
        cands.sort(key=lambda c: -c["perimeter"])
        return {"plot_boundary_candidates": cands[:5]}
    return {}


def scan_drawing(path: str, root: str, rules: dict, cache_dir: str | None) -> dict:
    t0 = time.time()
    rel = os.path.relpath(path, root)
    role, groups, role_title = detect_role(rel, rules)
    rec = {"file": os.path.basename(path), "rel_path": rel, "discipline": detect_discipline(rel, rules),
           "role": role, "role_groups": groups, "role_title": role_title, "status": "error", "log": []}
    try:
        dwg = load_dxf(path, root, rules.get("units", {}).get("default_insunits_if_missing", 6))
    except Exception as exc:
        rec["log"].append({"level": "error", "message": f"Could not open DXF: {exc}"})
        rec["drawing_id"] = None
        rec["seconds"] = round(time.time() - t0, 2)
        return rec
    rec["drawing_id"] = dwg.drawing_id
    rec["meta"] = dwg.meta
    rec["inventory"] = inventory(dwg)
    if role:
        flatten(dwg)
        rec["facts"] = classify(dwg, role, rules)
        rec["tables"] = decode_tables(dwg)
        rec["flattened_entities"] = len(dwg.entities)
        try:
            extra = role_extras(dwg, role, rules)
            rec["facts"].update(extra)
        except Exception as exc:  # extras are best-effort; the drawing is still processed
            rec["log"].append({"level": "warning", "message": f"{role} extraction failed: {exc}"})
        rec["unsupported"] = dict(dwg.unsupported)
        rec["status"] = "processed"
        if cache_dir:
            try:
                import json
                os.makedirs(cache_dir, exist_ok=True)
                with open(os.path.join(cache_dir, f"{dwg.drawing_id}.json"), "w", encoding="utf-8") as fh:
                    json.dump(viewer_geometry(dwg), fh, separators=(",", ":"))
                rec["viewer_cached"] = True
            except Exception as exc:
                rec["log"].append({"level": "warning", "message": f"Viewer geometry not cached: {exc}"})
    else:
        # Inventory only: count unsupported types in model space for the report
        rec["unsupported"] = {}
        rec["status"] = "inventoried"
        rec["log"].append({"level": "info", "message": "No quantity rule applies to this drawing type - inventoried only"})
    rec["log"] = dwg.log + rec["log"]
    rec["seconds"] = round(time.time() - t0, 2)
    dwg.doc = None
    return rec
