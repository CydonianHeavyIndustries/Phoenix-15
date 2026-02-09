import os
import shutil
import zipfile
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parent
MODULES_DIR = (ROOT / "modules").resolve()
APPROVED_FILE = MODULES_DIR / "approved.json"


def ensure_modules_dir() -> Path:
    MODULES_DIR.mkdir(parents=True, exist_ok=True)
    if not APPROVED_FILE.exists():
        APPROVED_FILE.write_text("[]", encoding="utf-8")
    return MODULES_DIR


def import_zip(zip_path: str, dest_dir: Path | None = None) -> Path:
    """Import a module from a zip file into modules/. Returns the target path."""
    ensure_modules_dir()
    dest = dest_dir or MODULES_DIR
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Use the zip filename (without suffix) as a subfolder
        target = dest / zip_path.stem
        target.mkdir(parents=True, exist_ok=True)
        zf.extractall(target)
    return target


def import_folder(folder_path: str, dest_dir: Path | None = None) -> Path:
    """Copy a folder into modules/."""
    ensure_modules_dir()
    dest = dest_dir or MODULES_DIR
    src = Path(folder_path)
    if not src.exists() or not src.is_dir():
        raise FileNotFoundError(src)
    target = dest / src.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(src, target)
    return target


def export_module(module_name: str, output_zip: str) -> Path:
    """Zip an existing module folder into output_zip."""
    ensure_modules_dir()
    mod_path = MODULES_DIR / module_name
    if not mod_path.exists():
        raise FileNotFoundError(mod_path)
    out = Path(output_zip)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.make_archive(out.with_suffix(""), "zip", mod_path)
    return out.with_suffix(".zip")


# Approved/official modules helpers -----------------------------------------
def _load_approved() -> list[str]:
    ensure_modules_dir()
    try:
        return json.loads(APPROVED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_approved(items: list[str]) -> None:
    ensure_modules_dir()
    APPROVED_FILE.write_text(json.dumps(sorted(set(items))), encoding="utf-8")


def list_approved() -> list[str]:
    return _load_approved()


def mark_approved(name: str) -> None:
    items = _load_approved()
    if name not in items:
        items.append(name)
    _save_approved(items)


def is_approved(name: str) -> bool:
    return name in _load_approved()
