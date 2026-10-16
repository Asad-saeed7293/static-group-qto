"""Native .dwg support - converts a DWG to DXF so the rest of the pipeline (which only ever reads DXF)
never has to know the difference.

.dwg is Autodesk's proprietary binary format; no open-source Python library can read it directly. The
standard, legitimate way to read one without an AutoCAD license is the free ODA File Converter from the
Open Design Alliance - ezdxf already ships a thin wrapper for it (ezdxf.addons.odafc), but that wrapper
still needs the actual ODA File Converter program installed on the machine running this app. It is not
installed in every environment (in particular, not in a locked-down sandbox with no ability to run new
installers), so this module fails loudly and specifically when it is missing, rather than silently
pretending the .dwg could not be read for some other reason.

Converted files are cached next to a content hash of the source .dwg (path + size + mtime), so a project
is only ever converted once per revision of its drawings, not on every processing run.
"""
from __future__ import annotations

import glob
import hashlib
import os
import platform

from .. import store

ODA_DOWNLOAD_URL = "https://www.opendesign.com/guestfiles/oda_file_converter"
CACHE_DIR = os.path.join(store.DATA, "_dwg_cache")

# ezdxf's own default only looks for an *unversioned* install folder
# ("...\ODA\ODAFileConverter\ODAFileConverter.exe"), but the official ODA installer always creates a
# versioned one ("...\ODA\ODAFileConverter 26.3.0\..."), so that default never matches a real install out
# of the box. _locate() searches for whatever version is actually there and points ezdxf at it.
_WIN_GLOBS = [r"C:\Program Files\ODA\ODAFileConverter*\ODAFileConverter.exe",
              r"C:\Program Files (x86)\ODA\ODAFileConverter*\ODAFileConverter.exe"]


class DwgConverterMissing(RuntimeError):
    """Raised when a .dwg file is encountered but the ODA File Converter is not installed."""


def _locate_and_configure() -> None:
    if platform.system() != "Windows":
        return
    import ezdxf
    found = sorted((p for pat in _WIN_GLOBS for p in glob.glob(pat)), reverse=True)
    if found:
        ezdxf.options.set("odafc-addon", "win_exec_path", found[0])


def is_available() -> bool:
    from ezdxf.addons import odafc
    if odafc.is_installed():
        return True
    _locate_and_configure()
    return odafc.is_installed()


def _cache_key(path: str) -> str:
    st = os.stat(path)
    h = hashlib.sha1(f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}".encode("utf-8")).hexdigest()[:20]
    return f"{os.path.splitext(os.path.basename(path))[0]}-{h}.dxf"


def ensure_dxf(path: str) -> str:
    """Returns a path to a .dxf file for the given drawing: the path unchanged if it already is one,
    otherwise a cached DXF conversion of the .dwg at that path. Raises DwgConverterMissing with install
    instructions if the drawing is a .dwg and the ODA File Converter is not available."""
    if path.lower().endswith(".dxf"):
        return path
    if not path.lower().endswith(".dwg"):
        raise ValueError(f"Not a DXF or DWG file: {path}")
    if not is_available():
        raise DwgConverterMissing(
            f"'{os.path.basename(path)}' is a DWG file. Reading it needs the free ODA File Converter "
            f"installed on this machine (one-time setup, no license required): {ODA_DOWNLOAD_URL} - "
            "install it, then reprocess this project. DXF files work without any extra install.")
    os.makedirs(CACHE_DIR, exist_ok=True)
    out = os.path.join(CACHE_DIR, _cache_key(path))
    if not os.path.exists(out):
        from ezdxf.addons import odafc
        doc = odafc.readfile(path)
        doc.saveas(out)
    return out
