#!/usr/bin/env python3
"""dependency_prune.py
Scan the canonical repo for top-level imports and compare them to requirements.txt
Produces a report in G:\Bjorgsun_Backups
"""
import json
import re
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(r"G:\Bjorgsun-26\app")
BACKUP_DIR = Path(r"G:\Bjorgsun_Backups")
IMPORT_RE = re.compile(r"^(?:from|import)\s+([\w\.]+)", re.M)


def read_text(p: Path):
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        try:
            return p.read_text(encoding="latin-1")
        except Exception:
            return ""


def detect_imports_in_file(p: Path):
    txt = read_text(p)
    names = set()
    for m in IMPORT_RE.finditer(txt):
        names.add(m.group(1).split(".")[0])
    return names


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = BACKUP_DIR / f"dependency_prune_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    excludes = {
        ".git",
        ".venv",
        "venv",
        "build",
        "dist",
        "__pycache__",
        ".idea",
        ".vscode",
    }

    detected = set()
    files_scanned = 0
    for p in REPO_ROOT.rglob("*"):
        if p.is_dir():
            if p.name in excludes:
                continue
        if p.is_file():
            # skip files in excluded dirs
            if any(part in excludes for part in p.parts):
                continue
            if p.suffix in {".py", ".pyw"}:
                files_scanned += 1
                detected.update(detect_imports_in_file(p))

    # read requirements
    req_file = REPO_ROOT / "requirements.txt"
    reqs = []
    if req_file.exists():
        reqs = [
            ln.strip().split("#")[0].strip()
            for ln in req_file.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]

    # normalize req names (take package name before == or >= etc.)
    normalized_reqs = [re.split(r"[<=>]", r)[0].strip() for r in reqs]

    not_in_reqs = sorted([d for d in detected if d not in normalized_reqs])
    not_detected_in_reqs = sorted([r for r in normalized_reqs if r not in detected])

    out = {
        "timestamp": ts,
        "files_scanned": files_scanned,
        "detected_imports_count": len(detected),
        "detected_imports": sorted(detected),
        "requirements_count": len(normalized_reqs),
        "requirements": normalized_reqs,
        "imports_not_in_requirements": not_in_reqs,
        "requirements_not_detected": not_detected_in_reqs,
    }

    (out_dir / "dependency_prune_summary.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    (out_dir / "detected_imports.txt").write_text(
        "\n".join(sorted(detected)), encoding="utf-8"
    )
    (out_dir / "requirements_not_detected.txt").write_text(
        "\n".join(not_detected_in_reqs), encoding="utf-8"
    )
    (out_dir / "imports_not_in_requirements.txt").write_text(
        "\n".join(not_in_reqs), encoding="utf-8"
    )

    print("Dependency prune analysis complete. Outputs in", out_dir)


if __name__ == "__main__":
    main()
