import os
import subprocess
import sys
import time

import psutil

# ---------------------------------------------------------------------
# Safe unified launcher for Bjorgsun-26
# ---------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# launch_cli.py has moved under scripts/, so start.py is alongside it
START_SCRIPT = os.path.join(BASE_DIR, "start.py")
LOCK_FILE = os.path.join(BASE_DIR, "bjorgsun.lock")
PROCESS_TAG = "Bjorgsun-26"


def already_running():
    """Detect existing Bjorgsun-26 instances and prevent duplicates."""
    current_pid = os.getpid()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(proc.info.get("cmdline") or [])
            if proc.pid != current_pid and PROCESS_TAG.lower() in cmd.lower():
                return proc.pid
        except Exception:
            pass
    return None


def close_instance(pid: int):
    """Gracefully close any existing Bjorgsun-26 instance."""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except psutil.TimeoutExpired:
            proc.terminate()
        print(f"🩵 Closed previous Bjorgsun-26 instance (PID {pid}).")
    except Exception as e:
        print(f"⚠️ Unable to close existing instance: {e}")


def main():
    existing = already_running()
    if existing:
        print(f"⚠️ Bjorgsun-26 is already running (PID {existing}).")
        user = (
            input("Would you like to close it safely and start fresh? [y/N]: ")
            .strip()
            .lower()
        )
        if user == "y":
            close_instance(existing)
        else:
            print("🟡 Launch canceled.")
            time.sleep(2)
            return

    # Lock file
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    try:
        print("⚙️ Launching Bjorgsun-26 system core and interface...")
        subprocess.run([sys.executable, START_SCRIPT])
    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
        print("🔒 Lock released. System shutdown complete.")


if __name__ == "__main__":
    main()
