"""
VoiceMeeter automation (best-effort, optional).

Requires: pip install pyvoicemeeter

Provides apply_preset(mode) to set typical routing on VoiceMeeter Banana:
- private:  Mic->B1, VAIO->A1, VAIO->B1=OFF, AUX->A1, AUX->B1=OFF
- discord:  same as private (Discord should output to AUX)
- stream:   Mic->B1, VAIO->A1+B1, AUX->A1, AUX->B1=OFF

If pyvoicemeeter is not installed or VoiceMeeter not running, returns (False, reason).
"""

from __future__ import annotations

import ctypes
import json
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

# Persistent session globals (for R-BOX always-on)
_session_type: str | None = None  # 'pv' | 'dll' | None
_vm_kind: str | None = None  # banana | potato | default
_session_vm = None
_persist_enabled = False
_hb_thread: threading.Thread | None = None
_hb_stop = False
_last_err = ""
_scene_cache: dict[str, dict] | None = None
DEFAULT_SCENE_ID = "potato_stream_ai"
VM_ENABLED = os.getenv("VOICEMEETER_ENABLED", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_VM_DISABLED_REASON = "VoiceMeeter integration disabled"


def _list_output_devices() -> list[dict[str, str]]:
    """Return a list of sounddevice output device labels."""
    out: list[dict[str, str]] = []
    try:
        import sounddevice as sd  # type: ignore

        apis = sd.query_hostapis()
        for d in sd.query_devices():
            ch = int(d.get("max_output_channels", 0) or 0)
            if ch <= 0:
                continue
            host = ""
            try:
                host = apis[d["hostapi"]]["name"]
            except Exception:
                host = d.get("hostapi", "")
            label = f"{d.get('name','')} ({host})".strip()
            out.append(
                {
                    "name": d.get("name", ""),
                    "host": host,
                    "label": label,
                }
            )
    except Exception:
        pass
    return out


def list_output_devices() -> list[str]:
    """Public helper for UI: returns labels suitable for display."""
    return [d.get("label", "") for d in _list_output_devices() if d.get("label")]


def _pick_device(hints: Iterable[str]) -> str | None:
    devices = _list_output_devices()
    labels = [d.get("label", "") for d in devices]
    lowers = [lbl.lower() for lbl in labels]
    for hint in hints:
        h = hint.lower()
        for idx, lbl in enumerate(lowers):
            if h in lbl:
                return labels[idx]
    return None


def _to_vm_label(dev_label: str | None) -> str | None:
    if not dev_label:
        return None
    label = dev_label
    host = ""
    if "(" in dev_label and dev_label.endswith(")"):
        base, rest = dev_label.rsplit("(", 1)
        label = base.strip()
        host = rest.rstrip(")").strip()
    prefix = ""
    hu = host.upper()
    if "WASAPI" in hu:
        prefix = "WASAPI"
    elif "KS" in hu:
        prefix = "KS"
    elif "WDM" in hu:
        prefix = "WDM"
    return f"{prefix}: {label}" if prefix else label


def _update_env_vars(updates: dict[str, str]):
    try:
        root = Path(__file__).resolve().parents[1]
        env_path = root / ".env"
        data: dict[str, str] = {}
        if env_path.exists():
            with env_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.split("=", 1)
                        data[k.strip()] = v.rstrip("\n")
        data.update({k: str(v) for k, v in updates.items() if v is not None})
        tmp = env_path.with_suffix(".env.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for k, v in data.items():
                f.write(f"{k}={v}\n")
        tmp.replace(env_path)
    except Exception:
        pass


def _connect():
    global _vm_kind
    if not VM_ENABLED:
        return None, None, _VM_DISABLED_REASON
    # Reuse persistent session if available
    if _persist_enabled and _session_vm is not None:
        return (
            (_session_type if _session_type != "pv" else __import__("pyvoicemeeter")),
            _session_vm,
            None,
        )
    # First try pyvoicemeeter
    try:
        import pyvoicemeeter as pv  # type: ignore

        try:
            kind = pv.api.get_voicemeeter_kind() or "banana"
        except Exception:
            kind = "banana"
        vm = pv.helper.login(kind)
        _vm_kind = kind
        return pv, vm, None
    except Exception as e:
        pv = None  # type: ignore[assignment]
        vm = None
        last_err = f"pyvoicemeeter not available: {e}"

    # Fallback: use VoicemeeterRemote DLL directly via ctypes
    try:
        # Allow explicit override from environment
        env_path = os.getenv("VOICEMEETER_DLL_PATH") or os.getenv(
            "VOICEMEETER_REMOTE_DLL"
        )
        dll_paths = [
            # Hard-coded common installs (requested)
            r"C:\\Program Files (x86)\\VB\\Voicemeeter\\VoicemeeterRemote64.dll",
            r"C:\\Program Files\\VB\\Voicemeeter\\VoicemeeterRemote64.dll",
            r"C:\\VB\\VoicemeeterRemote64.dll",
        ]
        # Prepend env override if present
        if env_path:
            dll_paths.insert(0, env_path)
        dll = None
        for p in dll_paths:
            if p and os.path.exists(p):
                try:
                    dll = ctypes.WinDLL(p)
                    break
                except Exception:
                    continue
        if dll is None:
            return None, None, last_err + "; Remote DLL not found"

        dll.VBVMR_Login.restype = ctypes.c_long
        dll.VBVMR_Logout.restype = ctypes.c_long
        dll.VBVMR_SetParameterFloat.restype = ctypes.c_long
        dll.VBVMR_SetParameterFloat.argtypes = [ctypes.c_char_p, ctypes.c_float]
        # Getters
        try:
            dll.VBVMR_GetParameterFloat.restype = ctypes.c_long
            dll.VBVMR_GetParameterFloat.argtypes = [
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_float),
            ]
        except Exception:
            pass
        # Wide-char string setter is available on recent Remote DLLs
        try:
            dll.VBVMR_SetParameterStringW.restype = ctypes.c_long
            dll.VBVMR_SetParameterStringW.argtypes = [
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
            ]
        except Exception:
            pass
        try:
            dll.VBVMR_GetParameterStringW.restype = ctypes.c_long
            dll.VBVMR_GetParameterStringW.argtypes = [
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_int,
            ]
        except Exception:
            pass

        if dll.VBVMR_Login() != 0:
            return None, None, last_err + "; Login to Remote DLL failed"

        class _VMWrapper:
            def __init__(self, _dll, _path):
                self._dll = _dll
                self.path = _path

            def set(self, name: str, value: int | float):
                nm = name.encode("utf-8")
                val = float(value)
                return self._dll.VBVMR_SetParameterFloat(nm, ctypes.c_float(val))

            def set_str(self, name: str, value: str) -> int:
                try:
                    fn = getattr(self._dll, "VBVMR_SetParameterStringW", None)
                    if fn is None:
                        return -1
                    return int(fn(ctypes.c_wchar_p(name), ctypes.c_wchar_p(value)))
                except Exception:
                    return -1

            def get(self, name: str) -> tuple[bool, float]:
                try:
                    fn = getattr(self._dll, "VBVMR_GetParameterFloat", None)
                    if fn is None:
                        return False, 0.0
                    v = ctypes.c_float()
                    rc = fn(name.encode("utf-8"), ctypes.byref(v))
                    return (rc == 0), float(v.value)
                except Exception:
                    return False, 0.0

            def get_str(self, name: str, bufsize: int = 256) -> tuple[bool, str]:
                try:
                    fn = getattr(self._dll, "VBVMR_GetParameterStringW", None)
                    if fn is None:
                        return False, ""
                    buf = ctypes.create_unicode_buffer(bufsize)
                    rc = fn(ctypes.c_wchar_p(name), buf, ctypes.c_int(bufsize))
                    return (rc == 0), buf.value
                except Exception:
                    return False, ""

            def close(self):
                try:
                    self._dll.VBVMR_Logout()
                except Exception:
                    pass

        wrapper = _VMWrapper(dll, p)
        if _vm_kind is None:
            _vm_kind = (
                os.getenv("VOICEMEETER_KIND", "banana").strip().lower() or "banana"
            )
        return "dll", wrapper, None
    except Exception as e:
        return None, None, last_err + f"; DLL error: {e}"


def _set_strip(
    vm,
    idx: int,
    a1: int | bool | None = None,
    a2: int | bool | None = None,
    b1: int | bool | None = None,
    b2: int | bool | None = None,
    a3: int | bool | None = None,
    a4: int | bool | None = None,
    a5: int | bool | None = None,
    b3: int | bool | None = None,
):
    def tobit(x):
        return 1 if bool(x) else 0

    try:
        if hasattr(vm, "set"):
            if a1 is not None:
                vm.set(f"Strip[{idx}].A1", tobit(a1))
            if a2 is not None:
                vm.set(f"Strip[{idx}].A2", tobit(a2))
            if b1 is not None:
                vm.set(f"Strip[{idx}].B1", tobit(b1))
            if b2 is not None:
                vm.set(f"Strip[{idx}].B2", tobit(b2))
            if a3 is not None:
                vm.set(f"Strip[{idx}].A3", tobit(a3))
            if a4 is not None:
                vm.set(f"Strip[{idx}].A4", tobit(a4))
            if a5 is not None:
                vm.set(f"Strip[{idx}].A5", tobit(a5))
            if b3 is not None:
                vm.set(f"Strip[{idx}].B3", tobit(b3))
        else:
            # pyvoicemeeter helper object
            if a1 is not None:
                vm.set(f"Strip[{idx}].A1", tobit(a1))
            if a2 is not None:
                vm.set(f"Strip[{idx}].A2", tobit(a2))
            if b1 is not None:
                vm.set(f"Strip[{idx}].B1", tobit(b1))
            if b2 is not None:
                vm.set(f"Strip[{idx}].B2", tobit(b2))
            if a3 is not None:
                vm.set(f"Strip[{idx}].A3", tobit(a3))
            if a4 is not None:
                vm.set(f"Strip[{idx}].A4", tobit(a4))
            if a5 is not None:
                vm.set(f"Strip[{idx}].A5", tobit(a5))
            if b3 is not None:
                vm.set(f"Strip[{idx}].B3", tobit(b3))
        return True
    except Exception:
        return False


def _set_bus_device(vm, bus_index: int, device_label: str) -> bool:
    """Set A1/A2 output device by label via Remote DLL.
    Tries common parameter spellings for VoiceMeeter Banana.
    device_label should include driver prefix (e.g., 'KS: Razer Headset...' or 'WDM: CABLE Input').
    """
    try:
        # pyvoicemeeter helper might expose set; DLL wrapper exposes set_str
        targets = [
            f"Bus[{bus_index}].device",
            f"Bus[{bus_index}].Device",
            f"System.A{bus_index+1}",
        ]
        ok = False
        for t in targets:
            if hasattr(vm, "set_str"):
                r = vm.set_str(t, device_label)
                if r == 0:
                    ok = True
                    break
            else:
                try:
                    vm.set(t, device_label)  # type: ignore[arg-type]
                    ok = True
                    break
                except Exception:
                    continue
        return ok
    except Exception:
        return False


def apply_devices(a1_label: str | None, a2_label: str | None) -> tuple[bool, str]:
    """Best-effort assign A1/A2 output devices via Remote DLL.
    Returns (ok, message). Does nothing if DLL is unavailable.
    """
    pv, vm, err = _connect()
    if err:
        return False, f"[VM] {err}. Cannot set devices automatically."
    try:
        ok = True
        msgs = []
        if a1_label:
            ok &= _set_bus_device(vm, 0, a1_label)
            msgs.append(f"A1→{a1_label}")
        if a2_label:
            ok &= _set_bus_device(vm, 1, a2_label)
            msgs.append(f"A2→{a2_label}")
        if isinstance(pv, str) and pv == "dll" and not _persist_enabled:
            try:
                vm.close()
            except Exception:
                pass
        return ok, (
            ("[VM] Devices set: " + ", ".join(msgs))
            if msgs
            else "[VM] No device labels provided."
        )
    except Exception as e:
        return False, f"[VM] Device assign error: {e}"


def _scenes_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "voicemeeter_scenes.json"


def _load_scenes() -> dict[str, dict]:
    global _scene_cache
    if _scene_cache is not None:
        return _scene_cache
    path = _scenes_path()
    data: dict[str, dict] = {}
    try:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                scenes = raw.get("scenes")
                if isinstance(scenes, list):
                    for entry in scenes:
                        if isinstance(entry, dict) and entry.get("id"):
                            data[str(entry["id"])] = entry
                else:
                    for key, value in raw.items():
                        if isinstance(value, dict):
                            data[str(key)] = value
        if not data:
            data = {
                DEFAULT_SCENE_ID: {
                    "id": DEFAULT_SCENE_ID,
                    "label": "Potato // Stream+AI",
                    "description": "Fallback default scene (no JSON file found).",
                    "buses": {},
                    "strips": [],
                }
            }
    except Exception:
        data = {}
    _scene_cache = data
    return data


def _resolve_profile_path(ref: str | None) -> Path | None:
    if not ref:
        return None
    ref = ref.strip()
    if not ref:
        return None
    path = Path(ref)
    search: list[Path] = []
    if path.is_absolute():
        search.append(path)
    else:
        root = Path(__file__).resolve().parents[1]
        search.extend(
            [
                root / ref,
                root / "data" / ref,
                root / "data" / "voicemeeter_profiles" / ref,
            ]
        )
    for candidate in search:
        if candidate.exists():
            return candidate
    return None


def list_scenes() -> list[dict[str, str]]:
    scenes = _load_scenes()
    out: list[dict[str, str]] = []
    for scene_id, conf in scenes.items():
        out.append(
            {
                "id": scene_id,
                "label": conf.get("label", scene_id),
                "description": conf.get("description", ""),
            }
        )
    return out


def _load_profile_with_vm(vm, profile_ref: str) -> bool:
    path = _resolve_profile_path(profile_ref)
    if not path:
        return False
    cmd = str(path)
    try:
        if hasattr(vm, "set_str"):
            return vm.set_str("Command.Load", cmd) == 0
        vm.set("Command.Load", cmd)
        return True
    except Exception:
        return False


def _apply_strip_routes(vm, idx: int, routes: dict | None) -> bool:
    if not routes:
        return True
    toggles = {}
    gain = None
    mute = None
    for key, value in routes.items():
        if key is None:
            continue
        k = str(key).strip().lower()
        if k in {"a1", "a2", "a3", "a4", "a5", "b1", "b2", "b3"}:
            toggles[k] = bool(value)
        elif k == "gain":
            gain = float(value)
        elif k == "mute":
            mute = bool(value)
    ok = _set_strip(
        vm,
        idx,
        a1=toggles.get("a1"),
        a2=toggles.get("a2"),
        a3=toggles.get("a3"),
        a4=toggles.get("a4"),
        a5=toggles.get("a5"),
        b1=toggles.get("b1"),
        b2=toggles.get("b2"),
        b3=toggles.get("b3"),
    )
    if gain is not None:
        try:
            if hasattr(vm, "set"):
                vm.set(f"Strip[{idx}].Gain", float(gain))
            else:
                vm.set(f"Strip[{idx}].Gain", float(gain))
        except Exception:
            pass
    if mute is not None:
        try:
            if hasattr(vm, "set"):
                vm.set(f"Strip[{idx}].Mute", 1 if mute else 0)
            else:
                vm.set(f"Strip[{idx}].Mute", 1 if mute else 0)
        except Exception:
            pass
    return ok


def apply_scene(scene: str) -> tuple[bool, str]:
    """Apply a scene defined in data/voicemeeter_scenes.json."""
    scenes = _load_scenes()
    if not scenes:
        return False, "[VM] No scenes defined (data/voicemeeter_scenes.json missing)."
    key = (scene or "").strip()
    if key not in scenes:
        return False, f"[VM] Scene '{scene}' not found."
    conf = scenes[key]
    pv, vm, err = _connect()
    if err:
        return False, f"[VM] {err}. Cannot apply scene."
    try:
        profile_ref = conf.get("profile")
        if profile_ref:
            if not _load_profile_with_vm(vm, profile_ref):
                return False, f"[VM] Unable to load profile '{profile_ref}'."
        ok = True
        buses = conf.get("buses") or {}
        bus_map = {
            "a1": 0,
            "a2": 1,
            "a3": 2,
            "a4": 3,
            "a5": 4,
            "b1": 5,
            "b2": 6,
            "b3": 7,
        }
        for bus_key, label in buses.items():
            k = str(bus_key).strip().lower()
            if k in {"a1", "a2", "a3", "a4", "a5"} and label:
                ok &= _set_bus_device(vm, bus_map[k], label)
        for entry in conf.get("strips", []):
            if not isinstance(entry, dict):
                continue
            idx = entry.get("index")
            if idx is None:
                continue
            try:
                idx = int(idx)
            except Exception:
                continue
            ok &= _apply_strip_routes(vm, idx, entry.get("routes"))
        label = conf.get("label", key)
        if isinstance(pv, str) and pv == "dll" and not _persist_enabled:
            try:
                vm.close()
            except Exception:
                pass
        _update_env_vars({"VM_SCENE": key})
        return ok, f"[VM] Applied scene '{label}'."
    except Exception as e:
        return False, f"[VM] Scene apply failed: {e}"


def auto_setup(mode: str) -> tuple[bool, list[str], dict]:
    """Replicate setup_audio_profile logic inside the runtime/UI."""
    logs: list[str] = []
    info: dict[str, str] = {}
    m = (mode or "private").strip().lower()
    if m not in {"private", "discord", "stream"}:
        return False, [f"[VM] Unknown mode '{mode}'. Use private/discord/stream."], {}

    razer_hint = os.getenv("RAZER_HINT", "Razer")
    cable_hint = os.getenv("CABLE_HINT", "CABLE Input")
    vaio_hint = os.getenv("VAIO_HINT", "VoiceMeeter Input")

    def pick_device(hints: list[str]) -> str | None:
        return _pick_device(hints)

    if m == "private":
        a1 = pick_device([f"{razer_hint} (WASAPI)", razer_hint]) or pick_device(
            [razer_hint]
        )
        a2 = pick_device([f"{cable_hint} (WASAPI)", cable_hint]) or pick_device(
            [cable_hint]
        )
        desktop_hint = a1 or ""
        tts_hint = a1 or ""
    elif m == "discord":
        a1 = pick_device([f"{razer_hint} (WASAPI)", razer_hint]) or pick_device(
            [razer_hint]
        )
        a2 = pick_device([f"{cable_hint} (WASAPI)", cable_hint]) or pick_device(
            [cable_hint]
        )
        desktop_hint = pick_device([vaio_hint]) or "VoiceMeeter Input"
        tts_hint = desktop_hint
    else:  # stream
        a1 = pick_device([f"{razer_hint} (WASAPI)", razer_hint]) or pick_device(
            [razer_hint]
        )
        a2 = pick_device([f"{cable_hint} (WASAPI)", cable_hint]) or pick_device(
            [cable_hint]
        )
        desktop_hint = pick_device([vaio_hint]) or "VoiceMeeter Input"
        tts_hint = desktop_hint

    updates = {
        "DESKTOP_CAPTURE_ENABLED": "1",
        "BJORGSUN_ROUTING_MODE": m,
        "DESKTOP_DEVICE_HINT": desktop_hint or "",
        "TTS_OUTPUT_DEVICE_HINT": tts_hint or "",
        "VM_A1_LABEL": _to_vm_label(a1) or (a1 or ""),
        "VM_A2_LABEL": _to_vm_label(a2) or (a2 or ""),
    }
    _update_env_vars(updates)
    logs.append("[VM] .env updated with capture hints and routing mode.")

    vm_a1 = _to_vm_label(a1)
    vm_a2 = _to_vm_label(a2)
    ok_devices, msg_devices = apply_devices(vm_a1, vm_a2)
    logs.append(msg_devices)

    ok_preset, msg_preset = apply_preset(m)
    logs.append(msg_preset)

    info = {
        "a1": vm_a1 or (a1 or ""),
        "a2": vm_a2 or (a2 or ""),
        "desktop": desktop_hint or "",
        "tts": tts_hint or "",
    }
    return bool(ok_devices and ok_preset), logs, info


def apply_preset(mode: str) -> tuple[bool, str]:
    """Apply routing preset. Returns (ok, message)."""
    pv, vm, err = _connect()
    if err:
        return False, f"[VM] {err}. Install with: pip install pyvoicemeeter"
    try:
        m = (mode or "").strip().lower()
        global _vm_kind
        if (_vm_kind or "").startswith("potato"):
            scene = os.getenv("VM_SCENE", "").strip() or DEFAULT_SCENE_ID
            if isinstance(pv, str) and pv == "dll" and not _persist_enabled:
                try:
                    vm.close()
                except Exception:
                    pass
            return apply_scene(scene)
        # Strip indices for Banana: 0..2 hardware in, 3=VAIO, 4=AUX
        mic_idx = 0
        vaio_idx = 3
        aux_idx = 4

        if m in ("private", "discord"):
            ok = True
            ok &= _set_strip(vm, mic_idx, a1=1, b1=1)
            ok &= _set_strip(vm, vaio_idx, a1=1, b1=0, b2=0)
            ok &= _set_strip(vm, aux_idx, a1=1, b1=0)
            if isinstance(pv, str) and pv == "dll":
                msg = f"[VM] Applied Private/Discord routing (VAIO/AUX not to B1) via DLL: {getattr(vm,'path','unknown')}"
            else:
                msg = "[VM] Applied Private/Discord routing (VAIO/AUX not to B1)."
            if isinstance(pv, str) and pv == "dll" and not _persist_enabled:
                try:
                    vm.close()
                except Exception:
                    pass
            return ok, msg
        elif m == "stream":
            ok = True
            ok &= _set_strip(vm, mic_idx, a1=1, b1=1)
            ok &= _set_strip(vm, vaio_idx, a1=1, b1=1, b2=0)
            ok &= _set_strip(vm, aux_idx, a1=1, b1=0)
            if isinstance(pv, str) and pv == "dll":
                msg = f"[VM] Applied Stream routing (VAIO B1 ON) via DLL: {getattr(vm,'path','unknown')}"
            else:
                msg = "[VM] Applied Stream routing (VAIO B1 ON)."
            if isinstance(pv, str) and pv == "dll" and not _persist_enabled:
                try:
                    vm.close()
                except Exception:
                    pass
            return ok, msg
        elif m == "user":
            import os

            ok = True
            mic_idx = 0
            vaio_idx = 3
            aux_idx = 4

            def flag(name, default):
                v = os.getenv(name)
                if v is None:
                    return default
                return str(v).strip().lower() in {"1", "true", "yes", "on"}

            # Defaults based on the provided layout screenshot:
            # - Mic ➜ B2 ON (Complete Out), others OFF
            # - VAIO (Desktop Audio) ➜ A1 ON (headphones), B1/B2 OFF
            # - AUX (Discord Audio) ➜ A1 ON (headphones), B1/B2 OFF
            ok &= _set_strip(
                vm,
                mic_idx,
                a1=flag("VM_MIC_TO_A1", False),
                a2=flag("VM_MIC_TO_A2", False),
                b1=flag("VM_MIC_TO_B1", False),
                b2=flag("VM_MIC_TO_B2", True),
            )
            ok &= _set_strip(
                vm,
                vaio_idx,
                a1=flag("VM_VAIO_TO_A1", True),
                a2=flag("VM_VAIO_TO_A2", False),
                b1=flag("VM_VAIO_TO_B1", False),
                b2=flag("VM_VAIO_TO_B2", False),
            )
            ok &= _set_strip(
                vm,
                aux_idx,
                a1=flag("VM_AUX_TO_A1", True),
                a2=flag("VM_AUX_TO_A2", False),
                b1=flag("VM_AUX_TO_B1", False),
                b2=flag("VM_AUX_TO_B2", False),
            )
            msg = "[VM] Applied user profile (env-driven routing)."
            if isinstance(pv, str) and pv == "dll":
                try:
                    vm.close()
                except Exception:
                    pass
            return ok, msg
        else:
            return False, f"[VM] Unknown preset: {mode}"
    except Exception as e:
        return False, f"[VM] Apply failed: {e}"


def apply_custom(routes: dict) -> tuple[bool, str]:
    """Apply explicit bus toggles per strip. Expects routes like {'mic': {'a1':True,...}}."""
    pv, vm, err = _connect()
    if err:
        return False, f"[VM] {err}. Cannot apply custom routing."
    try:
        mapping = {"mic": 0, "vaio": 3, "aux": 4}
        ok = True
        for key, idx in mapping.items():
            conf = routes.get(key)
            if not conf:
                continue
            ok &= _set_strip(
                vm,
                idx,
                a1=None if conf.get("a1") is None else bool(conf.get("a1")),
                a2=None if conf.get("a2") is None else bool(conf.get("a2")),
                b1=None if conf.get("b1") is None else bool(conf.get("b1")),
                b2=None if conf.get("b2") is None else bool(conf.get("b2")),
            )
        if isinstance(pv, str) and pv == "dll" and not _persist_enabled:
            try:
                vm.close()
            except Exception:
                pass
        return ok, "[VM] Custom routing applied." if ok else "[VM] Some routes failed."
    except Exception as e:
        return False, f"[VM] Custom routing failed: {e}"


def set_strip_mute(index: int, enabled: bool) -> tuple[bool, str]:
    """Mute/unmute a VoiceMeeter strip (hardware input) by index.
    index: 0-based (0 is first hardware input).
    """
    pv, vm, err = _connect()
    if err:
        return False, f"[VM] {err}. Cannot set Strip[{index}].Mute."
    try:
        name = f"Strip[{int(index)}].Mute"
        ok = False
        try:
            if hasattr(vm, "set"):
                ok = (vm.set(name, 1 if enabled else 0) == 0) or True
            else:
                vm.set(name, 1 if enabled else 0)
                ok = True
        except Exception:
            ok = False
        if isinstance(pv, str) and pv == "dll" and not _persist_enabled:
            try:
                vm.close()
            except Exception:
                pass
        return ok, ("[VM] Mic muted" if enabled else "[VM] Mic unmuted")
    except Exception as e:
        return False, f"[VM] Set mute failed: {e}"


def set_discord_a2(enabled: bool) -> tuple[bool, str]:
    """Route Discord (AUX strip) to A2 bus for AI hearing when enabled.
    Returns (ok, message)."""
    pv, vm, err = _connect()
    if err:
        return False, f"[VM] {err}. Cannot toggle AUX→A2."
    try:
        aux_idx = 4
        ok = _set_strip(vm, aux_idx, a2=1 if enabled else 0)
        msg = (
            "[VM] AUX→A2 ON (Discord → AI)"
            if enabled
            else "[VM] AUX→A2 OFF (Discord hidden from AI)"
        )
        if isinstance(pv, str) and pv == "dll" and not _persist_enabled:
            try:
                vm.close()
            except Exception:
                pass
        return ok, msg
    except Exception as e:
        return False, f"[VM] AUX→A2 toggle failed: {e}"


def install_helper() -> tuple[bool, str]:
    """No longer auto-installs dependencies (security policy).
    Provide guidance instead of running pip from the app.
    """
    msg = (
        "[VM] Auto-install is disabled. Install 'pyVoicemeeter' manually:\n"
        "    python -m pip install pyVoicemeeter\n"
        "or configure VOICEMEETER_DLL_PATH to the VoicemeeterRemote64.dll."
    )
    return False, msg


def vban_use_preferred(
    preferred: list[str] | tuple[str, ...] = ("Bjorgsun", "Stream1")
) -> tuple[bool, str, str]:
    """Enable VBAN and ensure an incoming stream slot is ON with a preferred name.
    Tries first name in 'preferred'; if it fails, uses the next. Returns (ok, message, chosen_name).
    """
    pv, vm, err = _connect()
    if err:
        return False, f"[VM] {err}. VBAN not configured.", ""
    try:
        # Enable VBAN globally
        try:
            vm.set("VBAN.Enable", 1)
        except Exception:
            pass
        chosen = None
        for name in list(preferred) or ["Stream1"]:
            try:
                # Configure slot 0 with the desired name; keep defaults for SR/Ch/Format
                if hasattr(vm, "set_str"):
                    vm.set_str("VBAN.InStream[0].Name", name)
                vm.set("VBAN.InStream[0].On", 1)
                chosen = name
                break
            except Exception:
                continue
        if isinstance(pv, str) and pv == "dll" and not _persist_enabled:
            try:
                vm.close()
            except Exception:
                pass
        if not chosen:
            return False, "[VM] VBAN: unable to set VBAN.InStream[0].Name", ""
        return True, f"[VM] VBAN: using incoming stream '{chosen}' on In #1", chosen
    except Exception as e:
        return False, f"[VM] VBAN error: {e}", ""


def _hb_loop():
    global _session_vm, _session_type, _hb_stop, _last_err
    while not _hb_stop:
        try:
            if _session_vm is None:
                pv, vm, err = _connect()
                if err:
                    _last_err = err
                    time.sleep(2.0)
                    continue
                if isinstance(pv, str) and pv == "dll":
                    _session_type = "dll"
                else:
                    _session_type = "pv"
                _session_vm = vm
            else:
                try:
                    if _session_type == "dll":
                        _session_vm.get("Strip[0].Gain")
                    else:
                        _session_vm.set("Strip[0].Gain", 0.0)
                except Exception:
                    _session_vm = None
            time.sleep(3.0)
        except Exception:
            time.sleep(3.0)


def start_persistent():
    """Keep a persistent VM Remote connection so R‑BOX stays lit."""
    global _persist_enabled, _hb_thread, _hb_stop
    if not VM_ENABLED:
        return
    _persist_enabled = True
    if _hb_thread and _hb_thread.is_alive():
        return
    _hb_stop = False
    _hb_thread = threading.Thread(target=_hb_loop, daemon=True)
    _hb_thread.start()


def stop_persistent():
    global _hb_stop, _persist_enabled, _session_vm
    _persist_enabled = False
    _hb_stop = True
    try:
        if _session_vm and _session_type == "dll":
            try:
                _session_vm.close()
            except Exception:
                pass
    finally:
        _session_vm = None


def is_connected() -> bool:
    return bool(_session_vm)


def initialize():
    """Start persistent connection if requested by env (VM_PERSIST=1)."""
    if not VM_ENABLED:
        return False
    try:
        if (os.getenv("VM_PERSIST", "1").strip().lower()) in {"1", "true", "yes", "on"}:
            start_persistent()
            return True
    except Exception:
        pass
    return False
