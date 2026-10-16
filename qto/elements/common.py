"""Shared helpers for element builders: pairing labels to geometry, duplicate detection,
and SourceRef construction."""
from __future__ import annotations

import math

from shapely.geometry import Point, Polygon

from ..geometry import centroid, clean_ring, same_ring
from ..models import Flag, SourceRef, SEV_INFO, SEV_WARN, ST_CHECK, ST_REVIEW


def ref_from(drawing: dict, rec: dict, note: str = "") -> SourceRef:
    return SourceRef(drawing_id=drawing["drawing_id"], drawing=drawing["file"], layer=rec.get("layer", ""),
                     entity_type=rec.get("entity_type", rec.get("type", "")), handle=rec.get("handle", ""),
                     block=rec.get("block", "") or rec.get("block_name", ""), bbox=rec.get("bbox"), note=note)


def ref_from_dict(d: dict) -> SourceRef:
    return SourceRef(drawing_id=d.get("drawing_id", ""), drawing=d.get("drawing", ""), layer=d.get("layer", ""),
                     entity_type=d.get("entity_type", ""), handle=d.get("handle", ""), block=d.get("block", ""),
                     bbox=d.get("bbox"), note=d.get("note", ""))


def poly(rec) -> Polygon:
    return Polygon(clean_ring(rec["points"]))


def dist_point_outline(pt, rec) -> float:
    p = poly(rec)
    P = Point(pt)
    return 0.0 if p.contains(P) else p.exterior.distance(P)


def text_centre(t: dict) -> tuple:
    """Approximate visual centre of a single-line text from its insertion point."""
    x, y = t["insert"]
    h = t.get("height") or 0.2
    length = 0.8 * h * len(t["text"])
    a = math.radians(t.get("rotation", 0.0))
    if t.get("entity_type") == "MTEXT":
        return (x + math.cos(a) * length / 2, y - h / 2)
    return (x + math.cos(a) * length / 2 - math.sin(a) * h / 2, y + math.sin(a) * length / 2 + math.cos(a) * h / 2)


def greedy_pairs(outlines, tags, max_dist, key=None):
    """One-to-one pairing by ascending distance (centre of text to outline; 0 if inside).

    Returns (pairs: {outline_idx: (tag_idx, dist)}, unpaired_tags: [idx]).
    """
    cands = []
    for oi, o in enumerate(outlines):
        for ti, t in enumerate(tags):
            c = text_centre(t)
            d = dist_point_outline(c, o)
            if d <= max_dist:
                # tie-breaker: distance to the outline's centroid
                cx, cy = centroid(o["points"])
                cands.append((d, math.dist(c, (cx, cy)), oi, ti))
    cands.sort()
    pairs, used_t = {}, set()
    for d, dc, oi, ti in cands:
        if oi in pairs or ti in used_t:
            continue
        pairs[oi] = (ti, d)
        used_t.add(ti)
    return pairs, [i for i in range(len(tags)) if i not in used_t]


def dedupe(outlines, tol):
    """Remove geometrically identical outlines. Returns (unique, duplicates[(dup, original)])."""
    unique, dups = [], []
    for o in outlines:
        orig = next((u for u in unique if abs(u["area"] - o["area"]) < 1e-4 and same_ring(u["points"], o["points"], tol)), None)
        if orig:
            dups.append((o, orig))
        else:
            unique.append(o)
    return unique, dups


def flag_dup(dup, orig) -> Flag:
    return Flag("DUPLICATE_GEOMETRY", "Duplicate geometry excluded",
                f"Entity {dup['handle']} on layer {dup['layer']} is identical to {orig['handle']}; it was excluded so the quantity is not counted twice.",
                SEV_INFO, ST_CHECK)


def confidence_from_distance(d, max_d):
    if d <= 0:
        return 0.95, "label inside outline"
    return max(0.5, 0.95 - 0.4 * d / max_d), f"label {d:.2f} m from outline"
