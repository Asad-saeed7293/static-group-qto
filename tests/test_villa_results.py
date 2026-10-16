"""Regression checks on the real villa drawings (uses the latest processing run).

Run `python qto_cli.py run` first. These checks pin the results that were
verified by hand against the drawings and the earlier Excel prototype.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qto import service, store  # noqa: E402

PID = "ramzi-villa"
pytestmark = pytest.mark.skipif(not store.latest_run_id(PID), reason="no processing run for the villa yet")

# Footing sizes from the earlier Excel prototype (W x L, m) - must be reproduced by the automated pipeline.
EXCEL_FOOTINGS = {"F1": (0.7, 1.5), "F2": (1.5, 1.8), "F3": (2.2, 2.6), "F4": (2.1, 2.4), "F5": (2.0, 2.65), "F6": (1.2, 1.6),
                  "F7": (1.65, 2.3), "F8": (1.65, 2.15), "F11": (0.62, 1.3), "CF2": (1.0, 2.47)}
EXCEL_COLUMNS = {"C1": (0.3, 0.6), "C2": (0.35, 0.72), "C3": (0.4, 0.72), "C4": (0.2, 0.6), "C5": (0.2, 0.6), "C6": (0.35, 0.6),
                 "C7": (0.25, 0.6), "C8": (0.2, 0.6), "C9": (0.25, 0.75), "C10": (0.25, 0.9), "C11": (0.2, 0.6), "C12": (0.2, 0.85),
                 "C13": (0.35, 0.72), "C14": (0.2, 0.85), "C15": (0.3, 0.6), "C16": (0.2, 0.6), "C17": (0.35, 0.6), "C18": (0.25, 0.5)}


@pytest.fixture(scope="module")
def res():
    return service.results(PID)


def test_every_dxf_processed_without_errors(res):
    run = res["run"]
    assert run["counts"]["drawings"] == 80 and run["counts"]["failed"] == 0 and not run["errors"]


def test_footings_match_excel_prototype_and_schedule(res):
    fts = [e for e in res["results"]["elements"] if e["element_type"] == "footing" and e["mark"]]
    marks = {e["mark"] for e in fts}
    assert set(EXCEL_FOOTINGS) <= marks and "CF1" in marks           # CF1 was UNVERIFIED in the Excel prototype
    for e in fts:
        if e["mark"] in EXCEL_FOOTINGS:
            w, l = EXCEL_FOOTINGS[e["mark"]]
            assert e["dims"]["width"]["value"] == pytest.approx(w, abs=0.011)
            assert e["dims"]["length"]["value"] == pytest.approx(l, abs=0.011)
        assert e["dims"]["depth"]["value"] in (0.4, 0.45)             # from footing schedule, never assumed
        assert all(c["passed"] for c in e["cross_checks"])
    assert sum(1 for e in fts if e["mark"] == "F6") == 2


def test_footing_volume_f3(res):
    q = next(q for q in res["results"]["quantities"] if q["element_uid"] == "FTG-F3-01" and q["quantity_type"] == "concrete_volume")
    assert q["value"] == pytest.approx(2.6 * 2.2 * 0.45)


def test_rafts_identified_from_raft_tags(res):
    rafts = [e for e in res["results"]["elements"] if e["element_type"] == "raft"]
    assert len(rafts) == 2
    assert sorted(round(e["dims"]["plan_area"]["value"], 3) for e in rafts) == [27.134, 151.2]


def test_column_schedule_covers_all_18_excel_types(res):
    cs = res["results"]["design"]["column_schedule"]
    types = {k.split("|")[0] for k in cs}
    assert set(EXCEL_COLUMNS) <= types


def test_column_sections_cross_checked(res):
    cols = [e for e in res["results"]["elements"] if e["element_type"] == "column"]
    assert len(cols) == 62
    failed = sorted((e["floor"], e["mark"]) for e in cols if any(not c["passed"] for c in e["cross_checks"]))
    assert failed == [("GR", "C7"), ("L1", "C16")]   # genuine plan-vs-schedule differences in the drawings


def test_no_quantity_without_inputs(res):
    for q in res["results"]["quantities"]:
        if q["value"] is None:
            assert q["status"] == "Missing Data"
        for k, m in q["inputs"].items():
            if q["value"] is not None and k in ("depth", "thickness", "height"):
                assert m["value"] is not None


def test_beam_schedule_cross_check_finds_phb7_width(res):
    bm = [e for e in res["results"]["elements"] if e["element_type"] == "beam" and e["attributes"].get("beam_mark") == "PHB7"]
    assert bm and all(any(f["code"] == "SCHEDULE_MISMATCH" for f in e["flags"]) for e in bm)
