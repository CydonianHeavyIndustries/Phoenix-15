"""
setup_audio_profile.py — One‑shot audio setup for Bjorgsun-26 + VoiceMeeter.

Usage examples:
  python setup_audio_profile.py private
  python setup_audio_profile.py discord
  python setup_audio_profile.py stream

What it does (best‑effort, non‑destructive):
- Picks A1 (headphones) and A2 (AI Hears bus) devices by common names
- Assigns A1/A2 on VoiceMeeter via Remote DLL (if present)
- Applies VoiceMeeter routing preset (private/discord/stream)
- Updates .env hints so Bjorgsun uses the correct devices

Notes:
- Device names are matched case‑insensitively; you can override with env vars
  RAZER_HINT (e.g., "Razer Kraken") and CABLE_HINT (e.g., "CABLE Input").
- If the Remote DLL is not found, the script still updates .env and applies
  strip routing where possible; set VOICEMEETER_DLL_PATH to the DLL to enable.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional


def _print(msg: str):
    print(msg, flush=True)


# Load .env if available so overrides like RAZER_HINT work without VS Code
# terminal environment injection.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass


def _list_output_devices():
    try:
        import sounddevice as sd

        apis = sd.query_hostapis()
        out = []
        for idx, d in enumerate(sd.query_devices()):
            if int(d.get("max_output_channels", 0) or 0) > 0:
                host = apis[d["hostapi"]]["name"] if "hostapi" in d else ""
                out.append((idx, f"{d.get('name','')} ({host})"))
        return out
    except Exception:
        return []


def _pick_device(label_hints: list[str]) -> Optional[str]:
    devs = [name for _i, name in _list_output_devices()]
    low = [x.lower() for x in devs]
    for hint in label_hints:
        h = hint.lower()
        for i, nm in enumerate(low):
            if h in nm:
                return devs[i]
    return None


def _write_env_updates(mode: str, desktop_hint: str | None, tts_hint: str | None):
    # Preserve other keys; only update the ones we care about
    # Write to repository root .env (this script may live under scripts/)
    root = Path(__file__).resolve().parents[1]
    env_path = str(root / ".env")
    before = {}
    try:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.split("=", 1)
                        before[k.strip()] = v.rstrip("\n")
    except Exception:
        pass
    after = dict(before)
    after["DESKTOP_CAPTURE_ENABLED"] = "1"
    if desktop_hint:
        after["DESKTOP_DEVICE_HINT"] = desktop_hint
    if tts_hint:
        after["TTS_OUTPUT_DEVICE_HINT"] = tts_hint
    # Optional: remember last routing choice
    after["BJORGSUN_ROUTING_MODE"] = mode
    # Backup and write
    try:
        if os.path.exists(env_path):
            shutil.copyfile(env_path, env_path + ".bak")
    except Exception:
        pass
    with open(env_path, "w", encoding="utf-8") as f:
        for k, v in after.items():
            f.write(f"{k}={v}\n")
    _print(
        f"[.env] Updated: DESKTOP_CAPTURE_ENABLED=1, DESKTOP_DEVICE_HINT='{desktop_hint}', TTS_OUTPUT_DEVICE_HINT='{tts_hint}', BJORGSUN_ROUTING_MODE={mode}"
    )


def _apply_vm(mode: str, a1_label: Optional[str], a2_label: Optional[str]):
    try:
        from systems import voicemeeter as vm
    except Exception as e:
        _print(f"[VM] helper import failed: {e}")
        return
    # Assign devices first (best effort)
    try:
        okd, msgd = vm.apply_devices(a1_label, a2_label)
        _print(msgd)
    except Exception as e:
        _print(f"[VM] Device assign skipped: {e}")
    # Apply routing preset
    try:
        ok, msg = vm.apply_preset(mode)
        _print(msg)
    except Exception as e:
        _print(f"[VM] Preset failed: {e}")


def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else "private").strip().lower()
    if mode not in {"private", "discord", "stream"}:
        _print("Usage: python setup_audio_profile.py [private|discord|stream]")
        sys.exit(2)

    # Hints (user can override with env)
    razer_hint = os.getenv("RAZER_HINT", "Razer")
    cable_hint = os.getenv("CABLE_HINT", "CABLE Input")
    vaio_hint = os.getenv("VAIO_HINT", "VoiceMeeter Input")

    # Choose devices per mode
    if mode == "private":
        a1 = _pick_device([f"{razer_hint} (WASAPI)", razer_hint]) or _pick_device(
            [razer_hint]
        )
        a2 = _pick_device([f"{cable_hint} (WASAPI)", cable_hint]) or _pick_device(
            [cable_hint]
        )
        desktop_hint = a1 or ""
        tts_hint = a1 or ""
    elif mode == "discord":
        a1 = _pick_device([f"{razer_hint} (WASAPI)", razer_hint]) or _pick_device(
            [razer_hint]
        )
        a2 = _pick_device([f"{cable_hint} (WASAPI)", cable_hint]) or _pick_device(
            [cable_hint]
        )
        desktop_hint = _pick_device([vaio_hint]) or "VoiceMeeter Input"
        tts_hint = desktop_hint
    else:  # stream
        a1 = _pick_device([f"{razer_hint} (WASAPI)", razer_hint]) or _pick_device(
            [razer_hint]
        )
        a2 = _pick_device([f"{cable_hint} (WASAPI)", cable_hint]) or _pick_device(
            [cable_hint]
        )
        desktop_hint = _pick_device([vaio_hint]) or "VoiceMeeter Input"
        tts_hint = desktop_hint

    # Update .env for Bjorgsun hints
    _write_env_updates(mode, desktop_hint, tts_hint)

    # Convert sounddevice label -> VoiceMeeter label (Driver: Name)
    def _to_vm_label(dev: Optional[str]) -> Optional[str]:
        if not dev:
            return None
        name = dev
        host = ""
        if "(" in dev and dev.endswith(")"):
            base, rest = dev.rsplit("(", 1)
            name = base.strip()
            host = rest.rstrip(")").strip()
        prefix = (
            "WASAPI"
            if "WASAPI" in host.upper()
            else (
                "KS"
                if "KS" in host.upper()
                else ("WDM" if "WDM" in host.upper() else "")
            )
        )
        return f"{prefix}: {name}" if prefix else name

    vm_a1 = _to_vm_label(a1)
    vm_a2 = _to_vm_label(a2)

    # Try VoiceMeeter changes (devices + preset)
    _apply_vm(mode, vm_a1, vm_a2)

    _print(
        "\nDone. Restart Bjorgsun or click UI → Preset to refresh runtime state if needed."
    )


if __name__ == "__main__":
    main()
