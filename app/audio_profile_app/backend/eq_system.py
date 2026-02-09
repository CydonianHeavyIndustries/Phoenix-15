from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


START_MARKER = "# AudioProfileApp Start"
END_MARKER = "# AudioProfileApp End"


def _default_config_paths() -> List[Path]:
    paths = []
    env_path = os.getenv("AUDIO_PROFILE_APO_CONFIG")
    if env_path:
        paths.append(Path(env_path))
    program_data = os.getenv("PROGRAMDATA")
    if program_data:
        paths.append(Path(program_data) / "EqualizerAPO" / "config" / "config.txt")
    paths.extend(
        [
            Path(r"C:\Program Files\EqualizerAPO\config\config.txt"),
            Path(r"C:\Program Files (x86)\EqualizerAPO\config\config.txt"),
        ]
    )
    return paths


def _coerce_config_path(raw: Optional[str]) -> Optional[Path]:
    if not raw:
        return None
    value = str(raw).strip().strip('"').strip()
    if not value:
        return None
    candidate = Path(value)
    if value.endswith(("\\", "/")):
        return candidate / "config.txt"
    if candidate.suffix.lower() != ".txt" and candidate.name.lower() != "config.txt":
        return candidate / "config.txt"
    return candidate


def _resolve_config_path(override: Optional[str]) -> Optional[Path]:
    override_path = _coerce_config_path(override)
    if override_path:
        if override_path.exists() or override_path.parent.exists():
            return override_path
        return None
    for path in _default_config_paths():
        if path.exists():
            return path
    return None


def _path_writable(path: Path) -> bool:
    try:
        target = path if path.exists() else path.parent
        return os.access(target, os.W_OK)
    except Exception:
        return False


def find_equalizer_apo_config() -> Optional[Path]:
    return _resolve_config_path(None)


def get_engine_status(config_override: Optional[str] = None) -> Dict[str, Any]:
    config_path = _resolve_config_path(config_override)
    if config_path is None:
        return {
            "available": False,
            "engine": "none",
            "config_path": None,
            "exists": False,
            "writable": False,
            "detail": "Equalizer APO config not found.",
        }
    exists = config_path.exists()
    writable = _path_writable(config_path)
    detail = None
    if not exists:
        detail = "Config file missing."
    elif not writable:
        detail = "Config not writable; run as admin or set a writable path."
    return {
        "available": True,
        "engine": "equalizer_apo",
        "config_path": str(config_path),
        "exists": exists,
        "writable": writable,
        "detail": detail,
    }


def _read_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_state(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=False)


def _build_graphic_eq(bands: List[float]) -> str:
    band_labels = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    pairs = [f"{band} {value:.1f}" for band, value in zip(band_labels, bands)]
    joined = "; ".join(pairs)
    return f"GraphicEQ: {joined}"


def _write_config_block(config_path: Path, line: str) -> None:
    if config_path.exists():
        content = config_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    else:
        content = []

    if START_MARKER in content and END_MARKER in content:
        start_index = content.index(START_MARKER)
        end_index = content.index(END_MARKER)
        updated = content[: start_index + 1] + [line] + content[end_index:]
    else:
        updated = content + [START_MARKER, line, END_MARKER]

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def apply_system_eq(
    bands: List[float], state_path: Path, config_override: Optional[str] = None
) -> Dict[str, Any]:
    status = get_engine_status(config_override)
    if not status["available"]:
        return status | {"applied": False, "bands": bands}

    config_path = Path(status["config_path"])
    eq_line = _build_graphic_eq(bands)
    try:
        _write_config_block(config_path, eq_line)
        _write_state(state_path, {"bands": bands, "engine": status["engine"]})
    except Exception as exc:
        return status | {"applied": False, "bands": bands, "error": str(exc)}
    return status | {"applied": True, "bands": bands}


def get_last_applied(state_path: Path) -> Dict[str, Any]:
    return _read_state(state_path)
