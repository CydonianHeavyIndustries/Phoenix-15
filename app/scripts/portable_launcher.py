import os
import sys
import time
import urllib.request
from pathlib import Path
import subprocess
import json
import ctypes


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "portable_launcher.log"
STOP_SCRIPT = ROOT / "scripts" / "stop_existing_instances.ps1"


def log(message: str) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"{message}\n")
    except Exception:
        pass


def stop_existing_instances() -> None:
    if os.name != "nt":
        return
    if not STOP_SCRIPT.exists():
        return
    try:
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
        )
        log("stop_existing_ok")
    except Exception as exc:
        log(f"stop_existing_failed:{exc}")


def ping(url: str, timeout: float = 1.0) -> bool:
    try:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=timeout):  # nosec
            return True
    except Exception:
        return False


def resolve_ui_dist() -> Path | None:
    candidates = [
        ROOT / "ui" / "scifiaihud" / "build",
        ROOT / "ui" / "build",
    ]
    for path in candidates:
        if (path / "index.html").exists():
            return path
    return None


def _is_removable_root(path: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        drive = path.drive or path.anchor
        if not drive:
            return False
        root = drive if drive.endswith("\\") else drive + "\\"
        dtype = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))  # type: ignore[attr-defined]
        return int(dtype) == 2
    except Exception:
        return False


def _load_settings() -> dict:
    try:
        settings_path = ROOT / "server" / "data" / "settings.json"
        if settings_path.exists():
            return json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _try_launch_local_install() -> bool:
    settings = _load_settings()
    if not settings.get("usbLocalBootEnabled"):
        return False
    local_path = str(settings.get("usbLocalBootPath") or "").strip()
    if not local_path:
        return False
    local_root = Path(local_path).expanduser().resolve()
    if not local_root.exists():
        return False
    if not _is_removable_root(ROOT):
        return False
    run_target = local_root / "RUN_PHOENIX_15.bat"
    if not run_target.exists():
        run_target = local_root / "app" / "launch_phoenix.bat"
    if not run_target.exists():
        return False
    try:
        log(f"local_boot_redirect:{run_target}")
        subprocess.Popen(["cmd.exe", "/c", str(run_target)], cwd=str(local_root))
        return True
    except Exception as exc:
        log(f"local_boot_failed:{exc}")
        return False


def main() -> int:
    os.chdir(str(ROOT))
    stop_existing_instances()
    env = os.environ.copy()
    if _try_launch_local_install():
        return 0
    ui_dist = resolve_ui_dist()
    if not ui_dist:
        msg = "UI build missing. Expected ui/scifiaihud/build/index.html."
        print(msg)
        log(msg)
        return 1

    env.setdefault("BJORGSUN_UI_DIST", str(ui_dist))
    env.setdefault("BJORGSUN_UI_HOST", "127.0.0.1")
    env.setdefault("BJORGSUN_UI_PORT", "56795")
    env.setdefault("BJORGSUN_UI_WEBVIEW", "1")
    env.setdefault("BJORGSUN_UI_WEBVIEW_ENGINE", "edgechromium")
    env.setdefault("BJORGSUN_UI_HEADLESS", "0")
    env.setdefault("BJORGSUN_UI_STDLOG", str(LOG_DIR / "portable_ui_stdout.log"))
    env.setdefault("BJORGSUN_UI_CRASHLOG", str(LOG_DIR / "portable_ui_crash.log"))
    env.setdefault("BJORGSUN_USER", "Father")
    env.setdefault("BJORGSUN_PASS", "")

    backend_url = env.get("BJORGSUN_BACKEND_URL", "http://127.0.0.1:1326")
    ping_url = backend_url.rstrip("/") + "/ping"
    if not ping(ping_url, timeout=1.0):
        log("backend_not_running_starting")
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.Popen(
                [sys.executable, str(ROOT / "server" / "server.py")],
                cwd=str(ROOT),
                env=env,
                creationflags=creationflags,
            )
        except Exception as exc:
            log(f"backend_spawn_failed: {exc}")
            print("Backend failed to start. Check logs.")
        for _ in range(20):
            if ping(ping_url, timeout=1.0):
                break
            time.sleep(0.5)

    log("launching_start_ui")
    os.execvpe(
        sys.executable,
        [sys.executable, str(ROOT / "scripts" / "start_ui.py")],
        env,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
