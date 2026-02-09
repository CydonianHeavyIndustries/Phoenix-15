import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import HTTPException

try:
    import config  # type: ignore
except Exception:
    class _C:
        TITANFALL2_LOG_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Titanfall2\R2Northstar\logs"
        TITANFALL2_TELEMETRY_FILE = str(Path(os.getenv("LOCALAPPDATA", "")) / "TF2AI" / "advice.json")
        TITANFALL2_COMMAND_FILE = ""

    config = _C()  # type: ignore


MARKER = "[AI_COACH_TELEMETRY]"
_last_cache: Dict[str, Any] = {"ts": 0.0, "data": None}


def _latest_log_path() -> Optional[Path]:
    log_dir = Path(getattr(config, "TITANFALL2_LOG_PATH", "") or r"C:\Program Files (x86)\Steam\steamapps\common\Titanfall2\R2Northstar\logs")
    if not log_dir.exists():
        return None
    logs = sorted(log_dir.glob("nslog*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def _tail_marker(path: Path, max_bytes: int = 200_000) -> Optional[Dict[str, Any]]:
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            sz = f.tell()
            f.seek(max(sz - max_bytes, 0), os.SEEK_SET)
            chunk = f.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

    for line in reversed(chunk.splitlines()):
        if MARKER in line:
            start = line.find("{")
            if start == -1:
                continue
            payload = line[start:]
            try:
                return json.loads(payload)
            except Exception:
                continue
    return None


def latest_telemetry(force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    now = time.time()
    if not force_refresh and _last_cache["data"] and now - _last_cache["ts"] < 5:
        return _last_cache["data"]

    log_path = _latest_log_path()
    if not log_path:
        return None
    data = _tail_marker(log_path)
    _last_cache["data"] = data
    _last_cache["ts"] = now
    return data


def read_advice() -> Dict[str, Any]:
    advice_path = Path(getattr(config, "TITANFALL2_TELEMETRY_FILE", "") or (Path(os.getenv("LOCALAPPDATA", "")) / "TF2AI" / "advice.json"))
    bot_path = advice_path.parent / "bot_tuning.json"
    advice, bot = {}, {}
    try:
        if advice_path.exists():
            advice = json.loads(advice_path.read_text(encoding="utf-8"))
    except Exception:
        advice = {}
    try:
        if bot_path.exists():
            bot = json.loads(bot_path.read_text(encoding="utf-8"))
    except Exception:
        bot = {}
    return {"advice": advice.get("advice", advice), "bot_tuning": advice.get("bot_tuning", bot)}


def handle_post_telemetry(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Minimal validation
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    _last_cache["data"] = payload
    _last_cache["ts"] = time.time()
    # Optionally write to a file if configured
    out_path = Path(getattr(config, "TITANFALL2_COMMAND_FILE", "") or "")
    if out_path:
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            pass
    return payload
