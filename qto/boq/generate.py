"""Layer 6 - generate a BOQ from calculated quantities.

One BOQ line per (element type, mark, floor). Each line keeps the list of
element instances and quantity records behind it, so every BOQ number can be
traced back to CAD entities.
"""
from __future__ import annotations

import re
from collections import OrderedDict

from ..models import ST_MISSING, ST_OK, STATUS_ORDER

SECTIONS = OrderedDict([
    ("blinding", ("01", "Substructure - Blinding concrete", "Plain concrete blinding under footings and raft")),
    ("footing", ("02", "Substructure - Footings", "Reinforced concrete in footing")),
    ("raft", ("03", "Substructure - Raft", "Reinforced concrete in raft foundation")),
    ("tie_beam", ("04", "Substructure - Tie beams", "Reinforced concrete in tie beam")),
    ("pedestal", ("05", "Substructure - Pedestals", "Reinforced concrete in pedestal")),
    ("wall", ("06", "Superstructure - RC walls", "Reinforced concrete in wall")),
    ("column", ("07", "Superstructure - Columns", "Reinforced concrete in column")),
    ("beam", ("08", "Superstructure - Beams", "Reinforced concrete in beam")),
    ("slab", ("09", "Superstructure - Slabs", "Reinforced concrete in slab")),
])
FLOOR_NAMES = {"FDN": "Foundation", "BS": "Basement", "GR": "Ground floor", "L1": "First floor", "PH": "Penthouse", "TOR": "Roof"}
FLOOR_ORDER = ["FDN", "BS", "GR", "L1", "PH", "TOR"]


def norm_mark(m: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (m or "").upper())


def section_of(e: dict) -> str:
    if e["element_type"] == "beam" and (e.get("attributes", {}).get("beam_mark") or "").startswith("T.B"):
        return "tie_beam"
    return e["element_type"]


def _worst(statuses):
    order = {s: i for i, s in enumerate(STATUS_ORDER)}
    return max(statuses, key=lambda s: order.get(s, 0)) if statuses else ST_OK


def generate_boq(elements: list, quantities: list) -> list:
    """elements/quantities as dicts. Returns BOQ lines (dicts)."""
    el = {e["uid"]: e for e in elements}
    vol = [q for q in quantities if q["quantity_type"] in ("concrete_volume", "blinding_volume")]
    groups = OrderedDict()
    for q in vol:
        e = el[q["element_uid"]]
        sec = section_of(e)
        mark = e["mark"] or ""
        key_mark = mark if mark else e["uid"]  # unidentified elements are never merged
        k = (sec, key_mark, e["floor"])
        groups.setdefault(k, []).append((e, q))

    lines = []
    for sec in SECTIONS:
        keys = [k for k in groups if k[0] == sec]
        keys.sort(key=lambda k: (FLOOR_ORDER.index(k[2]) if k[2] in FLOOR_ORDER else 9, _natural(k[1])))
        num, title, desc_base = SECTIONS[sec]
        for n, k in enumerate(keys, start=1):
            items = groups[k]
            e0 = items[0][0]
            vals = [q["value"] for _, q in items]
            avail = [v for v in vals if v is not None]
            missing = len(vals) - len(avail)
            statuses = [q["status"] for _, q in items]
            identified = bool(e0["mark"])
            mark = e0["mark"] if identified else ""
            desc = f"{desc_base} {mark}".strip() if identified else f"{desc_base} - UNIDENTIFIED ({e0['uid']})"
            dims = _uniform_dims(items)
            if dims:
                desc += f" ({dims})"
            if e0["element_type"] == "slab":
                desc = f"{desc_base}: {e0['description']}"
            desc += f" - {FLOOR_NAMES.get(k[2], k[2])}"
            line = {
                "item_no": f"{num}.{n:02d}",
                "section": num,
                "category": title,
                "description": desc,
                "element_type": e0["element_type"],
                "element_id": mark,
                "floor": k[2],
                "floor_name": FLOOR_NAMES.get(k[2], k[2]),
                "unit": "m3",
                "count": len(items),
                "count_missing": missing,
                "quantity": round(sum(avail), 3) if avail else None,
                "status": _worst(statuses) if not missing else ST_MISSING,
                "drawings": sorted({e["drawing"] for e, _ in items}),
                "layers": sorted({e["layer"] for e, _ in items}),
                "element_uids": [e["uid"] for e, _ in items],
                "qids": [q["qid"] for _, q in items],
                "calculation_evidence": [{"qid": q["qid"], "formula": q["formula"], "substitution": q["substitution"],
                                          "inputs": q.get("inputs", {}), "evidence": q.get("evidence", [])}
                                         for _, q in items],
                "formula": items[0][1]["formula"],
                "match_key": f"{norm_mark(mark) if identified else e0['uid']}@{k[2]}",
                "mark_norm": norm_mark(mark) if identified else "",
                "confidence": round(min(q["confidence"] for _, q in items), 2),
                "notes": ([f"{missing} of {len(items)} instance(s) could not be quantified (missing data)"] if missing else []),
            }
            if missing and avail:
                line["notes"].append("Quantity shown is the sum of the instances that could be quantified")
            lines.append(line)
    return lines


def _uniform_dims(items):
    e = items[0][0]
    t = e["element_type"]
    d = {k: v.get("value") for k, v in e["dims"].items()}
    def same(*names):
        return all(all(abs((x[0]["dims"].get(nm, {}).get("value") or -1) - (d.get(nm) or -1)) < 1e-6 for x in items) for nm in names)
    mm = lambda v: f"{v * 1000:.0f}"
    if t in ("footing",) and d.get("width") and d.get("length") and d.get("depth") and same("width", "length", "depth"):
        return f"{mm(d['width'])}x{mm(d['length'])}x{mm(d['depth'])} mm"
    if t == "column" and d.get("width") and d.get("depth") and same("width", "depth"):
        return f"{mm(d['width'])}x{mm(d['depth'])} mm"
    if t == "beam" and d.get("width") and d.get("depth") and same("width", "depth"):
        return f"{mm(d['width'])}x{mm(d['depth'])} mm"
    if t == "pedestal" and d.get("length") and d.get("width") and d.get("height"):
        return f"{mm(d['length'])}x{mm(d['width'])}x{mm(d['height'])} mm"
    if t == "blinding" and d.get("thickness"):
        return f"{mm(d['thickness'])} mm thick"
    return ""


def _natural(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s or "")]
