#!/usr/bin/env python3
"""Generate a candidate pruned requirements file using the dependency_prune summary."""
import json
import os
from pathlib import Path

REPO = Path(os.getenv("BJORG_CANONICAL_ROOT", str(Path(__file__).resolve().parents[1])))
BACKUP = Path(os.getenv("BJORG_BACKUP_DIR", str(REPO.parent / "Bjorgsun_Backups")))
SUMMARY = (
    REPO
    / "tools"
    / "dependency_prune_20251117_182840"
    / "dependency_prune_summary.json"
)
REQ = REPO / "requirements.txt"

# A conservative whitelist of packages to include even if static analysis didn't detect them
WHITELIST = {
    "pyinstaller-hooks-contrib",
    "python-dotenv",
    "pytesseract",
    "pillow",
    "numpy",
    "psutil",
    "sounddevice",
    "soundfile",
    "requests",
    "pywin32-ctypes",
    "pyaudio",
    "faster-whisper",
}

out_ts = "20251117_190000"
OUT_DIR = BACKUP / f"pruned_requirements_{out_ts}"
OUT_DIR.mkdir(parents=True, exist_ok=True)

summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
detected = set(summary.get("detected_imports", []))
# read original requirements and normalize
orig = []
if REQ.exists():
    for ln in REQ.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        orig.append(s)

# normalize package names to compare
norm_map = {}
for r in orig:
    key = r.split("=")[0].split("<")[0].split(">")[0].strip()
    norm_map[key] = r

pruned = []
for pkg_key, raw in norm_map.items():
    # if package name appears in detected imports OR in whitelist keep it
    if (
        pkg_key in detected
        or pkg_key.lower() in {d.lower() for d in detected}
        or pkg_key in WHITELIST
    ):
        pruned.append(raw)

# write candidate file
pruned_file = OUT_DIR / "requirements.pruned-candidates.txt"
pruned_file.write_text("\n".join(sorted(pruned)), encoding="utf-8")
# also copy into repo tools folder for review
copy_to = REPO / "tools" / "requirements.pruned-candidates.txt"
copy_to.write_text("\n".join(sorted(pruned)), encoding="utf-8")
print("Wrote pruned requirements candidate to", pruned_file)
