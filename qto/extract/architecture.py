"""Architectural extraction: wall polygons and openings from floor plans.

Observed in all three projects (Revit exports): block/masonry walls are filled with HATCH on
layer A-WALL-PATT; concrete is on STC-RCCE (excluded); doors and windows are block references
whose geometry sits on A-DOOR / A-GLAZ / A-DOOR-FRAM. Hatch patterns are named FP_n per file and
carry no meaning, so wall type is derived from measured thickness.

For a wall polygon of area A and perimeter P the thickness of a thin rectangle is
t = (P - sqrt(P^2 - 16A)) / 4 (exact for a rectangle); centre-line length = A / t.
For L/T-shaped hatches the same formula gives the mean thickness; thickness is snapped to
the nearest standard block size when within 15 mm, otherwise kept as measured and flagged.
"""
from __future__ import annotations

import math
import re

from ezdxf import bbox as ezbbox
from ezdxf import path as ezpath
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

STANDARD_T = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]


def _layer_ok(layer, pats):
    L = layer.split("$")[-1].upper()
    return any(re.fullmatch(p, L) for p in pats)


def hatch_polygons(hatch, f):
    polys = []
    try:
        for p in ezpath.from_hatch(hatch):
            pts = [(v.x * f, v.y * f) for v in p.flattening(0.005)]
            if len(pts) >= 3:
                poly = Polygon(pts)
                if not poly.is_valid:
                    poly = make_valid(poly)
                if poly.area > 1e-4:
                    polys.append(poly)
    except Exception:
        pass
    return polys


def thickness_length(poly):
    A, P = poly.area, poly.length
    disc = P * P - 16 * A
    if disc < 0:
        t = math.sqrt(A)
    else:
        t = (P - math.sqrt(disc)) / 4
    if t <= 0:
        return None, None, False
    snapped = min(STANDARD_T, key=lambda s: abs(s - t))
    ok = abs(snapped - t) <= 0.015
    tt = snapped if ok else t
    return round(tt, 3), round(A / tt, 3), ok


def _axis(poly):
    r = poly.minimum_rotated_rectangle
    c = list(r.exterior.coords)[:4]
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    p, q = (c[0], c[1]) if a >= b else (c[1], c[2])
    L = math.dist(p, q) or 1
    return ((q[0] - p[0]) / L, (q[1] - p[1]) / L)


def _composites(walls, max_gap=0.11, reach=0.8):
    """Group parallel wall layers (block + insulation + void + block) into one composite wall.

    A ray normal to each piece through its centre is intersected with all wall pieces; contiguous
    material (gaps <= max_gap, i.e. insulation/air void that is not hatched) forms the stack.
    The thickest layer of a stack is its 'primary' piece and carries the stack's length.
    """
    from shapely.geometry import LineString
    from shapely.strtree import STRtree
    polys = [Polygon(w["points"]) for w in walls]
    tree = STRtree(polys)
    for i, (w, p) in enumerate(zip(walls, polys)):
        ux, uy = _axis(p)
        nx, ny = -uy, ux
        c = p.representative_point()
        ray = LineString([(c.x - nx * reach, c.y - ny * reach), (c.x + nx * reach, c.y + ny * reach)])
        hits = []
        for j in tree.query(ray):
            if abs(abs(_axis(polys[j])[0] * ux + _axis(polys[j])[1] * uy) - 1) > 0.02:
                continue  # not parallel - a crossing wall
            inter = polys[j].intersection(ray)
            if inter.is_empty:
                continue
            for g in (inter.geoms if hasattr(inter, "geoms") else [inter]):
                cs = list(g.coords)
                s = sorted(((x - c.x) * nx + (y - c.y) * ny) for x, y in cs)
                hits.append((s[0], s[-1], j))
        hits.sort()
        # contiguous chain containing the centre (offset 0)
        chain = [h for h in hits if h[0] <= 1e-6 <= h[1] + 1e-6][:1]
        if not chain:
            w.update(composite_thickness=w["thickness"], stack=[i], primary=True)
            continue
        lo, hi = chain[0][0], chain[0][1]
        members = {chain[0][2]}
        changed = True
        while changed:
            changed = False
            for a, b, j in hits:
                if j in members:
                    continue
                if a - hi <= max_gap and b > hi:
                    hi, changed = b, True
                    members.add(j)
                elif lo - b <= max_gap and a < lo:
                    lo, changed = a, True
                    members.add(j)
        w["composite_thickness"] = round(hi - lo, 3)
        w["stack"] = sorted(members)
        w["stack_layers"] = sorted((walls[j]["thickness"] for j in members), reverse=True)
    for i, w in enumerate(walls):
        st = w.get("stack", [i])
        best = max(st, key=lambda j: (walls[j]["thickness"], -j))
        w["primary"] = best == i


def extract_walls_openings(dwg, rules: dict) -> dict:
    cfg = rules.get("architecture", {})
    wall_layers = cfg.get("wall_hatch_layers", ["A-WALL-PATT"])
    opening_layers = cfg.get("opening_layers", ["A-GLAZ", "A-DOOR", "A-DOOR-FRAM"])
    f = dwg.unit_factor
    doc = dwg.doc
    msp = doc.modelspace()
    raw = []
    for h in msp.query("HATCH"):
        if _layer_ok(h.dxf.layer, wall_layers):
            for poly in hatch_polygons(h, f):
                raw.append((h.dxf.handle, h.dxf.get("pattern_name", ""), poly))
    # merge hatches that are the same wall drawn in pieces? Keep separate: each hatch = one wall piece.
    walls = []
    for handle, pat, poly in raw:
        geoms = list(poly.geoms) if hasattr(poly, "geoms") else [poly]
        for g in geoms:
            if g.geom_type != "Polygon" or g.area < 0.005:
                continue
            t, L, snapped = thickness_length(g)
            if not t:
                continue
            walls.append({"handle": handle, "pattern": pat, "area": round(g.area, 4), "perimeter": round(g.length, 3),
                          "thickness": t, "length": L, "thickness_snapped": snapped,
                          "points": [[round(x, 4), round(y, 4)] for x, y in list(g.exterior.coords)[:-1]],
                          "bbox": [round(v, 3) for v in g.bounds]})
    if walls:
        _composites(walls)
        # external vs internal: building outline = walls closed over door/column gaps; a wall within
        # its stack thickness of the outline is external
        polys = [Polygon(w["points"]) for w in walls]
        closed = unary_union([p.buffer(0.6) for p in polys]).buffer(-0.6)
        parts = list(closed.geoms) if hasattr(closed, "geoms") else [closed]
        rings = unary_union([Polygon(p.exterior.coords) for p in parts if p.geom_type == "Polygon" and p.area > 4]).boundary
        for w, p in zip(walls, polys):
            w["external"] = bool(p.distance(rings) <= (w.get("composite_thickness") or w["thickness"]) + 0.1)
    # openings: block references whose content is on door/window layers
    openings = []
    for ins in msp.query("INSERT"):
        name = ins.dxf.name
        if name.startswith("*") or name not in doc.blocks:
            continue
        blk = doc.blocks[name]
        lay = [e.dxf.layer for e in blk if e.dxftype() != "ATTDEF"]
        if not lay:
            continue
        share = sum(1 for L in lay if _layer_ok(L, opening_layers)) / len(lay)
        if share < 0.5 and not _layer_ok(ins.dxf.layer, opening_layers):
            continue
        try:
            ext = ezbbox.extents(blk, fast=True)
            sx = abs(ins.dxf.get("xscale", 1)) * ext.size.x * f
            sy = abs(ins.dxf.get("yscale", 1)) * ext.size.y * f
        except Exception:
            continue
        width = max(sx, sy)
        kind = "door" if any(k in name.upper() for k in ("DOOR", "ELEVATOR", "GATE")) or \
            sum(1 for L in lay if "DOOR" in L.upper()) > sum(1 for L in lay if "GLAZ" in L.upper()) else "window"
        p = ins.dxf.insert
        openings.append({"handle": ins.dxf.handle, "block": name, "kind": kind, "width": round(width, 3),
                         "depth": round(min(sx, sy), 3), "insert": [round(p.x * f, 3), round(p.y * f, 3)],
                         "rotation": round(ins.dxf.get("rotation", 0), 1)})
    # host wall: nearest wall polygon to the opening insert point
    if walls:
        polys = [Polygon(w["points"]) for w in walls]
        from shapely.geometry import Point
        for o in openings:
            P = Point(o["insert"])
            d, i = min((pp.distance(P), i) for i, pp in enumerate(polys))
            o["host_wall"] = walls[i]["handle"] if d < 0.6 else None
            o["host_external"] = walls[i]["external"] if d < 0.6 else None
            o["host_thickness"] = walls[i]["thickness"] if d < 0.6 else None
    return {"walls": walls, "openings": openings}
