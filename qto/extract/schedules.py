"""Layer 2c - reading design information that lives outside the plan geometry:
schedule tables, the column schedule grid, section-detail dimensions and level tags.

Every record returned carries a ``source`` dict that ends up in the evidence view.
"""
from __future__ import annotations

import re
from collections import Counter

from ..geometry import centroid, rectangle_dims, min_rotated_rect
from .tables import header_text, parse_mm, table_to_records, table_to_records_by_header


# ---------------------------------------------------------------------------
def footing_schedule(drawing: dict, rules: dict) -> dict:
    """{mark: {w, l, d, source}} from footing schedule tables."""
    spec = rules["tables"]["footing_schedule"]
    out = {}
    for t in drawing.get("tables", []):
        hdr = header_text(t)
        if not all(k in hdr for k in spec["header_must_contain"]):
            continue
        recs = table_to_records_by_header(t, spec["header_map"]) if spec.get("header_map") else []
        for rec in (recs or table_to_records(t, spec)):
            mark = (rec.get("mark") or "").strip()
            if not re.fullmatch(r"C?F\d+", mark):
                continue
            out[mark] = {
                "w": parse_mm(rec.get("w_mm")), "l": parse_mm(rec.get("l_mm")), "d": parse_mm(rec.get("d_mm")),
                "raw": rec["_cells"],
                "source": {"drawing_id": drawing["drawing_id"], "drawing": drawing["file"], "entity_type": "ACAD_TABLE",
                           "handle": t["handle"], "block": t["block"], "layer": "0",
                           "note": f"Footing schedule table {t['block']}, row '{mark}'"},
            }
    return out


def beam_schedule(drawing: dict, rules: dict) -> dict:
    """{(mark, span): {w, d, remarks, source}}; span '-' when the beam has a single span."""
    spec = rules["tables"]["beam_schedule"]
    out = {}
    for t in drawing.get("tables", []):
        hdr = header_text(t)
        if not all(k in hdr for k in spec["header_must_contain"]):
            continue
        recs = table_to_records_by_header(t, spec["header_map"]) if spec.get("header_map") else []
        for rec in (recs or table_to_records(t, spec)):
            mark = (rec.get("mark") or "").strip()
            if not mark:
                continue
            span = (rec.get("span") or "-").strip()
            w_raw, d_raw = rec.get("w_mm"), rec.get("d_mm")
            out[(mark, span)] = {
                "w": parse_mm(w_raw), "d": parse_mm(d_raw), "w_raw": w_raw, "d_raw": d_raw,
                "remarks": rec.get("remarks") or "",
                "raw": rec["_cells"],
                "source": {"drawing_id": drawing["drawing_id"], "drawing": drawing["file"], "entity_type": "ACAD_TABLE",
                           "handle": t["handle"], "block": t["block"], "layer": "0",
                           "note": f"Beam schedule table {t['block']}, row '{mark}' span '{span}'"},
            }
    return out


# ---------------------------------------------------------------------------
def column_schedule(drawing: dict, rules: dict) -> tuple[dict, list]:
    """Read the 'SCHEDULE OF COLUMNS' grid on S-CD.

    The schedule is drawn, not tabulated: column marks across the top, floor
    names down the side, and in each cell a drawn cross-section (closed
    polyline on S-ELEV) with dimension strings. Returns
    ({(mark, floor_id): {w, d, source, dims_in_cell}}, warnings).
    """
    cfg = rules["column_schedule"]
    floors = {f["schedule_row"]: f["id"] for f in rules["floors"] if f.get("schedule_row")}
    texts = drawing["facts"]["all_texts"]
    sections = drawing["facts"]["outlines"].get(cfg["section_role"], [])
    dims = drawing["facts"]["dimensions"]
    warnings = []
    titles = [t for t in texts if re.search(cfg["title_regex"], t["text"])]
    mark_texts = [t for t in texts if re.fullmatch(cfg["mark_regex"], t["text"])]
    floor_texts = [t for t in texts if t["text"].strip().upper() in floors]
    result = {}
    used_sections = set()
    for ti, title in enumerate(titles):
        tx, ty = title["insert"]
        marks = [m for m in mark_texts if 0 < ty - m["insert"][1] < 0.5 and m["insert"][0] > tx - 0.5]
        rows = [f for f in floor_texts if abs(f["insert"][0] - tx) < 1.0 and 0 < ty - f["insert"][1] < 4.5]
        if not marks or not rows:
            warnings.append(f"Column schedule title at {title['insert']} has no marks/rows")
            continue
        # keep only marks belonging to this table (stop at a gap > 3 m, which separates side-by-side tables)
        marks.sort(key=lambda m: m["insert"][0])
        table_marks = [marks[0]]
        for m in marks[1:]:
            if m["insert"][0] - table_marks[-1]["insert"][0] > 3.0:
                break
            table_marks.append(m)
        xmin = tx - 0.3
        xmax = table_marks[-1]["insert"][0] + cfg["col_tolerance"] + 0.4
        ymin = min(r["insert"][1] for r in rows) - cfg["row_tolerance"]
        ymax = ty
        for s in sections:
            cx, cy = centroid(s["points"])
            if not (xmin <= cx <= xmax and ymin <= cy <= ymax):
                continue
            # marks are left-aligned text; compare against their visual centre
            def mx(m):
                return m["insert"][0] + 0.06 * len(m["text"]) * 0.5
            mark = min(table_marks, key=lambda m: abs(mx(m) - cx))
            row = min(rows, key=lambda r: abs(r["insert"][1] - cy))
            if abs(mx(mark) - cx) > cfg["col_tolerance"] or abs(row["insert"][1] - cy) > cfg["row_tolerance"]:
                warnings.append(f"Section {s['handle']} at ({cx:.2f},{cy:.2f}) could not be placed in a schedule cell")
                continue
            floor_id = floors[row["text"].strip().upper()]
            key = (mark["text"], floor_id)
            rect = rectangle_dims(s["points"])
            if rect is None:
                mr = min_rotated_rect(s["points"])
                w, d, shape = mr["short"], mr["long"], "non-rectangular"
            else:
                w, d, shape = rect["short"], rect["long"], "rectangular"
            b = s["bbox"]
            cell_dims = [round(dm["value"], 3) for dm in dims
                         if b[0] - 0.25 <= dm["defpoint"][0] <= b[2] + 0.25 and b[1] - 0.25 <= dm["defpoint"][1] <= b[3] + 0.25]
            if key in result:
                warnings.append(f"Two sections found in schedule cell {key}; keeping the first ({result[key]['source']['handle']})")
                continue
            used_sections.add(s["handle"])
            result[key] = {
                "w": round(w, 4), "d": round(d, 4), "shape": shape, "area": s["area"],
                "dims_in_cell": cell_dims,
                "source": {"drawing_id": drawing["drawing_id"], "drawing": drawing["file"], "entity_type": s["entity_type"],
                           "handle": s["handle"], "layer": s["layer"], "bbox": s["bbox"],
                           "note": f"Column schedule '{title['text'].strip()}' cell {mark['text']} / {row['text'].strip()}"},
            }
        # Fallback for schedules whose sections are drawn with plain lines (no closed outline):
        # read the section size from the dimension strings inside the cell.
        def mx(m):
            return m["insert"][0] + 0.06 * len(m["text"]) * 0.5
        for mk in table_marks:
            for row in rows:
                fid = floors[row["text"].strip().upper()]
                key = (mk["text"], fid)
                if key in result:
                    continue
                cx, cy = mx(mk), row["insert"][1]
                cell = [d for d in dims
                        if abs(d["defpoint"][0] - cx) <= cfg["col_tolerance"] and abs(d["defpoint"][1] - cy) <= cfg["row_tolerance"]
                        and 0.1 <= d["value"] <= 3.0]
                vals = sorted({round(d["value"], 3) for d in cell})
                if len(vals) < 1:
                    continue
                w, dpt = vals[0], vals[-1]
                if len(vals) == 1:
                    w = dpt  # square section dimensioned once
                handles = ",".join(d["handle"] for d in cell[:4])
                result[key] = {
                    "w": w, "d": dpt, "shape": "from dimension strings", "area": w * dpt, "dims_in_cell": vals,
                    "source": {"drawing_id": drawing["drawing_id"], "drawing": drawing["file"], "entity_type": "DIMENSION",
                               "handle": handles, "layer": cell[0]["layer"],
                               "note": f"Column schedule '{title['text'].strip()}' cell {mk['text']} / {row['text'].strip()} "
                                       f"(dimension strings {vals}; smallest = width, largest = depth)"},
                }
                warnings.append(f"Column schedule cell {key}: no drawn section outline, size read from dimension strings {vals}")
    stray = [s["handle"] for s in sections if s["handle"] not in used_sections]
    if stray:
        warnings.append(f"{len(stray)} section outline(s) on the schedule sheet are outside any schedule cell: {', '.join(stray[:10])}")
    return result, warnings


# ---------------------------------------------------------------------------
def section_detail_depths(drawing: dict, rules: dict) -> dict:
    """Tie-beam depths from section details ('TYPICAL SECTION THROUGH T.B.n').

    Depth = the largest vertical DIMENSION inside a window above the title.
    """
    cfg = rules["section_details"]["tie_beam"]
    w = cfg["window"]
    out = {}
    for t in drawing["facts"]["titles"]:
        m = re.search(cfg["title_regex"], t["viewname"])
        if not m:
            continue
        mark = f"T.B{m.group('n')}"
        tx, ty = t["insert"]
        vert = [d for d in drawing["facts"]["dimensions"]
                if abs((d["angle"] % 180) - 90) < 1
                and tx + w["dx_min"] <= d["defpoint"][0] <= tx + w["dx_max"]
                and ty + w["dy_min"] <= d["defpoint"][1] <= ty + w["dy_max"]
                and cfg["depth_min"] <= d["value"] <= cfg["depth_max"]]
        horiz = [d for d in drawing["facts"]["dimensions"]
                 if abs(d["angle"] % 180) < 1
                 and tx + w["dx_min"] <= d["defpoint"][0] <= tx + w["dx_max"]
                 and ty + w["dy_min"] <= d["defpoint"][1] <= ty + w["dy_max"]]
        rec = {"title": t["viewname"], "title_handle": t["handle"], "depth": None, "width_candidates": sorted({d["value"] for d in horiz}),
               "source": {"drawing_id": drawing["drawing_id"], "drawing": drawing["file"], "entity_type": "DIMENSION",
                          "handle": "", "layer": "", "note": f"Section detail '{t['viewname']}'"}}
        if vert:
            best = max(vert, key=lambda d: d["value"])
            rec["depth"] = best["value"]
            rec["source"]["handle"] = best["handle"]
            rec["source"]["layer"] = best["layer"]
            rec["source"]["note"] += f": vertical dimension {best['value']:.3f} m (largest of {len(vert)} in detail window)"
        out[mark] = rec
    return out


def blinding_thickness(drawing: dict) -> dict | None:
    vals = Counter()
    first = {}
    for t in drawing["facts"]["texts"].get("blinding_note", []):
        v = float(t["groups"]["t"]) / 1000.0
        vals[v] += 1
        first.setdefault(v, t)
    if not vals:
        return None
    v, n = vals.most_common(1)[0]
    t = first[v]
    return {"value": v, "occurrences": n, "distinct_values": sorted(vals),
            "source": {"drawing_id": drawing["drawing_id"], "drawing": drawing["file"], "entity_type": t["entity_type"],
                       "handle": t["handle"], "layer": t["layer"], "note": f"Note '{t['text']}' appears {n}x on the sheet"}}


# ---------------------------------------------------------------------------
_LEVEL_RE = re.compile(r"^[+\-±]?\s*\d+(\.\d+)?$")


def parse_level(s: str):
    s = (s or "").replace("%%P", "").replace("±", "").strip()
    return float(s.replace(" ", "")) if _LEVEL_RE.match(s) else None


def floor_level(drawing: dict, kind: str) -> dict:
    """Most frequent level value of `kind` (T.O.S / T.O.F) on a drawing, with full evidence."""
    tags = drawing["facts"]["blocks"].get("level_tag", [])
    vals = []
    unparsable = []
    for t in tags:
        if t["values"].get("kind", "").strip().upper() != kind.upper():
            continue
        v = parse_level(t["values"].get("value", ""))
        if v is None:
            unparsable.append(t["values"].get("value", ""))
        else:
            vals.append((v, t))
    if not vals:
        return {"value": None, "candidates": [], "unparsable": unparsable, "tie": False}
    cnt = Counter(v for v, _ in vals)
    top = cnt.most_common()
    best_n = top[0][1]
    tied = sorted(v for v, n in top if n == best_n)
    chosen = tied[0]
    tag = next(t for v, t in vals if v == chosen)
    return {
        "value": chosen, "kind": kind,
        "candidates": [{"value": v, "count": n} for v, n in sorted(cnt.items())],
        "unparsable": unparsable, "tie": len(tied) > 1, "tied_values": tied,
        "source": {"drawing_id": drawing["drawing_id"], "drawing": drawing["file"], "entity_type": "INSERT",
                   "handle": tag["handle"], "layer": tag["layer"], "block": tag["block_name"],
                   "note": f"{kind} {chosen:+.2f} = most frequent of {len(vals)} level tags on the sheet"},
    }
