import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


LOG_PATH = (Path(__file__).resolve().parents[2] / "logs" / "Phoenix-15_FIXME_log.log").resolve()


def log_issue(
    code: str,
    message: str,
    detail: str | None = None,
    *,
    severity: str = "error",
    source: str = "core",
    extra: Dict[str, Any] | None = None,
) -> None:
    try:
        payload = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "code": code or "PHX-UNK-000",
            "severity": severity,
            "source": source,
            "message": message,
            "detail": detail or "",
            "extra": extra or {},
        }
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
    except Exception:
        pass
