"""Unit tests for the deterministic layers: geometry, calculation, variance, comparison, import, tables."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qto.boq.compare import compare, match_rows, norm_unit, parse_floor, tolerance_status, variance  # noqa: E402
from qto.boq.generate import generate_boq  # noqa: E402
from qto.boq.importer import detect_header, suggest_mapping  # noqa: E402
from qto.calc.engine import calculate  # noqa: E402
from qto.calc.validation import validate_calculations  # noqa: E402
from qto.extract.schedules import parse_level  # noqa: E402
from qto.extract.tables import _cluster, parse_mm, table_to_records  # noqa: E402
from qto.geometry import rectangle_dims, same_ring, shoelace_area, simplify_ring  # noqa: E402
from qto.models import Element, Flag, Measurement, SourceRef, ST_CHECK, ST_MISSING, ST_REVIEW  # noqa: E402
from qto.review.queue import build_queue  # noqa: E402

SETTINGS = {"tolerances": [{"max_abs_pct": 2.0, "status": "OK"}, {"max_abs_pct": 5.0, "status": "Check"}],
            "tolerance_above_status": "Review Required", "verified_requires_cross_checks": True}


# --- geometry -------------------------------------------------------------------
def test_shoelace_rectangle_and_closing_vertex():
    sq = [(0, 0), (2, 0), (2, 1.5), (0, 1.5), (0, 0)]
    assert shoelace_area(sq) == pytest.approx(3.0)


def test_shoelace_irregular_l_shape():
    l_shape = [(0, 0), (4, 0), (4, 1), (1, 1), (1, 3), (0, 3)]
    assert shoelace_area(l_shape) == pytest.approx(4 + 2)


def test_rectangle_dims_rotated():
    import math
    a = math.radians(30)
    L, W = 5.2, 0.3
    pts = [(0, 0), (L * math.cos(a), L * math.sin(a)),
           (L * math.cos(a) - W * math.sin(a), L * math.sin(a) + W * math.cos(a)), (-W * math.sin(a), W * math.cos(a))]
    r = rectangle_dims(pts)
    assert r["long"] == pytest.approx(5.2) and r["short"] == pytest.approx(0.3) and r["angle_deg"] == pytest.approx(30)


def test_rectangle_dims_rejects_irregular_and_ignores_collinear_points():
    assert rectangle_dims([(0, 0), (4, 0), (4, 1), (1, 1), (1, 3), (0, 3)]) is None
    assert rectangle_dims([(0, 0), (1, 0), (2, 0), (2, 1), (0, 1)])["long"] == pytest.approx(2)
    assert len(simplify_ring([(0, 0), (1, 0), (2, 0), (2, 1), (0, 1)])) == 4


def test_same_ring_detects_duplicates_regardless_of_start():
    a = [(0, 0), (1, 0), (1, 1), (0, 1)]
    b = [(1, 1), (0, 1), (0, 0), (1, 0)]
    assert same_ring(a, b) and not same_ring(a, [(0, 0), (1.1, 0), (1.1, 1), (0, 1)])


# --- calculation engine -------------------------------------------------------------
def _footing(L, W, D):
    e = Element(uid="FTG-F3-01", element_type="footing", mark="F3", floor="FDN")
    e.dims = {"plan_area": Measurement("plan_area", L * W, "m2"), "length": Measurement("length", L),
              "width": Measurement("width", W), "depth": Measurement("depth", D)}
    return e


def test_footing_volume_example_from_brief():
    q = calculate([_footing(2.0, 2.0, 0.45)])[0]
    assert q.value == pytest.approx(1.80) and q.formula == "L x W x D" and q.substitution == "2.000 x 2.000 x 0.450"


def test_missing_thickness_gives_no_volume_and_missing_status():
    e = _footing(2.0, 2.0, None)
    e.flags.append(Flag("MISSING_THICKNESS", "x", "y", status_impact=ST_MISSING))
    q = calculate([e])[0]
    assert q.value is None and q.status == ST_MISSING and "depth" in q.notes[0]


def test_beam_slab_deduction_and_brief_example():
    e = Element(uid="B", element_type="beam", mark="B12")
    e.dims = {"length": Measurement("length", 5.2), "width": Measurement("width", 0.3), "depth": Measurement("depth", 0.6),
              "slab_deduction": Measurement("slab_deduction", 0.0)}
    assert calculate([e])[0].value == pytest.approx(0.936)
    e.dims["slab_deduction"] = Measurement("slab_deduction", 0.25)
    q = calculate([e])[0]
    assert q.value == pytest.approx(5.2 * 0.3 * 0.35) and "slab t" in q.formula


def test_column_height_assumption_is_listed():
    e = Element(uid="C", element_type="column", mark="C1", attributes={"shape": "rectangular"})
    e.dims = {"width": Measurement("width", 0.3), "depth": Measurement("depth", 0.6), "section_area": Measurement("section_area", 0.18),
              "height": Measurement("height", 3.5, detail="levels", is_assumption=True)}
    e.flags.append(Flag("HEIGHT_DERIVED", "t", "d", status_impact=ST_CHECK))
    q = calculate([e])[0]
    assert q.value == pytest.approx(0.63) and q.status == ST_CHECK and q.assumptions


def test_slab_volume_uses_net_polygon_area():
    e = Element(uid="S", element_type="slab", mark="GR-S01")
    e.dims = {"gross_area": Measurement("gross_area", 100.0), "openings_area": Measurement("openings_area", 10.0),
              "net_area": Measurement("net_area", 90.0), "thickness": Measurement("thickness", 0.25)}
    assert calculate([e])[0].value == pytest.approx(22.5)


def _evidenced_footing(uid="FTG-F3-01", handle="A1"):
    e = _footing(2.0, 2.0, 0.45)
    e.uid = uid
    ref = SourceRef("D1", "S-FP.dxf", layer="S-FTG", entity_type="LWPOLYLINE", handle=handle)
    e.sources = [ref]
    for measurement in e.dims.values():
        measurement.ref = ref
    return e


def test_quantity_retains_formula_input_and_entity_evidence():
    e = _evidenced_footing()
    q = calculate([e])[0]
    assert q.value == pytest.approx(1.8)
    assert q.missing_inputs == []
    assert any(ev["ref"] and ev["ref"]["handle"] == "A1" for ev in q.evidence)
    assert q.inputs["depth"]["ref"]["drawing"] == "S-FP.dxf"
    assert validate_calculations([e], [q]) == []


def test_missing_quantity_evidence_enters_review_queue():
    e = _footing(2.0, 2.0, 0.45)
    q = calculate([e])[0]
    issues = validate_calculations([e], [q])
    assert any(i["code"] == "MISSING_CALCULATION_EVIDENCE" for i in issues)
    assert q.status == ST_REVIEW
    queue = build_queue([e.to_dict()], None, {}, {})
    assert any(i["code"] == "MISSING_CALCULATION_EVIDENCE" for i in queue)


@pytest.mark.parametrize("field,value,unit,expected_code", [
    ("depth", -0.45, "m", "INVALID_CALCULATION_DIMENSION"),
    ("depth", 0.45, "mm", "UNSUPPORTED_QUANTITY_UNIT"),
])
def test_invalid_dimension_or_unit_invalidates_quantity(field, value, unit, expected_code):
    e = _evidenced_footing()
    e.dims[field].value = value
    e.dims[field].unit = unit
    q = calculate([e])[0]
    issues = validate_calculations([e], [q])
    assert any(i["code"] == expected_code for i in issues)
    assert q.value is None and q.status == ST_MISSING


def test_unsupported_quantity_output_unit_invalidates_quantity():
    e = _evidenced_footing()
    q = calculate([e])[0]
    q.unit = "ft3"
    issues = validate_calculations([e], [q])
    assert any(i["code"] == "UNSUPPORTED_QUANTITY_UNIT" for i in issues)
    assert q.value is None and q.status == ST_MISSING


def test_missing_formula_input_is_recorded_as_incomplete():
    e = _evidenced_footing()
    del e.dims["depth"]
    q = calculate([e])[0]
    assert "depth" in q.missing_inputs
    issues = validate_calculations([e], [q])
    assert any(i["code"] == "INCOMPLETE_CALCULATION" for i in issues)
    assert q.value is None


def test_duplicate_geometry_handle_is_flagged_for_each_element():
    first = _evidenced_footing("FTG-F3-01", "A1")
    second = _evidenced_footing("FTG-F3-02", "A1")
    quantities = calculate([first, second])
    issues = validate_calculations([first, second], quantities)
    assert len([i for i in issues if i["code"] == "DUPLICATE_SOURCE_ENTITY"]) == 2
    assert all(q.status == ST_CHECK for q in quantities)


# --- variance & tolerance ----------------------------------------------------------
def test_variance_brief_example():
    v, p, _ = variance(0.936, 1.020)
    assert v == pytest.approx(-0.084) and p == pytest.approx(-8.235, abs=1e-3)
    assert tolerance_status(p, SETTINGS) == "Review Required"


def test_variance_zero_and_missing_boq_are_safe():
    assert variance(1.0, 0.0)[1] is None
    assert variance(1.0, None)[0] is None
    assert variance(None, 1.0)[0] is None


@pytest.mark.parametrize("p,exp", [(0, "OK"), (2.0, "OK"), (-2.01, "Check"), (5.0, "Check"), (5.01, "Review Required")])
def test_tolerance_bands_are_configurable(p, exp):
    assert tolerance_status(p, SETTINGS) == exp
    strict = dict(SETTINGS, tolerances=[{"max_abs_pct": 0.5, "status": "OK"}])
    assert tolerance_status(1.0, strict) == "Review Required"


def test_units_and_floors():
    assert norm_unit("cu.m") == "m3" and norm_unit("M³") == "m3" and norm_unit("sqm") == "m2" and norm_unit("") is None
    assert parse_floor("Ground Floor") == "GR" and parse_floor("first floor slab") == "L1" and parse_floor("") is None


# --- BOQ generation + comparison ---------------------------------------------------------
def _elements_and_quantities():
    f1, f2 = _footing(2.0, 2.0, 0.45), _footing(2.0, 2.0, 0.45)
    f2.uid = "FTG-F3-02"
    for e in (f1, f2):
        e.drawing = "S-FP.dxf"
        e.cross_checks = []
    bl = Element(uid="BLD-1", element_type="blinding", mark="BL-F3", floor="FDN", drawing="S-FP.dxf")
    bl.dims = {"plan_area": Measurement("plan_area", 4.84), "thickness": Measurement("thickness", 0.1)}
    els = [f1, f2, bl]
    qs = calculate(els)
    return [e.to_dict() for e in els], [q.to_dict() for q in qs]


def test_generate_boq_groups_instances_by_mark():
    els, qs = _elements_and_quantities()
    lines = generate_boq(els, qs)
    f3 = next(l for l in lines if l["element_id"] == "F3")
    assert f3["count"] == 2 and f3["quantity"] == pytest.approx(3.6) and f3["unit"] == "m3"


def test_compare_statuses_and_unmatched_items():
    els, qs = _elements_and_quantities()
    lines = generate_boq(els, qs)
    by_uid = {e["uid"]: e for e in els}
    boq = [{"row": 5, "item_no": "1", "description": "Concrete in footing F3", "element": "F3", "floor": "", "unit": "m3", "quantity": 3.6},
           {"row": 6, "item_no": "2", "description": "Lift pit", "element": "LP1", "floor": "", "unit": "m3", "quantity": 2.0}]
    res = compare(boq, lines, by_uid, SETTINGS)["rows"]
    assert res[0]["status"] in ("OK", "Verified") and res[0]["variance"] == pytest.approx(0)
    assert res[1]["flag"] == "BOQ_ITEM_NOT_IN_DRAWINGS"
    assert any(r.get("flag") == "DRAWING_ITEM_NOT_IN_BOQ" for r in res)  # the blinding line


def test_compare_unit_mismatch_and_zero_quantity():
    els, qs = _elements_and_quantities()
    lines = generate_boq(els, qs)
    res = compare([{"row": 1, "item_no": "1", "description": "footing", "element": "F3", "floor": "", "unit": "m2", "quantity": 3.6},
                   {"row": 2, "item_no": "2", "description": "blinding", "element": "BL-F3", "floor": "", "unit": "m3", "quantity": 0}],
                  lines, {e["uid"]: e for e in els}, SETTINGS)["rows"]
    assert res[0]["flag"] == "UNIT_MISMATCH" and res[1]["flag"] == "BOQ_QTY_ZERO" and res[1]["variance_pct"] is None


def test_match_rows_disambiguates_type_by_description():
    lines = [{"mark_norm": "X1", "element_type": "footing", "floor": "FDN"}, {"mark_norm": "X1", "element_type": "blinding", "floor": "FDN"}]
    (_, idx, method), = match_rows([{"element": "X1", "description": "Plain concrete blinding", "floor": ""}], lines)
    assert idx == [1] and "type" in method


# --- import + tables --------------------------------------------------------------------
def test_import_header_detection_and_mapping():
    rows = [["TEST BOQ title"], [], ["Ref", "Item Description", "Element Mark", "UoM", "Qty"], ["1", "x", "F1", "m3", 1]]
    h = detect_header(rows)
    assert h == 2
    m = suggest_mapping(rows[h])
    assert m == {"item_no": 0, "description": 1, "element": 2, "unit": 3, "quantity": 4}


def test_table_decoding_handles_column_positions():
    t = {"char_height": 0.05, "rows": [
        [{"text": "FOOTING NO.", "x": 0}], [{"text": "W (mm)", "x": 1}, {"text": "L (mm)", "x": 2}, {"text": "D (mm)", "x": 3}],
        [{"text": "F1", "x": 0}, {"text": "700", "x": 1}, {"text": "1500", "x": 2}, {"text": "400", "x": 3}, {"text": "-", "x": 4}]]}
    rec = table_to_records(t, {"columns": {"mark": 0, "w_mm": 1, "l_mm": 2, "d_mm": 3}})[0]
    assert rec["mark"] == "F1" and parse_mm(rec["w_mm"]) == 0.7 and parse_mm("REFER TO FR. PLAN") is None
    assert _cluster([1.0, 1.01, 2.0], 0.05) == pytest.approx([1.005, 2.0])


def test_level_parsing():
    assert parse_level("+4.85") == 4.85 and parse_level("-3.25") == -3.25 and parse_level("AS PER ARCH") is None
    assert parse_level("%%P0.00") == 0.0
