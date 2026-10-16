"""Layer 2b - decoding schedule tables.

AutoCAD TABLE entities (ACAD_TABLE) store their rendered content in an
anonymous block (*T..). ezdxf does not expose the cell model, so we rebuild the
grid from the text entities inside that block: rows are clustered by Y, columns
by X. This works for any table regardless of its style.
"""
from __future__ import annotations

import re
import statistics


def _cluster(values, tol):
    """Cluster sorted 1-D values; returns list of cluster centres."""
    centres = []
    for v in sorted(values):
        if centres and abs(v - centres[-1][-1]) <= tol:
            centres[-1].append(v)
        else:
            centres.append([v])
    return [sum(c) / len(c) for c in centres]


def decode_tables(dwg) -> list:
    doc = dwg.doc
    tables = []
    for t in doc.modelspace().query("ACAD_TABLE"):
        name = t.dxf.get("geometry")
        if not name or name not in doc.blocks:
            dwg.log.append({"level": "warning", "message": f"ACAD_TABLE {t.dxf.handle} has no geometry block"})
            continue
        cells = []
        heights = []
        for e in doc.blocks[name]:
            if e.dxftype() not in ("TEXT", "MTEXT"):
                continue
            txt = (e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text or "").replace("\n", " / ").strip()
            if not txt:
                continue
            p = e.dxf.insert
            h = e.dxf.get("char_height" if e.dxftype() == "MTEXT" else "height", 1.0) or 1.0
            heights.append(h)
            cells.append({"x": p.x, "y": p.y, "text": re.sub(r"\s+", " ", txt), "h": h})
        if not cells:
            continue
        hmed = statistics.median(heights)
        row_centres = _cluster([c["y"] for c in cells], tol=hmed * 0.8)
        rows = {}
        for c in cells:
            ri = min(range(len(row_centres)), key=lambda i: abs(row_centres[i] - c["y"]))
            rows.setdefault(ri, []).append(c)
        ordered = [sorted(rows[i], key=lambda c: c["x"]) for i in sorted(rows, key=lambda i: -row_centres[i])]
        tables.append({
            "handle": t.dxf.handle,
            "block": name,
            "insert": [t.dxf.insert.x * dwg.unit_factor, t.dxf.insert.y * dwg.unit_factor],
            "rows": [[{"text": c["text"], "x": c["x"]} for c in r] for r in ordered],
            "char_height": hmed,
        })
    return tables


def _is_data_row(row):
    texts = [c["text"] for c in row]
    if len(texts) < 4:
        return False
    if any("(mm)" in t.lower() for t in texts):
        return False
    return any(re.fullmatch(r"\d+(\.\d+)?", t) for t in texts)


def table_to_records(table: dict, spec: dict) -> list:
    """Map a decoded table to records using column positions inferred from the data rows."""
    data_rows = [(i, r) for i, r in enumerate(table["rows"]) if _is_data_row(r)]
    if not data_rows:
        return []
    xs = [c["x"] for _, r in data_rows for c in r]
    # Cluster tolerance must stay below half the narrowest column spacing, or neighbouring
    # columns merge when the text height is large relative to the column width.
    widest = max((r for _, r in data_rows), key=len)
    gx = sorted(c["x"] for c in widest)
    gaps = [b - a for a, b in zip(gx, gx[1:]) if b - a > 1e-9]
    tol = table["char_height"] * 1.5
    if gaps:
        tol = min(tol, min(gaps) * 0.45)
    col_centres = _cluster(xs, tol)
    ncols = len(col_centres)
    out = []
    for ri, r in data_rows:
        vals = [None] * ncols
        for c in r:
            ci = min(range(ncols), key=lambda i: abs(col_centres[i] - c["x"]))
            vals[ci] = c["text"] if vals[ci] is None else vals[ci] + " " + c["text"]
        rec = {"_row": ri, "_cells": vals}
        for key, idx in spec["columns"].items():
            rec[key] = vals[idx] if -ncols <= idx < ncols else None
        out.append(rec)
    return out


def table_to_records_by_header(table: dict, header_map: dict) -> list:
    """Map data cells to named columns via the nearest header cell (robust to empty/offset cells).

    header_map: {field: header text (case-insensitive, whitespace-normalised)}.
    Falls back to [] when a required header is not found, so the caller can use positions instead.
    """
    norm = lambda s: re.sub(r"\s+", " ", s.strip().upper())
    headers = [(norm(c["text"]), c["x"]) for r in table["rows"] if not _is_data_row(r) for c in r]
    targets = {}
    for field, htxt in header_map.items():
        hx = [x for t, x in headers if t == norm(htxt)]
        if not hx:
            return []
        targets[field] = hx[0]
    all_hx = [x for _, x in headers]
    out = []
    for ri, r in enumerate(table["rows"]):
        if not _is_data_row(r):
            continue
        rec = {"_row": ri, "_cells": [c["text"] for c in r]}
        for field in header_map:
            rec[field] = None
        for c in r:
            nearest = min(all_hx, key=lambda x: abs(x - c["x"]))
            for field, tx in targets.items():
                if abs(nearest - tx) < 1e-9 and rec[field] is None:
                    rec[field] = c["text"]
        out.append(rec)
    return out


def header_text(table: dict) -> str:
    return " | ".join(c["text"] for r in table["rows"] if not _is_data_row(r) for c in r)


def parse_mm(v):
    """'2400' -> 2.4 (m). Returns None for '-', 'REFER TO ...', empty."""
    if v is None:
        return None
    v = str(v).strip()
    if re.fullmatch(r"\d+(\.\d+)?", v):
        return float(v) / 1000.0
    return None
