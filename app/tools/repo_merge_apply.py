#!/usr/bin/env python3
"""repo_merge_apply.py
Perform a full repo merge from OTHER -> CANONICAL according to the "custom rule".
Backs up originals and writes audit to the configured backup directory.
"""
import difflib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
import os

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = Path(os.getenv("BJORG_CANONICAL_ROOT", str(DEFAULT_ROOT)))
OTHER_ROOT = Path(os.getenv("BJORG_OTHER_ROOT", str(DEFAULT_ROOT)))
BACKUP_DIR = Path(os.getenv("BJORG_BACKUP_DIR", str(DEFAULT_ROOT.parent / "Bjorgsun_Backups")))
HEAVY_IMPORTS = [
    "cv2",
    "numpy",
    "pytesseract",
    "faster_whisper",
    "sounddevice",
    "keyboard",
    "pyvoicemeeter",
    "websocket",
    "websockets",
    "requests",
    "torch",
    "whisper",
]
DEPRECATED_RE = re.compile(r"deprecat|obsolete|do not use", re.I)
IMPORT_RE = re.compile(r"^(?:from|import)\s+([\w\.]+)", re.M)
EXCLUDE_DIRS = {".git", ".venv", "venv", "build", "dist", "__pycache__", ".idea"}


def read_text(p: Path):
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        try:
            return p.read_text(encoding="latin-1")
        except Exception:
            return None


def detect_imports(text: str):
    names = set()
    if not text:
        return names
    for m in IMPORT_RE.finditer(text):
        pkg = m.group(1).split(".")[0]
        names.add(pkg)
    return names


def non_comment_lines(text: str):
    if not text:
        return 0
    cnt = 0
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        cnt += 1
    return cnt


def score_pair(canon_text: str, other_text: str):
    score_c = 100
    score_o = 50
    if canon_text and DEPRECATED_RE.search(canon_text):
        score_c -= 40
    if other_text and DEPRECATED_RE.search(other_text):
        score_o -= 40
    canon_imps = detect_imports(canon_text or "")
    other_imps = detect_imports(other_text or "")
    added_heavy = [h for h in HEAVY_IMPORTS if h in other_imps and h not in canon_imps]
    if added_heavy:
        score_o -= 30
    n_c = non_comment_lines(canon_text or "")
    n_o = non_comment_lines(other_text or "")
    if n_c > 0 and n_o / (n_c + 0.001) > 1.2:
        score_o += 10
    score_c = max(0, score_c)
    score_o = max(0, score_o)
    return score_c, score_o, added_heavy


def unified_diff(a_text, b_text, fromfile, tofile):
    a_lines = (a_text or "").splitlines(keepends=True)
    b_lines = (b_text or "").splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(a_lines, b_lines, fromfile=fromfile, tofile=tofile)
    )


def should_exclude(path: Path):
    return any(part in EXCLUDE_DIRS for part in path.parts)


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if CANONICAL_ROOT.resolve() == OTHER_ROOT.resolve():
        raise SystemExit("OTHER_ROOT matches CANONICAL_ROOT; set BJORG_OTHER_ROOT to a different path.")
    out_dir = BACKUP_DIR / f"repo_merge_apply_{ts}"
    diffs_dir = out_dir / "diffs"
    originals_backup = out_dir / "originals"
    out_dir.mkdir(parents=True, exist_ok=True)
    diffs_dir.mkdir(parents=True, exist_ok=True)
    originals_backup.mkdir(parents=True, exist_ok=True)

    all_files = set()
    if CANONICAL_ROOT.exists():
        for p in CANONICAL_ROOT.rglob("*"):
            if p.is_file() and not should_exclude(p):
                rel = p.relative_to(CANONICAL_ROOT)
                all_files.add(rel)
    if OTHER_ROOT.exists():
        for p in OTHER_ROOT.rglob("*"):
            if p.is_file() and not should_exclude(p):
                rel = p.relative_to(OTHER_ROOT)
                all_files.add(rel)

    summary = {
        "timestamp": ts,
        "canonical": str(CANONICAL_ROOT),
        "other": str(OTHER_ROOT),
        "total_files": len(all_files),
        "results": [],
    }

    for rel in sorted(all_files):
        cpath = CANONICAL_ROOT / rel
        opath = OTHER_ROOT / rel
        in_c = cpath.exists()
        in_o = opath.exists()
        ctext = read_text(cpath) if in_c else None
        otext = read_text(opath) if in_o else None
        rec = {
            "path": str(rel).replace("\\", "/"),
            "in_canonical": in_c,
            "in_other": in_o,
        }

        if in_c and not in_o:
            rec["decision"] = "keep_canonical_only"
            action = "none"
        elif in_o and not in_c:
            rec["decision"] = "take_other_only"
            # copy other -> canonical
            tgt = cpath
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(opath, tgt)
            action = "copied other -> canonical"
        else:
            if ctext == otext:
                rec["decision"] = "identical"
                action = "none"
            else:
                sc, so, added_heavy = score_pair(ctext, otext)
                rec["score_canonical"] = sc
                rec["score_other"] = so
                rec["added_heavy_imports_in_other"] = added_heavy
                if so > sc:
                    rec["decision"] = "choose_other"
                    # backup original canonical file
                    backup_tgt = originals_backup / (
                        str(rel).replace("/", "__") + ".orig"
                    )
                    backup_tgt.parent.mkdir(parents=True, exist_ok=True)
                    if cpath.exists():
                        shutil.copy2(cpath, backup_tgt)
                    # copy other -> canonical
                    cpath.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(opath, cpath)
                    action = "overwritten canonical with other"
                else:
                    rec["decision"] = "choose_canonical"
                    action = "kept canonical"
                # write diff
                diff_text = unified_diff(
                    ctext or "", otext or "", f"canonical/{rel}", f"other/{rel}"
                )
                diff_file = diffs_dir / (
                    str(rel).replace("/", "__").replace("\\", "__") + ".diff"
                )
                diff_file.parent.mkdir(parents=True, exist_ok=True)
                diff_file.write_text(diff_text, encoding="utf-8")
                rec["diff"] = str(diff_file.relative_to(out_dir))

        rec["action"] = action
        summary["results"].append(rec)

    # save summary and audit
    (out_dir / f"repo-merge-audit-{ts}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (out_dir / f"repo-merge-report-{ts}.txt").write_text(
        "\n".join(
            [
                f"{r['path']}: {r.get('decision')} -> {r.get('action')}"
                for r in summary["results"]
            ]
        ),
        encoding="utf-8",
    )

    print("Repo merge apply complete. Outputs in", out_dir)


if __name__ == "__main__":
    main()
