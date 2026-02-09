"""
scripts/organize_workspace.py — One‑shot workspace organizer

Safely organizes clutter in the project root into tidy folders. Supports
preview (--dry-run) and apply (--apply) modes. No files are deleted.

Moves:
  - Root HTML manuals (*.1.html, *.html) → docs/tesseract/
  - Tesseract training tools (combine_*.exe, unichar*.exe, wordlist2dawg.exe,
    text2image.exe, cntraining.exe, mftraining.exe, shapeclustering.exe, etc.) → vendor/tesseract/tools/
  - Old root logs (awareness_log.txt, cursor_log.txt, vision_log.txt) → logs/
  - Misc exe utilities (winpath.exe, vbanthing.xml → tools/)

Does not move DLLs by default to avoid breaking dependencies. If you want to
relocate DLLs under vendor/dlls and add a DLL directory at runtime, set
--move-dlls and then configure os.add_dll_directory in your startup.

Usage:
  python scripts/organize_workspace.py --dry-run
  python scripts/organize_workspace.py --apply
  python scripts/organize_workspace.py --apply --move-dlls
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def plan_moves(move_dlls: bool = False) -> list[tuple[Path, Path]]:
    moves: list[tuple[Path, Path]] = []
    docs = ROOT / "docs" / "tesseract"
    tesseract_dir = ROOT / "Tesseract"
    tesseract_tools = tesseract_dir / "tools"
    tools = ROOT / "tools"
    logs = ROOT / "logs"
    ensure_dir(docs)
    ensure_dir(tesseract_tools)
    ensure_dir(tools)
    ensure_dir(logs)
    ensure_dir(tesseract_dir)

    html_globs = ["*.1.html", "*training.1.html", "*lang_model*.1.html", "*.html"]
    tool_names = [
        "combine_lang_model.exe",
        "combine_tessdata.exe",
        "unicharset_extractor.exe",
        "set_unicharset_properties.exe",
        "wordlist2dawg.exe",
        "text2image.exe",
        "cntraining.exe",
        "mftraining.exe",
        "shapeclustering.exe",
    ]
    misc_tools = ["winpath.exe"]
    root_logs = ["awareness_log.txt", "cursor_log.txt", "vision_log.txt"]

    # Docs
    for pat in html_globs:
        for f in ROOT.glob(pat):
            if f.is_file():
                moves.append((f, docs / f.name))

    # Tesseract training tools
    for name in tool_names:
        f = ROOT / name
        if f.exists():
            moves.append((f, tesseract_tools / f.name))

    # Misc
    for name in misc_tools:
        f = ROOT / name
        if f.exists():
            moves.append((f, tools / f.name))

    # Old logs
    for name in root_logs:
        f = ROOT / name
        if f.exists():
            moves.append((f, logs / f.name))

    # DLLs (optional)
    if move_dlls:
        # Move suspected Tesseract-related DLLs next to Tesseract\tesseract.exe
        dll_dst = tesseract_dir
        ensure_dir(dll_dst)
        for f in ROOT.glob("*.dll"):
            name = f.name.lower()
            if any(
                k in name
                for k in [
                    "tesseract",
                    "lept",
                    "png",
                    "jpeg",
                    "tiff",
                    "gif",
                    "webp",
                    "zlib",
                    "iconv",
                    "cairo",
                    "pango",
                    "harfbuzz",
                ]
            ):
                moves.append((f, dll_dst / f.name))

    return moves


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run", action="store_true", help="Preview moves without changing files"
    )
    ap.add_argument("--apply", action="store_true", help="Apply moves")
    ap.add_argument(
        "--move-dlls",
        action="store_true",
        help="Also move root DLLs to vendor/dlls (advanced)",
    )
    args = ap.parse_args()

    moves = plan_moves(move_dlls=args.move_dlls)
    if not moves:
        print("Nothing to move. Already tidy!")
        return 0

    print("Planned moves:")
    for src, dst in moves:
        print(f"  {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")

    if args.apply:
        for src, dst in moves:
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(src), str(dst))
            except Exception as e:
                print(f"  !! Failed to move {src} -> {dst}: {e}")
        print("Done.")
    else:
        print("\nDry run only. Re-run with --apply to apply these moves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
