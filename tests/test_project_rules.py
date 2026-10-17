import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qto import store
from qto.knowledge import rule_workflow, rules_engine
from server.app import project_rule_update, project_rules_list


@pytest.fixture
def rule_env(tmp_path, monkeypatch):
    config = tmp_path / "config"
    data = tmp_path / "data"
    knowledge = config / "knowledge"
    knowledge.mkdir(parents=True)
    shutil.copyfile(os.path.join(store.CONFIG, "knowledge", "methodology_rules.json"), knowledge / "methodology_rules.json")
    (config / "projects.json").write_text(json.dumps({"projects": [
        {"id": "project-a", "name": "Project A", "rules_file": "rules_villa_std.json"},
        {"id": "project-b", "name": "Project B", "rules_file": "rules_villa_std.json"},
    ]}), encoding="utf-8")
    (config / "rules_villa_std.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(store, "CONFIG", str(config))
    monkeypatch.setattr(store, "DATA", str(data))
    monkeypatch.setattr(rules_engine, "SEED", str(knowledge / "methodology_rules.json"))
    monkeypatch.setattr(rules_engine, "STATE", str(data / "knowledge" / "rule_state.json"))
    return data


def test_project_rule_override_does_not_change_shared_or_another_project(rule_env):
    rule_id = "beam_depth_method"

    rules_engine.update_rule(rule_id, "approve", option="full_depth", project_id="project-a")

    assert rules_engine.load_rules("project-a")[rule_id]["selected"] == "full_depth"
    assert rules_engine.load_rules("project-a")[rule_id]["status"] == "CONFIRMED"
    assert rules_engine.load_rules("project-a")[rule_id]["source"] == "Project override"
    assert rules_engine.load_rules("project-b")[rule_id]["status"] == "UNKNOWN"
    assert rules_engine.load_rules()[rule_id]["status"] == "UNKNOWN"


def test_project_rule_approval_recalculates_only_that_project(rule_env, monkeypatch):
    recalculated = []
    monkeypatch.setattr(rule_workflow, "_rule_lines", lambda pid, rule_id: {
        ("SUP-BEAM", ""): {"value": None, "status": "Requires Engineer Review"}
    })
    monkeypatch.setattr("qto.pipeline.recalc", lambda pid: recalculated.append(pid) or f"run-{pid}")
    monkeypatch.setattr("qto.knowledge.historical.benchmark_project", lambda pid: None)

    out = rule_workflow.decide("beam_depth_method", "approve", option="full_depth", project_id="project-a")

    assert out["recalculated"] == ["project-a"]
    assert recalculated == ["project-a"]
    assert {entry["event"] for entry in store.audit_log("project-a")} >= {"rule_approve", "rule_decision", "rule_decision_impact"}
    assert store.audit_log("project-b") == []


def test_local_rule_override_can_be_reset_to_shared_rule(rule_env):
    rule_id = "beam_depth_method"
    rules_engine.update_rule(rule_id, "approve", option="full_depth", project_id="project-a")

    rules_engine.reset_project_rule("project-a", rule_id)

    assert rules_engine.load_rules("project-a")[rule_id]["status"] == "UNKNOWN"
    assert rules_engine.load_rules("project-a")[rule_id]["source"] == "Shared default"
    state = json.loads(open(store.pdir("project-a", "rule_state.json"), encoding="utf-8").read())
    assert state[rule_id]["inherit"] is True


def test_project_rule_api_returns_and_updates_only_the_selected_project(rule_env):
    rule_id = "beam_depth_method"

    shared_view = project_rules_list("project-b")
    assert next(rule for rule in shared_view if rule["rule_id"] == rule_id)["status"] == "UNKNOWN"
    result = project_rule_update("project-a", rule_id, {"action": "approve", "option": "full_depth", "recalculate": False})

    assert result["rule"]["source"] == "Project override"
    assert next(rule for rule in project_rules_list("project-a") if rule["rule_id"] == rule_id)["status"] == "CONFIRMED"
    assert next(rule for rule in project_rules_list("project-b") if rule["rule_id"] == rule_id)["status"] == "UNKNOWN"
