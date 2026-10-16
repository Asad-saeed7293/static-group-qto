"""Command-line entry point (useful for batch runs and validation).

    python qto_cli.py run [--project ramzi-villa] [--scope all|structural]
    python qto_cli.py recalc [--project ramzi-villa]
    python qto_cli.py export [--project ramzi-villa] [--out samples]
    python qto_cli.py daily-report        (writes data/reports/daily_<date>.md/.json; schedule with Windows Task Scheduler)
    python qto_cli.py ask "Which projects have BOQ issues?" [--project kawari-villa]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qto import store  # noqa: E402
from qto.pipeline import Progress, recalc, run_full  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["run", "recalc", "export", "benchmark", "daily-report", "ask"])
    ap.add_argument("question", nargs="?", default="")
    ap.add_argument("--project", default="ramzi-villa")
    ap.add_argument("--scope", default="all")
    ap.add_argument("--out", default="samples")
    a = ap.parse_args()
    if a.command == "run":
        p = Progress()
        last = [0]

        def tick():
            pass
        run_id = run_full(a.project, p, a.scope)
        for s in p.state["stages"]:
            print(f"{s['status']:8} {s['name']:28} {s.get('seconds', ''):>6}  {s['detail'][:150]}")
        if p.state["error"]:
            print("ERROR", p.state["error"])
            print("\n".join(l["msg"] for l in p.state["log"][-15:]))
            sys.exit(1)
        meta = store.read_json(store.run_path(a.project, run_id, "run.json"))
        print("RUN", run_id, meta["counts"])
    elif a.command == "recalc":
        print("RUN", recalc(a.project))
    elif a.command == "benchmark":
        from qto.knowledge.historical import benchmark_project
        b = benchmark_project(a.project)
        if not b:
            print("No historical BOQ configured or no processing run for", a.project)
            sys.exit(1)
        print(b["summary"])
    elif a.command == "daily-report":
        from qto.reports.daily import REPORTS, build_daily_report
        rep = build_daily_report(save=True)
        print(rep["text"])
        print("saved to", REPORTS)
    elif a.command == "ask":
        from qto.ai.agent import answer
        r = answer(a.question, a.project)
        print(r["answer"])
        print("sources:", "; ".join(f"{c['type']} {c.get('project') or ''} {c.get('ref') or ''}".strip() for c in r["citations"]))
    elif a.command == "export":
        from qto.export.excel import export_all
        for f in export_all(a.project, a.out):
            print("wrote", f)


if __name__ == "__main__":
    main()
