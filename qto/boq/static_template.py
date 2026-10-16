"""Generate a BOQ in Static Group's own structure from the item calculations.

The output mirrors the real Static Group workbook format: multiple sheets (Preliminaries /
BOQ FOR VILLA / Plastering works), section codes (A, B, b.1, b.2.1 ...) on heading rows only,
and plain sequential item numbers (1, 2, 3 ...) that reset at the start of each section or
subsection - exactly as in the historical BOQs (e.g. QUO-SCC-1525-2026), where "1" appears in
many different sections rather than being chained to the section code.

Because that numbering repeats across sections, "code" is for DISPLAY only and is not globally
unique. Every line also carries a "key" (item_id + variant) that IS unique across the whole BOQ -
use it, not "code", to look a line up or to cross-reference it with other sheets (e.g. a
"Calculation Detail" sheet carrying the evidence/status columns).

Each line keeps: sheet, code, description, unit, section, subsection, group (when the item is
nested under a named group such as "External Block works"), quantity, calculation status,
source/evidence, confidence, rule statuses, candidates (when the method is UNKNOWN) and review
status. Quantities are left blank when not calculable - the status column says why.
"""
from __future__ import annotations

import json
import os

from .. import store
from ..knowledge.model import load_model

TEMPLATE = os.path.join(store.CONFIG, "knowledge", "boq_template.json")
DEFAULT_SHEET = "BOQ FOR VILLA"
DISPLAY = {"Automatically Calculated": "Calculated", "Calculated With Assumption": "Estimated",
           "Requires Input": "Missing", "Not Available From Drawing": "Missing",
           "Requires Engineer Review": "Needs Review", "Lump Sum": "Lump Sum", "Not Applicable": "Excluded"}


def load_template():
    with open(TEMPLATE, encoding="utf-8") as fh:
        return json.load(fh)


def generate_static_boq(items: list) -> dict:
    from ..knowledge.rates import suggestions as rate_suggestions
    tpl = load_template()
    model = load_model()
    rates = rate_suggestions()
    by_item = {}
    for r in items:
        by_item.setdefault(r["item_id"], []).append(r)
    lines, used = [], set()

    def missing_rec(iid):
        it = model["by_id"].get(iid)
        return [{"item_id": iid, "description": it["description"] if it else iid, "unit": it["unit"] if it else "",
                 "variant": "", "value": None, "candidates": {}, "status": "Not Available From Drawing", "rules": [],
                 "missing": ["Item not calculated in this run"], "evidence": [], "confidence": None, "category": it["category"] if it else ""}]

    def line_from(section, sub, code, group_title, r):
        rule_st = sorted({x["status"] for x in r.get("rules", [])})
        # Lump Sum / Excluded lines price as a single provisional sum or not at all - their RATE cell
        # always holds a literal marker ("ls" / "Excluded"), never a per-unit number, so a per-unit
        # suggestion would never actually be shown there. Only offer one for normally-priced lines.
        status = DISPLAY.get(r["status"], r["status"])
        sr = rates.get(f"{r['item_id']}|{r.get('variant', '')}") if status not in ("Lump Sum", "Excluded") else None
        lines.append({
            "sheet": section.get("sheet", DEFAULT_SHEET), "code": code,
            "key": f"{r['item_id']}|{r.get('variant', '')}",
            "section": section["code"], "section_title": section["title"],
            "subsection": sub["code"] if sub else "", "subsection_title": sub["title"] if sub else "",
            "group": group_title or "",
            "item_id": r["item_id"], "variant": r.get("variant", ""), "description": r["description"], "unit": r["unit"],
            "quantity": r["value"], "calculation_status": r["status"], "display_status": status,
            "candidates": r.get("candidates", {}), "rule_status": ", ".join(rule_st),
            "rules": [x["rule_id"] for x in r.get("rules", []) if x["selected"] is None],
            "source": "; ".join(r.get("evidence", []))[:400], "missing": r.get("missing", []),
            "confidence": r.get("confidence"),
            "review_status": "Open" if r["status"] in ("Requires Engineer Review", "Requires Input", "Not Available From Drawing") else "-",
            "category": r.get("category", ""),
            "suggested_rate": sr["rate"] if sr else None,
            "suggested_rate_source": f"{sr['project_name']} ({sr['as_of'][:10]}, n={sr['n']})" if sr else None,
        })

    def emit(section, sub, entries):
        """entries: list of item ids, or {"id": ..., "group": "Named group title"}.
        A plain id with exactly one calculated record becomes one numbered row "n". A plain id
        with several records (variants), or one explicitly marked with a "group" title, becomes
        a named group heading "n" followed by its variants "n.1", "n.2", ... - matching how
        Static Group lists e.g. "1 Villa" -> "1.1 ... 1.9" or "1 External Block works" -> "1.1 ...".
        """
        n = 0
        for entry in entries:
            iid, group_title = (entry["id"], entry.get("group")) if isinstance(entry, dict) else (entry, None)
            recs = by_item.get(iid) or missing_rec(iid)
            used.add(iid)
            n += 1
            if group_title or len(recs) > 1:
                title = group_title or recs[0]["description"]
                lines.append({"sheet": section.get("sheet", DEFAULT_SHEET), "code": str(n), "key": f"__group__{iid}",
                              "section": section["code"], "section_title": section["title"],
                              "subsection": sub["code"] if sub else "", "subsection_title": sub["title"] if sub else "",
                              "group": "", "item_id": iid, "variant": "", "description": title, "unit": "",
                              "quantity": None, "calculation_status": "", "display_status": "", "candidates": {},
                              "rule_status": "", "rules": [], "source": "", "missing": [], "confidence": None,
                              "review_status": "-", "category": "", "is_group_header": True})
                for k, r in enumerate(recs, start=1):
                    line_from(section, sub, f"{n}.{k}", title, r)
            else:
                line_from(section, sub, str(n), None, recs[0])

    for s in tpl["sections"]:
        if s.get("items"):
            emit(s, None, s["items"])
        for sub in s.get("subsections", []):
            emit(s, sub, sub["items"])
    # anything calculated but not placed in the template is a new pattern to place
    new_ids = [iid for iid in by_item if iid not in used]
    if new_ids:
        emit({"code": "X", "title": "NEW BOQ ITEMS (not in the Static Group template)", "sheet": DEFAULT_SHEET}, None, new_ids)
    counts = {}
    for l in lines:
        if l.get("is_group_header"):
            continue
        counts[l["display_status"]] = counts.get(l["display_status"], 0) + 1
    return {"title": tpl["title"], "lines": lines, "summary": counts}


def detect_new_items(boq_rows: list) -> list:
    """Client-BOQ lines that do not match any knowledge-model item -> 'New BOQ item detected'."""
    from ..knowledge.model import match_row
    model = load_model()
    out = []
    for r in boq_rows:
        row = {"description": r.get("description", ""), "sheet": r.get("sheet", ""), "section_names": r.get("section_names", [])}
        it, _ = match_row(row, model)
        if not it and r.get("description"):
            out.append({"row": r.get("row"), "description": r["description"], "unit": r.get("unit"), "quantity": r.get("quantity"),
                        "status": "New BOQ item detected", "action": "Create a knowledge-model item and rule for it (estimator)"})
    return out
