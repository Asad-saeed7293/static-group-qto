"""Controlled live validation: drawing register, immutable baseline, AI proposals, estimator line decisions
(ACCEPT / CORRECT / REJECT / KEEP_UNCONFIRMED), revision comparison, metrics, sessions and archive exclusion.
All state-changing tests run on temporary copies of the data."""
import hashlib
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qto import live, service, store  # noqa: E402
from qto.knowledge import rules_engine  # noqa: E402
from qto.knowledge.rules_engine import load_rules  # noqa: E402

KAWARI, SULAITI = "kawari-villa", "sulaiti-villa"
pytestmark = pytest.mark.skipif(not (store.latest_run_id(KAWARI) and store.latest_run_id(SULAITI)), reason="projects not processed")


def _copy(pid, root):
    src, rid = store.pdir(pid), store.latest_run_id(pid)
    dst = root / "projects" / pid
    (dst / "runs").mkdir(parents=True)
    shutil.copytree(os.path.join(src, "runs", rid), dst / "runs" / rid)
    for f in os.listdir(src):
        if os.path.isfile(os.path.join(src, f)) and f != "audit_log.jsonl":
            shutil.copy(os.path.join(src, f), dst / f)
    return rid


@pytest.fixture
def iso(tmp_path, monkeypatch):
    data = tmp_path / "data"
    runs = {p: _copy(p, data) for p in (KAWARI, SULAITI)}
    monkeypatch.setattr(store, "DATA", str(data))
    monkeypatch.setattr(rules_engine, "STATE", str(data / "knowledge" / "rule_state.json"))
    service.invalidate()
    yield runs
    service.invalidate()


def _h(path):
    with open(path, "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()


def _prop(pid, item_id, variant=""):
    return next(p for p in live.proposals(pid) if p["item_id"] == item_id and p["variant"] == variant)


def test_drawing_register_fields_and_entered_values_survive_sync(iso):
    reg = live.register(KAWARI)
    assert reg and all(k in reg[0] for k in ("project_id", "drawing_id", "drawing_number", "revision", "title", "source_file", "uploaded_at", "status"))
    fp = next(r for r in reg if r["source_file"].endswith("S-FP.dxf"))
    assert (fp["drawing_number"], fp["drawing_number_source"], fp["revision"], fp["revision_source"]) == ("S-FP", "parsed from file name", None, "not recorded")
    live.update_drawing(KAWARI, fp["drawing_id"], {"revision": "C", "title": "Foundation plan"})
    again = {r["drawing_id"]: r for r in live.register(KAWARI)}[fp["drawing_id"]]
    assert (again["revision"], again["revision_source"], again["title"]) == ("C", "entered by estimator", "Foundation plan")
    assert store.audit_log(KAWARI, 5)[0]["event"] == "drawing_register_updated"
    live.record_uploads(KAWARI, "drawings", [os.path.join("x", "NEW-001 Plan.dxf")])
    assert live._uploads(KAWARI)[-1]["uploaded_at"] and store.audit_log(KAWARI, 5)[0]["event"] == "files_uploaded"


def test_estimator_line_decisions_and_unknown_protection(iso):
    run_hash = _h(store.run_path(KAWARI, iso[KAWARI], "results.json"))
    ftg, beam = _prop(KAWARI, "SUB-FTG"), _prop(KAWARI, "SUP-BEAM")
    assert ftg["ai_quantity"] == pytest.approx(69.339, abs=1e-3) and not ftg["ai_final"]
    assert beam["ai_quantity"] is None and beam["unknown_rules"] == ["beam_depth_method"] and beam["candidates"]
    with pytest.raises(ValueError):                                   # nothing to accept on an UNKNOWN-rule line
        live.decide_line(KAWARI, "SUP-BEAM", "", "ACCEPT")
    a = live.decide_line(KAWARI, "SUB-FTG", "", "ACCEPT", user="Est")
    assert (a["final_quantity"], a["line_status"]) == (pytest.approx(69.339, abs=1e-3), "Accepted by estimator")
    with pytest.raises(ValueError):
        live.decide_line(KAWARI, "SUB-GB", "", "CORRECT", estimator_quantity=40)          # comment required
    c = live.decide_line(KAWARI, "SUB-FTG", "", "CORRECT", estimator_quantity=72, comment="tank footings added", user="Est")
    assert c["variance"] == pytest.approx(72 - 69.339, abs=1e-3) and c["variance_pct"] == pytest.approx((72 - 69.339) / 69.339 * 100, abs=1e-2)
    cb = live.decide_line(KAWARI, "SUP-BEAM", "", "CORRECT", estimator_quantity=130, comment="manual take-off", user="Est")
    assert cb["variance"] is None and cb["final_quantity"] == 130                         # no AI value -> no variance
    with pytest.raises(ValueError):
        live.decide_line(KAWARI, "SUB-GB", "", "REJECT")                                  # reason required
    r = live.decide_line(KAWARI, "SUB-GB", "", "REJECT", reason="tie beams missing", user="Est")
    k = live.decide_line(KAWARI, "SUB-SOG", "", "KEEP_UNCONFIRMED", comment="check zones", user="Est")
    assert r["final_quantity"] is None and k["final_quantity"] is None
    # a correction never changes methodology or the engine result
    assert load_rules()["beam_depth_method"]["status"] == "UNKNOWN" and not os.path.exists(rules_engine.STATE)
    assert _h(store.run_path(KAWARI, iso[KAWARI], "results.json")) == run_hash
    assert _prop(KAWARI, "SUP-BEAM")["ai_quantity"] is None and _prop(KAWARI, "SUP-BEAM")["ai_display_status"] == "Needs Review"
    ev = next(x for x in store.audit_log(KAWARI, 50) if x["event"] == "line_decision" and x["action"] == "CORRECT" and x["boq_line"] == "SUB-FTG|")
    for f in ("rules", "user_name", "comment", "session_id", "version", "project_affected", "boq_line", "previous_quantity", "new_quantity",
              "previous_line_status", "new_line_status", "benchmark_before", "benchmark_after", "rule_status_changed"):
        assert f in ev, f
    assert (ev["previous_quantity"], ev["new_quantity"], ev["version"], ev["rule_status_changed"]) == (pytest.approx(69.339, abs=1e-3), 72, 2, False)
    assert ev["previous_line_status"] == "Accepted by estimator" and ev["benchmark_before"] == ev["benchmark_after"]


def test_baseline_is_immutable_and_revision_comparison(iso):
    from qto.knowledge.rule_workflow import decide
    b = live.create_baseline(KAWARI, "historical_boq", revision="Tender rev 0")
    path = os.path.join(store.pdir(KAWARI, "baselines"), b["baseline_id"] + ".json")
    h0 = _h(path)
    assert b["lines"]["SUB-FTG|"]["quantity"] == pytest.approx(76.39, abs=0.01) and b["revision"] == "Tender rev 0"
    with pytest.raises(FileExistsError):                              # exclusive create: cannot be overwritten
        open(path, "x").close()
    c0 = live.revision_comparison(KAWARI, b["baseline_id"])
    beam0 = next(r for r in c0["rows"] if r["key"] == "SUP-BEAM|")
    assert beam0["change"].startswith("not comparable") and beam0["delta"] is None
    ftg0 = next(r for r in c0["rows"] if r["key"] == "SUB-FTG|")
    assert ftg0["change"] == "changed" and ftg0["delta"] == pytest.approx(69.339 - 76.39, abs=0.01)
    assert any(r["change"] == "added" for r in c0["rows"]) and any(r["change"] == "omitted" for r in c0["rows"])
    live.decide_line(KAWARI, "SUP-BEAM", "", "CORRECT", estimator_quantity=130, comment="manual", user="Est")
    decide("beam_depth_method", "approve", option="full_depth", user="Est")        # new run = new AI result
    c1 = live.revision_comparison(KAWARI, b["baseline_id"])
    beam1 = next(r for r in c1["rows"] if r["key"] == "SUP-BEAM|")
    assert beam1["new_ai_quantity"] == pytest.approx(83.584, abs=1e-3) and beam1["change"] == "changed"
    assert beam1["delta"] == pytest.approx(83.584 - beam1["baseline_quantity"], abs=1e-3)
    assert beam1["estimator_quantity"] is None and "stale" in beam1["status"]     # decision was made on the old AI result
    assert _h(path) == h0 and live.get_baseline(KAWARI, b["baseline_id"])["lines"] == b["lines"]
    b2 = live.create_baseline(KAWARI, "estimator_decisions", revision="after review")
    assert b2["baseline_id"] != b["baseline_id"] and _h(path) == h0


def test_metrics_are_preliminary_and_only_from_decisions(iso):
    m0 = live.metrics(KAWARI)
    assert (m0["accepted"], m0["corrected"], m0["rejected"], m0["variance_n"], m0["average_abs_variance_pct"]) == (0, 0, 0, 0, None)
    assert m0["unconfirmed"] == m0["measurable_lines"] and m0["preliminary"]
    live.decide_line(KAWARI, "SUB-FTG", "", "CORRECT", estimator_quantity=72, comment="a")
    live.decide_line(KAWARI, "SUB-GB", "", "CORRECT", estimator_quantity=40, comment="b")
    live.decide_line(KAWARI, "SUP-SLAB", "", "ACCEPT")
    live.decide_line(KAWARI, "SUB-SOG", "", "KEEP_UNCONFIRMED")
    m = live.metrics(KAWARI)
    v1, v2 = abs((72 - 69.339) / 69.339 * 100), abs((40 - 43.688) / 43.688 * 100)
    assert (m["accepted"], m["corrected"], m["kept_unconfirmed"], m["variance_n"]) == (1, 2, 1, 2)
    assert m["average_abs_variance_pct"] == pytest.approx((v1 + v2) / 2, abs=0.02) and m["max_abs_variance_pct"] == pytest.approx(max(v1, v2), abs=0.02)
    assert m["unconfirmed"] == m["measurable_lines"] - 3 and m["rules_unknown"] == 18
    body = json.dumps({k: v for k, v in m.items() if k != "note"}).lower()
    assert not any(w in body for w in ("roi", "saving", "accuracy", "confidence"))                # no such figures
    assert "not an accuracy" in m["note"].lower()                                                 # only the disclaimer names them


def test_session_counts_line_decisions_and_can_be_cancelled(iso):
    from qto.knowledge import validation
    s = validation.start("Est")
    live.decide_line(KAWARI, "SUB-FTG", "", "ACCEPT")
    live.decide_line(SULAITI, "SUB-FTG", "", "KEEP_UNCONFIRMED")
    done = validation.finish(s["id"], "done")
    assert done["outcome"] == "completed" and done["summary"]["line_decisions"] == 2
    assert done["summary"]["line_decisions_by_action"] == {"ACCEPT": 1, "KEEP_UNCONFIRMED": 1}
    assert done["summary"]["line_decision_projects"] == [KAWARI, SULAITI]
    s2 = validation.start("Est")
    c = validation.finish(s2["id"], "started by mistake", cancelled=True)
    assert c["outcome"] == "cancelled" and c["summary"]["line_decisions"] == 0
    assert store.audit_log("platform", 5)[0]["event"] == "validation_session_cancelled"
    assert validation.active() is None


def test_dependencies_expose_missing_static_group_inputs(iso):
    deps = {d["item"]: d for d in live.dependencies(KAWARI)}
    assert not deps["Real, unseen Static Group project"]["ok"]
    assert not deps["Drawing revisions recorded"]["ok"] and not deps["Baseline quantity set"]["ok"]
    assert not deps["Natural ground level"]["ok"] and not deps["Methodology rules confirmed"]["ok"]
    live.create_baseline(KAWARI, "historical_boq")
    assert {d["item"]: d for d in live.dependencies(KAWARI)}["Baseline quantity set"]["ok"]


def test_archived_project_excluded_from_live_validation(tmp_path, monkeypatch):
    from fastapi import HTTPException
    cfg = tmp_path / "config"
    shutil.copytree(store.CONFIG, cfg)
    pj = json.load(open(cfg / "projects.json", encoding="utf-8"))
    pj["projects"] = [p for p in pj["projects"] if p["id"] == KAWARI]
    pj["projects"][0]["archived"] = True
    json.dump(pj, open(cfg / "projects.json", "w", encoding="utf-8"))
    data = tmp_path / "data"
    _copy(KAWARI, data)
    monkeypatch.setattr(store, "CONFIG", str(cfg))
    monkeypatch.setattr(store, "DATA", str(data))
    service.invalidate()
    from server.app import live_overview
    with pytest.raises(HTTPException) as e:
        live_overview(KAWARI)
    assert e.value.status_code == 409
    assert KAWARI not in [p["id"] for p in store.projects()]
    service.invalidate()
