"""
Create a timestamped backup zip of the current workspace.

Outputs: backups/bjorgsun26-YYYYMMDD-HHMMSS.zip

Excludes:
- backups/ directory (to avoid recursive zips)
- __pycache__/ and *.pyc

Usage:
  python scripts/backup.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import zipfile
from datetime import datetime


def _iter_files(root: str):
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        # Exclude backup dir
        parts = set(p.lower() for p in dirpath.split(os.sep))
        if "backups" in parts or "__pycache__" in parts:
            continue
        for name in filenames:
            if name.endswith(".pyc"):
                continue
            p = os.path.join(dirpath, name)
            # Skip if under backups just in case
            if os.sep + "backups" + os.sep in p.lower():
                continue
            yield p


def main() -> int:
    here = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.join(here, "backups")
    os.makedirs(out_dir, exist_ok=True)
    out_zip = os.path.join(out_dir, f"bjorgsun26-{stamp}.zip")

    files = list(_iter_files(here))
    rel = lambda p: os.path.relpath(p, here)
    t0 = time.time()
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            try:
                z.write(p, rel(p))
            except Exception:
                # skip unreadable files
                continue
        manifest = {
            "created_at": stamp,
            "root": here,
            "count": len(files),
            "duration_sec": round(time.time() - t0, 3),
        }
        z.writestr("backup_manifest.json", json.dumps(manifest, indent=2))

    print(out_zip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
