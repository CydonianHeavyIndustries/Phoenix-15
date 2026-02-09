"""
Tablet Agent bootstrapper.

Responsibilities (initial stub):
- Detect a connected tablet via adb.
- Capture device metadata (model, codename, Android version, storage).
- Persist status/prompt files so the UI + launchers can coordinate stable/dev mode.
- Provide groundwork for the future Samsung custom OS + fallback workflow.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "logs" / "tablet_agent.log"
STATUS_PATH = ROOT / "data" / "tablet_status.json"
PROMPT_PATH = ROOT / "data" / "tablet_prompt.json"
CHOICE_PATH = ROOT / "data" / "tablet_mode_choice.json"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
REMOTE_TABLET_DIR = "/sdcard/Bjorgsun-hub"
REMOTE_PROMPT_PATH = f"{REMOTE_TABLET_DIR}/tablet_prompt.json"
REMOTE_CHOICE_PATH = f"{REMOTE_TABLET_DIR}/tablet_mode_choice.json"

ADB_CANDIDATES: List[Path] = []
for candidate in (
    os.getenv("ADB_PATH"),
    ROOT / "platform-tools" / "adb.exe",
    ROOT / "platform-tools" / "adb",
):
    if candidate:
        p = Path(candidate)
        if p.exists():
            ADB_CANDIDATES.append(p)

if not ADB_CANDIDATES:
    from shutil import which

    maybe = which("adb")
    if maybe:
        ADB_CANDIDATES.append(Path(maybe))


def log(msg: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%fZ")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _run_adb(args: List[str], timeout: int = 10) -> subprocess.CompletedProcess:
    if not ADB_CANDIDATES:
        raise RuntimeError("adb binary not found; set ADB_PATH or install platform-tools.")
    cmd = [str(ADB_CANDIDATES[0])] + args
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        text=True,
    )


def list_devices() -> List[str]:
    proc = _run_adb(["devices"])
    devices: List[str] = []
    for line in proc.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        if line.endswith("device"):
            serial = line.split("\t", 1)[0]
            devices.append(serial)
    return devices


def adb_shell(serial: str, command: str) -> str:
    proc = _run_adb(["-s", serial, "shell", command])
    return proc.stdout.strip()


def get_prop(serial: str, prop: str) -> str:
    return adb_shell(serial, f"getprop {prop}").strip()


def parse_storage(serial: str) -> Dict[str, str]:
    output = adb_shell(serial, "df -h /data")
    lines = [ln for ln in output.splitlines() if ln and not ln.startswith("Filesystem")]
    if not lines:
        return {}
    try:
        parts = lines[0].split()
        return {"size": parts[1], "used": parts[2], "available": parts[3], "use_pct": parts[4]}
    except Exception:
        return {}


@dataclass
class TabletInfo:
    serial: str
    brand: str
    model: str
    device: str
    hardware: str
    android_version: str
    sdk: str
    abi: str
    build_id: str
    storage: Dict[str, str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "serial": self.serial,
            "brand": self.brand,
            "model": self.model,
            "device": self.device,
            "hardware": self.hardware,
            "android_version": self.android_version,
            "sdk": self.sdk,
            "abi": self.abi,
            "build_id": self.build_id,
            "storage": self.storage,
        }


def inspect_tablet(serial: str) -> TabletInfo:
    props = {
        "brand": get_prop(serial, "ro.product.brand") or "unknown",
        "model": get_prop(serial, "ro.product.model") or serial,
        "device": get_prop(serial, "ro.product.device") or "unknown",
        "hardware": get_prop(serial, "ro.hardware") or "unknown",
        "android_version": get_prop(serial, "ro.build.version.release") or "unknown",
        "sdk": get_prop(serial, "ro.build.version.sdk") or "unknown",
        "abi": get_prop(serial, "ro.product.cpu.abi") or "unknown",
        "build_id": get_prop(serial, "ro.build.display.id") or "unknown",
    }
    storage = parse_storage(serial)
    return TabletInfo(
        serial=serial,
        storage=storage,
        **props,
    )


def _write_json(path: Path, payload: Dict[str, object]) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    tmp.replace(path)


class TabletAgent:
    def __init__(self, poll_interval: int = 5) -> None:
        self.poll_interval = poll_interval
        self.current_serial: Optional[str] = None

    def run(self) -> None:
        if not ADB_CANDIDATES:
            log("adb not available; tablet agent cannot start.")
            return
        log(f"Tablet agent watching via {ADB_CANDIDATES[0]}")
        try:
            while True:
                self._tick()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            log("Tablet agent shutting down (Ctrl+C).")

    def _tick(self) -> None:
        devices = list_devices()
        if not devices:
            if self.current_serial:
                log("Tablet disconnected.")
                self.current_serial = None
                self._write_status({"connected": False, "timestamp": self._now()})
            return
        serial = devices[0]
        if serial != self.current_serial:
            self.current_serial = serial
            self._handle_attach(serial)
        else:
            self._pull_remote_choice(serial)

    def _handle_attach(self, serial: str) -> None:
        log(f"Tablet detected: {serial}")
        try:
            info = inspect_tablet(serial)
        except Exception as exc:
            log(f"Failed to inspect tablet {serial}: {exc}")
            return
        payload = {
            "connected": True,
            "timestamp": self._now(),
            "tablet": info.to_dict(),
        }
        self._write_status(payload)
        self._write_prompt(info)
        self._mirror_prompt_to_tablet(serial)
        self._pull_remote_choice(serial)

    def _write_status(self, payload: Dict[str, object]) -> None:
        try:
            _write_json(STATUS_PATH, payload)
        except Exception as exc:
            log(f"Failed writing status: {exc}")

    def _write_prompt(self, info: TabletInfo) -> None:
        prompt = {
            "timestamp": self._now(),
            "tablet": info.to_dict(),
            "mode_request": {
                "default": "stable",
                "options": [
                    {"id": "stable", "label": "Stable (release/1.0.0)", "description": "Prefer E:\\Bjorgsun-26"},
                    {"id": "dev", "label": "Dev (Bjorgsun26EXE)", "description": "Use experiments / logging-heavy build"},
                ],
                "status": "awaiting",
            },
            "notes": "Tablet agent awaiting UI confirmation. Update tablet_mode_choice.json when user picks.",
        }
        try:
            _write_json(PROMPT_PATH, prompt)
            log(f"Mode prompt issued for {info.model} ({info.serial}).")
        except Exception as exc:
            log(f"Failed writing prompt: {exc}")
        # Default to stable unless an override file appears.
        if not CHOICE_PATH.exists():
            choice = {
                "selected_mode": "stable",
                "reason": "default",
                "timestamp": self._now(),
            }
            try:
                _write_json(CHOICE_PATH, choice)
            except Exception:
                pass

    def _mirror_prompt_to_tablet(self, serial: str) -> None:
        try:
            adb_shell(serial, f"mkdir -p {REMOTE_TABLET_DIR}")
            _run_adb(
                ["-s", serial, "push", str(PROMPT_PATH), REMOTE_PROMPT_PATH],
                timeout=10,
            )
            log("Prompt pushed to tablet storage.")
        except Exception as exc:
            log(f"Failed to mirror prompt to tablet: {exc}")

    def _pull_remote_choice(self, serial: str) -> None:
        tmp = CHOICE_PATH.with_suffix(".tablet")
        try:
            proc = _run_adb(
                ["-s", serial, "pull", REMOTE_CHOICE_PATH, str(tmp)], timeout=10
            )
        except Exception as exc:
            log(f"Choice pull error: {exc}")
            return
        if proc.returncode != 0:
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
            return
        try:
            tmp.replace(CHOICE_PATH)
            log("Tablet choice pulled from device.")
        except Exception as exc:
            log(f"Failed to update local choice file: {exc}")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


if __name__ == "__main__":
    agent = TabletAgent()
    agent.run()

