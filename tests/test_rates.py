"""Rate memory: priced-BOQ re-import captures real rates, never fabricates one, and the suggestion it
surfaces on a later project is clearly distinguished from a confirmed price."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qto import store  # noqa: E402
from qto.boq.importer import FIELDS, import_rows, SYNONYMS  # noqa: E402
from qto.boq.static_template import generate_static_boq  # noqa: E402
from qto.knowledge import rates  # noqa: E402

KAWARI = "kawari-villa"
need_kawari = pytest.mark.skipif(not store.latest_run_id(KAWARI), reason="Al-Kawari not processed")


@pytest.fixture
def isolated_rates(tmp_path, monkeypatch):
    """Isolates only the rate-history file, not all of store.DATA - tests that read real project results
    (e.g. the Al-Kawari run) must still see the real data directory."""
    monkeypatch.setattr(rates, "STORE", str(tmp_path / "rate_history.json"))
    return tmp_path


def test_importer_exposes_a_rate_field():
    assert "rate" in FIELDS
    assert "rate" in SYNONYMS


def test_record_from_import_skips_unmatched_and_unpriced_rows(isolated_rates):
    rows = [
        {"description": "Removal of excavated materials from the site", "rate": 450.0, "unit": "m3"},
        {"description": "Something nobody will ever match", "rate": 999.0, "unit": "m3"},
        {"description": "Removal of excavated materials from the site", "rate": None, "unit": "m3"},
    ]
    n = rates.record_from_import("kawari-villa", "Al-Kawari Villa", "priced.xlsx", rows)
    assert n == 1
    hist = rates._load()
    assert len(hist) == 1
    assert hist[0]["rate"] == 450.0
    assert hist[0]["project"] == "kawari-villa"
    assert hist[0]["source_file"] == "priced.xlsx"


def test_suggestions_keep_the_most_recent_rate_and_a_count(isolated_rates, monkeypatch):
    times = iter(["2026-01-01T00:00:00", "2026-06-01T00:00:00"])
    monkeypatch.setattr(store, "now", lambda: next(times))
    rates.record_from_import("kawari-villa", "Al-Kawari Villa", "first.xlsx", [{"description": "Removal of excavated materials from the site", "rate": 400.0, "unit": "m3"}])
    rates.record_from_import("sulaiti-villa", "Sulaiti Villa", "second.xlsx", [{"description": "Removal of excavated materials from the site", "rate": 420.0, "unit": "m3"}])
    sug = rates.suggestion_for("EW-REM")
    assert sug is not None
    assert sug["rate"] == 420.0, "the most recent rate must win, not the first or an average"
    assert sug["n"] == 2
    assert sug["project_name"] == "Sulaiti Villa"


def test_no_history_means_no_suggestions(isolated_rates):
    assert rates.suggestions() == {}
    assert rates.suggestion_for("EW-REM") is None


@need_kawari
def test_static_boq_lines_carry_a_suggested_rate_only_when_history_exists(isolated_rates):
    from qto import service
    items = service.results(KAWARI)["results"]["items"]
    b = generate_static_boq(items)
    assert all(l.get("suggested_rate") is None for l in b["lines"]), "no rate history yet - nothing should be suggested"

    rates.record_from_import(KAWARI, "Al-Kawari Villa", "priced.xlsx", [{"description": "Removal of excavated materials from the site", "rate": 475.5, "unit": "m3"}])
    b2 = generate_static_boq(items)
    ftg = next(l for l in b2["lines"] if l["item_id"] == "EW-REM")
    assert ftg["suggested_rate"] == 475.5
    assert "Al-Kawari Villa" in ftg["suggested_rate_source"]
    others = [l for l in b2["lines"] if l["item_id"] != "EW-REM"]
    assert all(l.get("suggested_rate") is None for l in others), "the suggestion must be scoped to the matched item only"


def test_built_up_area_parses_the_boq_header_and_is_none_without_one(isolated_rates):
    assert rates.built_up_area("sulaiti-villa") is None or isinstance(rates.built_up_area("sulaiti-villa"), float)
    assert rates.built_up_area("a-project-that-does-not-exist") is None


@need_kawari
def test_project_cost_summary_only_counts_lines_with_both_qty_and_rate(isolated_rates):
    from qto import service
    items = service.results(KAWARI)["results"].get("items") or []
    before = rates.project_cost_summary(KAWARI, items)
    assert before["priced_lines"] == 0
    assert before["indicative_total"] is None
    assert before["qr_per_m2"] is None
    assert before["eligible_lines"] == sum(1 for i in items if i["value"] is not None)

    slab = next(i for i in items if i["item_id"] == "SUP-SLAB")
    rates.record_from_import(KAWARI, "Al-Kawari Villa", "priced.xlsx", [{"description": "RC concrete works in slabs (GF + FF + PH)", "rate": 500.0, "unit": "m3"}])
    after = rates.project_cost_summary(KAWARI, items)
    assert after["priced_lines"] == 1
    assert after["indicative_total"] == pytest.approx(slab["value"] * 500.0, rel=1e-6)
    assert after["coverage_pct"] == pytest.approx(100 * 1 / after["eligible_lines"], abs=0.05)
    if after["built_up_area_m2"]:
        assert after["qr_per_m2"] == pytest.approx(after["indicative_total"] / after["built_up_area_m2"], abs=0.01)


@need_kawari
def test_cost_benchmark_lists_every_processed_project_sorted_by_qr_per_m2(isolated_rates):
    out = rates.cost_benchmark()
    ids = [r["project"] for r in out]
    assert KAWARI in ids
    assert all(r["priced_lines"] == 0 for r in out), "no rate history yet - everything must start at zero coverage"
    vals = [r["qr_per_m2"] for r in out if r["qr_per_m2"] is not None]
    assert vals == sorted(vals), "projects with a known QR/m2 must come first, in ascending order"
    assert all(r["qr_per_m2"] is None for r in out[len(vals):])


def test_import_rows_parses_rate_only_when_mapped(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Item", "Description", "Qty", "Unit", "Rate"])
    ws.append([1, "Removal of excavated materials from the site", 10, "m3", 450])
    ws.append([2, "No rate here", 5, "m3", None])
    path = tmp_path / "priced.xlsx"
    wb.save(path)
    rows, warnings = import_rows(str(path), {"item_no": 0, "description": 1, "quantity": 2, "unit": 3, "rate": 4}, 0)
    assert rows[0]["rate"] == 450.0
    assert rows[1]["rate"] is None
    rows_no_rate_mapped, _ = import_rows(str(path), {"item_no": 0, "description": 1, "quantity": 2, "unit": 3}, 0)
    assert all(r["rate"] is None for r in rows_no_rate_mapped), "rate must never be inferred when the column wasn't mapped"
