# -------------------------------------------------------------------------
# start.py — Bjorgsun-26 launcher and system core
# -------------------------------------------------------------------------

import os
import subprocess
import sys
import time
import traceback

# --- emergency crash log hook (catches early PyInstaller/runtime errors) ---
try:
    IS_FROZEN = getattr(sys, "frozen", False)
    BASE_PATH = (
        os.path.dirname(sys.executable) if IS_FROZEN else os.path.dirname(__file__)
    )
    # Add vendor DLLs to search path early (so ctypes/PIL/etc can find dependencies)
    ROOT_DIR = BASE_PATH if IS_FROZEN else os.path.dirname(BASE_PATH)

    # Ensure the project root (and scripts dir when running from source) are importable
    if ROOT_DIR and ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)
    _scripts_dir = os.path.join(ROOT_DIR, "scripts")
    if not IS_FROZEN and os.path.isdir(_scripts_dir) and _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)

    try:
        _dlls = os.path.join(ROOT_DIR, "vendor", "dlls")
        if os.path.isdir(_dlls) and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(_dlls)
    except Exception:
        pass
    logs_base = BASE_PATH if IS_FROZEN else ROOT_DIR or BASE_PATH
    LOGS_DIR = os.path.join(logs_base, "logs")
    os.makedirs(LOGS_DIR, exist_ok=True)
    EMERGENCY_LOG = os.path.join(LOGS_DIR, "early_crash.log")
except Exception:
    EMERGENCY_LOG = os.path.join(os.getcwd(), "early_crash.log")

# --- mirror stdout/stderr to logs for easier troubleshooting ---
try:

    class _Tee:
        def __init__(self, stream, file):
            self.stream = stream
            self.file = file

        def write(self, s):
            try:
                self.stream.write(s)
            except Exception:
                pass
            try:
                self.file.write(s)
                self.file.flush()
            except Exception:
                pass

        def flush(self):
            try:
                self.stream.flush()
            except Exception:
                pass

    _tee_path = os.path.join(LOGS_DIR, "core_run.log")
    _tee_f = open(_tee_path, "a", encoding="utf-8")
    _tee_f.write(f"\n==== Core start {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    sys.stdout = _Tee(sys.stdout, _tee_f)
    sys.stderr = _Tee(sys.stderr, _tee_f)
except Exception:
    pass
# --- resolve base/extraction paths and importability (frozen or source) ---
try:
    EXTRACT_DIR = getattr(sys, "_MEIPASS", None)
    if EXTRACT_DIR:
        # Ensure project packages (runtime, systems, core, ui) are importable
        if EXTRACT_DIR not in sys.path:
            sys.path.insert(0, EXTRACT_DIR)
        internal = os.path.join(EXTRACT_DIR, "_internal")
        if os.path.isdir(internal) and internal not in sys.path:
            sys.path.insert(0, internal)
        # Add vendor DLL search path inside extraction dir (both root and _internal)
        for _cand in [
            os.path.join(EXTRACT_DIR, "vendor", "dlls"),
            os.path.join(internal, "vendor", "dlls"),
        ]:
            try:
                if os.path.isdir(_cand) and hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(_cand)
            except Exception:
                pass
except Exception:
    pass

# --- dynamic runtime imports for modular startup ---
try:
    # Primary: absolute import (Pylance-friendly when run as a script)
    from runtime import boot, coreloop, startup  # type: ignore
except ImportError:
    # Fallback for module/frozen contexts
    try:
        from .runtime import boot, coreloop, startup  # type: ignore
    except Exception as exc:
        print(f"[start] Failed to import runtime modules: {exc}")
        raise


# -------------------------------------------------------------------------
# Crash handler: persistent logging with auto Notepad open
# -------------------------------------------------------------------------
def handle_crash(exc: Exception | None = None):
    try:
        crash_path = os.path.join(LOGS_DIR, "core_crash.log")
        with open(crash_path, "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)

        print(f"⚠️ A fatal error occurred. Details saved to {crash_path}")

        # --- Auto-open Notepad for immediate viewing ---
        try:
            subprocess.Popen(["notepad.exe", crash_path])
        except Exception:
            print(
                "📝 Failed to open Notepad automatically, please open the log manually."
            )

    except Exception as err:
        with open(EMERGENCY_LOG, "w", encoding="utf-8") as f:
            f.write("CRASH LOGGER FAILURE:\n")
            traceback.print_exc(file=f)
            f.write("\n--- original exception ---\n")
            f.write(str(err))
        print(f"💥 Could not write core log. Emergency log saved to {EMERGENCY_LOG}")

        # Attempt to open emergency log in Notepad too
        try:
            subprocess.Popen(["notepad.exe", EMERGENCY_LOG])
        except Exception:
            print("📝 Notepad could not be opened for emergency log either.")

    finally:
        sys.exit(1)


# -------------------------------------------------------------------------
# Safety guard to prevent recursive relaunches
# -------------------------------------------------------------------------
if "launcher_bjorgsun" in os.path.basename(sys.argv[0]).lower():
    print("🛑 Recursive start detected — aborting to prevent loop.")
    sys.exit(0)


# -------------------------------------------------------------------------
# Splash and boot sequence
# -------------------------------------------------------------------------
def splash_screen():
    print("\n⚙️  Initializing Bjorgsun-26 system core...")
    time.sleep(0.8)
    print("💠 Calibrating subsystems...")
    time.sleep(0.6)
    print("🔋 Ley-thread interface stable.")
    time.sleep(0.5)
    print("🧠 Cognitive kernel standing by.\n")
    time.sleep(0.8)


# -------------------------------------------------------------------------
# Main execution
# -------------------------------------------------------------------------
def _run_headless():
    try:
        splash_screen()

        # Core startup sequence
        startup.authenticate()
        boot.boot_all()
        startup.first_greeting()

        # Enter persistent loop
        coreloop.main_loop()

    except KeyboardInterrupt:
        print("\n🧩 Manual shutdown requested.")
        time.sleep(1)

    except Exception as e:
        print(f"⚠️  Runtime exception: {e}")
        handle_crash(e)

    finally:
        print("🔒 Bjorgsun-26 safely powered down.")
        time.sleep(1)


def _run_ui():
    try:
        from . import start_ui as _start_ui
    except ImportError:
        import start_ui as _start_ui
    _start_ui.run_ui()


def _headless_requested():
    flag = os.getenv("BJORGSUN_HEADLESS", "0").strip().lower()
    return flag in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    if _headless_requested():
        _run_headless()
    else:
        _run_ui()
