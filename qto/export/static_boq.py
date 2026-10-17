"""Export quantities into the supplied Static Group BOQ without changing its layout."""
from __future__ import annotations

import os
import re
from datetime import date
from difflib import SequenceMatcher

import openpyxl
from openpyxl.cell.cell import MergedCell
from openpyxl.utils import get_column_letter

from .. import service, store


# The workbook is the source of truth for wording, row positions, merged cells,
# print areas, formulas and page breaks. We only populate measured data cells.
SHEET_LAYOUTS = {
    "Preliminaries": {"start_col": 2, "section_col": 2, "desc_col": 3, "qty_col": 4, "rate_col": 6, "amount_col": 7},
    "BOQ FOR VILLA": {"start_col": 3, "section_col": 3, "desc_col": 4, "qty_col": 5, "rate_col": 7, "amount_col": 8},
    "Plastering works": {"start_col": 2, "section_col": 2, "desc_col": 3, "qty_col": 4, "rate_col": 6, "amount_col": 7},
}


def _normalise(value):
    value = str(value or "").lower().replace("<l>", "")
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _score(left, right):
    """Conservative text score; low-confidence or ambiguous matches stay blank."""
    a, b = _normalise(left), _normalise(right)
    if not a or not b:
        return 0.0
    a_words, b_words = set(a.split()), set(b.split())
    overlap = len(a_words & b_words) / max(1, len(a_words | b_words))
    return 0.55 * SequenceMatcher(None, a, b).ratio() + 0.45 * overlap


def _section_ranges(ws, layout):
    """Find template rows belonging to each top-level section code."""
    col = layout["section_col"]
    starts = []
    for row in range(6, ws.max_row + 1):
        value = ws.cell(row, col).value
        if isinstance(value, str) and value.strip() in {"A", "B", "C", "D", "E", "F"}:
            starts.append((value.strip(), row))
    ranges = {}
    for index, (code, first) in enumerate(starts):
        end = starts[index + 1][1] - 1 if index + 1 < len(starts) else ws.max_row
        ranges[code] = (first, end)
    return ranges


def _match_line(ws, line, layout, ranges, used_rows):
    """Match to an existing item row within the same top-level section only."""
    if line.get("is_group_header"):
        return None
    bounds = ranges.get(str(line.get("section", "")).strip())
    if not bounds:
        return None
    first, last = bounds
    candidates = []
    for row in range(first, last + 1):
        if row in used_rows:
            continue
        # Item rows have a numeric item reference in the template's first table column.
        code = ws.cell(row, layout["section_col"]).value
        description = ws.cell(row, layout["desc_col"]).value
        if (not isinstance(code, (int, float)) or not isinstance(description, str)
                or isinstance(ws.cell(row, layout["qty_col"]), MergedCell)):
            continue
        score = _score(line.get("description"), description)
        candidates.append((score, row))
    candidates.sort(reverse=True)
    if not candidates or candidates[0][0] < 0.72:
        return None
    # If two template rows are similarly plausible, do not guess which one is intended.
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.07:
        return None
    return candidates[0][1]


def export_static_boq(pid, path):
    """Fill measurable quantities while preserving the reference workbook's layout."""
    from ..boq.static_template import generate_static_boq

    result = service.results(pid)
    lines = generate_static_boq(result["results"].get("items") or [])["lines"]
    project = store.project(pid)
    template_path = os.path.join(store.CONFIG, "templates", "static_group_boq_template.xlsx")
    wb = openpyxl.load_workbook(template_path)
    sheets = {name: wb[name] for name in SHEET_LAYOUTS}
    ranges = {name: _section_ranges(ws, SHEET_LAYOUTS[name]) for name, ws in sheets.items()}
    used_rows = {name: set() for name in sheets}

    # Clear every old sample quantity, rate and amount on data rows. Keep all
    # descriptions, codes, units, row heights, merges, styles and print settings.
    for name, ws in sheets.items():
        layout = SHEET_LAYOUTS[name]
        for row in range(6, ws.max_row + 1):
            code = ws.cell(row, layout["section_col"]).value
            description = ws.cell(row, layout["desc_col"]).value
            if isinstance(code, (int, float)) and isinstance(description, str):
                for col in (layout["qty_col"], layout["rate_col"], layout["amount_col"]):
                    cell = ws.cell(row, col)
                    if not isinstance(cell, MergedCell):
                        cell.value = None

    for line in lines:
        name = line.get("sheet")
        if name not in sheets:
            name = "BOQ FOR VILLA"
        ws, layout = sheets[name], SHEET_LAYOUTS[name]
        row = _match_line(ws, line, layout, ranges[name], used_rows[name])
        if row is None:
            continue
        used_rows[name].add(row)
        status = line.get("display_status")
        if status == "Excluded":
            cell = ws.cell(row, layout["amount_col"])
            if not isinstance(cell, MergedCell):
                cell.value = "Excluded"
        elif status == "Lump Sum":
            qty_cell, rate_cell = ws.cell(row, layout["qty_col"]), ws.cell(row, layout["rate_col"])
            if not isinstance(qty_cell, MergedCell):
                qty_cell.value = line.get("quantity") or 1
            if not isinstance(rate_cell, MergedCell):
                rate_cell.value = "ls"
        elif line.get("quantity") is not None:
            qty_col, rate_col, amount_col = layout["qty_col"], layout["rate_col"], layout["amount_col"]
            qty_cell, amount_cell = ws.cell(row, qty_col), ws.cell(row, amount_col)
            if not isinstance(qty_cell, MergedCell):
                qty_cell.value = line["quantity"]
            if not isinstance(amount_cell, MergedCell):
                qty_letter, rate_letter = get_column_letter(qty_col), get_column_letter(rate_col)
                amount_cell.value = f"={qty_letter}{row}*{rate_letter}{row}"

    # Refresh project fields, while retaining the workbook's fixed commercial text.
    for name in SHEET_LAYOUTS:
        ws = wb[name]
        ws["C2" if name != "BOQ FOR VILLA" else "D2"] = project["name"]
        ws["C3" if name != "BOQ FOR VILLA" else "D3"] = project.get("client") or ""
        ws["C4" if name != "BOQ FOR VILLA" else "D4"] = project.get("location") or ""
        ws["E3" if name != "BOQ FOR VILLA" else "F3"] = project.get("ref_no") or ""
        ws["E4" if name != "BOQ FOR VILLA" else "F4"] = date.today()

    summary = wb["Summary"]
    summary["C2"], summary["C3"], summary["C4"] = project["name"], project.get("client") or "", project.get("location") or ""
    summary["E3"], summary["E4"] = project.get("ref_no") or "", date.today()
    for row in range(28, 38):
        for cell in summary[row]:
            if not isinstance(cell, MergedCell) and cell.data_type != "f":
                cell.value = None
    # Keep the template's own totals and exact wording; refresh only its formula result.
    wb["Preliminaries"]["G51"] = "=SUM(G6:G50)"
    cover = wb["CP "]
    cover["C7"], cover["C8"], cover["C9"] = project["name"], "=Summary!C3", "=Summary!C4"
    for row in cover.iter_rows(min_row=67, max_row=cover.max_row):
        for cell in row:
            if not isinstance(cell, MergedCell):
                cell.value = None

    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.save(path)
    return path
