"""
runtime.singleton
------------------

Centralized single-instance guard so every launcher (start_ui.py,
launch_both.py, PyInstaller entrypoints) can share the same locking logic.

The guard attempts to bind to a fixed localhost port; if that fails it falls
back to a PID lock file to detect stale instances. A small helper class manages
cleanup so callers can simply register it with ``atexit`` and forget about it.
"""

from __future__ import annotations

import atexit
import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional, Union

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - psutil optional
    psutil = None  # type: ignore

try:
    import pygetwindow as _pygw  # type: ignore
except Exception:  # pragma: no cover - optional UI detection
    _pygw = None  # type: ignore

SINGLETON_PORT = 49266
WINDOW_TITLE = "Bjorgsun-26 // Resonant Interface"


def _project_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


LOCK_FILE = os.path.join(_project_root(), "bjorgsun.lock")


@dataclass
class SingletonLock:
    socket_handle: Optional[socket.socket]

    def release(self) -> None:
        try:
            if self.socket_handle:
                self.socket_handle.close()
        except Exception:
            pass
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception:
            pass


def _bind_port() -> Optional[socket.socket]:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", SINGLETON_PORT))
        sock.listen(1)
        return sock
    except OSError:
        return None


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if psutil is not None:
        try:
            return psutil.pid_exists(pid)  # type: ignore[attr-defined]
        except Exception:
            return True
    if os.name == "nt":
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}"], creationflags=0x08000000
            )
            text = out.decode(errors="ignore")
            return str(pid) in text and "No tasks" not in text
        except Exception:
            return True
    try:
        out = subprocess.check_output(["ps", "-p", str(pid)], stderr=subprocess.DEVNULL)
        return str(pid).encode() in out
    except Exception:
        return False


def _lock_file_stale() -> bool:
    try:
        if not os.path.exists(LOCK_FILE):
            return False
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            pid_txt = f.read().strip()
        pid = int(pid_txt) if pid_txt.isdigit() else None
        return not pid or not _is_pid_alive(pid)
    except Exception:
        return False


def _remove_lock_file() -> None:
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


def acquire(
    force: bool = False, window_title: str = WINDOW_TITLE
) -> Union[SingletonLock, str]:
    """
    Attempt to lock the running instance.

    Returns a ``SingletonLock`` object on success, the string ``\"busy\"`` if an
    instance is already running, or raises no exception if force is requested.
    """
    if force:
        return SingletonLock(None)

    sock = _bind_port()
    if sock:
        return SingletonLock(sock)

    if _lock_file_stale():
        _remove_lock_file()
        sock = _bind_port()
        if sock:
            return SingletonLock(sock)

    # If a window is visible, consider the instance active
    if _pygw is not None:
        try:
            wins = _pygw.getWindowsWithTitle(window_title)
            if wins:
                return "busy"
        except Exception:
            return "busy"
    else:
        return "busy"

    # If we can't detect windows but also can't acquire the lock, stay safe.
    return "busy"


def mark_pid(pid: Optional[int] = None) -> None:
    try:
        pid = pid or os.getpid()
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            f.write(str(pid))
    except Exception:
        pass


def release(lock: Optional[SingletonLock]) -> None:
    if isinstance(lock, SingletonLock):
        lock.release()
    else:
        _remove_lock_file()


def register_release(lock: Optional[SingletonLock]) -> None:
    """Convenience helper to auto-clean on interpreter exit."""
    atexit.register(release, lock)
