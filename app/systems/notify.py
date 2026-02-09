import os
import threading
from datetime import datetime

from config import DESKTOP_NOTIFICATIONS_ENABLED, XSO_ENABLED

_ui_callback = None
_toast_lock = threading.Lock()

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "notifications.log")


def _log(title: str, message: str):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {title}: {message}\n")
    except Exception:
        pass


def set_ui_callback(cb):
    """Register a UI callback to show in-app toasts.
    Signature: cb(title: str, message: str, duration_sec: int)
    """
    global _ui_callback
    _ui_callback = cb


def _notify_win_toast(title: str, message: str, duration: int) -> bool:
    try:
        from win10toast import ToastNotifier  # type: ignore

        with _toast_lock:
            toaster = ToastNotifier()
            toaster.show_toast(title, message, threaded=True, duration=duration)
        return True
    except Exception:
        return False


def _notify_plyer(title: str, message: str, duration: int) -> bool:
    try:
        from plyer import notification  # type: ignore

        notification.notify(title=title, message=message, timeout=duration)
        return True
    except Exception:
        return False


def notify(title: str, message: str, duration: int = 5):
    """Best-effort desktop notification.
    - Try Windows toast (win10toast) then plyer
    - If UI callback registered, call it
    - Always log to file
    """
    _log(title, message)

    # OS desktop routes (configurable)
    if DESKTOP_NOTIFICATIONS_ENABLED:
        if _notify_win_toast(title, message, duration):
            return
        if _notify_plyer(title, message, duration):
            return

    # UI-integrated route
    if _ui_callback:
        try:
            _ui_callback(title, message, duration)
        except Exception:
            pass

    # XSOverlay (VR) route (non-blocking best-effort)
    if XSO_ENABLED:
        try:
            import systems.xsoverlay as xso  # lazy

            # fire and forget in a tiny thread to avoid blocking
            def _send():
                try:
                    xso.push(title, message, duration)
                except Exception:
                    pass

            threading.Thread(target=_send, daemon=True).start()
        except Exception:
            pass

    # Fallback: print
    try:
        print(f"🔔 {title}: {message}")
    except Exception:
        pass
