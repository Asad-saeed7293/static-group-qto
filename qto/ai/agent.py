"""Business assistant / management chat.

Two modes, both answering ONLY from application data via qto.ai.tools:

* deterministic (default, offline): the question is routed to data tools by intent; the answer is
  assembled from the returned records with citations. Unrecognised questions get the list of
  questions it can answer - never an invented answer.
* LLM (optional): if settings.ai.enabled and the `anthropic` package + credentials are available,
  Claude receives the same tools and must answer from tool results only. Project data is sent to
  the API only in this explicitly configured mode.
"""
from __future__ import annotations

import json
import re

from .. import store
from . import tools as T

HELP = ["Give me today's Static Group project update", "Which projects have BOQ issues?", "Which project has the highest quantity risk?",
        "How many BOQ items are complete?", "Show me unresolved issues", "What changed since yesterday?",
        "Which projects need estimator attention?", "How much concrete is required across all active projects?",
        "Compare the current project with Al-Kawari", "Why is beam concrete different from the historical BOQ?",
        "Which methodology rules are unknown?", "Generate a management report"]

ITEM_WORDS = [("beam", "SUP-BEAM"), ("column", "SUP-COLW"), ("slab on grade", "SUB-SOG"), ("sog", "SUB-SOG"), ("slab", "SUP-SLAB"),
              ("footing", "SUB-FTG"), ("blinding", "SUB-BLD"), ("ground beam", "SUB-GB"), ("neck", "SUB-NECK"), ("excavation", "EW-EXC"),
              ("backfill", "EW-BF"), ("block", "BLK-EXT"), ("plaster", "PL-INT"), ("lintel", "LINTEL"), ("manhole", "SRV-MH-DR"), ("waterproof", "WP-SUB-V")]


STOP = {"villa", "construction", "works", "annex", "abdulla", "abdulrahman", "with", "from", "the"}


def _projects_in_text(text):
    """Project ids mentioned in the text, in order of first mention (matches 'Sulaiti' to 'Alsulaiti', 'Al-Kawari')."""
    t = text.lower()
    found = []
    for p in store.projects():
        words = set()
        for w in re.findall(r"[a-z]{4,}", p["name"].lower()):
            if w not in STOP:
                words.add(w)
                if w.startswith("al") and len(w) > 5:
                    words.add(w[2:])
        pos = [t.find(w) for w in words if w in t]
        if pos:
            found.append((min(pos), p["id"]))
    return [pid for _, pid in sorted(found)]


def _project_from_text(text, default):
    ids = _projects_in_text(text)
    return ids[0] if ids else default


def _fmt(v, d=1):
    return "—" if v is None else f"{v:,.{d}f}"


def answer(message: str, pid: str | None = None) -> dict:
    settings = store.base_settings().get("ai", {})
    if settings.get("enabled"):
        try:
            return _llm_answer(message, pid, settings)
        except Exception as exc:  # fall back to deterministic answers, say so
            out = _route(message, pid)
            out["notes"] = [f"AI model unavailable ({type(exc).__name__}); answered from data directly."]
            return out
    return _route(message, pid)


def _route(message, pid):
    m = message.lower()
    current = pid
    pid = _project_from_text(message, pid)
    cites, lines, used = [], [], []

    def use(name, **kw):
        fn = T.TOOLS[name][0]
        r = fn(**kw)
        used.append({"tool": name, "args": kw})
        cites.extend(r["citations"])
        return r["data"]

    if re.search(r"daily|today|management (report|summary)|project update|summary of all|status of all", m):
        from ..reports.daily import build_daily_report
        rep = build_daily_report(save=False)
        used.append({"tool": "daily_report", "args": {}})
        cites.append({"type": "daily_report", "project": None, "ref": rep["date"], "url": "#/ceo"})
        return {"answer": rep["text"], "citations": cites, "tool_calls": used, "mode": "deterministic"}
    if re.search(r"concrete", m) and re.search(r"all|across|total", m):
        rows = use("concrete_all")
        lines.append("Calculated concrete per project (only items with a calculated value; items awaiting rule approval are excluded):")
        for r in rows:
            lines.append(f"- {r['project']}: {_fmt(r['concrete_calculated_m3'])} m³ ({r['items_needing_review']} BOQ items still need review)")
        lines.append(f"Total calculated: {_fmt(sum(r['concrete_calculated_m3'] for r in rows))} m³ — not a final figure while methodology rules are UNKNOWN.")
    elif re.search(r"why|different|lower|higher|variance", m) and pid:
        iid = next((i for w, i in ITEM_WORDS if w in m), None)
        if not iid:
            rows = use("benchmark_lines", pid=pid, min_abs_pct=5)
            lines.append("Lines differing by more than 5 % from the historical BOQ:" if rows else "No historical BOQ benchmark for this project.")
            for r in (rows or {}).get("rows", [])[:12]:
                lines.append(f"- {r['description'][:60]}: engine {_fmt(r['engine_qty'], 2)} vs BOQ {_fmt(r['historical_qty'], 2)} {r['unit']} ({r['diff_pct']:+.1f} %)")
        else:
            d = use("item_detail", pid=pid, item_id=iid)
            for b in d["benchmark"][:3]:
                eng = f"the engine has {_fmt(b['engine_qty'], 2)} {b['unit']}" if b["engine_qty"] is not None else "the engine has no approved quantity yet"
                lines.append(f"{b['description']}: {eng} against {_fmt(b['historical_qty'], 2)} {b['unit']} in the historical BOQ"
                             + (f" ({b['diff_pct']:+.1f} %)." if b["diff_pct"] is not None else "."))
                for c in b.get("diagnosis", [])[:5]:
                    lines.append(f"- {c['cause']}: {c['evidence']}")
            for c in d["calculations"][:1]:
                if c["candidates"]:
                    lines.append("Candidate quantities per methodology option: " + "; ".join(f"{k} = {_fmt(v, 2)}" for k, v in c["candidates"].items() if v is not None))
                open_r = [r for r in c["rules"] if r["selected"] is None]
                if open_r:
                    lines.append("Open rules: " + ", ".join(f"{r['title']} ({r['status']})" for r in open_r) + ". No conclusion has been made.")
            if not lines:
                lines.append(f"No calculation or benchmark line for {iid} in this project.")
    elif re.search(r"unknown|methodolog|rule|approval|pending", m):
        rows = use("unknown_rules")
        lines.append(f"{len(rows)} methodology rules are not yet confirmed by an estimator:")
        for r in rows:
            lines.append(f"- [{r['status']}] {r['title']} — affects {', '.join(r['items'][:5])}")
    elif re.search(r"missing|information (is )?needed|what do (we|you) need|inputs? required", m):
        ps = [pid] if pid else [p["id"] for p in store.projects()]
        for p in ps:
            rows = [r for r in use("boq_items", pid=p) if r["missing"] and r["value"] is None]
            if not rows:
                continue
            reasons = {}
            for r in rows:
                for x in r["missing"]:
                    reasons.setdefault(x, []).append(r["item_id"] + (f" {r['variant']}" if r["variant"] else ""))
            lines.append(f"{store.project(p)['name']}: {len(rows)} BOQ items without a quantity because information is missing:")
            for x, its in sorted(reasons.items(), key=lambda kv: -len(kv[1]))[:10]:
                lines.append(f"- {x} → {', '.join(sorted(set(its))[:6])}{' …' if len(set(its)) > 6 else ''}")
    elif re.search(r"(boq )?(items?|lines?) (that )?(need|needs|requir\w*) (a )?review", m) and pid:
        rows = use("boq_items", pid=pid)
        groups = {"Candidate quantities — methodology rule not yet approved": [], "Measured — value needs validation": [],
                  "No quantity yet — extraction not automated or incomplete": []}
        for r in rows:
            if r["status"] != "Requires Engineer Review":
                continue
            name = r["item_id"] + (f" {r['variant']}" if r["variant"] else "")
            if r["value"] is not None:
                groups["Measured — value needs validation"].append(f"{name} ({r['value']:,.2f} {r['unit']}; {'; '.join(r['missing'][:1]) or 'awaiting validation'})")
            elif r["open_rules"]:
                groups["Candidate quantities — methodology rule not yet approved"].append(f"{name} (rules: {', '.join(r['open_rules'][:2])})")
            else:
                groups["No quantity yet — extraction not automated or incomplete"].append(f"{name} ({'; '.join(r['missing'][:1])[:90]})")
        n = sum(len(v) for v in groups.values())
        lines.append(f"{store.project(pid)['name']}: {n} BOQ items require review.")
        for g, v in groups.items():
            if v:
                lines.append(f"{g} ({len(v)}):")
                lines += [f"- {x}" for x in v[:8]] + ([f"- … {len(v) - 8} more on the BOQ page"] if len(v) > 8 else [])
    elif re.search(r"changed|since yesterday|what's new|whats new|new issues", m):
        if pid:
            c = use("run_changes", pid=pid)
            if c.get("available") is False:
                lines.append(f"{store.project(pid)['name']}: {c.get('reason')}")
            else:
                s = c["summary"]
                lines.append(f"{store.project(pid)['name']} — latest run {c['new']} compared with {c['old']}: {s['drawings_changed']} drawings changed, "
                             f"+{s['elements_added']}/-{s['elements_removed']} elements ({s['elements_modified']} modified), {s['boq_items_changed']} BOQ lines changed.")
                for i in c["items"][:10]:
                    lines.append(f"- {i['item_id']} {i['variant']}: {i['old']} → {i['new']} {i['unit']} ({i['old_status']} → {i['new_status']})")
                lines.append("Revision comparison has not yet been validated against a real revised drawing set.")
        rows = use("recent_activity", hours=24)
        lines.append(f"{len(rows)} recorded events in the last 24 hours:" if rows else "No recorded activity in the last 24 hours.")
        for r in rows[:15]:
            lines.append(f"- {r['at']} {r['user']}: {r['event']} {r.get('project') or ''} {r.get('rule_id') or r.get('item') or r.get('run_id') or ''}")
    elif re.search(r"compare", m):
        ids = _projects_in_text(message)
        if len(ids) >= 2:
            pid, other = ids[0], ids[1]
        else:
            pid, other = current, (ids[0] if ids and ids[0] != current else None)
        if not (pid and other):
            lines.append("Name two projects to compare (e.g. 'Compare Al-Sulaiti with Al-Kawari').")
        else:
            d = use("compare_projects", a=pid, b=other)
            lines.append(f"{d['a']} vs {d['b']} (calculated values only; '—' = not calculated):")
            for r in d["rows"]:
                if r["a"] is not None or r["b"] is not None:
                    lines.append(f"- {r['item']}: {_fmt(r['a'], 2)} vs {_fmt(r['b'], 2)} {r['unit']}")
    elif re.search(r"issue|unresolved|attention|risk|problem|review", m):
        ps = [p["id"] for p in store.projects()] if re.search(r"which project|projects|all", m) or not pid else [pid]
        stats = []
        for p in ps:
            s = use("project_status", pid=p)
            if s.get("processed"):
                stats.append(s)
        stats.sort(key=lambda s: (s["critical_review_items"], s["items_needing_review"] + s["items_missing_input"]), reverse=True)
        lines.append("Projects ranked by open BOQ / review risk:")
        for s in stats:
            lines.append(f"- {s['project']}: {s['items_needing_review']} BOQ items need methodology review, {s['items_missing_input']} missing input, "
                         f"{s['critical_review_items']} critical review items, {s['schedule_conflicts']} drawing/schedule conflicts")
    elif re.search(r"complete|how many|status|progress", m) and pid:
        s = use("project_status", pid=pid)
        if not s.get("processed"):
            lines.append(f"{s['project']} has not been processed yet.")
        else:
            lines.append(f"{s['project']}: {s['boq_items']} BOQ item calculations; {s['items_with_value']} have a quantity, "
                         f"{s['items_needing_review']} await methodology review, {s['items_missing_input']} are missing data. "
                         f"{s['open_review_items']} open review items ({s['critical_review_items']} critical). Calculated concrete {_fmt(s['concrete_calculated_m3'])} m³.")
    elif re.search(r"project", m):
        rows = use("list_projects")
        for r in rows:
            lines.append(f"- {r['name']} — {r['role']} — {'processed ' + str(r['finished']) if r['processed'] else 'not processed'}")
    if not lines:
        return {"answer": "I answer from Static Group project data only. I could not match that question to the data I can query. Try one of:\n- " + "\n- ".join(HELP),
                "citations": [], "tool_calls": [], "mode": "deterministic"}
    return {"answer": "\n".join(lines), "citations": cites, "tool_calls": used, "mode": "deterministic"}


def _llm_answer(message, pid, settings):
    import anthropic
    client = anthropic.Anthropic()
    tools = [{"name": n, "description": d, "input_schema": {"type": "object", "properties": {k: {"type": "string", "description": v} for k, v in a.items()}}}
             for n, (_, d, a) in T.TOOLS.items()]
    system = ("You are Static Group's project intelligence assistant. Answer ONLY from tool results. Never estimate or compute "
              "construction quantities yourself; quote the system's numbers and their status (Calculated / Needs Review / Missing). "
              "If a methodology rule is UNKNOWN say that no conclusion has been made. Cite the project and record you used. "
              f"Current project id: {pid or 'none'}.")
    msgs = [{"role": "user", "content": message}]
    cites, used = [], []
    for _ in range(8):
        resp = client.messages.create(model=settings.get("model", "claude-opus-5-5"), max_tokens=4000, system=system, tools=tools, messages=msgs)
        if resp.stop_reason == "refusal":
            raise RuntimeError("model declined")
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return {"answer": text, "citations": cites, "tool_calls": used, "mode": "llm", "model": resp.model}
        msgs.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            fn = T.TOOLS[b.name][0]
            args = {k: (float(v) if k in ("min_abs_pct", "hours") and v not in (None, "") else v) for k, v in (b.input or {}).items()}
            try:
                r = fn(**args)
                cites.extend(r["citations"])
                used.append({"tool": b.name, "args": args})
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(r["data"], default=str)[:60000]})
            except Exception as exc:
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": f"error: {exc}", "is_error": True})
        msgs.append({"role": "user", "content": results})
    raise RuntimeError("too many tool rounds")
