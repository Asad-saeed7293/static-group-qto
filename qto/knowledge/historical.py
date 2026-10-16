"""Historical project intelligence: benchmark a processed project against its own Static Group BOQ."""
from __future__ import annotations

from .. import store
from .benchmark import run_benchmark
from .boq_reader import read_static_boq
from .model import load_model


def benchmark_project(pid: str) -> dict | None:
    proj = store.project(pid)
    path = proj.get("historical_boq")
    rid = store.latest_run_id(pid)
    if not path or not rid:
        return None
    res = store.read_json(store.run_path(pid, rid, "results.json"))
    drawings = store.read_json(store.run_path(pid, rid, "drawings.json")) or []
    boq = read_static_boq(path)
    b = run_benchmark(boq, res, load_model(), drawings)
    b["project"] = pid
    b["run_id"] = rid
    b["boq_meta"] = {k: v for k, v in boq["meta"].items() if k != "file"}
    b["boq_file"] = path
    store.write_json(store.pdir(pid, "benchmark.json"), b)
    return b


def benchmark_markdown(b: dict, name: str) -> str:
    s = b["summary"]
    lines = [f"## {name}", "",
             f"Run `{b['run_id']}` vs Static Group BOQ {b['boq_meta'].get('ref', '')} ({b['boq_meta'].get('date', '')[:10]}).", "",
             f"* BOQ lines: {s['boq_lines']} ({s['measured_lines']} measured, the rest lump sum / excluded)",
             f"* Mapped to the knowledge model: {s['mapped_to_model']}",
             "* Measured lines by result: " + ", ".join(f"{k} {v}" for k, v in sorted(s["by_status"].items())), "",
             "| Item | BOQ description | Unit | Static Group qty | Engine qty | Diff % | Result | Engine evidence |",
             "|---|---|---|---|---|---|---|---|"]
    for r in b["rows"]:
        if r["kind"] != "measured":
            continue
        hq = f"{r['historical_qty']:.2f}" if r["historical_qty"] is not None else ""
        eq = f"{r['engine_qty']:.2f}" if r["engine_qty"] is not None else "—"
        dp = f"{r['diff_pct']:+.1f}" if r["diff_pct"] is not None else ""
        lines.append(f"| {r['item_id'] or '(unmapped)'} | {r['description'][:70]} | {r['unit']} | {hq} | {eq} | {dp} | {r['status']} | {r['engine_detail'][:80]} |")
    return "\n".join(lines) + "\n"
