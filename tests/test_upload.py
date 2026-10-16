"""Folder upload: a browser folder picker (webkitdirectory) sends each file's name as its full relative
path within the chosen folder (e.g. "Structural/Plans/S-FP.dxf"), not just a basename. _safe_rel_path
turns that into a safe path under the project's upload destination, preserving the folder structure so
same-named files from different subfolders never collide, and rejecting anything that tries to escape
the destination folder."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.app import _safe_rel_path, _within  # noqa: E402


def test_preserves_nested_folder_structure():
    assert _safe_rel_path("Structural/Plans/S-FP.dxf") == os.path.join("Structural", "Plans", "S-FP.dxf")


def test_normalises_windows_backslashes():
    assert _safe_rel_path("Structural\\Plans\\S-FP.dxf") == os.path.join("Structural", "Plans", "S-FP.dxf")


def test_plain_filename_with_no_folder():
    assert _safe_rel_path("S-FP.dxf") == "S-FP.dxf"


def test_rejects_parent_directory_traversal():
    assert _safe_rel_path("../../etc/passwd") is None
    assert _safe_rel_path("Structural/../../../etc/passwd") is None


def test_leading_slash_is_relocated_under_the_destination_not_rejected():
    """A leading '/' is stripped rather than treated as absolute - the result is still a harmless
    relative path (a subfolder literally named 'etc' under the destination), not an escape."""
    assert _safe_rel_path("/etc/passwd") == os.path.join("etc", "passwd")


def test_rejects_empty_paths():
    assert _safe_rel_path("") is None
    assert _safe_rel_path(None) is None


def test_rejects_windows_drive_letter_component():
    """Regression: os.path.join('dest', 'C:/Windows/evil.dxf') silently DISCARDS 'dest' and returns
    'C:/Windows/evil.dxf' - ntpath treats a drive-letter component as absolute and resets the join. A
    part containing ':' must never reach os.path.join as a path component."""
    assert _safe_rel_path("C:/Windows/evil.dxf") is None
    assert _safe_rel_path("C:\\Windows\\evil.dxf") is None
    assert _safe_rel_path("Structural/C:/evil.dxf") is None


def test_within_catches_the_drive_letter_escape_as_a_second_independent_layer():
    """Defense in depth: even if a path component slipped past _safe_rel_path's own checks, joining it
    onto a Windows drive letter resets os.path.join entirely - _within must still catch the result
    landing outside the destination folder."""
    dest = os.path.join("C:" + os.sep, "dest", "folder")
    escaped = os.path.join(dest, "C:/Windows/evil.dxf")
    assert not _within(dest, escaped)


def test_within_accepts_a_path_genuinely_inside_the_destination(tmp_path):
    dest = str(tmp_path / "dest")
    target = os.path.join(dest, "Structural", "Plans", "S-FP.dxf")
    assert _within(dest, target)


def test_same_basename_in_different_subfolders_does_not_collide():
    """The whole point of preserving folders: two files named identically but in different disciplines
    must resolve to two different destination paths, not overwrite each other."""
    a = _safe_rel_path("Architectural/Plan.dxf")
    b = _safe_rel_path("Structural/Plan.dxf")
    assert a != b
    assert os.path.basename(a) == os.path.basename(b) == "Plan.dxf"


def test_uploaded_nested_files_are_all_found_by_the_recursive_scanner(tmp_path):
    """End-to-end check: files saved the way the upload endpoint saves them (nested, via _safe_rel_path)
    must all be picked up by qto.scan.list_files - nothing from a folder upload should go missing."""
    from qto.scan import list_files

    layout = ["A/plan1.dxf", "A/plan2.dxf", "B/C/plan3.dxf", "notes.pdf", "B/same_name.dxf", "A/same_name.dxf"]
    for raw in layout:
        rel = _safe_rel_path(raw)
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("0\nEOF\n")

    dxf, other = list_files(str(tmp_path))
    assert len(dxf) == 5, "every .dxf from every subfolder must be found, including same-named ones in different folders"
    assert len(other) == 1
    assert len({os.path.abspath(p) for p in dxf}) == 5, "same-named files in different folders must remain distinct files on disk"
