"""Rule-decision workflow, readiness buckets, status semantics and assistant routing added for estimator validation.

The approval workflow runs on an isolated copy of the Al-Kawari run (tmp data folder, tmp rule state),
so the real methodology state and project data are never modified by the tests.
"""
import copy
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qto import service, store  # noqa: E402
from qto.knowledge import rules_engine  # noqa: E402
from qto.knowledge.model import load_model  # noqa: E402
from qto.knowledge.rules_engine import load_rules  # noqa: E402
from qto.takeoff import items as I  # noqa: E402

KAWARI, SULAITI = "kawari-villa", "sulaiti-villa"
need = lambda *pids: pytest.mark.skipif(not all(store.latest_run_id(p) for p in pids), reason="projects not processed")


def _item(pid, iid, variant=""):
    return next(i for i in service.results(pid)["results"]["items"] if i["item_id"] == iid and i["variant"] == variant)


def test_rule_edit_cannot_bypass_explicit_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(rules_engine, "STATE", str(tmp_path / "rule_state.json"))
    before = load_rules()["beam_depth_method"]

    with pytest.raises(ValueError, match="explicit approve action"):
        rules_engine.update_rule("beam_depth_method", "edit", status="CONFIRMED", option="full_depth")

    after = load_rules()["beam_depth_method"]
    assert after["status"] == before["status"] == "UNKNOWN"
    assert after["selected"] is None
    assert not os.path.exists(rules_engine.STATE)


@pytest.fixture
def isolated_kawari(tmp_path, monkeypatch):
    """Copy the latest Al-Kawari run into a temporary data folder; rule state and audit also go there."""
    src = store.pdir(KAWARI)
    rid = store.latest_run_id(KAWARI)
    dst = tmp_path / "data" / "projects" / KAWARI
    (dst / "runs").mkdir(parents=True)
    shutil.copytree(os.path.join(src, "runs", rid), dst / "runs" / rid)
    for f in os.listdir(src):
        if os.path.isfile(os.path.join(src, f)) and f != "audit_log.jsonl":
            shutil.copy(os.path.join(src, f), dst / f)
    monkeypatch.setattr(store, "DATA", str(tmp_path / "data"))
    monkeypatch.setattr(rules_engine, "STATE", str(tmp_path / "data" / "knowledge" / "rule_state.json"))
    service.invalidate()
    yield rid
    service.invalidate()


@need(KAWARI)
def test_rule_approval_recalculates_benchmarks_and_audits(isolated_kawari):
    from qto.knowledge.rule_workflow import decide
    before = _item(KAWARI, "SUP-BEAM")
    assert before["value"] is None and "full_depth" in before["candidates"]
    out = decide("beam_depth_method", "approve", option="full_depth", note="test approval", user="estimator")
    assert out["rule"]["status"] == "CONFIRMED" and out["rule"]["version"] == 2
    assert out["recalculated"] == [KAWARI], "only processed projects whose BOQ uses the rule are recalculated"
    assert store.latest_run_id(KAWARI) != isolated_kawari
    after = _item(KAWARI, "SUP-BEAM")
    assert after["value"] == pytest.approx(before["candidates"]["full_depth"], abs=1e-3)
    assert after["rules"][0]["selected"] == "full_depth" and after["rules"][0]["status"] == "CONFIRMED"
    bm = store.read_json(store.pdir(KAWARI, "benchmark.json"))
    assert bm["run_id"] == store.latest_run_id(KAWARI)
    row = next(r for r in bm["rows"] if r.get("item_id") == "SUP-BEAM")
    assert row["engine_qty"] == pytest.approx(after["value"], abs=1e-3) and row["diff_pct"] is not None
    log = store.audit_log("platform", 50)
    appr = next(a for a in log if a["event"] == "rule_approve")
    assert (appr["rule_id"], appr["previous_status"], appr["new_status"], appr["new_option"], appr["note"]) == \
           ("beam_depth_method", "UNKNOWN", "CONFIRMED", "full_depth", "test approval")
    imp = next(a for a in log if a["event"] == "rule_decision_impact")
    line = next(x for x in imp["lines"] if x["item_id"] == "SUP-BEAM")
    assert line["old_value"] is None and line["new_value"] == pytest.approx(after["value"], abs=1e-3)
    # reject returns the rule to UNKNOWN and the quantity to candidates only
    out2 = decide("beam_depth_method", "reject", note="undo", user="estimator")
    assert out2["rule"]["status"] == "UNKNOWN" and _item(KAWARI, "SUP-BEAM")["value"] is None


@need(KAWARI)
def test_keep_unconfirmed_note_changes_nothing(isolated_kawari):
    from qto.knowledge.rule_workflow import decide
    before = _item(KAWARI, "SUB-FTG")
    out = decide("footing_volume_method", "note", note="Reviewed - kept unconfirmed", recalculate=False)
    assert out["rule"]["status"] == "INFERRED" and out["recalculated"] == [] and out["impact"] == []
    assert store.latest_run_id(KAWARI) == isolated_kawari
    assert _item(KAWARI, "SUB-FTG") == before


def test_assumed_or_inferred_rule_is_never_calculated():
    rules = copy.deepcopy(load_rules())
    model = load_model()
    res = {"elements": [{"uid": "F1", "element_type": "footing", "floor": "FDN"}],
           "quantities": [{"element_uid": "F1", "quantity_type": "concrete_volume", "value": 1.5}]}
    ctx = lambda rs: I.Ctx(res, {}, [], {}, rs, {}, model)
    for st in ("ASSUMED", "INFERRED"):
        rules["footing_volume_method"]["status"] = st
        r = I.element_item(ctx(rules), model["by_id"]["SUB-FTG"], ["footing"], rule_ids=["footing_volume_method"])
        assert r["value"] == 1.5 and r["status"] == I.ASSUMPTION, st      # shown as Estimated
    rules["footing_volume_method"]["status"] = "CONFIRMED"
    r = I.element_item(ctx(rules), model["by_id"]["SUB-FTG"], ["footing"], rule_ids=["footing_volume_method"])
    assert r["status"] == I.AUTO                                            # Calculated only when confirmed
    assert load_rules()["storey_level_selection"]["status"] == "ASSUMED"


@need(KAWARI, SULAITI)
def test_sulaiti_identical_beam_options_are_explained():
    s, k = _item(SULAITI, "SUP-BEAM"), _item(KAWARI, "SUP-BEAM")
    assert len(set(s["candidates"].values())) == 1, "no slab detected -> no deduction -> options identical"
    assert _item(SULAITI, "SUP-SLAB")["value"] is None and not _item(SULAITI, "SUP-SLAB")["candidates"]
    assert k["candidates"]["full_depth"] > k["candidates"]["below_slab"], "with slabs detected the options differ"
    from server.app import rules_list
    beam = next(r for r in rules_list() if r["rule_id"] == "beam_depth_method")
    ties = [t for t in beam["identical_options"] if t["project"] == SULAITI]
    assert ties and "slab geometry has not yet been detected" in ties[0]["reason"]
    assert not [t for t in beam["identical_options"] if t["project"] == KAWARI]


@need(KAWARI)
def test_readiness_buckets_are_exclusive_and_complete():
    from server.app import ceo
    for p in ceo()["projects"]:
        if not p.get("processed"):
            continue
        rd = p["readiness"]
        assert sum(rd[k] for k in ("final", "lump_excluded", "measured_review", "candidates", "not_automated", "missing")) == p["boq_items"]
        assert rd["lines_with_candidates"] == rd["candidates"] + rd["missing_with_candidates"]


@need(KAWARI)
def test_assistant_review_items_changes_and_summary(monkeypatch):
    from qto.ai import agent
    real = store.base_settings
    monkeypatch.setattr(store, "base_settings", lambda: {**real(), "ai": {"enabled": False}})
    a = agent.answer("Which BOQ items need review?", KAWARI)
    n = sum(1 for i in service.results(KAWARI)["results"]["items"] if i["status"] == "Requires Engineer Review")
    assert f"{n} BOQ items require review" in a["answer"] and a["citations"]
    c = agent.answer("What changed?", KAWARI)
    assert any(x["type"] == "changes" for x in c["citations"]) and "not yet been validated" in c["answer"]
    assert "chat_question" not in c["answer"]
    m = agent.answer("Management summary", None)
    assert m["answer"].startswith("# Static Group daily project report") and m["citations"]
