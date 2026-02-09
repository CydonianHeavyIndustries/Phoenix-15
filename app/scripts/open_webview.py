import json
import os
import socket
import subprocess
import sys
import time
import threading
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "open_webview.log"
BACKEND_LOCK = LOG_DIR / "backend.lock"
MUTEX_NAME = "Global\\Phoenix15Webview"
_MUTEX_HANDLE = None


def log(message: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"{message}\n")
    except Exception:
        pass


def wait_for_port(host: str, port: int, timeout_s: float) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.4):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _read_backend_lock_pid() -> int | None:
    try:
        raw = BACKEND_LOCK.read_text(encoding="utf-8").strip()
        return int(raw) if raw.isdigit() else None
    except Exception:
        return None


def _pid_alive(pid: int) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        import psutil  # type: ignore

        return psutil.pid_exists(pid)  # type: ignore[attr-defined]
    except Exception:
        pass
    if os.name == "nt":
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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


def _write_backend_lock(pid: int) -> None:
    try:
        BACKEND_LOCK.write_text(str(pid), encoding="utf-8")
    except Exception:
        pass


def ensure_server(host: str, port: int) -> None:
    if wait_for_port(host, port, 2.0):
        log("server_already_listening")
        return

    py_exec = ROOT / "venv" / "Scripts" / "python.exe"
    if not py_exec.exists():
        py_exec = Path(sys.executable)
    start_ui = ROOT / "scripts" / "start_ui.py"
    if not start_ui.exists():
        log("start_ui_missing")
        return

    env = os.environ.copy()
    env.setdefault("BJORGSUN_UI_HOST", host)
    env.setdefault("BJORGSUN_UI_PORT", str(port))
    env.setdefault("BJORGSUN_UI_HEADLESS", "1")
    env.setdefault("BJORGSUN_UI_WEBVIEW", "0")
    env.setdefault("BJORGSUN_UI_DIST", str(ROOT / "ui" / "scifiaihud" / "build"))
    env.setdefault("BJORGSUN_UI_STDLOG", str(LOG_DIR / "start_ui_stdout_open_webview.log"))
    env.setdefault("BJORGSUN_UI_CRASHLOG", str(LOG_DIR / "ui_crash_open_webview.log"))

    try:
        subprocess.Popen(
            [str(py_exec), str(start_ui)],
            cwd=str(ROOT),
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        log("start_ui_spawned")
    except Exception:
        log("start_ui_spawn_failed")
        return


def fetch_json(url: str, timeout_s: float = 2.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # nosec
            data = resp.read().decode("utf-8")
            return json.loads(data) if data else {}
    except Exception:
        return {}


def ensure_backend() -> bool:
    backend_url = os.getenv("BJORGSUN_BACKEND_URL", "http://127.0.0.1:1326").strip()
    try:
        from urllib.parse import urlparse

        parsed = urlparse(backend_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 1326
    except Exception:
        host = "127.0.0.1"
        port = 1326
    if host not in {"127.0.0.1", "localhost"}:
        return False
    lock_pid = _read_backend_lock_pid()
    if lock_pid:
        if _pid_alive(lock_pid):
            log("backend_lock_active")
            return True
        try:
            BACKEND_LOCK.unlink()
            log("backend_lock_cleared")
        except Exception:
            pass
    if wait_for_port(host, port, 3.0):
        log("backend_already_listening")
        return True
    py_exec = ROOT / "venv" / "Scripts" / "python.exe"
    if not py_exec.exists():
        py_exec = Path(sys.executable)
    server_script = ROOT / "server" / "server.py"
    if not server_script.exists():
        log("backend_script_missing")
        return False
    env = os.environ.copy()
    log_path = LOG_DIR / "backend_stdout_open_webview.log"
    try:
        log_handle = log_path.open("a", encoding="utf-8")
    except Exception:
        log_handle = subprocess.DEVNULL  # type: ignore[assignment]
    try:
        proc = subprocess.Popen(
            [str(py_exec), str(server_script)],
            cwd=str(ROOT),
            env=env,
            stdout=log_handle,
            stderr=log_handle,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.pid:
            _write_backend_lock(proc.pid)
        log("backend_spawned")
        return True
    except Exception:
        log("backend_spawn_failed")
        return False


def spawn_launcher() -> bool:
    candidates = [
        ROOT / "run_tray.bat",
        ROOT / "launch_phoenix.bat",
        ROOT / "run_stack.bat",
        ROOT / "run_desktop.bat",
        ROOT / "run_web_ui.bat",
    ]
    launcher = next((path for path in candidates if path.exists()), None)
    if not launcher:
        log("launcher_missing")
        return False
    try:
        if os.name == "nt":
            launcher_str = str(launcher).replace("'", "''")
            workdir = str(ROOT).replace("'", "''")
            ps_script = (
                "Start-Sleep -Seconds 2;"
                f" Start-Process -FilePath \"cmd.exe\" -ArgumentList \"/c\", \"{launcher_str}\""
                f" -WorkingDirectory \"{workdir}\""
            )
            subprocess.Popen(
                ["powershell", "-NoLogo", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["/bin/sh", "-c", f"sleep 2; '{launcher}'"],
                cwd=str(ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        log("launcher_spawned")
        return True
    except Exception:
        log("launcher_spawn_failed")
        return False


def _read_json(path: Path) -> dict:
    try:
        if not path.exists():
            return {}
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def _read_local_settings() -> tuple[bool, list[str]]:
    settings_path = ROOT / "server" / "data" / "settings.json"
    settings = _read_json(settings_path)
    enabled = bool(settings.get("desktopViewEnabled"))
    raw_ids = settings.get("desktopViewMonitors")
    ids = [str(item) for item in raw_ids] if isinstance(raw_ids, list) else []
    return enabled, [item for item in ids if item]


def _get_system_monitors_local() -> list[dict]:
    if os.name != "nt":
        return []
    try:
        import ctypes

        user32 = ctypes.windll.user32
        monitors: list[dict] = []

        class _RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        class _MONITORINFOEX(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("rcMonitor", _RECT),
                ("rcWork", _RECT),
                ("dwFlags", ctypes.c_ulong),
                ("szDevice", ctypes.c_wchar * 32),
            ]

        MONITORINFOF_PRIMARY = 1

        def _enum_proc(hmonitor, hdc, rect_ptr, lparam):
            info = _MONITORINFOEX()
            info.cbSize = ctypes.sizeof(_MONITORINFOEX)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                rect = info.rcMonitor
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                device = info.szDevice.strip()
                monitors.append(
                    {
                        "id": device or f"monitor-{len(monitors) + 1}",
                        "label": device or f"Display {len(monitors) + 1}",
                        "x": rect.left,
                        "y": rect.top,
                        "width": width,
                        "height": height,
                        "primary": bool(info.dwFlags & MONITORINFOF_PRIMARY),
                        "orientation": "portrait" if height > width else "landscape",
                    }
                )
            return True

        enum_proc = ctypes.WINFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_RECT), ctypes.c_long
        )(_enum_proc)
        user32.EnumDisplayMonitors(0, 0, enum_proc, 0)
        return monitors
    except Exception:
        return []


def _compute_desktop_bounds(
    enabled: bool, monitor_ids: list[str], monitors: list[dict]
) -> tuple[int, int, int, int] | None:
    if not enabled or not monitors:
        return None
    selected = [m for m in monitors if m.get("id") in monitor_ids]
    if not selected:
        primary = next((m for m in monitors if m.get("primary")), None)
        selected = [primary] if primary else monitors[:1]
    if not selected:
        return None
    left = min(monitor.get("x", 0) or 0 for monitor in selected)
    top = min(monitor.get("y", 0) or 0 for monitor in selected)
    right = max(
        (monitor.get("x", 0) or 0) + (monitor.get("width", 0) or 0) for monitor in selected
    )
    bottom = max(
        (monitor.get("y", 0) or 0) + (monitor.get("height", 0) or 0) for monitor in selected
    )
    width = max(600, right - left)
    height = max(500, bottom - top)
    return int(left), int(top), int(width), int(height)


def _pick_desktop_monitors(
    enabled: bool, monitor_ids: list[str], monitors: list[dict]
) -> list[dict]:
    if not enabled or not monitors:
        return []
    selected = [m for m in monitors if m.get("id") in monitor_ids]
    if not selected:
        primary = next((m for m in monitors if m.get("primary")), None)
        selected = [primary] if primary else monitors[:1]
    return selected


def _bounds_from_monitor(monitor: dict) -> tuple[int, int, int, int] | None:
    try:
        x = int(monitor.get("x", 0) or 0)
        y = int(monitor.get("y", 0) or 0)
        width = int(monitor.get("width", 0) or 0)
        height = int(monitor.get("height", 0) or 0)
        if width <= 0 or height <= 0:
            return None
        return x, y, width, height
    except Exception:
        return None


def _load_desktop_view_state(backend_url: str) -> tuple[bool, list[str], list[dict]]:
    enabled = False
    ids: list[str] = []
    monitors: list[dict] = []
    try:
        settings = fetch_json(f"{backend_url}/settings/get")
        if isinstance(settings, dict):
            enabled = bool(settings.get("desktopViewEnabled"))
            stored_ids = settings.get("desktopViewMonitors")
            if isinstance(stored_ids, list):
                ids = [str(item) for item in stored_ids if item]
    except Exception:
        pass
    if not ids or not enabled:
        local_enabled, local_ids = _read_local_settings()
        if local_enabled:
            enabled = True
        if local_ids:
            ids = local_ids
    try:
        monitors_payload = fetch_json(f"{backend_url}/system/monitors")
        if isinstance(monitors_payload, dict):
            monitors = monitors_payload.get("monitors", []) or []
    except Exception:
        monitors = []
    if not monitors:
        monitors = _get_system_monitors_local()
    return enabled, ids, monitors


def main() -> None:
    host = os.getenv("BJORGSUN_UI_HOST", "127.0.0.1").strip() or "127.0.0.1"
    if host in {"0.0.0.0", "::", "[::]"}:
        host = "127.0.0.1"
    port = os.getenv("BJORGSUN_UI_PORT", "56795").strip() or "56795"
    port_num = int(port)
    title = os.getenv("BJORGSUN_UI_TITLE", "Bjorgsun-26").strip() or "Bjorgsun-26"
    engine = os.getenv("BJORGSUN_UI_WEBVIEW_ENGINE", "edgechromium").strip() or None
    url = f"http://{host}:{port}/"
    if os.name == "nt":
        try:
            import ctypes

            global _MUTEX_HANDLE
            _MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(None, True, MUTEX_NAME)
            if ctypes.windll.kernel32.GetLastError() == 183:
                log("webview_instance_exists")
                return
        except Exception:
            log("webview_instance_check_failed")

    try:
        ensure_server(host, port_num)
    except Exception:
        log("ensure_server_failed")
    try:
        ensure_backend()
    except Exception:
        log("ensure_backend_failed")

    backend_url = os.getenv("BJORGSUN_BACKEND_URL", "http://127.0.0.1:1326").rstrip("/")
    desktop_view_enabled, desktop_view_ids, desktop_view_monitors = _load_desktop_view_state(
        backend_url
    )
    desktop_disable = os.getenv("BJORGSUN_DESKTOP_DISABLED", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    force_single = os.getenv("BJORGSUN_DESKTOP_SINGLE", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if desktop_disable:
        desktop_view_enabled = False
        desktop_view_ids = []
    if force_single:
        desktop_view_enabled = False
        desktop_view_ids = []
    selected_monitors = _pick_desktop_monitors(
        desktop_view_enabled, desktop_view_ids, desktop_view_monitors
    )
    if selected_monitors:
        selected_monitors.sort(key=lambda item: 0 if item.get("primary") else 1)
        if force_single and len(selected_monitors) > 1:
            selected_monitors = [selected_monitors[0]]
    multi_window = len(selected_monitors) > 1
    desktop_bounds = None
    if not multi_window:
        desktop_bounds = _compute_desktop_bounds(
            desktop_view_enabled, desktop_view_ids, desktop_view_monitors
        )

    try:
        import webview  # type: ignore
    except Exception:
        webview = None

    if webview:
        try:
            webview.settings["DRAG_REGION_SELECTOR"] = ".pywebview-drag-region"
            webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = True
        except Exception:
            pass

        def _request_backend_shutdown() -> None:
            try:
                import urllib.request

                url = os.getenv("BJORGSUN_BACKEND_URL", "http://127.0.0.1:1326").rstrip("/")
                req = urllib.request.Request(
                    f"{url}/power",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=2)  # nosec
            except Exception:
                pass

        def _pick_screen():
            try:
                screens = list(getattr(webview, "screens", []) or [])
            except Exception:
                screens = []
            if not screens:
                return None
            for screen in screens:
                try:
                    if (
                        screen.x <= 0 <= screen.x + screen.width
                        and screen.y <= 0 <= screen.y + screen.height
                    ):
                        return screen
                except Exception:
                    continue
            return max(
                screens, key=lambda s: getattr(s, "width", 0) * getattr(s, "height", 0)
            )

        def _force_window_bounds(win, bounds=None, screen=None):
            try:
                if bounds:
                    win.move(int(bounds[0]), int(bounds[1]))
                    win.resize(int(bounds[2]), int(bounds[3]))
                    return
                if desktop_bounds:
                    win.move(int(desktop_bounds[0]), int(desktop_bounds[1]))
                    win.resize(int(desktop_bounds[2]), int(desktop_bounds[3]))
                    return
                if screen is not None:
                    win.move(int(screen.x), int(screen.y))
                    win.resize(int(screen.width), int(screen.height))
                win.maximize()
            except Exception:
                pass

        window_refs: list = []

        class WindowBridge:
            def __init__(self, bounds=None, screen=None):
                self.window = None
                self.bounds = bounds
                self.screen = screen

            def bind(self, window):
                self.window = window

            def minimize(self):
                if self.window:
                    self.window.minimize()

            def hide(self):
                if self.window:
                    self.window.hide()

            def show(self):
                if self.window:
                    self.window.show()
                    _force_window_bounds(self.window, self.bounds, self.screen or _pick_screen())

            def exit(self):
                threading.Thread(target=_request_backend_shutdown, daemon=True).start()
                try:
                    for win in list(window_refs):
                        win.destroy()
                except Exception:
                    pass
                try:
                    os._exit(0)
                except Exception:
                    pass

            def start_backend(self):
                threading.Thread(target=ensure_backend, daemon=True).start()
                return True

            def reboot(self):
                threading.Thread(target=spawn_launcher, daemon=True).start()
                return True

        try:
            placeholder = f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <style>
      body {{
        margin: 0;
        font-family: "Segoe UI", sans-serif;
        background: #0b1016;
        color: #d9f7ff;
        display: grid;
        place-items: center;
        height: 100vh;
      }}
      .card {{
        padding: 24px 28px;
        border: 1px solid rgba(62, 242, 224, 0.3);
        border-radius: 14px;
        background: rgba(9, 22, 34, 0.85);
        box-shadow: 0 18px 60px rgba(2, 8, 16, 0.7);
        text-align: center;
      }}
      .title {{
        text-transform: uppercase;
        letter-spacing: 0.2em;
        font-size: 0.9rem;
        margin-bottom: 10px;
      }}
      .hint {{
        color: rgba(217, 247, 255, 0.6);
        font-size: 0.8rem;
      }}
    </style>
  </head>
  <body class="pywebview-drag-region">
    <div class="card">
      <div class="title">Starting Bjorgsun-26</div>
      <div class="hint">Bringing the UI online...</div>
    </div>
  </body>
</html>
"""
            window_meta: list[tuple[object, tuple[int, int, int, int] | None, str, str]] = []

            def _create_window(bounds=None, screen=None, label="", display_mode="main"):
                bridge = WindowBridge(bounds, screen)
                width = 1400
                height = 900
                pos_x = None
                pos_y = None
                if bounds:
                    pos_x, pos_y, width, height = bounds
                elif screen:
                    width = int(getattr(screen, "width", width))
                    height = int(getattr(screen, "height", height))
                    pos_x = int(getattr(screen, "x", 0))
                    pos_y = int(getattr(screen, "y", 0))
                window = webview.create_window(
                    title if not label else f"{title} - {label}",
                    html=placeholder,
                    zoomable=True,
                    width=width,
                    height=height,
                    x=pos_x,
                    y=pos_y,
                    resizable=True,
                    maximized=False if bounds else True,
                    frameless=True,
                    easy_drag=False,
                    js_api=bridge,
                    screen=screen,
                )
                bridge.bind(window)
                window_refs.append(window)
                window_meta.append((window, bounds, label, display_mode))
                try:
                    window.events.shown += lambda w=window, b=bounds, s=screen: _force_window_bounds(
                        w, b, s
                    )
                except Exception:
                    pass
                return window

            if multi_window:
                for idx, monitor in enumerate(selected_monitors):
                    bounds = _bounds_from_monitor(monitor)
                    if not bounds:
                        continue
                    label = monitor.get("label") or monitor.get("id") or "Display"
                    mode = "main" if idx == 0 else "secondary"
                    _create_window(bounds=bounds, label=label, display_mode=mode)
            else:
                screen = _pick_screen() if not desktop_bounds else None
                bounds = desktop_bounds
                if not bounds and screen:
                    bounds = (
                        int(getattr(screen, "x", 0)),
                        int(getattr(screen, "y", 0)),
                        int(getattr(screen, "width", 1400)),
                        int(getattr(screen, "height", 900)),
                    )
                _create_window(bounds=bounds, screen=screen, display_mode="main")

            def _load_when_ready(win, bounds, label, display_mode):
                def _load_window():
                    load_url = url
                    if display_mode != "main":
                        base = url.rstrip("/")
                        load_url = f"{base}/secondary.html"
                    win.load_url(load_url)
                    log("webview_loaded" if not label else f"webview_loaded:{label}")

                if wait_for_port(host, port_num, 25.0):
                    try:
                        if not multi_window and not force_single:
                            refreshed = _load_desktop_view_state(backend_url)
                            refreshed_bounds = _compute_desktop_bounds(*refreshed)
                            if refreshed_bounds:
                                win.move(int(refreshed_bounds[0]), int(refreshed_bounds[1]))
                                win.resize(int(refreshed_bounds[2]), int(refreshed_bounds[3]))
                        _load_window()
                        return
                    except Exception:
                        log("webview_load_failed")
                win.load_html(
                    "<html><body style='font-family:Segoe UI; background:#0b1016; color:#d9f7ff; display:grid; place-items:center; height:100vh;'>"
                    "<div style='text-align:center;'>UI server not responding. Check logs in app\\\\logs.</div>"
                    "</body></html>"
                )
                log("webview_timeout" if not label else f"webview_timeout:{label}")
                def _late_retry():
                    if wait_for_port(host, port_num, 30.0):
                        try:
                            _load_window()
                            log("webview_loaded_late" if not label else f"webview_loaded_late:{label}")
                        except Exception:
                            log("webview_late_load_failed" if not label else f"webview_late_load_failed:{label}")
                threading.Thread(target=_late_retry, daemon=True).start()

            def _on_start():
                for win, bounds, label, display_mode in window_meta:
                    _force_window_bounds(win, bounds)
                    threading.Thread(
                        target=_load_when_ready, args=(win, bounds, label, display_mode), daemon=True
                    ).start()

            webview.start(_on_start, gui=engine or None)
            return
        except Exception:
            log("webview_launch_failed")

    try:
        if wait_for_port(host, port_num, 25.0):
            webbrowser.open(url)
            return
        log("browser_timeout")
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    main()
