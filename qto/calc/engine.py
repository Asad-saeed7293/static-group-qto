"""Layer 5 - deterministic quantity calculation engine.

The ONLY place where quantities are computed. Each element type has one
function that returns QuantityRecords with:
  * the symbolic formula        e.g. "L x W x D"
  * the substituted formula     e.g. "2.600 x 2.200 x 0.450"
  * the inputs with provenance  (Measurement dicts)
  * explicit assumptions
If any required input is missing, value is None and the status is Missing Data.
No AI, no defaults, no hidden constants.
"""
from __future__ import annotations

from ..models import (Element, Measurement, QuantityRecord, ST_CHECK, ST_MISSING, ST_OK, ST_REVIEW, STATUS_ORDER)


def _r(v, dp=3):
    return None if v is None else round(v + 0.0, dp)


def _fmt(v, dp=3):
    return "?" if v is None else f"{v:.{dp}f}"


def _worst(statuses):
    order = {s: i for i, s in enumerate(STATUS_ORDER)}
    return max(statuses, key=lambda s: order.get(s, 0)) if statuses else ST_OK


def _element_status(e: Element) -> str:
    return _worst([f.status_impact for f in e.flags] or [ST_OK])


def _record(e: Element, qtype, unit, value, formula, subst, input_names, assumptions=None, notes=None, idx=1):
    inputs = {k: e.dims[k].to_dict() for k in input_names if k in e.dims}
    missing = [k for k in input_names if k not in e.dims or e.dims[k].value is None]
    evidence, seen = [], set()
    for name in input_names:
        measurement = e.dims.get(name)
        if not measurement:
            continue
        item = {"input": name, "value": measurement.value, "unit": measurement.unit,
                "source": measurement.source, "detail": measurement.detail,
                "ref": measurement.ref.to_dict() if measurement.ref else None}
        key = (item["input"], item["source"], item["detail"], repr(item["ref"]))
        if key not in seen:
            evidence.append(item)
            seen.add(key)
    for source in e.sources:
        ref = source.to_dict()
        key = ("source", ref.get("drawing_id"), ref.get("handle"), ref.get("entity_type"))
        if ref.get("drawing") and ref.get("handle") and key not in seen:
            evidence.append({"input": None, "value": None, "unit": "", "source": "Element source",
                             "detail": ref.get("note", ""), "ref": ref})
            seen.add(key)
    status = ST_MISSING if value is None else _element_status(e)
    if value is None and status != ST_MISSING:
        status = ST_MISSING
    assm = list(assumptions or [])
    for k in input_names:
        m = e.dims.get(k)
        if m and m.is_assumption:
            assm.append(f"{k} = {_fmt(m.value)} {m.unit}: {m.detail} (not yet confirmed)")
    n = list(notes or [])
    if missing:
        n.append("Not calculated - missing: " + ", ".join(missing))
    return QuantityRecord(
        qid=f"{e.uid}:{qtype}", element_uid=e.uid, element_type=e.element_type, mark=e.mark, floor=e.floor,
        drawing_id=e.drawing_id, drawing=e.drawing, layer=e.layer, quantity_type=qtype, unit=unit,
        value=_r(value, 4), formula=formula, substitution=subst, inputs=inputs, evidence=evidence,
        missing_inputs=missing, assumptions=assm,
        status=status, confidence=round(e.confidence, 2), notes=n)


def _mul(*vals):
    if any(v is None for v in vals):
        return None
    out = 1.0
    for v in vals:
        out *= v
    return out


def calc_footing(e: Element):
    A, D = e.dim("plan_area"), e.dim("depth")
    L, W = e.dim("length"), e.dim("width")
    if L is not None and W is not None and abs(L * W - (A or 0)) < 1e-6:
        vol = _mul(L, W, D)
        f, s = "L x W x D", f"{_fmt(L)} x {_fmt(W)} x {_fmt(D)}"
        ins = ["length", "width", "depth"]
    else:
        vol = _mul(A, D)
        f, s = "Plan area (polygon) x D", f"{_fmt(A, 4)} x {_fmt(D)}"
        ins = ["plan_area", "depth"]
    return [_record(e, "concrete_volume", "m3", vol, f, s, ins),
            _record(e, "plan_area", "m2", A, "Polygon area (shoelace)", _fmt(A, 4), ["plan_area"])]


def calc_column(e: Element):
    A, H = e.dim("section_area"), e.dim("height")
    W, D = e.dim("width"), e.dim("depth")
    if e.attributes.get("shape") == "rectangular":
        vol = _mul(W, D, H)
        f, s, ins = "W x D x H", f"{_fmt(W)} x {_fmt(D)} x {_fmt(H)}", ["width", "depth", "height"]
    else:
        vol = _mul(A, H)
        f, s, ins = "Section area (polygon) x H", f"{_fmt(A, 4)} x {_fmt(H)}", ["section_area", "height"]
    return [_record(e, "concrete_volume", "m3", vol, f, s, ins)]


def calc_wall(e: Element):
    A, H = e.dim("plan_area"), e.dim("height")
    return [_record(e, "concrete_volume", "m3", _mul(A, H), "Plan area (polygon) x H", f"{_fmt(A, 4)} x {_fmt(H)}",
                    ["plan_area", "height"], ["Wall openings not deducted"])]


def calc_beam(e: Element):
    L, W, D, t = e.dim("length"), e.dim("width"), e.dim("depth"), e.dim("slab_deduction") or 0.0
    Dn = None if D is None else D - t
    if "plan_area" in e.dims:  # irregular outline: exact plan area x depth
        A = e.dim("plan_area")
        vol = _mul(A, Dn)
        f = "Plan area (polygon) x (D - slab t)" if t else "Plan area (polygon) x D"
        s = f"{_fmt(A, 4)} x ({_fmt(D)} - {_fmt(t)})" if t else f"{_fmt(A, 4)} x {_fmt(D)}"
        return [_record(e, "concrete_volume", "m3", vol, f, s, ["plan_area", "depth", "slab_deduction"],
                        [f"Slab thickness {t:.3f} m deducted from beam depth"] if t else [])]
    vol = _mul(L, W, Dn)
    if t:
        f, s = "L x W x (D - slab t)", f"{_fmt(L)} x {_fmt(W)} x ({_fmt(D)} - {_fmt(t)})"
    else:
        f, s = "L x W x D", f"{_fmt(L)} x {_fmt(W)} x {_fmt(D)}"
    assm = []
    if t:
        assm.append(f"Slab thickness {t:.3f} m deducted from beam depth - that concrete is measured in the slab")
    return [_record(e, "concrete_volume", "m3", vol, f, s, ["length", "width", "depth", "slab_deduction"], assm)]


def calc_slab(e: Element):
    A, T = e.dim("net_area"), e.dim("thickness")
    return [_record(e, "concrete_volume", "m3", _mul(A, T), "Net area (zone polygon - openings) x thickness",
                    f"{_fmt(A, 4)} x {_fmt(T)}", ["gross_area", "openings_area", "net_area", "thickness"],
                    ["Slab measured over beams (beam volume is taken below the slab)"]),
            _record(e, "plan_area", "m2", A, "Zone polygon area - openings",
                    f"{_fmt(e.dim('gross_area'), 4)} - {_fmt(e.dim('openings_area'), 4)}", ["gross_area", "openings_area", "net_area"])]


def calc_pedestal(e: Element):
    L, W, H = e.dim("length"), e.dim("width"), e.dim("height")
    return [_record(e, "concrete_volume", "m3", _mul(L, W, H), "L x W x H", f"{_fmt(L)} x {_fmt(W)} x {_fmt(H)}",
                    ["length", "width", "height"])]


def calc_blinding(e: Element):
    A, T = e.dim("plan_area"), e.dim("thickness")
    return [_record(e, "blinding_volume", "m3", _mul(A, T), "Plan area (polygon) x blinding thickness",
                    f"{_fmt(A, 4)} x {_fmt(T)}", ["plan_area", "thickness"]),
            _record(e, "plan_area", "m2", A, "Polygon area (shoelace)", _fmt(A, 4), ["plan_area"])]


CALCULATORS = {
    "footing": calc_footing, "raft": calc_footing, "column": calc_column, "wall": calc_wall,
    "beam": calc_beam, "slab": calc_slab, "pedestal": calc_pedestal, "blinding": calc_blinding,
}


def calculate(elements: list) -> list:
    out = []
    for e in elements:
        fn = CALCULATORS.get(e.element_type)
        if fn:
            out.extend(fn(e))
    return out
