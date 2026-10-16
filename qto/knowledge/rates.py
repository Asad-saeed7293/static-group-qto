"""Rate memory: real prices Static Group has entered into a priced BOQ, captured only when that priced
file is imported back into the app (see server.app.boq_import -> record_from_import). Nothing here is
estimated or looked up externally - every entry is a rate a person actually typed into their own pricing
sheet for a real project, carried forward so the next project's BOQ can show what this item cost last
time instead of a blank box every time. Until Static Group imports at least one priced BOQ, there is no
history and no suggestions - that is correct, not a bug.

Store: data/knowledge/rate_history.json - a flat, append-only list of every rate ever seen (not just the
latest), so the full history stays auditable: which project, which file, when.
"""
from __future__ import annotations

import os
import re

from .. import store
from .model import load_model, match_row

STORE = os.path.join(store.DATA, "knowledge", "rate_history.json")
_AREA_RE = re.compile(r"Total\s+Built[- ]?Up\s+Area\s*=\s*([\d,]+\.?\d*)\s*m", re.I)


def _load() -> list:
    return store.read_json(STORE, []) or []


def _save(entries: list):
    store.write_json(STORE, entries)


def _key(item_id: str, variant: str = "") -> str:
    return f"{item_id}|{variant or ''}"


def record_from_import(pid: str, project_name: str, source_file: str, rows: list[dict]) -> int:
    """Matches each imported row with a rate to a knowledge-model item (same matcher used to detect new
    BOQ items) and appends one history entry per match. Rows that cannot be matched, or carry no rate,
    are skipped - nothing is guessed. A known gap: items whose match depends on section context
    (section_hint in the knowledge model, e.g. several substructure items that share wording with a
    boundary-wall equivalent) will not match here, because the generic BOQ importer does not capture
    which sheet/section a row came from - better to record nothing than to risk crediting a rate to the
    wrong item. Returns how many entries were recorded."""
    priced = [r for r in rows if r.get("rate") and r.get("description")]
    if not priced:
        return 0
    model = load_model()
    hist = _load()
    at = store.now()
    n = 0
    for r in priced:
        it, _score = match_row({"description": r["description"], "sheet": r.get("sheet", ""), "section_names": r.get("section_names", [])}, model)
        if not it:
            continue
        hist.append({"item_id": it["id"], "variant": r.get("variant", ""), "unit": r.get("unit") or it.get("unit", ""),
                     "rate": r["rate"], "project": pid, "project_name": project_name, "source_file": source_file, "at": at})
        n += 1
    if n:
        _save(hist)
    return n


def suggestions() -> dict:
    """{"ITEM_ID|variant": {"rate","unit","as_of","project_name","n"}} - the most recent rate seen for
    each item/variant, plus how many priced BOQs have contributed a price for it (n=1 is one data point,
    treat it as a starting guess to check; n=4+ is a pattern worth trusting more)."""
    out = {}
    for e in sorted(_load(), key=lambda x: x["at"]):
        k = _key(e["item_id"], e.get("variant"))
        d = out.setdefault(k, {"n": 0})
        d["n"] += 1
        d.update(rate=e["rate"], unit=e["unit"], as_of=e["at"], project_name=e["project_name"])
    return out


def suggestion_for(item_id: str, variant: str = "") -> dict | None:
    return suggestions().get(_key(item_id, variant))


def built_up_area(pid: str) -> float | None:
    """Total built-up area in m2, read from the project's own BOQ header (boq_meta.areas) when a
    historical BOQ provided one. None for a project with no such data - never estimated."""
    meta = (store.read_json(store.pdir(pid, "benchmark.json")) or {}).get("boq_meta", {})
    for line in meta.get("areas") or []:
        m = _AREA_RE.search(line)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def project_cost_summary(pid: str, items: list[dict]) -> dict:
    """What rate memory implies about this project's cost so far: only the lines that have BOTH a
    calculated quantity and a suggested rate are summed - everything else is counted as a coverage gap,
    never filled in. 'indicative_total' is explicitly not a real tender total; it is only as complete as
    'priced_lines' out of 'priced_eligible_lines' says it is."""
    sug = suggestions()
    priced_lines = eligible_lines = 0
    indicative_total = 0.0
    for it in items:
        if it["value"] is None:
            continue
        eligible_lines += 1
        s = sug.get(_key(it["item_id"], it.get("variant")))
        if s:
            priced_lines += 1
            indicative_total += s["rate"] * it["value"]
    area = built_up_area(pid)
    return {
        "project": pid,
        "indicative_total": round(indicative_total, 2) if priced_lines else None,
        "priced_lines": priced_lines,
        "eligible_lines": eligible_lines,
        "coverage_pct": round(100 * priced_lines / eligible_lines, 1) if eligible_lines else None,
        "built_up_area_m2": area,
        "qr_per_m2": round(indicative_total / area, 2) if priced_lines and area else None,
    }


def cost_benchmark() -> list[dict]:
    """One cost summary per processed project, for comparing Static Group's own projects against each
    other. A project contributes nothing until it has processed drawings AND at least one line is both
    calculated and has a suggested rate - most projects will show zero coverage until priced BOQs start
    being imported, which is the honest starting state, not a bug."""
    from .. import service
    out = []
    for p in store.projects():
        if not store.latest_run_id(p["id"]):
            continue
        try:
            items = service.results(p["id"])["results"].get("items") or []
        except Exception:
            continue
        summary = project_cost_summary(p["id"], items)
        summary["project_name"] = p["name"]
        out.append(summary)
    out.sort(key=lambda s: (s["qr_per_m2"] is None, s["qr_per_m2"]))
    return out
