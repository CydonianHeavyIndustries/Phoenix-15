#!/usr/bin/env python3
"""systems_merge_audit.py
Compare two `systems/` trees, produce diffs, score files with a "custom rule",
and write audit outputs into G:\Bjorgsun_Backups.

Usage: python tools/systems_merge_audit.py
"""
import difflib
import json
import re
from datetime import datetime
from pathlib import Path

CANONICAL = Path(r"G:\Bjorgsun-26\app\systems")
OTHER = Path(r"G:\OneDrive\Bjorgsun-26\systems")
BACKUP_DIR = Path(r"G:\Bjorgsun_Backups")
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


def read_text(p: Path):
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        try:
            return p.read_text(encoding="latin-1")
        except Exception:
            return ""


def detect_imports(text: str):
    names = set()
    for m in IMPORT_RE.finditer(text):
        pkg = m.group(1).split(".")[0]
        names.add(pkg)
    return names


def non_comment_lines(text: str):
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
    # Base scores (canonical preferred)
    score_c = 100
    score_o = 50
    # Deprecation penalties
    if DEPRECATED_RE.search(canon_text):
        score_c -= 40
    if DEPRECATED_RE.search(other_text):
        score_o -= 40
    # Heavy import penalty: if other adds heavy imports not in canonical, penalize other
    canon_imps = detect_imports(canon_text)
    other_imps = detect_imports(other_text)
    added_heavy = [h for h in HEAVY_IMPORTS if h in other_imps and h not in canon_imps]
    if added_heavy:
        score_o -= 30
    # If other is substantially longer (non-comment lines) and canonical is small, give small boost
    n_c = non_comment_lines(canon_text)
    n_o = non_comment_lines(other_text)
    if n_c > 0 and n_o / (n_c + 0.001) > 1.2:
        score_o += 10
    # clamp
    score_c = max(0, score_c)
    score_o = max(0, score_o)
    return score_c, score_o, added_heavy


def unified_diff(a_text, b_text, fromfile, tofile):
    a_lines = a_text.splitlines(keepends=True)
    b_lines = b_text.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(a_lines, b_lines, fromfile=fromfile, tofile=tofile)
    )


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = BACKUP_DIR / f"systems_merge_audit_{ts}"
    diffs_dir = out_dir / "diffs"
    out_dir.mkdir(parents=True, exist_ok=True)
    diffs_dir.mkdir(parents=True, exist_ok=True)

    all_files = set()
    if CANONICAL.exists():
        for p in CANONICAL.rglob("*.py"):
            rel = p.relative_to(CANONICAL)
            all_files.add(rel)
    if OTHER.exists():
        for p in OTHER.rglob("*.py"):
            rel = p.relative_to(OTHER)
            all_files.add(rel)

    summary = {
        "timestamp": ts,
        "canonical": str(CANONICAL),
        "other": str(OTHER),
        "total_files": len(all_files),
        "results": [],
    }

    global_imports = set()
    chosen_files = {}

    for rel in sorted(all_files):
        cpath = CANONICAL / rel
        opath = OTHER / rel
        in_c = cpath.exists()
        in_o = opath.exists()
        ctext = read_text(cpath) if in_c else ""
        otext = read_text(opath) if in_o else ""

        record = {
            "path": str(rel).replace("\\", "/"),
            "in_canonical": in_c,
            "in_other": in_o,
        }

        if in_c and not in_o:
            record["decision"] = "keep_canonical_only"
            chosen_text = ctext
        elif in_o and not in_c:
            record["decision"] = "take_other_only"
            chosen_text = otext
        else:
            if ctext == otext:
                record["decision"] = "identical"
                chosen_text = ctext
            else:
                sc, so, added_heavy = score_pair(ctext, otext)
                record["score_canonical"] = sc
                record["score_other"] = so
                record["added_heavy_imports_in_other"] = added_heavy
                if sc >= so:
                    record["decision"] = "choose_canonical"
                    chosen_text = ctext
                else:
                    record["decision"] = "choose_other"
                    chosen_text = otext
                # write per-file diff
                diff_text = unified_diff(
                    ctext, otext, f"canonical/{rel}", f"other/{rel}"
                )
                diff_file = diffs_dir / (
                    str(rel).replace("/", "__").replace("\\", "__") + ".diff"
                )
                diff_file.parent.mkdir(parents=True, exist_ok=True)
                diff_file.write_text(diff_text, encoding="utf-8")
                record["diff"] = str(diff_file.relative_to(out_dir))

        # collect imports
        imps = detect_imports(chosen_text)
        global_imports.update(imps)
        chosen_files[str(rel)] = record["decision"]
        summary["results"].append(record)

    # Write summary files
    summary_file = out_dir / f"systems-merge-summary-{ts}.json"
    audit_file = out_dir / f"systems-merge-audit-{ts}.json"
    with summary_file.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"timestamp": ts, "chosen_files": chosen_files}, indent=2))
    with audit_file.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, indent=2))

    # write imports and pruned candidates
    imports_file = out_dir / f"detected_imports_{ts}.txt"
    with imports_file.open("w", encoding="utf-8") as fh:
        for pkg in sorted(global_imports):
            fh.write(pkg + "\n")

    pruned_file = out_dir / f"requirements.pruned-candidates-{ts}.txt"
    with pruned_file.open("w", encoding="utf-8") as fh:
        fh.write("# Heavy imports detected across chosen files\n")
        for h in HEAVY_IMPORTS:
            if h in global_imports:
                fh.write(f"{h}  # heavy (detected)\n")
        fh.write("\n# All detected top-level imports\n")
        for pkg in sorted(global_imports):
            fh.write(pkg + "\n")

    # also write a human-readable top-line summary
    human = out_dir / f"systems-merge-report-{ts}.txt"
    with human.open("w", encoding="utf-8") as fh:
        fh.write(f"Systems merge audit - {ts}\n")
        fh.write(f"Canonical: {CANONICAL}\n")
        fh.write(f"Other: {OTHER}\n")
        fh.write(f"Total files examined: {len(all_files)}\n")
        fh.write("\nDecisions (first 200):\n")
        for rec in summary["results"][:200]:
            fh.write(f"{rec['path']}: {rec.get('decision')}\n")
        fh.write("\nDiffs directory: diffs/\n")
        fh.write(f"Imported packages file: {imports_file}\n")
        fh.write(f"Pruned candidates file: {pruned_file}\n")

    print("Audit complete. Outputs in:", out_dir)


if __name__ == "__main__":
    main()
