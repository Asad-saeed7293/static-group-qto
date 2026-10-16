"""Native .dwg support: conversion wrapper, file classification, pipeline error handling when the ODA
File Converter is not installed, and a real DXF -> DWG -> DXF round trip when it is. Whichever state this
environment happens to be in, the other state's tests are skipped rather than faked - a missing-converter
test run with the converter present (or vice versa) would not prove anything."""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qto.ingest.dwg_convert import DwgConverterMissing, ensure_dxf, is_available  # noqa: E402
from qto.scan import list_files, scan_drawing  # noqa: E402

need_oda = pytest.mark.skipif(not is_available(), reason="ODA File Converter not installed in this environment")


def test_ensure_dxf_passes_through_dxf_unchanged(tmp_path):
    f = tmp_path / "plan.dxf"
    f.write_text("0\nEOF\n")
    assert ensure_dxf(str(f)) == str(f)


def test_ensure_dxf_rejects_unknown_extension(tmp_path):
    f = tmp_path / "plan.pdf"
    f.write_text("x")
    with pytest.raises(ValueError):
        ensure_dxf(str(f))


@pytest.mark.skipif(is_available(), reason="only meaningful when the converter is NOT installed")
def test_ensure_dxf_fails_clearly_without_converter(tmp_path):
    f = tmp_path / "plan.dwg"
    f.write_bytes(b"fake dwg bytes")
    with pytest.raises(DwgConverterMissing) as exc:
        ensure_dxf(str(f))
    msg = str(exc.value)
    assert "ODA File Converter" in msg
    assert "opendesign.com" in msg
    assert "plan.dwg" in msg


def test_list_files_classifies_dwg_as_a_drawing(tmp_path):
    (tmp_path / "a.dxf").write_text("0\nEOF\n")
    (tmp_path / "b.dwg").write_bytes(b"fake")
    (tmp_path / "c.pdf").write_bytes(b"fake")
    dxf, other = list_files(str(tmp_path))
    names = {os.path.basename(p) for p in dxf}
    assert names == {"a.dxf", "b.dwg"}
    assert [os.path.basename(p) for p in other] == ["c.pdf"]


@pytest.mark.skipif(is_available(), reason="only meaningful when the converter is NOT installed")
def test_scan_drawing_reports_missing_converter_without_crashing(tmp_path):
    f = tmp_path / "plan.dwg"
    f.write_bytes(b"fake dwg bytes")
    rec = scan_drawing(str(f), str(tmp_path), {}, None)
    assert rec["status"] == "error"
    assert rec["drawing_id"] is None
    assert any("ODA File Converter" in l["message"] for l in rec["log"])


@need_oda
def test_ensure_dxf_converts_and_caches_a_real_dwg(tmp_path, monkeypatch):
    """Builds a tiny DXF in memory, round-trips it DXF -> DWG -> DXF through the real ODA File Converter
    (self-contained - no external fixture file needed), then runs the result through the actual pipeline
    entry point (scan_drawing) to confirm the converted file is genuinely readable and measurable, not
    just present on disk."""
    import ezdxf
    from ezdxf.addons import odafc

    from qto import store

    monkeypatch.setattr(store, "DATA", str(tmp_path / "data"))
    import qto.ingest.dwg_convert as dwg_convert
    monkeypatch.setattr(dwg_convert, "CACHE_DIR", str(tmp_path / "data" / "_dwg_cache"))

    doc = ezdxf.new("R2018")
    doc.modelspace().add_line((0, 0), (10, 0))
    doc.modelspace().add_line((10, 0), (10, 10))
    dwg_path = tmp_path / "sample.dwg"
    odafc.export_dwg(doc, str(dwg_path))
    assert dwg_path.exists() and dwg_path.stat().st_size > 0

    out = ensure_dxf(str(dwg_path))
    assert out.endswith(".dxf") and os.path.exists(out)
    out2 = ensure_dxf(str(dwg_path))
    assert out2 == out, "a second call must reuse the cached conversion, not reconvert"

    converted = ezdxf.readfile(out)
    assert len(converted.modelspace()) == 2, "both lines drawn into the original DXF must survive the round trip"

    rec = scan_drawing(str(dwg_path), str(tmp_path), {}, None)
    assert rec["status"] != "error"
    assert rec["meta"]["modelspace_entities"] == 2
    assert any("Converted from DWG" in l["message"] for l in rec["log"])
