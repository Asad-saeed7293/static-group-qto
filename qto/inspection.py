"""Phase-1 inspection report: what is actually inside the drawing set."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

ID_RE = re.compile(r"^(P?C\d+|C?F\d+|W\d+|(L1B|PHB|TORB|GRB)\d+(-\d+)?|T\.B\d+|B\d+X\d+)$")


def inspection_summary(data: dict) -> dict:
    drawings = data["drawings"]
    disc = defaultdict(lambda: {"files": 0, "entities": 0, "types": Counter(), "layers": Counter()})
    units = Counter()
    versions = Counter()
    blocks = Counter()
    ids = Counter()
    per_file = []
    for d in drawings:
        inv = d.get("inventory") or {}
        m = d.get("meta") or {}
        g = disc[d["discipline"]]
        g["files"] += 1
        g["entities"] += m.get("modelspace_entities") or 0
        g["types"].update(inv.get("entity_types", {}))
        g["layers"].update(inv.get("layers_used", {}))
        units[m.get("units")] += 1
        versions[m.get("acad_release")] += 1
        blocks.update(inv.get("blocks_inserted", {}))
        for t in inv.get("text_sample", []):
            if ID_RE.match(t.strip()):
                ids[re.sub(r"\d+.*", "#", t.strip())] += 1
        per_file.append({"file": d["file"], "discipline": d["discipline"], "role": d.get("role_title"), "units": m.get("units"),
                         "entities": m.get("modelspace_entities"), "layers": len(inv.get("layers_used", {})),
                         "top_types": dict(list((inv.get("entity_types") or {}).items())[:6]),
                         "top_layers": dict(list((inv.get("layers_used") or {}).items())[:8]),
                         "layouts": m.get("layouts"), "rule_hits": None})
    res = data["results"]
    design = res["design"]
    findings = {
        "Footings": f"{sum(1 for e in res['elements'] if e['element_type'] == 'footing')} outlines on S-FNDN-FTNG (S-FP); thickness from footing schedule tables in S-FD ({len(design['footing_schedule'])} rows).",
        "Rafts": f"{sum(1 for e in res['elements'] if e['element_type'] == 'raft')} raft outlines identified by 'Iden-Slab Thickness' tag SLAB_TYPE=RAFT.",
        "Columns": f"Outlines in bound xrefs X-CO-<floor> (layer X-CO-COLS-OTLN) on S-CP-BS/GR/L1/PH, tagged C#/PC# on S-COLS-ANNO-TEXT; schedule grid on S-CD ({len(design['column_schedule'])} cells).",
        "Walls": "RC walls on X-CO-WALL-RCNC inside the same xrefs, tagged W1/W2.",
        "Beams": f"Closed rectangles on S-FRAM-BEAM-HIDD in S-FR-*; marks/size labels on S-FRAM-BEAM-ATXT; beam schedule ACAD_TABLEs on S-BD01 ({len(design['beam_schedule'])} rows); tie-beam depths from S-FD section details.",
        "Slabs": "No closed slab polygons. Boundary linework X-LOS-SLAB-BNDY (bound xref X-LOS-<floor>), shafts X-LOS-SLAB-SHAFT, thickness/type via 'Iden-Slab Thickness' attributes.",
        "Levels": "'Iden-Level Plan' block attributes (T.O.S / T.O.F) on framing and foundation plans.",
        "Grid lines": "Bound xref 'X-AXIS' (C-PROP-LINE lines + grid bubbles).",
        "Dimensions": "DIMENSION entities exist (A-AXIS$0$S-ANNO-DIMS-ITNL, S-ANNO-DIMS-GNRL) and are used to cross-check schedule sections and tie-beam depths.",
        "Units": "All structural files: $INSUNITS=6 (metres). One electrical file (E-102) declares millimetres.",
    }
    return {
        "files": len(drawings), "by_discipline": {k: {"files": v["files"], "entities": v["entities"],
                                                       "types": dict(v["types"].most_common(10)),
                                                       "layers": dict(v["layers"].most_common(25)),
                                                       "layer_count": len(v["layers"])} for k, v in disc.items()},
        "units": dict(units), "dxf_versions": dict(versions), "top_blocks": dict(blocks.most_common(30)),
        "id_patterns": dict(ids.most_common()), "structural_findings": findings, "per_file": per_file,
    }
