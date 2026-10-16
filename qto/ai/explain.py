"""AI layer - sits ON TOP of the deterministic engine, never inside it.

* explain_element / explain_comparison_row build a plain-English explanation
  directly from the evidence (always available, no AI needed).
* If settings.ai.enabled is true and the `anthropic` package + credentials are
  available, Claude may rephrase that explanation for a non-technical reader.
  It receives only the evidence text; it never computes or changes a number.
* search() is a simple keyword search over elements, BOQ lines and drawings
  (the hook where semantic / natural-language search can be added later).
"""
from __future__ import annotations

import re


def _fmt(v, dp=3):
    return "not available" if v is None else f"{v:.{dp}f}"


def explain_element(e: dict, qs: list, line: dict | None, row: dict | None, settings: dict) -> dict:
    parts = []
    name = e["mark"] or "an unidentified element"
    parts.append(f"{e['description']}. The system found {name} on drawing {e['drawing']} (layer {e['layer']}).")
    vol = next((q for q in qs if q["quantity_type"] in ("concrete_volume", "blinding_volume")), None)
    if vol:
        if vol["value"] is not None:
            parts.append(f"Its quantity is {vol['formula']} = {vol['substitution']} = {vol['value']:.3f} {vol['unit']}.")
        else:
            parts.append(f"Its quantity could not be calculated: {'; '.join(vol['notes']) or 'an input is missing'}.")
    srcs = []
    for k, m in e["dims"].items():
        if m["value"] is None:
            srcs.append(f"{k} is not available ({m['detail']})")
        else:
            srcs.append(f"{k} {_fmt(m['value'])} {m['unit']} comes from {m['source'].lower()} ({m['detail']})")
    if srcs:
        parts.append("Where each number came from: " + "; ".join(srcs) + ".")
    if e["cross_checks"]:
        ok = [c for c in e["cross_checks"] if c["passed"]]
        bad = [c for c in e["cross_checks"] if not c["passed"]]
        parts.append(f"{len(ok)} of {len(e['cross_checks'])} independent cross-checks passed"
                     + (": failed - " + "; ".join(f"{c['name']} (expected {c['expected']}, drawn {c['actual']})" for c in bad) if bad else "") + ".")
    if e["flags"]:
        parts.append("Why it needs attention: " + " ".join(f"{f['title']} - {f['detail']}" for f in e["flags"]))
    if row:
        if row.get("boq_quantity") is not None and row.get("variance") is not None:
            parts.append(f"Against the BOQ ({row['boq_quantity']:.3f}), the drawing quantity differs by {row['variance']:+.3f}"
                         + (f" ({row['variance_pct']:+.2f}%)" if row.get("variance_pct") is not None else "") + f"; status {row['status']}.")
        elif row.get("reasons"):
            parts.append("BOQ comparison: " + "; ".join(row["reasons"]) + ".")
    text = " ".join(parts)
    return {"text": text, "ai_rewrite": _maybe_llm(text, settings), "method": "deterministic template from evidence"}


def explain_comparison_row(r: dict, settings: dict) -> dict:
    p = []
    if r.get("boq_description"):
        p.append(f"BOQ item {r.get('boq_item_no') or ''} '{r['boq_description']}' ({r.get('boq_quantity')} {r.get('boq_unit') or ''}).")
    if r.get("matched_items"):
        p.append(f"It was matched to drawing item(s) {', '.join(r['matched_items'])} by {r.get('match_method') or 'no BOQ row'}.")
    if r.get("drawing_quantity") is not None:
        p.append(f"The drawings give {r['drawing_quantity']:.3f} m3.")
    if r.get("variance") is not None:
        p.append(f"Variance = drawing - BOQ = {r['variance']:+.3f}" + (f" ({r['variance_pct']:+.2f}%)." if r.get("variance_pct") is not None else "."))
    p.append(f"Status: {r['status']}. " + " ".join(r.get("reasons", [])))
    text = " ".join(p)
    return {"text": text, "ai_rewrite": _maybe_llm(text, settings), "method": "deterministic template from evidence"}


def _maybe_llm(text: str, settings: dict):
    cfg = (settings or {}).get("ai", {})
    if not cfg.get("enabled"):
        return None
    try:
        import anthropic
    except ImportError:
        return {"error": "AI enabled but the 'anthropic' package is not installed (pip install anthropic)"}
    try:
        client = anthropic.Anthropic()
        resp = client.beta.messages.create(
            model=cfg.get("model", "claude-opus-5-5"),
            max_tokens=2000,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=("You rewrite construction quantity-takeoff evidence for a managing director. Keep every number exactly as given, "
                    "do not add numbers, do not speculate about missing values. Plain English, at most 5 sentences."),
            messages=[{"role": "user", "content": text}],
        )
        if resp.stop_reason == "refusal":
            return {"error": "AI declined to rewrite this explanation"}
        return {"text": "".join(b.text for b in resp.content if b.type == "text"), "model": resp.model}
    except Exception as exc:  # AI is optional: never break the evidence view
        return {"error": f"AI rewrite unavailable: {type(exc).__name__}: {exc}"}


def search(data: dict, q: str) -> list:
    q = (q or "").strip()
    if not q:
        return []
    toks = [t for t in re.split(r"\s+", q.lower()) if t]
    out = []
    for e in data["results"]["elements"]:
        hay = " ".join([e["uid"], e["mark"], e["element_type"], e["floor"], e["description"], e["drawing"], e["layer"],
                        " ".join(f["code"] + " " + f["title"] for f in e["flags"])]).lower()
        if all(t in hay for t in toks):
            out.append({"kind": "element", "id": e["uid"], "title": e["description"], "sub": f"{e['drawing']} - {e['layer']}"})
    for l in data["results"]["boq"]:
        hay = f"{l['item_no']} {l['description']} {l['element_id']} {l['category']}".lower()
        if all(t in hay for t in toks):
            out.append({"kind": "boq", "id": l["item_no"], "title": l["description"], "sub": f"{l['quantity']} m3 - {l['status']}"})
    for d in data["drawings"]:
        hay = f"{d['file']} {d['rel_path']} {d.get('role_title') or ''} {d['discipline']}".lower()
        if all(t in hay for t in toks):
            out.append({"kind": "drawing", "id": d.get("drawing_id"), "title": d["file"], "sub": d["discipline"]})
    return out[:100]
