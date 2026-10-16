"""Layer 3 - configurable classification.

Turns flattened DXF entities into *candidates* (footing outlines, column tags,
slab thickness tags, ...) using the project rules file. The rules decide; this
module only applies them. Anything in a recognised drawing that matches no rule
is counted so that unknown layers are visible in the inspection report.
"""
from __future__ import annotations

import fnmatch
import re
from collections import Counter, defaultdict

from ..geometry import bbox, clean_ring, shoelace_area


def detect_discipline(rel_path: str, rules: dict) -> str:
    for d in rules.get("disciplines", []):
        if re.search(d["folder_regex"], rel_path):
            return d["discipline"]
    return "Unclassified"


def detect_role(rel_path: str, rules: dict):
    for r in rules.get("drawing_roles", []):
        m = re.search(r["file_regex"], rel_path)
        if m:
            groups = {k: v for k, v in m.groupdict().items() if v}
            # sheet-name floor codes differ between projects (e.g. S-FR-S.O.G = ground floor framing)
            aliases = rules.get("floor_aliases", {})
            if "floor" in groups:
                groups["floor"] = aliases.get(groups["floor"].upper(), groups["floor"].upper())
            return r["role"], groups, r.get("title", r["role"])
    return None, {}, None


def _layer_match(base_layer: str, patterns) -> bool:
    bl = base_layer.upper()
    return any(fnmatch.fnmatchcase(bl, p.upper()) for p in patterns)


def classify(dwg, role: str, rules: dict) -> dict:
    """Return facts for one drawing: outlines/texts/blocks grouped by role."""
    facts = {
        "outlines": defaultdict(list),
        "texts": defaultdict(list),
        "blocks": defaultdict(list),
        "dimensions": [],
        "titles": [],
        "all_texts": [],
        "unclassified_layers": Counter(),
        "rule_hits": Counter(),
    }
    layer_rules = [r for r in rules.get("layer_roles", []) if role in r.get("drawing_roles", [role])]
    text_rules = [r for r in rules.get("text_roles", []) if role in r.get("drawing_roles", [role])]
    block_rules = rules.get("block_roles", [])

    for fe in dwg.entities:
        t = fe.dxftype
        if t in ("LWPOLYLINE", "POLYLINE", "LINE"):
            matched = False
            for r in layer_rules:
                if t not in r.get("entities", [t]):
                    continue
                if not _layer_match(fe.base_layer, r["layers"]):
                    continue
                if r.get("closed") and not fe.closed:
                    continue
                pts = clean_ring(fe.points) if fe.closed else list(fe.points)
                if (fe.closed and len(pts) < 3) or len(pts) < 2:
                    facts["rule_hits"]["degenerate_outline_skipped"] += 1  # zero-area / single-point polyline
                    matched = True
                    break
                rec = {
                    "handle": fe.handle, "layer": fe.layer, "base_layer": fe.base_layer, "block": fe.block,
                    "entity_type": t, "points": [[round(x, 5), round(y, 5)] for x, y in pts],
                    "closed": fe.closed, "has_bulge": fe.has_bulge,
                    "bbox": [round(v, 4) for v in bbox(pts)] if pts else None,
                    "area": shoelace_area(pts) if fe.closed else 0.0,
                }
                facts["outlines"][r["role"]].append(rec)
                facts["rule_hits"][f"layer:{r['role']}"] += 1
                matched = True
                break
            if not matched and fe.closed:
                facts["unclassified_layers"][fe.base_layer] += 1
        elif t in ("TEXT", "MTEXT"):
            if not fe.text:
                continue
            txt = fe.text.replace("\n", " ").strip()
            rec = {"handle": fe.handle, "layer": fe.layer, "base_layer": fe.base_layer, "block": fe.block,
                   "entity_type": t, "text": txt, "insert": [round(fe.insert[0], 4), round(fe.insert[1], 4)],
                   "rotation": round(fe.rotation, 2), "height": round(fe.text_height, 4)}
            facts["all_texts"].append(rec)
            for r in text_rules:
                if r["layers"] != ["*"] and not _layer_match(fe.base_layer, r["layers"]):
                    continue
                m = re.search(r["regex"], txt)
                if m:
                    rr = dict(rec)
                    rr["groups"] = {k: v for k, v in m.groupdict().items() if v is not None}
                    facts["texts"][r["role"]].append(rr)
                    facts["rule_hits"][f"text:{r['role']}"] += 1
                    break
        elif t == "INSERT":
            if fe.attribs and "VIEWNAME" in fe.attribs:
                facts["titles"].append({"handle": fe.handle, "viewname": fe.attribs.get("VIEWNAME", ""),
                                        "scale": fe.attribs.get("VPSCALE", ""),
                                        "insert": [round(fe.insert[0], 4), round(fe.insert[1], 4)]})
            for r in block_rules:
                if re.search(r["block_regex"], fe.block_name):
                    vals = {k: fe.attribs.get(tag, "") for k, tag in r["attribs"].items()}
                    facts["blocks"][r["role"]].append({
                        "handle": fe.handle, "layer": fe.layer, "block_name": fe.block_name,
                        "insert": [round(fe.insert[0], 4), round(fe.insert[1], 4)], "values": vals,
                        "raw_attribs": fe.attribs})
                    facts["rule_hits"][f"block:{r['role']}"] += 1
                    break
        elif t == "DIMENSION":
            if fe.measurement is not None and fe.insert:
                facts["dimensions"].append({"handle": fe.handle, "layer": fe.layer,
                                            "value": round(fe.measurement, 4), "text": fe.text,
                                            "angle": round(fe.dim_angle or 0.0, 2),
                                            "defpoint": [round(fe.insert[0], 4), round(fe.insert[1], 4)],
                                            "points": [[round(a, 4), round(b, 4)] for a, b in fe.points]})
    # defaultdict -> dict for JSON
    for k in ("outlines", "texts", "blocks"):
        facts[k] = dict(facts[k])
    facts["unclassified_layers"] = dict(facts["unclassified_layers"])
    facts["rule_hits"] = dict(facts["rule_hits"])
    return facts
