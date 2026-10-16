"""Layer 1 - DXF ingestion.

Opens a DXF with ezdxf (falling back to ezdxf's recover mode for damaged files),
resolves drawing units, and flattens model space - including nested block
references and bound xrefs - into simple ``FlatEntity`` records expressed in
metres. Nothing here knows about footings or beams; that is the job of the
classification layer.

Robustness rules:
* A failure on one entity is logged and skipped, never fatal.
* Entity types that are not used for quantities are counted and reported.
* Block nesting is followed to MAX_DEPTH; deeper content is reported.
"""
from __future__ import annotations

import hashlib
import math
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

import ezdxf
from ezdxf import recover

MAX_DEPTH = 4

# DXF $INSUNITS -> metres
INSUNITS_TO_M = {
    0: None, 1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0, 7: 1000.0,
    8: 2.54e-8, 9: 2.54e-5, 10: 0.9144, 14: 0.1, 15: 10.0,
}
INSUNITS_NAME = {0: "Unitless", 1: "Inches", 2: "Feet", 4: "Millimetres", 5: "Centimetres",
                 6: "Metres", 7: "Kilometres", 10: "Yards", 14: "Decimetres"}

# Entity types the extraction engine reads directly.
EXTRACTED_TYPES = {"LWPOLYLINE", "POLYLINE", "LINE", "TEXT", "MTEXT", "INSERT", "DIMENSION",
                   "ACAD_TABLE", "ATTRIB", "CIRCLE", "ARC"}
# Types that are rendered in the viewer but never used for quantities.
RENDER_ONLY_TYPES = {"ELLIPSE", "SPLINE", "LEADER", "SOLID", "POINT", "MULTILEADER", "TRACE"}
# Types that are recognised but deliberately skipped (logged as unsupported for QTO).
IGNORED_TYPES = {"HATCH", "IMAGE", "WIPEOUT", "OLE2FRAME", "VIEWPORT", "ATTDEF", "3DFACE",
                 "3DSOLID", "REGION", "BODY", "MESH", "XLINE", "RAY", "TOLERANCE", "UNDERLAY",
                 "PDFUNDERLAY", "DWFUNDERLAY", "DGNUNDERLAY", "SHAPE"}


def drawing_id_for(rel_path: str) -> str:
    stem = os.path.splitext(os.path.basename(rel_path))[0]
    slug = "".join(c if c.isalnum() else "-" for c in stem.lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"{slug[:40]}-{hashlib.sha1(rel_path.lower().encode()).hexdigest()[:6]}"


def base_layer(layer: str) -> str:
    """Bound xrefs prefix layers as 'XREFNAME$0$LAYER'. The CAD standard layer is the last part."""
    return layer.split("$")[-1] if "$" in layer else layer


@dataclass
class FlatEntity:
    handle: str
    dxftype: str
    layer: str
    base_layer: str
    block: str = ""                 # name of containing block ("" = model space)
    depth: int = 0
    points: list = field(default_factory=list)   # [(x, y)] metres
    closed: bool = False
    has_bulge: bool = False
    text: str = ""
    text_height: float = 0.0
    rotation: float = 0.0
    insert: Optional[tuple] = None
    block_name: str = ""            # for INSERT
    attribs: dict = field(default_factory=dict)
    measurement: Optional[float] = None   # for DIMENSION
    dim_angle: Optional[float] = None
    radius: Optional[float] = None

    def bbox(self):
        pts = self.points or ([self.insert] if self.insert else [])
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return [min(xs), min(ys), max(xs), max(ys)]


@dataclass
class LoadedDrawing:
    path: str
    rel_path: str
    drawing_id: str
    doc: object
    unit_factor: float
    meta: dict
    log: list                                   # [{level, message}]
    entities: list = field(default_factory=list)   # [FlatEntity]
    type_counts: Counter = field(default_factory=Counter)
    unsupported: Counter = field(default_factory=Counter)


def load_dxf(path: str, root: str, default_insunits: int = 6) -> LoadedDrawing:
    rel = os.path.relpath(path, root)
    log = []
    read_path = path
    if path.lower().endswith(".dwg"):
        from .dwg_convert import ensure_dxf
        read_path = ensure_dxf(path)
        log.append({"level": "info", "message": f"Converted from DWG via ODA File Converter (cached as {os.path.basename(read_path)})"})
    try:
        doc = ezdxf.readfile(read_path)
    except ezdxf.DXFStructureError as exc:
        log.append({"level": "warning", "message": f"Structure error ({exc}); retried with recover mode"})
        doc, auditor = recover.readfile(read_path)
        for err in auditor.errors[:20]:
            log.append({"level": "warning", "message": f"Recovered: {err.message}"})
    insunits = doc.header.get("$INSUNITS", 0)
    factor = INSUNITS_TO_M.get(insunits)
    if factor is None:
        log.append({"level": "warning",
                    "message": f"$INSUNITS={insunits} is unitless/unknown; assuming project default {INSUNITS_NAME.get(default_insunits)}"})
        factor = INSUNITS_TO_M[default_insunits]
    msp = doc.modelspace()
    meta = {
        "dxf_version": doc.dxfversion,
        "acad_release": ezdxf.const.acad_release.get(doc.dxfversion, doc.dxfversion),
        "insunits": insunits,
        "units": INSUNITS_NAME.get(insunits, f"code {insunits}"),
        "unit_factor_to_m": factor,
        "measurement_system": "Metric" if doc.header.get("$MEASUREMENT", 1) == 1 else "Imperial (header flag)",
        "layouts": [l.name for l in doc.layouts],
        "layer_count": len(doc.layers),
        "block_count": len([b for b in doc.blocks if not b.name.startswith("*Model") and not b.name.startswith("*Paper")]),
        "modelspace_entities": len(msp),
        "file_size": os.path.getsize(path),
    }
    try:
        ext_min, ext_max = doc.header.get("$EXTMIN"), doc.header.get("$EXTMAX")
        meta["header_extents"] = [ext_min[0] * factor, ext_min[1] * factor, ext_max[0] * factor, ext_max[1] * factor]
    except Exception:
        meta["header_extents"] = None
    return LoadedDrawing(path=path, rel_path=rel, drawing_id=drawing_id_for(rel), doc=doc,
                         unit_factor=factor, meta=meta, log=log)


def _text_anchor(e):
    try:
        if e.dxftype() == "TEXT" and (e.dxf.halign or e.dxf.valign) and e.dxf.hasattr("align_point"):
            return e.dxf.align_point
    except Exception:
        pass
    return e.dxf.insert


def _flat(e, f, block, depth, handle_prefix) -> Optional[FlatEntity]:
    t = e.dxftype()
    layer = e.dxf.get("layer", "0")
    h = e.dxf.get("handle")
    if not h:  # virtual copy of a block entity: report the handle inside the block definition
        src = getattr(e, "source_of_copy", None)
        h = src.dxf.get("handle") if src is not None else "virtual"
    fe = FlatEntity(handle=f"{handle_prefix}{h}", dxftype=t, layer=layer, base_layer=base_layer(layer),
                    block=block, depth=depth)
    if t == "LWPOLYLINE":
        pts = list(e.get_points("xyb"))
        fe.points = [(p[0] * f, p[1] * f) for p in pts]
        fe.has_bulge = any(abs(p[2]) > 1e-9 for p in pts)
        fe.closed = bool(e.closed)
    elif t == "POLYLINE":
        if e.is_2d_polyline or e.is_3d_polyline:
            fe.points = [(v.dxf.location.x * f, v.dxf.location.y * f) for v in e.vertices]
            fe.closed = bool(e.is_closed)
        else:
            return None
    elif t == "LINE":
        s, en = e.dxf.start, e.dxf.end
        fe.points = [(s.x * f, s.y * f), (en.x * f, en.y * f)]
    elif t in ("TEXT", "ATTRIB"):
        p = _text_anchor(e)
        fe.text = (e.dxf.text or "").strip()
        fe.insert = (p.x * f, p.y * f)
        fe.text_height = e.dxf.get("height", 0) * f
        fe.rotation = e.dxf.get("rotation", 0.0)
    elif t == "MTEXT":
        p = e.dxf.insert
        fe.text = e.plain_text().strip()
        fe.insert = (p.x * f, p.y * f)
        fe.text_height = e.dxf.get("char_height", 0) * f
        fe.rotation = e.dxf.get("rotation", 0.0)
    elif t == "INSERT":
        p = e.dxf.insert
        fe.insert = (p.x * f, p.y * f)
        fe.block_name = e.dxf.name
        fe.rotation = e.dxf.get("rotation", 0.0)
        try:
            fe.attribs = {a.dxf.tag: (a.dxf.text or "").strip() for a in e.attribs}
        except Exception:
            fe.attribs = {}
    elif t == "DIMENSION":
        try:
            fe.measurement = float(e.get_measurement()) * f
        except Exception:
            fe.measurement = None
        fe.text = e.dxf.get("text", "")
        fe.dim_angle = e.dxf.get("angle", 0.0)
        try:
            d = e.dxf.defpoint
            fe.insert = (d.x * f, d.y * f)
            p2, p3 = e.dxf.get("defpoint2"), e.dxf.get("defpoint3")
            if p2 is not None and p3 is not None:
                fe.points = [(p2.x * f, p2.y * f), (p3.x * f, p3.y * f)]
        except Exception:
            pass
    elif t == "CIRCLE":
        c = e.dxf.center
        fe.insert = (c.x * f, c.y * f)
        fe.radius = e.dxf.radius * f
    elif t == "ARC":
        c = e.dxf.center
        fe.insert = (c.x * f, c.y * f)
        fe.radius = e.dxf.radius * f
    elif t == "ACAD_TABLE":
        p = e.dxf.insert
        fe.insert = (p.x * f, p.y * f)
        fe.block_name = e.dxf.get("geometry", "")
    else:
        return None
    return fe


def flatten(dwg: LoadedDrawing, expand_blocks: bool = True):
    """Populate dwg.entities with model-space entities and the content of block references."""
    f = dwg.unit_factor
    out = dwg.entities
    deep_skipped = Counter()

    def walk(entities, block, depth, prefix):
        for e in entities:
            t = e.dxftype()
            dwg.type_counts[t] += 1
            if t in IGNORED_TYPES:
                dwg.unsupported[t] += 1
                continue
            try:
                fe = _flat(e, f, block, depth, prefix)
            except Exception as exc:  # never let one entity kill the drawing
                dwg.unsupported[f"{t} (error)"] += 1
                dwg.log.append({"level": "warning", "message": f"Could not read {t} {e.dxf.get('handle')}: {exc}"})
                continue
            if fe is not None:
                out.append(fe)
            elif t not in RENDER_ONLY_TYPES:
                dwg.unsupported[t] += 1
            if t == "INSERT" and expand_blocks:
                if depth >= MAX_DEPTH:
                    deep_skipped[e.dxf.name] += 1
                    continue
                try:
                    children = list(e.virtual_entities())
                except Exception as exc:
                    dwg.log.append({"level": "warning", "message": f"Block '{e.dxf.name}' could not be expanded: {exc}"})
                    continue
                walk(children, e.dxf.name, depth + 1, f"{fe.handle if fe else e.dxf.handle}>")

    walk(dwg.doc.modelspace(), "", 0, "")
    for name, n in deep_skipped.items():
        dwg.log.append({"level": "warning", "message": f"Block '{name}' nested deeper than {MAX_DEPTH} levels ({n}x) - not expanded"})
    return out


# ---------------------------------------------------------------------------
# Viewer geometry: a compact, render-ready representation of model space.
# ---------------------------------------------------------------------------
MAX_VIEW_ITEMS = 120_000


def viewer_geometry(dwg: LoadedDrawing) -> dict:
    from ezdxf import path as ezpath

    f = dwg.unit_factor
    layers = {}
    items = []
    skipped = Counter()
    truncated = False

    def lid(layer):
        if layer not in layers:
            color = 7
            try:
                color = dwg.doc.layers.get(layer).dxf.color
            except Exception:
                pass
            layers[layer] = {"i": len(layers), "name": layer, "base": base_layer(layer), "color": abs(color) or 7, "n": 0}
        layers[layer]["n"] += 1
        return layers[layer]["i"]

    def add_path(e, layer):
        p = ezpath.make_path(e)
        verts = list(p.flattening(0.01 / f if f else 0.01))
        if len(verts) < 2:
            return
        flat = []
        for v in verts:
            flat += [round(v.x * f, 4), round(v.y * f, 4)]
        items.append({"t": "p", "l": lid(layer), "p": flat, "h": e.dxf.get("handle", "")})

    def walk(entities, depth, inherited_layer=None):
        nonlocal truncated
        for e in entities:
            if len(items) >= MAX_VIEW_ITEMS:
                truncated = True
                return
            t = e.dxftype()
            layer = e.dxf.get("layer", "0")
            if layer == "0" and inherited_layer:
                layer = inherited_layer
            try:
                if t in ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE"):
                    if t == "POLYLINE" and not (e.is_2d_polyline or e.is_3d_polyline):
                        skipped[t] += 1
                        continue
                    add_path(e, layer)
                elif t in ("TEXT", "MTEXT", "ATTRIB"):
                    txt = e.plain_text() if t == "MTEXT" else (e.dxf.text or "")
                    if not txt.strip():
                        continue
                    p = _text_anchor(e) if t != "MTEXT" else e.dxf.insert
                    hgt = e.dxf.get("char_height" if t == "MTEXT" else "height", 0.2)
                    items.append({"t": "t", "l": lid(layer), "x": round(p.x * f, 4), "y": round(p.y * f, 4),
                                  "s": txt[:200], "hgt": round(hgt * f, 4), "r": round(e.dxf.get("rotation", 0.0), 2),
                                  "m": 1 if t == "MTEXT" else 0})
                elif t == "LEADER":
                    flat = []
                    for v in e.vertices:
                        flat += [round(v[0] * f, 4), round(v[1] * f, 4)]
                    if len(flat) >= 4:
                        items.append({"t": "p", "l": lid(layer), "p": flat})
                elif t == "SOLID":
                    pts = [e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx3, e.dxf.vtx2]
                    flat = []
                    for v in pts:
                        flat += [round(v[0] * f, 4), round(v[1] * f, 4)]
                    items.append({"t": "p", "l": lid(layer), "p": flat, "c": 1})
                elif t in ("INSERT", "DIMENSION", "MULTILEADER"):
                    if depth < MAX_DEPTH:
                        walk(e.virtual_entities(), depth + 1, layer)
                    if t == "INSERT":
                        for a in e.attribs:
                            walk([a], depth + 1, layer)
                elif t == "ACAD_TABLE":
                    name = e.dxf.get("geometry")
                    if name and name in dwg.doc.blocks:
                        walk(dwg.doc.blocks[name], depth + 1, layer)
                else:
                    skipped[t] += 1
            except Exception:
                skipped[f"{t} (error)"] += 1

    walk(dwg.doc.modelspace(), 0)
    xs, ys = [], []
    for it in items:
        if it["t"] == "p":
            xs += it["p"][0::2]
            ys += it["p"][1::2]
        else:
            xs.append(it["x"]); ys.append(it["y"])
    bounds = [min(xs), min(ys), max(xs), max(ys)] if xs else [0, 0, 1, 1]
    return {
        "drawing_id": dwg.drawing_id,
        "bounds": bounds,
        "layers": sorted(layers.values(), key=lambda l: l["i"]),
        "items": items,
        "not_rendered": dict(skipped),
        "truncated": truncated,
    }


def angle_of(p0, p1):
    return math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
