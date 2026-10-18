from io import BytesIO
import json
import os
import shutil

import ezdxf
import pytest
from starlette.datastructures import UploadFile

from qto import service, store
from qto.pipeline import Progress, run_full
from qto.scan import list_files
from server.app import classify_intake_file, upload_project_folder


@pytest.fixture
def intake_projects(tmp_path, monkeypatch):
    config, data = tmp_path / "config", tmp_path / "data"
    config.mkdir()
    for filename in ("rules_villa_std.json", "rules_ramzi_villa.json", "settings.json"):
        shutil.copyfile(os.path.join(store.CONFIG, filename), config / filename)
    (config / "projects.json").write_text(json.dumps({"projects": [
        {"id": "intake-a", "name": "Intake A", "source_folder": str(data / "projects" / "intake-a" / "files" / "drawings"),
         "rules_file": "rules_villa_std.json"},
        {"id": "intake-b", "name": "Intake B", "source_folder": str(data / "projects" / "intake-b" / "files" / "drawings"),
         "rules_file": "rules_villa_std.json"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(store, "CONFIG", str(config))
    monkeypatch.setattr(store, "DATA", str(data))
    service.invalidate()
    return tmp_path


def _upload(path, content=b"reference"):
    return UploadFile(filename=path, file=BytesIO(content))


def test_folder_file_classifier_sorts_cad_boq_schedules_specs_and_references():
    assert classify_intake_file("Consultant/Structural/Plans/S-FP.dxf") == "drawings"
    assert classify_intake_file("Consultant/Architecture/A-101.dwg") == "drawings"
    assert classify_intake_file("Commercial/Client BOQ.xlsx") == "client_boq"
    assert classify_intake_file("Consultant/Structural/Footing Schedule.pdf") == "schedules"
    assert classify_intake_file("Tender/Specifications/General Requirements.docx") == "specifications"
    assert classify_intake_file("Site/Photos/plot.jpg") == "references"
    assert classify_intake_file("archive.zip") == "references"


def test_folder_intake_preserves_paths_routes_all_files_and_runs_nested_dxf(intake_projects, tmp_path):
    dxf_path = tmp_path / "synthetic.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    doc.layers.new("S-FNDN-FTNG")
    doc.modelspace().add_lwpolyline([(0, 0), (2, 0), (2, 3), (0, 3)], close=True,
                                    dxfattribs={"layer": "S-FNDN-FTNG"})
    doc.saveas(str(dxf_path))
    uploads = [
        _upload("Villa/Structural/Plans/S-FP.dxf", dxf_path.read_bytes()),
        _upload("Villa/Structural/Schedules/Footing Schedule.pdf"),
        _upload("Villa/Commercial/Client BOQ.xlsx"),
        _upload("Villa/Specifications/General Requirements.docx"),
        _upload("Villa/Site/plot.jpg"),
    ]

    result = upload_project_folder("intake-a", uploads)

    assert result["counts"] == {"drawings": 1, "schedules": 1, "client_boq": 1, "specifications": 1, "references": 1}
    assert result["cad_files"] == 1
    assert os.path.isfile(store.project("intake-a")["source_folder"] + os.sep + os.path.join("Villa", "Structural", "Plans", "S-FP.dxf"))
    assert os.path.isfile(store.pdir("intake-a", "files", "schedules", "Villa", "Structural", "Schedules", "Footing Schedule.pdf"))
    assert os.path.isfile(store.pdir("intake-a", "files", "client_boq", "Villa", "Commercial", "Client BOQ.xlsx"))
    assert os.path.isfile(store.pdir("intake-a", "files", "specifications", "Villa", "Specifications", "General Requirements.docx"))
    assert os.path.isfile(store.pdir("intake-a", "files", "references", "Villa", "Site", "plot.jpg"))

    dxf_files, _ = list_files(store.project("intake-a")["source_folder"])
    assert len(dxf_files) == 1
    run_id = run_full("intake-a", Progress())
    meta = store.read_json(store.run_path("intake-a", run_id, "run.json"))
    results = store.read_project_run("intake-a", run_id, "results.json")
    assert meta["status"] == "completed"
    footing = next(e for e in results["elements"] if e["element_type"] == "footing")
    assert footing["dims"]["plan_area"]["value"] == 6.0
    assert service.results("intake-b") is None


def test_upload_project_folder_sorts_then_starts_processing_when_cad_exists(intake_projects, monkeypatch):
    import threading
    import server.app as app_module

    started = threading.Event()

    def record_run(pid, progress, scope):
        assert pid == "intake-a"
        assert scope == "all"
        drawings, _ = list_files(store.project(pid)["source_folder"])
        assert len(drawings) == 1, "processing must start after the folder's DXF has been stored"
        progress.state["running"] = False
        started.set()

    monkeypatch.setattr(app_module, "run_full", record_run)
    monkeypatch.setattr(app_module, "PROGRESS", {})

    result = app_module.upload_project_folder_and_process("intake-a", [
        _upload("Villa/Structural/Plans/S-FP.dxf", b"CAD drawing"),
        _upload("Villa/Commercial/Client BOQ.xlsx"),
    ])

    assert result["counts"]["drawings"] == 1
    assert result["counts"]["client_boq"] == 1
    assert result["drawings_ready"] == 1
    assert result["processing_started"] is True
    assert started.wait(2), "the processing worker should be launched after sorting"


def test_upload_project_folder_does_not_start_processing_without_cad(intake_projects, monkeypatch):
    import server.app as app_module

    monkeypatch.setattr(app_module, "PROGRESS", {})
    monkeypatch.setattr(app_module, "run_full", lambda *args: pytest.fail("processing must not start without DXF/DWG"))

    result = app_module.upload_project_folder_and_process("intake-a", [
        _upload("Villa/Commercial/Client BOQ.xlsx"),
        _upload("Villa/Specifications/General Requirements.pdf"),
    ])

    assert result["processing_started"] is False
    assert result["drawings_ready"] == 0
    assert result["counts"]["client_boq"] == 1
    assert result["counts"]["specifications"] == 1


def test_folder_intake_reports_conflicts_and_rejects_unsafe_paths_without_overwriting(intake_projects):
    existing = store.pdir("intake-a", "files", "references", "project", "notes.txt")
    os.makedirs(os.path.dirname(existing), exist_ok=True)
    with open(existing, "wb") as fh:
        fh.write(b"keep me")

    result = upload_project_folder("intake-a", [
        _upload("project/notes.txt", b"replace me"),
        _upload("../escape.dxf", b"unsafe"),
        _upload("C:/Windows/evil.dxf", b"unsafe"),
    ])

    assert result["counts"]["references"] == 0
    assert result["conflicts"] == [{"file": "project/notes.txt", "category": "references"}]
    assert result["rejected"] == [
        {"file": "../escape.dxf", "reason": "unsafe path"},
        {"file": "C:/Windows/evil.dxf", "reason": "unsafe path"},
    ]
    with open(existing, "rb") as fh:
        assert fh.read() == b"keep me"
    assert not (intake_projects / "escape.dxf").exists()
