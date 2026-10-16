"""Estimator validation sessions, targeted recalculation, status transitions, final-quantity guard,
pilot measurement records and test-project isolation. Everything that writes runs on isolated copies."""
import copy
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qto import service, store  # noqa: E402
from qto.boq.static_template import generate_static_boq  # noqa: E402
from qto.knowledge import rules_engine  # noqa: E402
from qto.knowledge.model import load_model  # noqa: E402
from qto.knowledge.rules_engine import load_rules  # noqa: E402
from qto.takeoff import items as I  # noqa: E402

KAWARI, SULAITI, RAMZI = "kawari-villa", "sulaiti-villa", "ramzi-villa"
need = lambda *pids: pytest.mark.skipif(not all(store.latest_run_id(p) for p in pids), reason="projects not processed")


def _copy_project(pid, root):
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
    runs = {p: _copy_project(p, data) for p in (KAWARI, SULAITI)}
    monkeypatch.setattr(store, "DATA", str(data))
    monkeypatch.setattr(rules_engine, "STATE", str(data / "knowledge" / "rule_state.json"))
    service.invalidate()
    yield runs
    service.invalidate()


def _item(pid, iid, variant=""):
    return next(i for i in service.results(pid)["results"]["items"] if i["item_id"] == iid and i["variant"] == variant)


@need(KAWARI, SULAITI)
def test_validation_session_records_estimator_decisions(iso):
    from qto.knowledge import validation
    from qto.knowledge.rule_workflow import decide
    s = validation.start("Estimator A", "Reference projects", "first review")
    with pytest.raises(ValueError):
        validation.start("Estimator B")                       # one open session at a time
    decide("beam_depth_method", "approve", option="full_depth", note="matches our practice", user="Estimator A")
    decide("footing_volume_method", "note", note="kept unconfirmed - check tank footings", recalculate=False, user="Estimator A")
    decide("lintel_bearing", "approve", option="0.15", user="Estimator A")
    decide("lintel_bearing", "reject", note="reopen - bearing differs by opening width", user="Estimator A")
    done = validation.finish(s["id"], "session closed")
    sm = done["summary"]
    assert done["estimator"] == "Estimator A" and done["started"] <= done["finished"]
    assert sm["reviewed"] == ["beam_depth_method", "footing_volume_method", "lintel_bearing"]
    assert sm["confirmed"] == ["beam_depth_method"] and sm["rejected"] == ["lintel_bearing"]
    assert sm["kept_unconfirmed"] == ["footing_volume_method"]
    assert "beam_depth_method" not in sm["unresolved"] and len(sm["unresolved"]) == 21
    assert set(sm["recalculations"]) == {KAWARI, SULAITI}
    assert sm["boq_lines_changed"] >= 1 and KAWARI in sm["benchmark_changes"]
    assert any("tank footings" in n["text"] for n in sm["notes"])
    ev = [a for a in store.audit_log("platform", 1000) if a["event"] == "rule_decision"]
    assert all(a["session_id"] == s["id"] for a in ev) and len(ev) == 4
    first = next(a for a in ev if a["rule_id"] == "beam_depth_method")
    assert (first["previous_status"], first["new_status"], first["previous_option"], first["new_option"]) == ("UNKNOWN", "CONFIRMED", None, "full_depth")
    with pytest.raises(ValueError):
        validation.finish(s["id"])


@need(KAWARI, SULAITI)
def test_unrelated_project_is_not_recalculated(iso):
    from qto.knowledge.rule_workflow import decide
    # make Al-Sulaiti a project whose BOQ does not use the lintel rule
    p = store.run_path(SULAITI, iso[SULAITI], "results.json")
    res = store.read_json(p)
    for it in res["items"]:
        it["rules"] = [r for r in it["rules"] if r["rule_id"] != "lintel_bearing"]
    store.write_json(p, res)
    service.invalidate()
    out = decide("lintel_bearing", "approve", option="0.20", user="Estimator A")
    assert out["recalculated"] == [KAWARI]
    assert store.latest_run_id(SULAITI) == iso[SULAITI] and store.latest_run_id(KAWARI) != iso[KAWARI]
    assert all(l["project"] == KAWARI for l in out["impact"])
    assert store.latest_run_id(RAMZI) is None, "projects outside the isolated data are untouched"


def test_boq_status_transition_follows_rule_state():
    rules = copy.deepcopy(load_rules())
    model = load_model()
    res = {"elements": [{"uid": "S1", "element_type": "slab", "floor": "GR"}],
           "quantities": [{"element_uid": "S1", "quantity_type": "concrete_volume", "value": 12.0}]}
    item = model["by_id"]["SUB-SOG"]

    def run():
        return I.element_item(I.Ctx(res, {}, [], {}, rules, {}, model), item, ["slab"], ["GR"], rule_ids=["slab_on_grade_extent"])
    r = run()
    assert (r["status"], r["value"], r["candidates"]) == (I.REVIEW, None, {"tagged_sog_zones": 12.0})   # UNKNOWN -> candidates only
    rules["slab_on_grade_extent"].update(status="INFERRED", selected="tagged_sog_zones")
    assert (run()["status"], run()["value"]) == (I.ASSUMPTION, 12.0)                                  # Estimated
    rules["slab_on_grade_extent"].update(status="ASSUMED")
    assert run()["status"] == I.ASSUMPTION
    rules["slab_on_grade_extent"].update(status="CONFIRMED")
    assert (run()["status"], run()["value"]) == (I.AUTO, 12.0)                                        # Calculated


@need(RAMZI, KAWARI, SULAITI)
@pytest.mark.parametrize("pid", [RAMZI, KAWARI, SULAITI])
def test_no_unconfirmed_quantity_presented_as_final(pid):
    items = service.results(pid)["results"]["items"]
    rules = load_rules()
    st_of = {(i["item_id"], i["variant"]): [rules[r["rule_id"]]["status"] for r in i["rules"]] for i in items}
    for l in generate_static_boq(items)["lines"]:
        sts = st_of.get((l["item_id"], l["variant"]), [])
        if l["display_status"] == "Calculated":
            assert all(s == "CONFIRMED" for s in sts), l["code"]
        if l["display_status"] == "Estimated":
            assert "UNKNOWN" not in sts and any(s in ("INFERRED", "ASSUMED") for s in sts), l["code"]
        if l["rules"]:                                    # an open (undecided) rule
            assert l["display_status"] not in ("Calculated", "Estimated"), l["code"]
        if l["candidates"] and l["quantity"] is None:
            assert l["display_status"] in ("Needs Review", "Missing"), l["code"]


@need(KAWARI)
def test_pilot_record_only_compares_real_values(tmp_path, monkeypatch):
    from qto import pilot
    data = tmp_path / "data"
    _copy_project(KAWARI, data)
    monkeypatch.setattr(store, "DATA", str(data))
    service.invalidate()
    r0 = pilot.report(KAWARI)
    assert all(row["manual"] is None and row["difference"] is None for row in r0["comparison"])
    assert r0["revision"]["state"] == "Implemented — Real Revised Drawing Validation Pending"
    assert "accuracy" not in json.dumps({k: v for k, v in r0.items() if k != "note"}).lower()
    with pytest.raises(ValueError):
        pilot.save(KAWARI, {"manual": {"takeoff_hours": -2}})
    pilot.save(KAWARI, {"manual": {"takeoff_hours": 16, "missing_items_found": 10},
                        "quantities": [{"item_id": "SUB-FTG", "manual_qty": 70}, {"item_id": "SUP-BEAM", "manual_qty": 90}]})
    r = pilot.report(KAWARI)
    take = next(x for x in r["comparison"] if x["category"].startswith("Takeoff"))
    assert take["manual"] == 16
    assert take["difference"] is None if take["automated"] is None else take["difference"] == pytest.approx(take["automated"] - 16, abs=1e-3)
    miss = next(x for x in r["comparison"] if x["category"].startswith("Missing"))
    assert (miss["manual"], miss["automated"], miss["difference"]) == (10, 21, 11)
    review = next(x for x in r["comparison"] if x["category"].startswith("Review"))
    assert review["difference"] is None                   # automated review hours not entered -> no difference
    ftg = next(q for q in r["quantities"] if q["item_id"] == "SUB-FTG")
    assert ftg["automated_qty"] == pytest.approx(69.339, abs=1e-3) and not ftg["automated_final"]
    beam = next(q for q in r["quantities"] if q["item_id"] == "SUP-BEAM")
    assert beam["automated_qty"] is None and beam["difference"] is None and beam["candidates"]
    assert any(a["event"] == "pilot_record_updated" for a in store.audit_log(KAWARI, 50))


def test_archived_test_project_is_isolated(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    shutil.copytree(store.CONFIG, cfg)
    with open(cfg / "projects.json", encoding="utf-8") as fh:
        pj = json.load(fh)
    pj["projects"] = [p for p in pj["projects"] if p["id"] in (KAWARI,)] + [
        {"id": "demo-test", "name": "demo-test", "source_folder": str(tmp_path), "rules_file": "rules_villa_std.json", "role": "new project"}]
    with open(cfg / "projects.json", "w", encoding="utf-8") as fh:
        json.dump(pj, fh)
    monkeypatch.setattr(store, "CONFIG", str(cfg))
    monkeypatch.setattr(store, "DATA", str(tmp_path / "data"))
    assert "demo-test" in [p["id"] for p in store.projects()]
    store.set_archived("demo-test", True, "test data")
    assert "demo-test" not in [p["id"] for p in store.projects()]
    assert store.project("demo-test")["archived"] and store.project("demo-test")["archived_reason"] == "test data"
    from qto.reports.daily import build_daily_report
    from server.app import ceo
    assert "demo-test" not in [p["id"] for p in ceo()["projects"]]
    assert "demo-test" not in [p["id"] for p in build_daily_report(save=False)["projects"]]
    assert store.audit_log("demo-test", 5)[0]["event"] == "project_archived"
    store.set_archived("demo-test", False)
    assert "demo-test" in [p["id"] for p in store.projects()]
