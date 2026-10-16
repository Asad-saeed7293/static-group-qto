"""Read Static Group's BOQ workbooks (the company template) into structured rows.

The template (seen in every historical project): sheets 'Summary', 'Preliminaries',
'BOQ FOR VILLA', optional 'Plastering works' / 'BOQ of Boundarywall'. Each BOQ sheet has a
header row 'ITEM | DESCRIPTION | QTY | UNIT | RATE | AMOUNT', item codes such as 'b.2.1'
(section) and '1.2' (item), and the quantity as a typed value.

Every row keeps sheet, row number, section path and the raw cells, so a quantity can be
traced back to the original workbook cell.
"""
from __future__ import annotations

import re

import openpyxl

SECTION_RE = re.compile(r"^[A-Za-z](\.\d+)*$")      # B, b.1, b.2.1, c.3, f.2
ITEM_RE = re.compile(r"^\d+(\.\d+)*$")               # 1, 1.2, 2.1


def _header(ws):
    for r in range(1, min(ws.max_row, 15) + 1):
        vals = {c: str(ws.cell(r, c).value or "").strip().upper() for c in range(1, ws.max_column + 1)}
        cols = {v: c for c, v in vals.items() if v}
        if "DESCRIPTION" in cols and ("QTY" in cols or "UNIT" in cols):
            return r, cols
    return None, None


def read_static_boq(path: str) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True)
    meta = {"file": path, "sheets": wb.sheetnames, "project": "", "client": "", "location": "", "ref": "", "date": ""}
    if "Summary" in wb.sheetnames:
        s = wb["Summary"]
        for r in range(1, 6):
            k = str(s.cell(r, 2).value or "").strip().rstrip(":").lower()
            if k in ("project", "client", "location"):
                meta[k] = str(s.cell(r, 3).value or "").strip()
        meta["ref"] = str(s.cell(3, 5).value or "")
        meta["date"] = str(s.cell(4, 5).value or "")
        meta["areas"] = [str(s.cell(r, 3).value).strip() for r in range(20, s.max_row + 1)
                         if s.cell(r, 3).value and "m2" in str(s.cell(r, 3).value)]
    rows = []
    for ws in wb:
        if ws.title.strip().upper() in ("CP", "SUMMARY"):
            continue
        hr, cols = _header(ws)
        if not hr:
            continue
        c_item = cols.get("ITEM")
        c_desc = cols.get("DESCRIPTION")
        c_qty = cols.get("QTY")
        c_unit = cols.get("UNIT")
        c_rate = cols.get("RATE")
        section_stack = []
        for r in range(hr + 1, ws.max_row + 1):
            item = ws.cell(r, c_item).value if c_item else None
            desc = ws.cell(r, c_desc).value if c_desc else None
            # 'QTY' header is sometimes missing; the quantity then sits in the column left of UNIT
            qcol = c_qty or (c_unit - 1 if c_unit else None)
            qty = ws.cell(r, qcol).value if qcol else None
            unit = ws.cell(r, c_unit).value if c_unit else None
            rate = ws.cell(r, c_rate).value if c_rate else None
            if desc is None and item is None:
                continue
            item_s = str(item).strip() if item is not None else ""
            desc_s = re.sub(r"\s+", " ", str(desc or "")).strip()
            if desc_s.upper().startswith(("TOTAL CARRIED", "SUMMARY", "PAGE", "GRAND TOTAL")) or item_s.upper().startswith(("TOTAL", "GRAND")):
                continue
            if SECTION_RE.match(item_s) and (qty in (None, "", "-") or isinstance(qty, str)):
                level = item_s.count(".")
                section_stack = [s for s in section_stack if s[0] < level] + [(level, item_s, desc_s)]
                continue
            is_number = isinstance(qty, (int, float))
            if is_number and qty == 1 and str(rate or "").strip().lower() == "ls":
                unit = unit or "item"
                rows.append({
                    "sheet": ws.title.strip(), "row": r, "item": item_s, "description": desc_s, "quantity": 1.0,
                    "unit": str(unit).strip(), "rate_note": "ls", "kind": "lump_sum",
                    "section_path": [s[1] for s in section_stack], "section_names": [s[2] for s in section_stack],
                })
                continue  # '1 m2 ... ls' is a lump-sum price, not a measured quantity
            kind = "measured" if is_number and str(unit or "").strip().lower() not in ("item", "ls", "") else \
                   "lump_sum" if str(unit or "").strip().lower() in ("item", "ls") or str(rate or "").strip().lower() == "ls" else \
                   "excluded" if str(ws.cell(r, cols.get("AMOUNT (QR)", 0) or 1).value or "").strip().lower() == "excluded" else \
                   "heading" if not is_number else "measured"
            if kind == "heading" and not unit:
                # item-level headings (e.g. '2 Tanks', '2.1 Holding tank ...', '# notes') accumulate
                # under the current section so that context such as 'Tanks' is not lost
                section_stack = section_stack + [(9, item_s, desc_s)]
                continue
            rows.append({
                "sheet": ws.title.strip(), "row": r, "item": item_s, "description": desc_s,
                "quantity": float(qty) if is_number else None, "unit": str(unit or "").strip(),
                "rate_note": str(rate or "").strip(), "kind": kind,
                "section_path": [s[1] for s in section_stack], "section_names": [s[2] for s in section_stack],
            })
    return {"meta": meta, "rows": rows}
