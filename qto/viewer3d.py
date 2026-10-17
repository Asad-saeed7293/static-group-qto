"""Build review-oriented 3D structural solids from a processed takeoff run.

This is a generated visualization of measured footprints and dimensions, not a native
CAD/BIM reconstruction. Missing measurements are reported instead of guessed.
"""
from __future__ import annotations

import math

from shapely.geometry import Polygon
from shapely.ops import triangulate

FLOOR_ORDER = ("FDN", "BS", "GR", "L1", "PH", "TOR")
DEPTH_KEYS = {
    "footing": "depth", "raft": "depth", "blinding": "thickness",
    "pedestal": "height", "column": "height", "wall": "height",
    "beam": "depth", "slab": "thickness",
}
MODEL_TYPES = tuple(DEPTH_KEYS)


def _value(dims: dict, key: str) -> tuple[float | None, dict]:
    measurement = dims.get(key) or {}
    value = measurement.get("value") if isinstance(measurement, dict) else measurement
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, measurement if isinstance(measurement, dict) else {}
    if not math.isfinite(number) or number <= 0:
        return None, measurement if isinstance(measurement, dict) else {}
    return number, measurement if isinstance(measurement, dict) else {}


def _level(design: dict, floor: str) -> tuple[float | None, bool, str]:
    level = (design.get("levels") or {}).get(floor) or {}
    value = level.get("value")
    try:
        z = float(value)
    except (TypeError, ValueError):
        return None, True, f"No usable level tag for {floor}"
    if not math.isfinite(z):
        return None, True, f"No usable level tag for {floor}"
    tied = bool(level.get("tie") or len(level.get("tied_values") or []) > 1)
    return z, tied, f"{level.get('kind') or 'level'} {z:+.3f} m on {floor}"


def _vertical_position(element: dict, design: dict, dimension: float, dimension_meta: dict,
                       element_by_uid: dict) -> tuple[float | None, float | None, bool, str]:
    kind, floor = element.get("element_type"), element.get("floor") or ""
    inferred = bool(dimension_meta.get("is_assumption"))
    placement = ""

    if kind in ("footing", "raft"):
        top, level_inferred, placement = _level(design, "FDN")
        if top is None:
            return None, None, True, placement
        inferred |= level_inferred
        return top - dimension, top, inferred, f"{placement}; depth {dimension:.3f} m"

    if kind == "blinding":
        host = element_by_uid.get((element.get("attributes") or {}).get("host_uid"))
        if host and host.get("element_type") in ("footing", "raft"):
            host_depth, _ = _value(host.get("dims") or {}, "depth")
            top_level, level_inferred, level_note = _level(design, "FDN")
            if host_depth and top_level is not None:
                top = top_level - host_depth
                host_meta = ((host.get("dims") or {}).get("depth") or {})
                inferred |= level_inferred or bool(host_meta.get("is_assumption"))
                return top - dimension, top, inferred, f"Below {host.get('uid')} ({level_note})"
        top, level_inferred, placement = _level(design, "FDN")
        if top is None:
            return None, None, True, placement
        inferred = True
        return top - dimension, top, inferred, "Placed below the foundation level; host footing elevation unavailable"

    if kind in ("column", "wall"):
        storey = (design.get("storey_heights") or {}).get(floor) or {}
        base = storey.get("base_level")
        try:
            base = float(base)
        except (TypeError, ValueError):
            base, level_inferred, placement = _level(design, floor)
        else:
            level_inferred = not bool(storey.get("confirmed"))
            placement = f"Base of {floor} storey at {base:+.3f} m"
        if base is None or not math.isfinite(base):
            return None, None, True, placement or f"No usable base level for {floor}"
        inferred |= level_inferred
        return base, base + dimension, inferred, f"{placement}; height {dimension:.3f} m"

    if kind == "pedestal":
        top, level_inferred, placement = _level(design, floor)
        if top is None:
            return None, None, True, placement
        inferred = True  # the takeoff has a height, but no support/top connection level
        return top - dimension, top, inferred, f"Top aligned to {placement}; support elevation not defined"

    top, level_inferred, placement = _level(design, floor)
    if top is None:
        return None, None, True, placement
    inferred |= level_inferred
    if kind == "beam":
        return top - dimension, top, inferred, f"Top aligned to {placement}; depth {dimension:.3f} m"
    if kind == "slab":
        return top - dimension, top, inferred, f"Top aligned to {placement}; thickness {dimension:.3f} m"
    return None, None, True, f"Unsupported structural type: {kind}"


def _component_mesh(poly: Polygon, z0: float, z1: float) -> list[float]:
    """Triangulate a polygon (including holes) and return unindexed triangle vertices."""
    out: list[float] = []

    def tri(a, b, c, z):
        out.extend((float(a[0]), float(a[1]), z,
                    float(b[0]), float(b[1]), z,
                    float(c[0]), float(c[1]), z))

    for face in triangulate(poly):
        if not poly.covers(face):
            continue
        points = list(face.exterior.coords)[:3]
        tri(points[0], points[1], points[2], z1)
        tri(points[2], points[1], points[0], z0)

    for ring in (poly.exterior, *poly.interiors):
        points = list(ring.coords)
        for a, b in zip(points, points[1:]):
            a0, b0 = (a[0], a[1], z0), (b[0], b[1], z0)
            a1, b1 = (a[0], a[1], z1), (b[0], b[1], z1)
            out.extend((*a0, *b0, *b1, *a0, *b1, *a1))
    return out


def _polygons(element: dict) -> tuple[list[Polygon], str | None]:
    points = element.get("geometry")
    if not isinstance(points, list) or len(points) < 3:
        return [], "No usable plan footprint"
    attrs = element.get("attributes") or {}
    hole_rings = attrs.get("interior_rings") or []
    if attrs.get("holes_in_linework") and not hole_rings:
        return [], "Opening outlines are missing from this saved run; reprocess to include them in the 3D model"
    try:
        primary = Polygon(points, holes=hole_rings)
        if not primary.is_valid:
            return [], "Plan footprint is invalid and needs drawing review"
        polygons = [primary] if primary.area > 0 else []
        for ring in attrs.get("extra_rings") or []:
            if len(ring) >= 3:
                piece = Polygon(ring)
                if not piece.is_valid:
                    return [], "A separate plan footprint is invalid and needs drawing review"
                if piece.area > 0:
                    polygons.append(piece)
    except (TypeError, ValueError):
        return [], "Plan footprint coordinates could not be read"
    if not polygons:
        return [], "Plan footprint has no area"
    return polygons, None


def build_model(elements: list[dict], design: dict) -> dict:
    """Turn measured structural outlines into prism meshes without changing quantities."""
    element_by_uid = {e.get("uid"): e for e in elements}
    meshes, not_modelled = [], []
    all_bounds = []

    for element in elements:
        kind = element.get("element_type")
        if kind not in MODEL_TYPES:
            continue
        uid = element.get("uid") or "unknown"
        dims = element.get("dims") or {}
        thickness_key = DEPTH_KEYS[kind]
        thickness, dimension_meta = _value(dims, thickness_key)
        if thickness is None:
            not_modelled.append({"uid": uid, "element_type": kind, "floor": element.get("floor"),
                                 "description": element.get("description") or uid,
                                 "reason": f"Required {thickness_key} is missing or invalid",
                                 "sources": element.get("sources") or []})
            continue
        polygons, reason = _polygons(element)
        if reason:
            not_modelled.append({"uid": uid, "element_type": kind, "floor": element.get("floor"),
                                 "description": element.get("description") or uid,
                                 "reason": reason, "sources": element.get("sources") or []})
            continue
        z0, z1, inferred, placement = _vertical_position(element, design, thickness,
                                                         dimension_meta, element_by_uid)
        if z0 is None or z1 is None or z1 <= z0:
            not_modelled.append({"uid": uid, "element_type": kind, "floor": element.get("floor"),
                                 "description": element.get("description") or uid,
                                 "reason": placement or "Could not determine vertical placement",
                                 "sources": element.get("sources") or []})
            continue

        vertices = []
        for poly in polygons:
            vertices.extend(_component_mesh(poly, z0, z1))
        if not vertices:
            not_modelled.append({"uid": uid, "element_type": kind, "floor": element.get("floor"),
                                 "description": element.get("description") or uid,
                                 "reason": "Footprint could not be triangulated",
                                 "sources": element.get("sources") or []})
            continue
        mesh = {"uid": uid, "element_type": kind, "floor": element.get("floor"),
                "mark": element.get("mark"), "description": element.get("description") or uid,
                "drawing": element.get("drawing"), "layer": element.get("layer"),
                "vertices": vertices, "dimensions": dims, "quantity": element.get("quantity"),
                "unit": element.get("unit"), "sources": element.get("sources") or [],
                "flags": element.get("flags") or [], "confidence": element.get("confidence"),
                "model_status": "inferred" if inferred else "measured",
                "placement_note": placement,
                "dimension_source": dimension_meta.get("source") or "takeoff record",
                "dimension_assumed": bool(dimension_meta.get("is_assumption"))}
        meshes.append(mesh)
        all_bounds.extend(zip(vertices[0::3], vertices[1::3], vertices[2::3]))

    floors_seen = {m["floor"] for m in meshes if m.get("floor")}
    floors_seen.update(m["floor"] for m in not_modelled if m.get("floor"))
    floors = sorted(floors_seen, key=lambda x: (FLOOR_ORDER.index(x) if x in FLOOR_ORDER else len(FLOOR_ORDER), x))
    types = sorted({m["element_type"] for m in meshes} | {m["element_type"] for m in not_modelled})
    bounds = ([min(p[0] for p in all_bounds), min(p[1] for p in all_bounds), min(p[2] for p in all_bounds),
               max(p[0] for p in all_bounds), max(p[1] for p in all_bounds), max(p[2] for p in all_bounds)]
              if all_bounds else None)
    inferred_count = sum(m["model_status"] == "inferred" for m in meshes)
    return {"available": bool(meshes), "source": "generated_from_takeoff",
            "disclaimer": "Generated from 2D takeoff geometry and available dimensions/levels. Review inferred placements; this is not a native or verified coordination model.",
            "units": "m", "floors": floors, "types": types, "bounds": bounds,
            "meshes": meshes, "not_modelled": not_modelled,
            "summary": {"modelled": len(meshes), "inferred": inferred_count,
                        "not_modelled": len(not_modelled)}}
