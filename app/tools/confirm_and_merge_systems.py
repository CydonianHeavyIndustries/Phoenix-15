#!/usr/bin/env python3
"""Confirm identical files in systems/ by hashing, copy missing files from OTHER to CANONICAL.
Writes report into G:\Bjorgsun_Backups/systems_confirm_merge_<ts>
"""
import json
import shutil
from datetime import datetime
from hashlib import sha256
from pathlib import Path

CANONICAL = Path(r"G:\Bjorgsun-26\app\systems")
OTHER = Path(r"G:\OneDrive\Bjorgsun-26\systems")
BACKUP_DIR = Path(r"G:\Bjorgsun_Backups")


def hash_file(p: Path):
    h = sha256()
    try:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = BACKUP_DIR / f"systems_confirm_merge_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_files = set()
    if CANONICAL.exists():
        for p in CANONICAL.rglob("*.py"):
            all_files.add(p.relative_to(CANONICAL))
    if OTHER.exists():
        for p in OTHER.rglob("*.py"):
            all_files.add(p.relative_to(OTHER))

    report = {"timestamp": ts, "items": []}

    for rel in sorted(all_files):
        cpath = CANONICAL / rel
        opath = OTHER / rel
        in_c = cpath.exists()
        in_o = opath.exists()
        h_c = hash_file(cpath) if in_c else None
        h_o = hash_file(opath) if in_o else None
        decision = None
        action = None

        if in_c and in_o:
            if h_c == h_o and h_c is not None:
                decision = "identical"
                action = "none"
            else:
                decision = "different"
                action = "no-action (defer to full repo merge)"
        elif in_o and not in_c:
            decision = "other-only"
            # copy file into canonical
            tgt = cpath
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(opath, tgt)
            action = "copied other -> canonical"
        elif in_c and not in_o:
            decision = "canonical-only"
            action = "keep"
        else:
            decision = "missing-both"
            action = "skip"

        report["items"].append(
            {
                "path": str(rel).replace("\\", "/"),
                "in_canonical": in_c,
                "in_other": in_o,
                "hash_canonical": h_c,
                "hash_other": h_o,
                "decision": decision,
                "action": action,
            }
        )

    # Save report
    repf = out_dir / "systems_confirm_merge_report.json"
    repf.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Confirm & merge complete. Report at", repf)


if __name__ == "__main__":
    main()
