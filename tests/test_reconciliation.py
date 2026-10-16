import os
import sys

import pytest
from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qto.boq.compare import compare, match_rows, variance
from qto.boq.importer import import_rows
from qto.review.queue import build_queue

SETTINGS = {"tolerances": [{"max_abs_pct": 2.0, "status": "OK"},
                           {"max_abs_pct": 5.0, "status": "Check"}],
            "tolerance_above_status": "Review Required", "verified_requires_cross_checks": True}


def _line(item_no="02.01", mark="F3", desc="Reinforced concrete in footing F3", quantity=3.6, floor="FDN"):
    return {"item_no": item_no, "mark_norm": "".join(c for c in mark.upper() if c.isalnum()),
            "element_type": "footing", "floor": floor, "description": desc,
            "quantity": quantity, "unit": "m3", "status": "OK", "category": "Footings",
            "element_uids": ["F3-1"], "qids": ["F3-1:concrete_volume"],
            "calculation_evidence": [{"qid": "F3-1:concrete_volume", "formula": "L x W x D",
                                     "substitution": "2 x 2 x .45", "inputs": {},
                                     "evidence": [{"ref": {"drawing": "S-FP.dxf", "handle": "A1"}}]}]}


def _row(**overrides):
    row = {"row": 8, "source_row": 8, "source_sheet": "BOQ", "item_no": "1.1",
           "description": "Reinforced concrete in footing F3", "element": "F3",
           "floor": "", "unit": "m3", "quantity": 3.6, "issues": [],
           "source_item_no": "1.1", "source_description": "Reinforced concrete in footing F3",
           "source_unit": "m3", "source_quantity": 3.6}
    row.update(overrides)
    return row


def _result(rows, lines):
    return compare(rows, lines, {"F3-1": {"cross_checks": [], "sources": []}}, SETTINGS)


def test_exact_match_carries_source_row_and_calculation_evidence():
    result = _result([_row()], [_line()])["rows"][0]
    assert result["match_class"] == "exact"
    assert result["boq_source_row"] == 8 and result["boq_sheet"] == "BOQ"
    assert result["calculation_refs"][0]["qids"] == ["F3-1:concrete_volume"]
    assert result["calculation_refs"][0]["evidence"][0]["evidence"][0]["ref"]["handle"] == "A1"
    assert result["variance"] == 0 and result["absolute_variance"] == 0


def test_normalized_element_and_item_codes_match():
    line = _line()
    row = _row(element="f.3")
    assert match_rows([row], [line])[0][1] == [0]
    row = _row(element="", item_no="02-01")
    assert match_rows([row], [line])[0][1] == [0]


def test_description_only_match_is_suggestion_and_not_verified():
    row = _row(element="", description="Reinforced concrete footing")
    result = _result([row], [_line()])["rows"][0]
    assert result["match_class"] == "suggested"
    assert result["mapping_decision"] == "suggestion pending confirmation"
    assert result["status"] == "Check"
    assert "confirm" in " ".join(result["reasons"]).lower()


def test_ambiguous_description_candidates_are_not_compared():
    lines = [_line(item_no="01", mark="F1", desc="Reinforced concrete footing ground floor"),
             _line(item_no="02", mark="F2", desc="Reinforced concrete footing ground floor")]
    row = _row(element="", description="Reinforced concrete footing ground floor")
    result = _result([row], lines)["rows"][0]
    assert result["match_class"] == "ambiguous"
    assert result["flag"] == "AMBIGUOUS_MATCH"
    assert result["drawing_quantity"] is None and result["candidate_items"]
    assert result["candidate_refs"][0]["qids"]


def test_duplicate_boq_codes_are_flagged_even_when_element_ids_match():
    rows = [_row(row=8, source_row=8, item_no="A-1"), _row(row=9, source_row=9, item_no="A.1")]
    result = _result(rows, [_line()])["rows"]
    assert all("DUPLICATE_BOQ_CODE" in r["flags"] for r in result)
    assert all(r["status"] == "Review Required" for r in result)
    queue = build_queue([], {"rows": result, "boq": {}}, {}, {})
    assert len([i for i in queue if i["code"] == "DUPLICATE_BOQ_CODE"]) == 2


def test_reused_display_codes_are_not_assumed_to_be_duplicates():
    rows = [_row(row=8, source_row=8, item_no="1", description="Footing concrete"),
            _row(row=9, source_row=9, item_no="1", description="Beam concrete")]
    result = _result(rows, [_line()])["rows"]
    assert all("REUSED_BOQ_CODE" in r["flags"] for r in result)
    assert all("DUPLICATE_BOQ_CODE" not in r["flags"] for r in result)
    assert all(r["status"] == "Review Required" for r in result)


def test_duplicate_detection_scopes_codes_to_supplied_section():
    rows = [_row(row=8, source_row=8, item_no="1", section="Footings"),
            _row(row=9, source_row=9, item_no="1", section="Beams")]
    result = _result(rows, [_line()])["rows"]
    assert all("DUPLICATE_BOQ_CODE" not in r["flags"] for r in result)
    assert all("DUPLICATE_DRAWING_MAPPING" in r["flags"] for r in result)
    assert all(r["status"] == "Review Required" for r in result)


def test_incompatible_and_blank_units_are_not_compared():
    incompatible = _result([_row(unit="m2")], [_line()])["rows"][0]
    assert incompatible["flag"] == "UNIT_MISMATCH"
    assert incompatible["variance"] is None and incompatible["variance_pct"] is None
    blank = _result([_row(unit="")], [_line()])["rows"][0]
    assert blank["flag"] == "BOQ_UNIT_MISSING" and blank["variance"] is None


def test_missing_quantity_zero_baseline_and_safe_variance():
    missing = _result([_row(quantity=None)], [_line()])["rows"][0]
    assert missing["flag"] == "BOQ_QTY_MISSING" and missing["variance_pct"] is None
    zero = _result([_row(quantity=0)], [_line()])["rows"][0]
    assert zero["flag"] == "BOQ_QTY_ZERO" and zero["variance"] == pytest.approx(3.6)
    assert zero["absolute_variance"] == pytest.approx(3.6) and zero["variance_pct"] is None
    assert variance(1.0, 0.0) == (1.0, None, "BOQ quantity is zero - percentage undefined")
    signed, percent, note = variance(3.6, 4.0)
    assert signed == pytest.approx(-0.4) and percent == pytest.approx(-10.0) and note == ""


def test_import_retains_source_row_original_values_and_sheet(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text("Code,Description,Element,Unit,Qty\nA-01,RC footing,F3,m3,1.234\n", encoding="utf-8")
    rows, _ = import_rows(str(path), {"item_no": 0, "description": 1, "element": 2, "unit": 3, "quantity": 4}, 0)
    assert rows[0]["source_row"] == rows[0]["row"] == 2
    assert rows[0]["source_sheet"] == "CSV"
    assert rows[0]["source_item_no"] == "A-01"
    assert rows[0]["source_description"] == "RC footing"
    assert rows[0]["source_unit"] == "m3"
    assert rows[0]["source_quantity"] == "1.234"
    assert rows[0]["quantity"] == pytest.approx(1.234)


def test_xlsx_import_retains_original_cell_values_and_source_location(tmp_path):
    path = tmp_path / "source.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Priced BOQ"
    sheet.append(["Code", "Description", "Element", "Unit", "Qty"])
    sheet.append([" A-01 ", "RC footing F3", "F3", "m³", 1.234])
    workbook.save(path)

    rows, _ = import_rows(str(path), {"item_no": 0, "description": 1, "element": 2, "unit": 3, "quantity": 4}, 0,
                          "Priced BOQ")
    assert rows[0]["source_row"] == 2 and rows[0]["source_sheet"] == "Priced BOQ"
    assert rows[0]["source_item_no"] == " A-01 " and rows[0]["item_no"] == "A-01"
    assert rows[0]["source_description"] == rows[0]["description"] == "RC footing F3"
    assert rows[0]["source_unit"] == rows[0]["unit"] == "m³"
    assert rows[0]["source_quantity"] == rows[0]["quantity"] == pytest.approx(1.234)
