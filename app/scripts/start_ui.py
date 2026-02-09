from __future__ import annotations

import contextlib
import importlib
import importlib.machinery
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    def load_dotenv(*_args, **_kwargs):
        return False

try:
    import psutil  # type: ignore
except Exception:
    psutil = None  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
try:
    root_str = str(ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
except Exception:
    pass
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
CRASH_LOG = Path(os.getenv("BJORGSUN_UI_CRASHLOG", str(LOG_DIR / "ui_crash.log")))
STDLOG = Path(os.getenv("BJORGSUN_UI_STDLOG", str(LOG_DIR / "start_ui_stdout.log")))
CORE_RUN_LOG = LOG_DIR / "core_run.log"
BACKEND_LOCK = LOG_DIR / "backend.lock"
FIXME_LOG = LOG_DIR / "Phoenix-15_FIXME_log.log"
CLIENT_LOG = LOG_DIR / "client_errors.log"
PERF_LOG = LOG_DIR / "perf_stats.log"


def _append_run_log(message: str) -> None:
    try:
        ts = datetime.utcnow().isoformat() + "Z"
        with CORE_RUN_LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"{ts} {message}\n")
    except Exception:
        pass


def _log_crash(message: str, exc: Exception | None = None) -> None:
    try:
        ts = datetime.utcnow().isoformat() + "Z"
        with CRASH_LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"[{ts}] {message}\n")
            if exc:
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=handle)
    except Exception:
        pass


def _redirect_stdio() -> None:
    try:
        STDLOG.parent.mkdir(parents=True, exist_ok=True)
        log_handle = STDLOG.open("a", encoding="utf-8")
    except Exception:
        return

    class _Tee:
        def __init__(self, stream, file_handle):
            self.stream = stream
            self.file_handle = file_handle

        def write(self, s):
            try:
                self.stream.write(s)
            except Exception:
                pass
            try:
                self.file_handle.write(s)
                self.file_handle.flush()
            except Exception:
                pass

        def flush(self):
            try:
                self.stream.flush()
            except Exception:
                pass
            try:
                self.file_handle.flush()
            except Exception:
                pass

    sys.stdout = _Tee(sys.stdout, log_handle)
    sys.stderr = _Tee(sys.stderr, log_handle)


def _port_open(host: str, port: int, timeout_s: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _wait_for_port(host: str, port: int, timeout_s: float = 3.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _port_open(host, port, timeout_s=0.4):
            return True
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
    if psutil is not None:
        try:
            return psutil.pid_exists(pid)  # type: ignore[attr-defined]
        except Exception:
            return True
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


def _ensure_backend() -> None:
    auto = os.getenv("BJORGSUN_BACKEND_AUTOSTART", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not auto:
        return
    backend_url = os.getenv("BJORGSUN_BACKEND_URL", "http://127.0.0.1:1326").strip()
    parsed = urlparse(backend_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 1326
    if host not in {"127.0.0.1", "localhost"}:
        return
    lock_pid = _read_backend_lock_pid()
    if lock_pid:
        if _pid_alive(lock_pid):
            if _wait_for_port(host, port, 1.0):
                _append_run_log("backend_autostart_lock_active")
                return
            _append_run_log("backend_autostart_lock_stale_port")
        try:
            BACKEND_LOCK.unlink()
            _append_run_log("backend_autostart_lock_cleared")
        except Exception:
            pass
    if _wait_for_port(host, port, 3.0):
        _append_run_log("backend_autostart_skipped")
        return
    py_exec = ROOT / "venv" / "Scripts" / "python.exe"
    if not py_exec.exists():
        py_exec = Path(sys.executable)
    log_path = LOG_DIR / "backend_stdout_start_ui.log"
    try:
        log_handle = log_path.open("a", encoding="utf-8")
    except Exception:
        log_handle = subprocess.DEVNULL  # type: ignore[assignment]
    try:
        proc = subprocess.Popen(
            [str(py_exec), str(ROOT / "server" / "server.py")],
            cwd=str(ROOT),
            env=os.environ.copy(),
            stdout=log_handle,
            stderr=log_handle,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.pid:
            _write_backend_lock(proc.pid)
        _append_run_log("backend_autostarted")
    except Exception as exc:
        _append_run_log(f"backend_autostart_failed: {exc}")


def _inject_env_config(dist_dir: Path) -> None:
    user = os.getenv("BJORGSUN_USER", "Father")
    password = os.getenv("BJORGSUN_PASS", "")
    backend_url = os.getenv("BJORGSUN_BACKEND_URL", "http://127.0.0.1:1326").rstrip("/")
    payload = {"user": user, "pass": password, "apiBase": backend_url}
    content = (
        "window.__BJ_CFG = "
        + json.dumps(payload)
        + ";\n"
        + "window.addEventListener('error', function(e){\n"
        + "  try {\n"
        + "    fetch('/log/client', {method:'POST', headers:{'Content-Type':'application/json'},"
        + " body: JSON.stringify({message:'window.onerror', detail:(e.message||'') + ' @' +"
        + " (e.filename||'') + ':' + (e.lineno||'')})});\n"
        + "  } catch(_) {}\n"
        + "});\n"
        + "window.addEventListener('unhandledrejection', function(e){\n"
        + "  try {\n"
        + "    fetch('/log/client', {method:'POST', headers:{'Content-Type':'application/json'},"
        + " body: JSON.stringify({message:'unhandledrejection', detail:(e.reason&&e.reason.toString())||''})});\n"
        + "  } catch(_) {}\n"
        + "});\n"
    )
    try:
        (dist_dir / "env-config.js").write_text(content, encoding="utf-8")
    except Exception:
        pass


def _load_runtime_singleton():
    singleton_path = ROOT / "runtime" / "singleton.py"
    try:
        if not singleton_path.exists():
            _append_run_log(f"singleton_missing_path: {singleton_path}")
            return None
        root_str = str(ROOT)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)
        try:
            return importlib.import_module("runtime.singleton")
        except Exception:
            pass
        spec = importlib.util.spec_from_file_location("runtime.singleton", singleton_path)
        if not spec or not spec.loader:
            _append_run_log("singleton_spec_failed")
            return None
        module = importlib.util.module_from_spec(spec)
        if "runtime" not in sys.modules:
            pkg = importlib.util.module_from_spec(importlib.machinery.ModuleSpec("runtime", None))
            pkg.__path__ = [str(ROOT / "runtime")]
            sys.modules["runtime"] = pkg
        sys.modules["runtime.singleton"] = module
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        _append_run_log(f"singleton_import_fallback_failed: {exc}")
        return None


def _write_log(path: Path, entry: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass


def _log_payload(path: Path, label: str, payload: dict) -> None:
    _write_log(
        path,
        {"ts": datetime.utcnow().isoformat() + "Z", "label": label, "payload": payload},
    )


class UiHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, *_args):
        return

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def _send_json(self, data: dict, status: int = 200) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/ping":
            return self._send_json({"ok": True})
        return super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        payload = {}
        if body:
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {"raw": body.decode("utf-8", "ignore")}

        if self.path == "/log/client":
            _log_payload(CLIENT_LOG, "client", payload)
            return self._send_json({"ok": True})
        if self.path == "/log/issue":
            _log_payload(FIXME_LOG, "issue", payload)
            return self._send_json({"ok": True})
        if self.path == "/log/perf":
            _log_payload(PERF_LOG, "perf", payload)
            return self._send_json({"ok": True})
        self._send_json({"ok": False, "error": "Not found"}, status=404)


def _launch_web_ui(dist_dir: Path) -> None:
    env_port = os.getenv("BJORGSUN_UI_PORT", "").strip()
    port = int(env_port) if env_port.isdigit() else 56795
    host = os.getenv("BJORGSUN_UI_HOST", "").strip() or "127.0.0.1"
    display_host = host
    if host in {"0.0.0.0", "::", "[::]"}:
        display_host = "127.0.0.1"

    _inject_env_config(dist_dir)
    _append_run_log("Env config injected for web UI")

    handler = lambda *args, **kwargs: UiHandler(  # noqa: E731
        *args, directory=str(dist_dir), **kwargs
    )
    try:
        srv = ThreadingHTTPServer((host, port), handler)
    except Exception as exc:
        _append_run_log(f"Web UI server failed: {exc}")
        raise

    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    url = f"http://{display_host}:{port}/"
    _append_run_log(f"Web UI server started at http://{host}:{port}/ (open at {url})")

    headless = os.getenv("BJORGSUN_UI_HEADLESS", "").strip().lower() in {"1", "true", "yes"}
    webview_enabled = os.getenv("BJORGSUN_UI_WEBVIEW", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if headless:
        while True:
            time.sleep(1.0)

    try:
        import webview  # type: ignore
    except Exception:
        webview = None
        webview_enabled = False

    def _request_backend_shutdown() -> None:
        try:
            import urllib.request

            backend_url = os.getenv("BJORGSUN_BACKEND_URL", "http://127.0.0.1:1326").rstrip("/")
            req = urllib.request.Request(
                f"{backend_url}/power",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=2)  # nosec
        except Exception:
            pass

    def _spawn_launcher() -> bool:
        candidates = [
            ROOT / "run_tray.bat",
            ROOT / "launch_phoenix.bat",
            ROOT / "run_stack.bat",
            ROOT / "run_desktop.bat",
            ROOT / "run_web_ui.bat",
        ]
        launcher = next((path for path in candidates if path.exists()), None)
        if not launcher:
            _append_run_log("launcher_missing")
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
            _append_run_log("launcher_spawned")
            return True
        except Exception:
            _append_run_log("launcher_spawn_failed")
            return False

    class WindowBridge:
        def __init__(self):
            self.window = None

        def bind(self, window):
            self.window = window

        def minimize(self):
            if self.window:
                self.window.minimize()
            return True

        def hide(self):
            if self.window:
                self.window.hide()
            return True

        def show(self):
            if self.window:
                self.window.show()
            return True

        def exit(self):
            threading.Thread(target=_request_backend_shutdown, daemon=True).start()
            try:
                if self.window:
                    self.window.destroy()
            except Exception:
                pass
            return True

        def close(self):
            return self.exit()

        def start_backend(self):
            threading.Thread(target=_ensure_backend, daemon=True).start()
            return True

        def reboot(self):
            threading.Thread(target=_spawn_launcher, daemon=True).start()
            return True

    if webview_enabled and webview:
        try:
            try:
                webview.settings["DRAG_REGION_SELECTOR"] = ".pywebview-drag-region"
                webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = True
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

            screen = _pick_screen()
            width = int(getattr(screen, "width", 1400)) if screen else 1400
            height = int(getattr(screen, "height", 900)) if screen else 900
            pos_x = int(getattr(screen, "x", 0)) if screen else None
            pos_y = int(getattr(screen, "y", 0)) if screen else None
            bridge = WindowBridge()
            window = webview.create_window(
                "Bjorgsun-26",
                url,
                zoomable=True,
                width=width,
                height=height,
                x=pos_x,
                y=pos_y,
                resizable=True,
                maximized=True,
                frameless=True,
                easy_drag=False,
                js_api=bridge,
                screen=screen,
            )
            bridge.bind(window)

            def _on_start():
                try:
                    if window:
                        window.maximize()
                except Exception:
                    pass

            webview.start(_on_start, gui=os.getenv("BJORGSUN_UI_WEBVIEW_ENGINE", "edgechromium"))
            return
        except Exception as exc:
            _append_run_log(f"webview_launch_failed: {exc}")

    try:
        webbrowser.open(url)
    except Exception:
        pass
    while True:
        time.sleep(1.0)


def run_ui() -> None:
    _redirect_stdio()
    load_dotenv(str(ROOT / ".env"))
    _append_run_log("UI start requested")
    _ensure_backend()
    force = "--force" in sys.argv or os.getenv("BJORGSUN_FORCE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    try:
        from runtime import singleton  # type: ignore
    except Exception as exc:
        _append_run_log(f"singleton_import_failed: {exc}")
        _append_run_log(
            f"singleton_import_debug: root={ROOT} cwd={Path.cwd()} sys_path={sys.path}"
        )
        singleton = _load_runtime_singleton()
        if not singleton:
            raise

    lock = singleton.acquire(force=force)
    if lock == "busy":
        ui_host = os.getenv("BJORGSUN_UI_HOST", "127.0.0.1").strip() or "127.0.0.1"
        ui_port_raw = os.getenv("BJORGSUN_UI_PORT", "").strip()
        ui_port = int(ui_port_raw) if ui_port_raw.isdigit() else 56795
        if ui_host in {"0.0.0.0", "::", "[::]"}:
            ui_host = "127.0.0.1"
        if not _port_open(ui_host, ui_port, timeout_s=0.5):
            _append_run_log("ui_lock_busy_no_port_force")
            lock = singleton.acquire(force=True)
        else:
            print(
                "Bjorgsun-26 UI is already running. Use --force if you truly need another instance."
            )
            return
    singleton.mark_pid()
    singleton.register_release(lock)

    override_dist = os.getenv("BJORGSUN_UI_DIST", "").strip()
    if override_dist:
        dist_dir = Path(override_dist)
    else:
        dist_dir = ROOT / "ui" / "scifiaihud" / "build"
        if not dist_dir.exists():
            dist_dir = ROOT / "ui" / "build"
    if not dist_dir.exists() or not any(dist_dir.glob("index.html")):
        _append_run_log(f"UI build not found at {dist_dir}")
        raise SystemExit("UI build not found.")
    _append_run_log(f"Launching web UI from {dist_dir}")
    _launch_web_ui(dist_dir)
    singleton.release(lock)


if __name__ == "__main__":
    try:
        run_ui()
    except Exception as exc:
        _log_crash("UI crashed at __main__", exc)
        raise
