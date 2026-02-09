"""
systems/calm_shutdown.py — Background watcher for USBMK calm-shutdown triggers.

Design
- Each programmed USBMK contains a visible script (BJ-CALM.cmd) that writes a
  file BJ-CALM.SIGNAL with a shared calm_token in the USB root when executed.
- When detected, we perform a calm, safe shutdown.
"""

from __future__ import annotations

import ctypes
import os
import threading
import time

_running = False


def _usbmk_reg() -> dict | None:
    try:
        base = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "data", "usbmk.json")
        )
        if os.path.exists(base):
            import json

            with open(base, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return None
    return None


def _iter_drives():
    try:
        import string

        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            try:
                if os.path.exists(root) and _is_removable(root):
                    yield root
            except Exception:
                continue
    except Exception:
        return


def _get_label(root: str) -> str:
    """Return volume label for a drive root like 'E:\\' (Windows)."""
    try:
        # Windows GetVolumeInformationW
        vol_name_buf = ctypes.create_unicode_buffer(256)
        fs_name_buf = ctypes.create_unicode_buffer(256)
        serial = ctypes.c_uint32()
        max_comp_len = ctypes.c_uint32()
        file_flags = ctypes.c_uint32()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root),
            vol_name_buf,
            ctypes.sizeof(vol_name_buf),
            ctypes.byref(serial),
            ctypes.byref(max_comp_len),
            ctypes.byref(file_flags),
            fs_name_buf,
            ctypes.sizeof(fs_name_buf),
        )
        if ok:
            return vol_name_buf.value or ""
    except Exception:
        pass
    return ""


def _is_removable(root: str) -> bool:
    try:
        DRIVE_REMOVABLE = 2
        import ctypes

        t = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))
        return int(t) == DRIVE_REMOVABLE
    except Exception:
        return False


def _read_text(p: str) -> str:
    try:
        # Hard limit to a small size; we only ever need a short token/password.
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(256).strip()
    except Exception:
        return ""


def _shutdown_now():
    try:
        from systems import audio

        audio.alert_speak("Calm shutdown engaged. Powering down safely.")
    except Exception:
        pass
    try:
        from runtime import coreloop

        coreloop.shutdown_sequence()
    except Exception:
        # last resort
        os._exit(0)


def _watch_loop():
    global _running
    _running = True
    stable_hits = {}
    while _running:
        try:
            # Only ever check a single allow-listed file name (FFNKB.txt) on the friend's key.
            for root in _iter_drives():
                try:
                    label = (_get_label(root) or "").strip().lower()
                    if label in ("ahb rest", "ffnkb"):
                        token_path = os.path.join(root, "FFNKB.txt")
                        tok = (
                            _read_text(token_path).strip()
                            if os.path.exists(token_path)
                            else ""
                        )
                        ok = False
                        if tok:
                            try:
                                from runtime import startup as _startup

                                ok = bool(
                                    getattr(_startup, "verify_master", lambda x: False)(
                                        tok
                                    )
                                )
                            except Exception:
                                ok = False
                        # Debounce: require 2 consecutive confirmations ~> 1.6s
                        if ok:
                            tnow = time.time()
                            last = stable_hits.get(root, 0)
                            stable_hits[root] = tnow
                            if tnow - last > 0 and tnow - last < 2.0:
                                _shutdown_now()
                                return
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.8)


def initialize() -> bool:
    try:
        t = threading.Thread(target=_watch_loop, daemon=True)
        t.start()
        return True
    except Exception:
        return False
