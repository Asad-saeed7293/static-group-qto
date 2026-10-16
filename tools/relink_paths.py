"""Re-point project paths after the app was copied to another computer.

For every project whose drawing folder / historical BOQ path does not exist here:
  * a path inside the old application folder (e.g. D:\\Static-Group-QTO\\data\\...) is moved to this application folder;
  * any other path is looked up in the bundled 'Drawings' folder next to the application, which keeps the original
    folder structure without the drive letter (D:\\Mr. X\\DFX FILES  ->  <package>\\Drawings\\Mr. X\\DFX FILES).
Only paths that are missing AND found in the new location are changed; everything else is left untouched.
Run automatically by run.bat; safe to run any number of times.
"""
import json
import os
import re
import sys

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.dirname(APP)
CFG = os.path.join(APP, "config", "projects.json")
APP_NAME = os.path.basename(APP)


def candidates(path):
    rest = re.sub(r"^[A-Za-z]:[\\/]+", "", path)
    parts = re.split(r"[\\/]+", rest)
    if APP_NAME in parts:                                         # inside the old application folder
        i = parts.index(APP_NAME)
        yield os.path.join(APP, *parts[i + 1:])
    yield os.path.join(PKG, "Drawings", *parts)
    yield os.path.join(APP, "Drawings", *parts)


def manifest():
    """DWG/manifest.json written by make_portable_zip.ps1: {project_id: {key: path relative to Drawings}}."""
    for base in (os.path.join(PKG, "DWG"), os.path.join(APP, "DWG"), os.path.join(PKG, "Drawings"), os.path.join(APP, "Drawings")):
        m = os.path.join(base, "manifest.json")
        if os.path.exists(m):
            with open(m, encoding="utf-8-sig") as fh:
                return base, json.load(fh)
    return None, {}


def main():
    with open(CFG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    base, man = manifest()
    changed = []
    for p in cfg["projects"]:
        for key in ("source_folder", "historical_boq"):
            path = p.get(key)
            if not path or os.path.exists(path):
                continue
            mapped = [os.path.join(base, *re.split(r"[\\/]+", man[p["id"]][key]))] if base and man.get(p["id"], {}).get(key) else []
            for c in mapped + list(candidates(path)):
                if os.path.exists(c):
                    p[key] = c
                    changed.append(f"{p['id']}: {key} -> {c}")
                    break
            else:
                if p.get("archived"):
                    continue
                print(f"  note: {p['id']} {key} not found on this computer: {path}")
    if changed:
        with open(CFG, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        print("  Project paths updated for this computer:")
        for c in changed:
            print("   ", c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
