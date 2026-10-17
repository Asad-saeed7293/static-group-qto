"""Slab zones from framing plans.

The drawings do not contain closed slab polygons. They contain slab boundary
linework (layer *X-LOS-SLAB-BNDY* inside the bound 'X-LOS-<floor>' xref) that
marks the slab perimeter and the lines where level/thickness changes, plus a
thickness tag ('Iden-Slab Thickness' block) placed inside each zone.

Zones are reconstructed by polygonising that linework (shapely.polygonize).
Each zone takes its thickness from the tag(s) it contains:
  * exactly one distinct thickness -> volume is calculated
  * several distinct thicknesses   -> the boundary linework is incomplete; the
    zone is split with beam/wall edges and re-evaluated; anything still
    ambiguous is flagged, never averaged
  * no tag                         -> 'Missing thickness'
Shafts/openings (X-LOS-SLAB-SHAFT) inside a zone are deducted from its area.
"""
from __future__ import annotations

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union
from shapely.validation import make_valid

from ..geometry import clean_ring
from ..models import (Element, Flag, Measurement, SEV_INFO, SEV_WARN, SRC_CAD_GEOMETRY, SRC_SLAB_TAG,
                      SRC_MISSING, SRC_DERIVED, SRC_USER, ST_CHECK, ST_MISSING, ST_REVIEW)
from .common import ref_from

MIN_FACE_AREA = 0.05
RESIDUAL_MAX_AREA = 2.0   # untagged split pieces smaller than this are grouped into one residual zone
SUGGEST_MAX_DIST = 0.75   # a tag this close outside an untagged zone is offered as a suggestion


def _valid_poly(points):
    """Polygon from CAD points, repaired if self-intersecting (CAD outlines often are)."""
    p = Polygon(clean_ring(points))
    return p if p.is_valid else make_valid(p)


def _safe_area(a, b):
    try:
        return a.intersection(b).area
    except Exception:
        return a.buffer(0).intersection(b.buffer(0)).area


def _lines(recs):
    out = []
    for r in recs:
        pts = [tuple(p) for p in r["points"]]
        if r.get("closed") and len(pts) > 2:
            pts = pts + [pts[0]]
        if len(pts) >= 2:
            out.append(LineString(pts))
    return out


def _tag_key(t):
    return (t["values"].get("thickness_mm", "").strip(), t["values"].get("slab_type", "").strip())


def slab_zones(fr: dict, floor: str, settings: dict, overrides: dict | None = None) -> tuple[list, list]:
    """overrides: {slab uid: thickness_mm} entered by users for zones without a usable tag."""
    facts = fr["facts"]
    bnd = facts["outlines"].get("slab_boundary", [])
    openings = [o for o in facts["outlines"].get("slab_opening", []) if o["closed"] and len(o["points"]) >= 3]
    tags = facts["blocks"].get("slab_thickness_tag", [])
    warnings = []
    if not bnd:
        return [], [f"{fr['file']}: no slab boundary linework found"]
    faces = [f for f in polygonize(unary_union(_lines(bnd))) if f.area >= MIN_FACE_AREA]
    tiny = len(list(polygonize(unary_union(_lines(bnd))))) - len(faces)
    if tiny:
        warnings.append(f"{fr['file']}: {tiny} sliver face(s) < {MIN_FACE_AREA} m2 ignored")

    # splitter linework used only when a face holds conflicting tags
    splitters = _lines(facts["outlines"].get("beam_outline", []))

    zones = []  # (polygon, [tags], refined: bool, parent_index)
    for fi, face in enumerate(sorted(faces, key=lambda p: -p.area)):
        inside = [t for t in tags if face.contains(Point(t["insert"]))]
        keys = {_tag_key(t) for t in inside}
        if len(keys) <= 1:
            zones.append((face, inside, False, fi))
            continue
        sub = [s for s in polygonize(unary_union([face.boundary] + [l for l in splitters if l.intersects(face)]))
               if s.area >= MIN_FACE_AREA and face.buffer(1e-6).contains(s.representative_point())]
        if len(sub) <= 1:
            zones.append((face, inside, False, fi))
            continue
        residual = []
        for s in sorted(sub, key=lambda p: -p.area):
            sin = [t for t in inside if s.contains(Point(t["insert"]))]
            if not sin and s.area < RESIDUAL_MAX_AREA:
                residual.append(s)      # beam strips / slivers created by the split
            else:
                zones.append((s, sin, True, fi))
        if residual:
            zones.append((unary_union(residual), [], True, fi))

    elements = []
    min_open = settings["measurement"].get("deduct_openings_min_area_m2", 0.0)
    overrides = overrides or {}
    zi = 0
    for z, inside, refined, parent in zones:
        parts = list(z.geoms) if z.geom_type == "MultiPolygon" else [z]
        main = max(parts, key=lambda p: p.area)
        # skip zones that are entirely an opening (shaft drawn with its own boundary)
        occupied = sum(_safe_area(_valid_poly(o["points"]), z) for o in openings)
        if z.area - occupied < MIN_FACE_AREA:
            warnings.append(f"{fr['file']}: zone of {z.area:.2f} m2 is entirely a shaft/opening - not a slab")
            continue
        zi += 1
        coords = [[round(x, 4), round(y, 4)] for x, y in list(main.exterior.coords)[:-1]]
        bb = [round(v, 4) for v in z.bounds]
        e = Element(uid=f"SLB-{floor}-{zi:02d}", element_type="slab", mark=f"{floor}-S{zi:02d}", floor=floor,
                    drawing_id=fr["drawing_id"], drawing=fr["file"], layer="X-LOS-SLAB-BNDY", geometry=coords)
        if len(parts) > 1:
            e.attributes["extra_rings"] = [[[round(x, 4), round(y, 4)] for x, y in list(p.exterior.coords)[:-1]]
                                           for p in parts if p is not main]
            e.attributes["residual_pieces"] = len(parts)
        e.attributes["id_note"] = "System-generated zone ID: slab panels are not numbered on the drawing"
        e.attributes["zone_method"] = ("Polygonised slab-boundary linework, split along beam outlines" if refined
                                       else "Polygonised slab-boundary linework")
        e.attributes["parent_face"] = parent
        e.sources.append(ref_from(fr, {"layer": "X-LOS-SLAB-BNDY", "entity_type": "LWPOLYLINE/LINE (polygonised)",
                                       "handle": ", ".join(b["handle"] for b in bnd[:6]) + ("…" if len(bnd) > 6 else ""),
                                       "bbox": bb}, "Zone reconstructed from slab boundary linework"))
        if main.interiors:
            e.attributes["holes_in_linework"] = len(main.interiors)
            e.attributes["interior_rings"] = [
                [[round(x, 4), round(y, 4)] for x, y in list(ring.coords)[:-1]]
                for ring in main.interiors
            ]
        gross = z.area
        deducted = []
        for o in openings:
            op = _valid_poly(o["points"])
            if op.area >= min_open and z.contains(op.representative_point()):
                inter = _safe_area(op, z)
                if inter > 1e-4:
                    deducted.append((o, inter))
        net = gross - sum(a for _, a in deducted)
        e.dims["gross_area"] = Measurement("gross_area", round(gross, 4), "m2", SRC_CAD_GEOMETRY,
                                           f"Area of reconstructed zone polygon ({len(coords)} vertices)", e.sources[0])
        e.dims["openings_area"] = Measurement("openings_area", round(gross - net, 4), "m2", SRC_CAD_GEOMETRY,
                                              f"{len(deducted)} shaft/opening outline(s) inside the zone" if deducted else "No openings inside zone")
        e.dims["net_area"] = Measurement("net_area", round(net, 4), "m2", SRC_DERIVED, "Gross area - openings")
        for o, a in deducted:
            e.sources.append(ref_from(fr, o, f"Opening deducted: {a:.3f} m2"))
        keys = sorted({_tag_key(t) for t in inside})
        for t in inside:
            e.sources.append(ref_from(fr, t, f"Slab tag {t['values']}"))
        if len(keys) == 1:
            th, typ = keys[0]
            try:
                thv = float(th) / 1000.0
            except ValueError:
                thv = None
            e.attributes["slab_type"] = typ
            e.description = f"{_type_name(typ)} {th} mm - {floor} zone {zi}"
            if thv:
                e.dims["thickness"] = Measurement("thickness", thv, "m", SRC_SLAB_TAG,
                                                  f"SLAB_THICKNESS={th}, SLAB_TYPE={typ} ({len(inside)} tag(s) in zone)",
                                                  ref_from(fr, inside[0]))
                e.confidence, e.confidence_reason = (0.85 if not refined else 0.7), ("thickness tag inside zone" + (" (zone split along beams)" if refined else ""))
            else:
                e.dims["thickness"] = Measurement("thickness", None, "m", SRC_MISSING, f"Unparsable thickness '{th}'")
        elif not keys:
            e.description = f"Slab zone {zi} ({floor}) - no thickness tag"
            e.dims["thickness"] = Measurement("thickness", None, "m", SRC_MISSING, "No 'Iden-Slab Thickness' tag inside this zone")
            e.flags.append(Flag("MISSING_THICKNESS", "Slab zone has no thickness tag",
                                "Area is measured, but the drawing does not tag a thickness inside this zone. "
                                "Thickness was NOT assumed - confirm it from sections/details.", SEV_WARN, ST_MISSING))
            e.confidence, e.confidence_reason = 0.5, "no thickness tag"
        else:
            e.description = f"Slab zone {zi} ({floor}) - conflicting tags"
            e.dims["thickness"] = Measurement("thickness", None, "m", SRC_MISSING,
                                              "Conflicting tags in one zone: " + "; ".join(f"{a} mm {b}" for a, b in keys))
            e.flags.append(Flag("AMBIGUOUS_THICKNESS", "Several slab thicknesses inside one zone",
                                "The boundary linework does not separate these slab types: "
                                + "; ".join(f"{a} mm {b}" for a, b in keys)
                                + ". The system does not average or guess - an engineer must split the zone.",
                                SEV_WARN, ST_REVIEW))
            e.confidence, e.confidence_reason = 0.4, "conflicting thickness tags"
        if e.dim("thickness") is None:
            # Suggest (never apply) the nearest tag that sits just outside this zone.
            cands = sorted(((z.exterior.distance(Point(t["insert"])) if z.geom_type == "Polygon" else z.distance(Point(t["insert"])), t)
                            for t in tags if not z.contains(Point(t["insert"]))), key=lambda x: x[0])
            if cands and cands[0][0] <= SUGGEST_MAX_DIST:
                d, t = cands[0]
                e.attributes["suggested_thickness_mm"] = t["values"].get("thickness_mm")
                e.attributes["suggestion"] = (f"Tag {t['values'].get('thickness_mm')} mm {t['values'].get('slab_type')} "
                                              f"({t['handle']}) sits {d:.2f} m outside this zone - it may belong here.")
                e.flags.append(Flag("SUGGESTION", "Nearby thickness tag may belong to this zone",
                                    e.attributes["suggestion"] + " Not applied automatically; accept it in the Review Queue.",
                                    SEV_INFO, ST_MISSING))
            ov = overrides.get(e.uid)
            if ov not in (None, ""):
                e.dims["thickness"] = Measurement("thickness", float(ov) / 1000.0, "m", SRC_USER,
                                                  f"Entered/confirmed by user: {ov} mm (drawing value not available)")
                e.flags = [f for f in e.flags if f.code not in ("MISSING_THICKNESS", "AMBIGUOUS_THICKNESS", "SUGGESTION")]
                e.flags.append(Flag("USER_INPUT", "Thickness entered by user",
                                    f"Thickness {ov} mm was entered by a user; see audit log.", SEV_INFO, ST_CHECK))
                e.confidence, e.confidence_reason = 0.75, "user-confirmed thickness"
        if refined:
            e.flags.append(Flag("ZONE_SPLIT_ALONG_BEAMS", "Zone boundary partly inferred from beam edges",
                                "The slab boundary linework alone left several slab types in one region; the region was split "
                                "along drawn beam edges. Check that the split matches the intended slab extents.", SEV_INFO, ST_CHECK))
        elements.append(e)
    used = {id(t) for _, ins, _, _ in zones for t in ins}
    for t in tags:
        if id(t) not in used:
            warnings.append(f"{fr['file']}: slab tag {t['values']} at {t['insert']} lies outside every reconstructed zone")
    return elements, warnings


def _type_name(code: str) -> str:
    c = code.upper().replace(" ", "")
    return {"S.S": "Suspended slab", "S.O.G.": "Slab on grade", "S.O.G": "Slab on grade",
            "D.P": "Slab (D.P)", "RAFT": "Raft"}.get(c, f"Slab ({code})")


def thickness_at(slabs: list, pt) -> tuple:
    """Thickness of the slab zone containing pt -> (value|None, element|None)."""
    P = Point(pt)
    hits = [s for s in slabs if Polygon(s.geometry).contains(P)]
    if not hits:
        return None, None
    s = min(hits, key=lambda s: s.dim("gross_area") or 0)  # innermost zone (outer faces may enclose holes)
    return s.dim("thickness"), s
