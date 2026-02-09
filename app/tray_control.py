from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None


ROOT = Path(__file__).resolve().parent
if load_dotenv:
    try:
        load_dotenv(str(ROOT / ".env"))
    except Exception:
        pass
VENV_PY = ROOT / "venv" / "Scripts" / "python.exe"
VENV_PYW = ROOT / "venv" / "Scripts" / "pythonw.exe"
WEBVIEW_SCRIPT = ROOT / "scripts" / "open_webview.py"
ICON_PATH = ROOT / "NewBjorgIcon.ico"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True, parents=True)
LOG_FILE = LOG_DIR / "tray_control.log"
STOP_SCRIPT = ROOT / "scripts" / "stop_existing_instances.ps1"
MUTEX_NAME = "Global\\Phoenix15Tray"
_MUTEX_HANDLE = None
LOCK_FILE = ROOT / "bjorgsun.lock"


def log(message: str, exc: Exception | None = None) -> None:
    try:
        LOG_DIR.mkdir(exist_ok=True, parents=True)
        ts = datetime.utcnow().isoformat() + "Z"
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"[{ts}] {message}\n")
            if exc:
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=handle)
    except Exception:
        pass


def stop_existing_instances() -> None:
    if os.name != "nt":
        return
    if not STOP_SCRIPT.exists():
        return
    try:
        log("tray_stop_existing_start")
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(STOP_SCRIPT),
                "-ExcludePid",
                str(os.getpid()),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
        log("tray_stop_existing_ok")
    except subprocess.TimeoutExpired as exc:
        log("tray_stop_existing_timeout", exc)
    except Exception as exc:
        log("tray_stop_existing_failed", exc)


def _port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _clear_stale_ui_lock() -> None:
    if not LOCK_FILE.exists():
        return
    if _port_open("127.0.0.1", DEFAULT_UI_PORT):
        return
    try:
        LOCK_FILE.unlink()
        log("tray_lockfile_cleared")
    except Exception:
        log("tray_lockfile_clear_failed")


try:
    import pystray  # type: ignore
    from PIL import Image  # type: ignore
except Exception as exc:
    pystray = None  # type: ignore
    Image = None  # type: ignore
    log("tray_import_failed", exc)

DEFAULT_UI_PORT = int(os.getenv("BJORGSUN_UI_PORT", "56795"))
DEFAULT_UI_HOST = os.getenv("BJORGSUN_UI_HOST", "0.0.0.0")
AUTO_OPEN = os.getenv("BJORGSUN_TRAY_AUTO_OPEN", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


class ProcGroup:
    def __init__(self) -> None:
        self.server: Optional[subprocess.Popen] = None
        self.ui: Optional[subprocess.Popen] = None

    def stop(self):
        for p in [self.server, self.ui]:
            if p and p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=5)
                except Exception:
                    pass
        self.server = None
        self.ui = None

    def is_running(self) -> bool:
        return any(p and p.poll() is None for p in [self.server, self.ui])


procs = ProcGroup()


def start_processes(icon):
    if procs.is_running():
        log("tray_start_skipped", None)
        return

    log("tray_start_begin")
    if os.getenv("PHOENIX_TRAY_CLOSE_EXISTING", "1").strip() == "1":
        stop_existing_instances()
        log("tray_stop_existing_sync")
    else:
        log("tray_stop_existing_skipped")

    env = os.environ.copy()
    env.setdefault("BJORGSUN_UI_HOST", DEFAULT_UI_HOST)
    env.setdefault("BJORGSUN_UI_PORT", str(DEFAULT_UI_PORT))
    env.setdefault("BJORGSUN_UI_WEBVIEW", "0")
    env.setdefault("BJORGSUN_UI_HEADLESS", "1")
    env.setdefault("BJORGSUN_UI_STDLOG", str(LOG_DIR / "start_ui_stdout_tray.log"))
    env.setdefault("BJORGSUN_UI_CRASHLOG", str(LOG_DIR / "ui_crash_tray.log"))
    env.setdefault("BJORGSUN_UI_DIST", str(ROOT / "ui" / "scifiaihud" / "build"))
    env.setdefault("BJORGSUN_USER", "Father")
    env.setdefault("BJORGSUN_PASS", "")
    _clear_stale_ui_lock()

    # Ollama models path
    user_ollama = Path.home() / ".ollama" / "models"
    if user_ollama.exists():
        env.setdefault("OLLAMA_MODELS", str(user_ollama))

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    # Start backend
    if _port_open("127.0.0.1", 1326):
        log("tray_backend_already_running")
    else:
        try:
            procs.server = subprocess.Popen(
                [str(VENV_PY), str(ROOT / "server" / "server.py")],
                cwd=str(ROOT),
                env=env,
                creationflags=creationflags,
            )
            log("tray_backend_started")
        except Exception as exc:
            log("tray_backend_failed", exc)

    try:
        procs.ui = subprocess.Popen(
            [str(VENV_PY), str(ROOT / "scripts" / "start_ui.py")],
            cwd=str(ROOT),
            env=env,
            creationflags=creationflags,
        )
        log("tray_ui_started")
    except Exception as exc:
        log("tray_ui_failed", exc)


def stop_processes(icon):
    procs.stop()
    log("tray_processes_stopped")


def open_ui(icon):
    log("tray_open_ui_begin")
    if not procs.is_running():
        start_processes(icon)
        time.sleep(1.0)

    url = f"http://127.0.0.1:{DEFAULT_UI_PORT}/"
    env = os.environ.copy()
    env.setdefault("BJORGSUN_UI_HOST", DEFAULT_UI_HOST)
    env.setdefault("BJORGSUN_UI_PORT", str(DEFAULT_UI_PORT))
    env.setdefault("BJORGSUN_UI_WEBVIEW_ENGINE", "edgechromium")
    py_exec = VENV_PYW if VENV_PYW.exists() else VENV_PY
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    try:
        if WEBVIEW_SCRIPT.exists():
            subprocess.Popen(
                [str(py_exec), str(WEBVIEW_SCRIPT)],
                cwd=str(ROOT),
                env=env,
                creationflags=creationflags,
            )
            log("tray_open_ui_webview")
        else:
            webbrowser.open(url)
            log("tray_open_ui_browser")
    except Exception as exc:
        log("tray_open_ui_failed", exc)


def quit_app(icon):
    try:
        url = os.getenv("BJORGSUN_BACKEND_URL", "http://127.0.0.1:1326").rstrip("/")
        req = urllib.request.Request(
            f"{url}/power",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2)  # nosec
        log("tray_power_requested")
    except Exception:
        procs.stop()
    icon.stop()
    log("tray_quit")


def create_image():
    if Image is None:
        return None
    if ICON_PATH.exists():
        return Image.open(str(ICON_PATH))
    img = Image.new("RGB", (64, 64), (60, 60, 60))
    return img


def build_menu(icon):
    return pystray.Menu(
        pystray.MenuItem("Start Bjorgsun-26", lambda _icon, _item: start_processes(_icon)),
        pystray.MenuItem("Stop Bjorgsun-26", lambda _icon, _item: stop_processes(_icon)),
        pystray.MenuItem("Open UI", lambda _icon, _item: open_ui(_icon)),
        pystray.MenuItem("Quit", lambda _icon, _item: quit_app(_icon)),
    )


def _spawn_open_webview() -> None:
    env = os.environ.copy()
    env.setdefault("BJORGSUN_UI_HOST", DEFAULT_UI_HOST)
    env.setdefault("BJORGSUN_UI_PORT", str(DEFAULT_UI_PORT))
    env.setdefault("BJORGSUN_UI_WEBVIEW_ENGINE", "edgechromium")
    py_exec = VENV_PYW if VENV_PYW.exists() else VENV_PY
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    try:
        if WEBVIEW_SCRIPT.exists():
            subprocess.Popen(
                [str(py_exec), str(WEBVIEW_SCRIPT)],
                cwd=str(ROOT),
                env=env,
                creationflags=creationflags,
            )
            log("tray_instance_open_ui")
    except Exception as exc:
        log("tray_instance_open_ui_failed", exc)


def main():
    log(f"tray_starting exe={sys.executable} cwd={os.getcwd()}")
    if not VENV_PY.exists():
        log(f"venv_python_missing: {VENV_PY}")
        raise SystemExit(f"venv Python not found at {VENV_PY}")
    if pystray is None or Image is None:
        log("tray_missing_pystray")
        raise SystemExit("pystray/PIL not available in venv")
    if os.name == "nt":
        try:
            import ctypes
            global _MUTEX_HANDLE
            _MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(None, True, MUTEX_NAME)
            if ctypes.windll.kernel32.GetLastError() == 183:
                log("tray_instance_exists")
                _spawn_open_webview()
                return
        except Exception as exc:
            log("tray_instance_check_failed", exc)

    icon = pystray.Icon("Bjorgsun-26", create_image(), "Bjorgsun-26", menu=build_menu(None))
    # pystray Icon requires menu constructed after icon creation; rebuild with icon bound
    icon.menu = build_menu(icon)

    # Start processes immediately
    log("tray_start_processes")
    start_processes(icon)
    if AUTO_OPEN:
        log("tray_auto_open_scheduled")
        try:
            time.sleep(1.5)
            open_ui(icon)
        except Exception as exc:
            log("tray_auto_open_failed", exc)

    icon.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log("tray_crash", exc)
        raise
