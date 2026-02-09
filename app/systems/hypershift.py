"""
Global Hypershift hotkeys (Razer) routed into Bjorgsun actions.

Bindings come from config.HYPERSHIFT_BINDINGS, formatted as:
    action_name:combo|action_name:combo
Example combo string: "right alt+right ctrl+right shift+m"
"""

from __future__ import annotations

import threading
from typing import Callable

try:
    import keyboard  # type: ignore
except Exception:  # pragma: no cover - keyboard optional
    keyboard = None  # type: ignore

from config import HYPERSHIFT_BINDINGS
from systems import (audio, audio_sense, discord_bridge, gaming_bridge, notify,
                     vision)

_bindings: list[int] = []
_lock = threading.Lock()
_share_prev: dict | None = None


def start():
    if keyboard is None:
        return
    if not HYPERSHIFT_BINDINGS:
        return
    with _lock:
        stop()
        for chunk in HYPERSHIFT_BINDINGS.split("|"):
            if ":" not in chunk:
                continue
            action, combo = chunk.split(":", 1)
            action = action.strip().lower()
            combo = combo.strip().lower()
            handler = _ACTIONS.get(action)
            if not handler or not combo:
                continue
            try:
                token = keyboard.add_hotkey(
                    combo,
                    lambda fn=handler: threading.Thread(target=fn, daemon=True).start(),
                )
                _bindings.append(token)
                print(f"[Hypershift] bound {combo} -> {action}")
            except Exception as exc:
                print(f"[Hypershift] failed to bind {combo}: {exc}")


def stop():
    if keyboard is None:
        return
    while _bindings:
        token = _bindings.pop()
        try:
            keyboard.remove_hotkey(token)
        except Exception:
            pass


def _vm_set_mute(flag: bool):
    try:
        from systems import voicemeeter as _vm  # lazy import

        _vm.set_strip_mute(0, flag)
    except Exception:
        pass


def _notify(title: str, msg: str):
    try:
        notify.notify(title, msg, duration=4)
    except Exception:
        pass


def _ensure_vision_on():
    try:
        vision.ensure_enabled(True)
    except Exception:
        try:
            if not vision.get_enabled():
                vision.toggle_vision()
        except Exception:
            pass


def _ensure_vision_off():
    try:
        vision.ensure_enabled(False)
    except Exception:
        try:
            if vision.get_enabled():
                vision.toggle_vision()
        except Exception:
            pass


def _set_presence(note: str, status: str = "online"):
    try:
        discord_bridge.set_presence(status, note)
    except Exception:
        pass


def _action_panic_mute():
    audio.set_hush(True)
    _vm_set_mute(True)
    _notify("Hypershift", "All microphones muted.")


def _action_panic_release():
    audio.set_hush(False)
    _vm_set_mute(False)
    _notify("Hypershift", "Audio restored.")


def _action_panic_cut():
    _action_share_stop()
    _action_panic_mute()
    try:
        gaming_bridge.set_game_mode(False)
    except Exception:
        pass
    _ensure_vision_off()
    _set_presence("Emergency mute", "dnd")
    _notify("Hypershift", "Emergency silence engaged.")


def _action_share_start():
    global _share_prev
    if _share_prev is None:
        try:
            prev_source = vision.get_source_settings()
        except Exception:
            prev_source = ("screen", "", 0)
        try:
            prev_enabled = vision.get_enabled()
        except Exception:
            prev_enabled = False
        try:
            prev_key = gaming_bridge.get_key_mode()
        except Exception:
            prev_key = "keepawake"
        try:
            prev_sense_running = audio_sense.is_running()
        except Exception:
            prev_sense_running = False
        try:
            prev_sense_mode = audio_sense.get_mode()
        except Exception:
            prev_sense_mode = "mic"
        _share_prev = {
            "source": prev_source,
            "vision_enabled": prev_enabled,
            "key_mode": prev_key,
            "sense_running": prev_sense_running,
            "sense_mode": prev_sense_mode,
        }
    vision.configure_source("screen", "", 0)
    _ensure_vision_on()
    try:
        audio_sense.stop()
    except Exception:
        pass
    try:
        audio_sense.start("desktop")
    except Exception:
        pass
    try:
        gaming_bridge.set_key_mode("learning")
        gaming_bridge.set_game_mode(True)
    except Exception:
        pass
    joined = False
    try:
        joined = discord_bridge.join_owner_or_channel()
    except Exception:
        joined = False
    if joined:
        _notify(
            "Hypershift",
            "Screen share active (joined Discord voice + desktop audio + key capture).",
        )
    else:
        _notify("Hypershift", "Screen share active (desktop audio + key capture).")


def _action_share_stop():
    global _share_prev
    try:
        audio_sense.stop()
    except Exception:
        pass
    if _share_prev:
        src, name, idx = _share_prev.get("source", ("screen", "", 0))
        vision.configure_source(src, name, idx)
        if not _share_prev.get("vision_enabled", True):
            _ensure_vision_off()
        try:
            gaming_bridge.set_key_mode(_share_prev.get("key_mode", "keepawake"))
        except Exception:
            pass
    try:
        gaming_bridge.set_game_mode(False)
    except Exception:
        pass
    try:
        discord_bridge.leave_voice()
    except Exception:
        pass
    if _share_prev:
        if _share_prev.get("sense_running"):
            try:
                audio_sense.start(_share_prev.get("sense_mode", "mic"))
            except Exception:
                pass
    _share_prev = None
    _notify("Hypershift", "Screen share stopped; capture restored to defaults.")


def _action_live_scene():
    _action_panic_release()
    _set_presence("Live on stream", "online")
    _notify("Hypershift", "Switched to LIVE scene (unmuted).")


def _action_scene_starting():
    _action_share_stop()
    _action_panic_mute()
    _set_presence("Starting soon", "idle")
    _notify("Hypershift", "Switched to starting soon scene.")


def _action_scene_brb():
    _action_share_stop()
    _action_panic_mute()
    _set_presence("BRB", "idle")
    _notify("Hypershift", "BRB scene active; capture muted.")


def _action_scene_intermission():
    _action_share_stop()
    _action_panic_mute()
    _set_presence("Intermission", "idle")
    _notify("Hypershift", "Intermission scene active; capture muted.")


_ACTIONS: dict[str, Callable[[], None]] = {
    "panic_cut": _action_panic_cut,
    "panic_mute": _action_panic_mute,
    "panic_release": _action_panic_release,
    "share_start": _action_share_start,
    "share_stop": _action_share_stop,
    "live_scene": _action_live_scene,
    "scene_starting": _action_scene_starting,
    "scene_brb": _action_scene_brb,
    "scene_intermission": _action_scene_intermission,
}
