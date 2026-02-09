import json
import threading
import time
from typing import Optional

try:
    import websocket  # type: ignore
except Exception:
    websocket = None  # soft dependency

from config import XSO_APP, XSO_ENABLED, XSO_URL

_lock = threading.Lock()
_ws = None
_last_err: str = ""


def get_last_error() -> str:
    return _last_err


def _connect() -> Optional["websocket.WebSocket"]:
    global _ws, _last_err
    if not XSO_ENABLED or websocket is None:
        return None
    try:
        if _ws is not None:
            return _ws
        _ws = websocket.create_connection(XSO_URL, timeout=1.0)
        return _ws
    except Exception as e:
        _last_err = f"XSOverlay connect error: {e}"
        _ws = None
        return None


def available() -> bool:
    return _connect() is not None


def push(title: str, content: str, duration: float = 3.5, level: str = "info") -> bool:
    """Send a basic notification to XSOverlay (if enabled and reachable).
    Falls back to no-op when websocket-client is missing or overlay not running.
    """
    global _ws, _last_err
    if not XSO_ENABLED or websocket is None:
        return False
    data = {
        "title": f"{XSO_APP}: {title}",
        "content": content,
        "duration": max(1.0, float(duration)),
        "level": level,
    }
    pay = json.dumps(data, ensure_ascii=False)
    with _lock:
        ws = _connect()
        if ws is None:
            return False
        try:
            ws.send(pay)
            return True
        except Exception as e:
            _last_err = f"XSOverlay send error: {e}"
            try:
                # Reset connection and retry once
                if _ws is not None:
                    _ws.close()
            except Exception:
                pass
            _ws = None
            return False
