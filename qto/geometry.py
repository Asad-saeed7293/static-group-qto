"""Pure geometry helpers (no DXF, no business rules) - independently testable."""
from __future__ import annotations

import math
from typing import Iterable, Optional

from shapely.geometry import Point, Polygon


def clean_ring(points: Iterable) -> list:
    """Drop the duplicated closing vertex and consecutive duplicates."""
    pts = []
    for p in points:
        p = (float(p[0]), float(p[1]))
        if not pts or abs(p[0] - pts[-1][0]) > 1e-9 or abs(p[1] - pts[-1][1]) > 1e-9:
            pts.append(p)
    if len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) < 1e-9 and abs(pts[0][1] - pts[-1][1]) < 1e-9:
        pts.pop()
    return pts


def shoelace_area(points) -> float:
    pts = clean_ring(points)
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def centroid(points):
    pts = clean_ring(points)
    if len(pts) >= 3:
        c = Polygon(pts).centroid
        return (c.x, c.y)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _collinear(a, b, c, tol=1e-6):
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < tol


def simplify_ring(points) -> list:
    """Remove collinear intermediate vertices (CAD often stores them)."""
    pts = clean_ring(points)
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            if _collinear(a, b, c):
                pts.pop(i)
                changed = True
                break
    return pts


def rectangle_dims(points, tol: float = 0.002) -> Optional[dict]:
    """If the ring is a (possibly rotated) rectangle return its side lengths.

    Returns {'long','short','angle_deg'} or None when the outline is not rectangular.
    """
    pts = simplify_ring(points)
    if len(pts) != 4:
        return None
    sides = [math.dist(pts[i], pts[(i + 1) % 4]) for i in range(4)]
    if abs(sides[0] - sides[2]) > tol or abs(sides[1] - sides[3]) > tol:
        return None
    # right angles
    for i in range(4):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % 4]
        v1 = (a[0] - b[0], a[1] - b[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        n = math.hypot(*v1) * math.hypot(*v2)
        if n == 0 or abs((v1[0] * v2[0] + v1[1] * v2[1]) / n) > 0.01:
            return None
    s1, s2 = (sides[0] + sides[2]) / 2, (sides[1] + sides[3]) / 2
    if s1 >= s2:
        ang = math.degrees(math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0]))
    else:
        ang = math.degrees(math.atan2(pts[2][1] - pts[1][1], pts[2][0] - pts[1][0]))
    ang = ang % 180.0
    return {"long": max(s1, s2), "short": min(s1, s2), "angle_deg": ang}


def min_rotated_rect(points) -> dict:
    poly = Polygon(clean_ring(points))
    r = poly.minimum_rotated_rectangle
    c = list(r.exterior.coords)[:4]
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    return {"long": max(a, b), "short": min(a, b)}


def point_poly_distance(pt, points) -> float:
    poly = Polygon(clean_ring(points))
    return poly.exterior.distance(Point(pt)) if not poly.contains(Point(pt)) else 0.0


def contains(points, pt) -> bool:
    return Polygon(clean_ring(points)).contains(Point(pt))


def same_ring(a, b, tol=0.002) -> bool:
    """True if two outlines are the same geometry (vertex order / start independent)."""
    pa, pb = simplify_ring(a), simplify_ring(b)
    if len(pa) != len(pb):
        return False
    for p in pa:
        if not any(math.dist(p, q) <= tol for q in pb):
            return False
    return True


def axis_angle(rotation_deg: float) -> float:
    """Normalise an angle to [0, 180)."""
    return rotation_deg % 180.0


def angle_diff(a: float, b: float) -> float:
    d = abs(axis_angle(a) - axis_angle(b))
    return min(d, 180.0 - d)
