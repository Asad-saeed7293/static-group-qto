"""Validation of calculated quantity inputs and their drawing evidence."""
from __future__ import annotations

import math
from collections import defaultdict

from ..models import Flag, ST_MISSING, ST_REVIEW, ST_CHECK

_LENGTH_INPUTS = {"length", "width", "depth", "height", "thickness", "slab_deduction", "width_drawn"}
_AREA_INPUTS = {"plan_area", "section_area", "gross_area", "openings_area", "net_area"}
_ZERO_ALLOWED = {"slab_deduction", "openings_area"}
_GEOMETRY_TYPES = {"LWPOLYLINE", "POLYLINE", "LINE", "CIRCLE", "ARC", "ELLIPSE"}
_EXPECTED_UNITS = {**{name: "m" for name in _LENGTH_INPUTS},
                   **{name: "m2" for name in _AREA_INPUTS}}
_QUANTITY_UNITS = {"plan_area": "m2", "concrete_volume": "m3", "blinding_volume": "m3"}
_UNIT_ALIASES = {"m": "m", "metre": "m", "meter": "m", "m2": "m2", "m²": "m2",
                 "sqm": "m2", "square metre": "m2", "square meter": "m2",
                 "m3": "m3", "m³": "m3", "cum": "m3", "cu.m": "m3"}


def _unit(value):
    return _UNIT_ALIASES.get(str(value or "").strip().lower())


def validate_calculations(elements: list, quantities: list) -> list:
    """Flag invalid/incomplete calculations and untraceable or duplicated geometry evidence.

    Invalid dimensions and units invalidate the affected quantity. Evidence and duplicate
    findings retain the calculated value but lower its status so it cannot appear verified.
    """
    by_uid = {e.uid: e for e in elements}
    issues, seen_issues = [], set()

    def add_issue(element, quantity, code, title, detail, impact):
        key = (element.uid, code)
        if key in seen_issues:
            return
        seen_issues.add(key)
        element.flags.append(Flag(code, title, detail, "error" if impact == ST_MISSING else "warning", impact))
        issues.append({"id": f"{element.uid}:{code}", "code": code, "title": title, "detail": detail,
                       "element_uid": element.uid, "quantity_id": quantity.qid if quantity else None,
                       "drawing": element.drawing, "drawing_id": element.drawing_id,
                       "element_type": element.element_type, "mark": element.mark})

    for quantity in quantities:
        element = by_uid.get(quantity.element_uid)
        if element is None:
            continue
        invalid = False
        expected_output = _QUANTITY_UNITS.get(quantity.quantity_type)
        if expected_output and _unit(quantity.unit) != expected_output:
            add_issue(element, quantity, "UNSUPPORTED_QUANTITY_UNIT", "Unsupported quantity output unit",
                      f"{quantity.qid}: output unit '{quantity.unit}' is unsupported; expected '{expected_output}'. "
                      "No implicit unit conversion is applied.", ST_MISSING)
            invalid = True
        for name, measurement in quantity.inputs.items():
            expected = _EXPECTED_UNITS.get(name)
            if expected and _unit(measurement.get("unit")) != expected:
                add_issue(element, quantity, "UNSUPPORTED_QUANTITY_UNIT", "Unsupported calculation input unit",
                          f"{quantity.qid}: input '{name}' uses unit '{measurement.get('unit')}', expected '{expected}'. "
                          "No implicit unit conversion is applied.", ST_MISSING)
                invalid = True
            value = measurement.get("value")
            if value is not None:
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    numeric = math.nan
                if not math.isfinite(numeric) or (numeric < 0 if name in _ZERO_ALLOWED else numeric <= 0):
                    add_issue(element, quantity, "INVALID_CALCULATION_DIMENSION", "Invalid calculation dimension",
                              f"{quantity.qid}: input '{name}' has invalid value {value!r} {measurement.get('unit')}; "
                              "lengths and areas must be positive (except non-negative openings and slab deductions).",
                              ST_MISSING)
                    invalid = True
        if quantity.missing_inputs and quantity.value is None:
            add_issue(element, quantity, "INCOMPLETE_CALCULATION", "Quantity could not be calculated",
                      f"{quantity.qid}: required input(s) unavailable: {', '.join(quantity.missing_inputs)}.",
                      ST_MISSING)
        if quantity.value is not None and (not math.isfinite(quantity.value) or quantity.value <= 0):
            add_issue(element, quantity, "INVALID_CALCULATION_RESULT", "Invalid calculated quantity",
                      f"{quantity.qid}: calculated value {quantity.value!r} {quantity.unit} is not positive and finite.",
                      ST_MISSING)
            invalid = True
        if invalid:
            quantity.value = None
            quantity.status = ST_MISSING
            quantity.notes.append("Not calculated - invalid dimension or unsupported unit; see the review queue.")

        if quantity.value is not None:
            usable_refs = [ev.get("ref") for ev in quantity.evidence
                           if ev.get("ref") and ev["ref"].get("drawing") and ev["ref"].get("handle")]
            if not usable_refs:
                add_issue(element, quantity, "MISSING_CALCULATION_EVIDENCE", "Calculation source evidence missing",
                          f"{quantity.qid}: no source drawing/entity handle is available for its calculation inputs.",
                          ST_REVIEW)
                if quantity.status not in (ST_MISSING,):
                    quantity.status = ST_REVIEW

    # A geometry entity should not define two distinct structural elements in the same run.
    references = defaultdict(list)
    for element in elements:
        for source in element.sources:
            if source.entity_type.upper() not in _GEOMETRY_TYPES or not source.handle:
                continue
            references[(source.drawing_id, source.handle)].append(element)
    for (drawing_id, handle), owners in references.items():
        distinct = {e.uid: e for e in owners}
        if len(distinct) < 2:
            continue
        names = ", ".join(sorted(e.uid for e in distinct.values()))
        for element in distinct.values():
            related = next((q for q in quantities if q.element_uid == element.uid and q.value is not None), None)
            add_issue(element, related, "DUPLICATE_SOURCE_ENTITY", "Source entity used by multiple elements",
                      f"Drawing entity {handle} in {element.drawing} is referenced by multiple elements: {names}. "
                      "Check for duplicate counting before accepting these quantities.", ST_CHECK)
            for quantity in quantities:
                if quantity.element_uid == element.uid and quantity.value is not None and quantity.status not in (ST_MISSING, ST_REVIEW):
                    quantity.status = ST_CHECK
    return issues
