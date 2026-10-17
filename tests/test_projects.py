import json
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qto import store
from server.app import add_project, update_project


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    config = tmp_path / "config"
    data = tmp_path / "data"
    config.mkdir()
    data.mkdir()
    (config / "projects.json").write_text('{"projects": []}', encoding="utf-8")
    (config / "rules_villa_std.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(store, "CONFIG", str(config))
    monkeypatch.setattr(store, "DATA", str(data))
    return data


def test_create_same_name_projects_gives_distinct_stable_ids_and_private_folders(isolated_registry):
    data = isolated_registry

    first = add_project({"name": "Test Villa", "client": "Client A", "mode": "upload"})
    second = add_project({"name": "Test Villa", "client": "Client B", "mode": "upload"})

    a, b = first, second
    assert a["id"] != b["id"]
    assert a["client"] == "Client A"
    assert b["client"] == "Client B"
    assert os.path.isdir(a["source_folder"])
    assert os.path.isdir(b["source_folder"])
    registry = json.loads((data.parent / "config" / "projects.json").read_text(encoding="utf-8"))["projects"]
    assert [p["id"] for p in registry] == [a["id"], b["id"]]


def test_project_metadata_can_be_renamed_without_changing_its_id(isolated_registry):
    isolated_registry
    created = add_project({"name": "Old Name", "mode": "upload"})

    changed = update_project(created["id"], {"name": "New Name", "project_type": "villa", "location": "Lusail"})

    assert changed["id"] == created["id"]
    assert changed["name"] == "New Name"
    assert changed["project_type"] == "villa"
    assert changed["location"] == "Lusail"


def test_invalid_project_ids_cannot_escape_project_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", str(tmp_path))

    with pytest.raises(ValueError, match="Invalid project id"):
        store.pdir("../outside", "audit_log.jsonl")

    assert not (tmp_path.parent / "outside").exists()


def test_project_rules_file_must_be_inside_config(isolated_registry):
    isolated_registry
    with pytest.raises(HTTPException) as exc:
        add_project({"name": "Bad Rules", "rules_file": "..\\outside.json", "mode": "upload"})
    assert exc.value.status_code == 400
    assert "rules_file" in exc.value.detail
