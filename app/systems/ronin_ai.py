"""
AI scaffolding for piloting Bjorgsun's Titanfall Ronin chassis.

- Learns from the owner's key presses (when learning mode is enabled).
- Stores captured patterns in data/ronin_profile.json so we can replay them later.
- Uses Titanfall telemetry to decide when to trigger macros (core, call Titan, eject, etc.).
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from typing import Any, Callable, Optional

from config import TITANFALL2_AUTOPILOT, TITANFALL2_CALLSIGN

try:
    import keyboard  # type: ignore
except Exception:
    keyboard = None  # type: ignore

PROFILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "ronin_profile.json"
)
os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)

StatusProvider = Callable[[], dict[str, Any]]
EventCallback = Callable[[str, str, Optional[dict[str, Any]]], None]

_PLAYBOOK_LIMIT = 200

_status_provider: Optional[StatusProvider] = None
_event_callback: Optional[EventCallback] = None
_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_enabled = bool(TITANFALL2_AUTOPILOT)
_learning = False
_key_history: "deque[tuple[float, str]]" = deque(maxlen=800)
_profile: dict[str, Any] = {
    "version": 2,
    "patterns": [],
    "stats": {"samples": 0, "heatmap": {}, "captures": 0},
}
_state_flags = {
    "titan_ready": False,
    "core_ready": False,
    "doom_alert": False,
    "titan_called": False,
    "eject_called": False,
}
_last_core_use = 0.0
_last_dash = 0.0
_last_pattern_capture = {"call_titan": 0.0, "core": 0.0, "eject": 0.0}
_last_initiative = 0.0
_fallback_active = False
_awaiting_fallback = False
_last_fallback_request = 0.0


def start(
    status_provider: Optional[StatusProvider] = None,
    callback: Optional[EventCallback] = None,
):
    """Boot the Ronin controller loop."""
    global _status_provider, _event_callback, _thread
    _load_profile()
    _status_provider = status_provider
    if callback is not None:
        _event_callback = callback
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(
        target=_autonomy_loop, name="RoninController", daemon=True
    )
    _thread.start()
    _emit(
        "Ronin controller online."
        if keyboard
        else "Ronin controller ready (no keyboard access)."
    )


def stop():
    global _thread
    _stop_event.set()
    if _thread and _thread.is_alive():
        try:
            _thread.join(timeout=2)
        except Exception:
            pass
    _thread = None


def set_enabled(flag: bool):
    global _enabled
    _enabled = bool(flag)
    _emit(f"Ronin autonomy {'enabled' if _enabled else 'disabled'}.")


def set_learning(flag: bool):
    global _learning
    _learning = bool(flag)
    _emit(f"Ronin learning mode {'enabled' if _learning else 'disabled'}.")


def record_manual_key(key: str):
    """Called when the owner presses W/A/S/D/etc. so we can learn their rhythm."""
    if not key:
        return
    now = time.time()
    _key_history.append((now, key))
    if not _learning:
        return
    stats = _profile.setdefault("stats", {"samples": 0, "heatmap": {}})
    stats["samples"] = int(stats.get("samples", 0) or 0) + 1
    heat = stats.setdefault("heatmap", {})
    heat[key] = int(heat.get(key, 0) or 0) + 1
    _save_profile()


def get_profile() -> dict[str, Any]:
    data = dict(_profile)
    data["enabled"] = _enabled
    data["learning"] = _learning
    data["keyboard_ready"] = keyboard is not None
    try:
        data["contexts"] = sum(
            1 for item in _profile.get("patterns", []) if item.get("context")
        )
    except Exception:
        data["contexts"] = 0
    data["fallback"] = {
        "active": _fallback_active,
        "awaiting": _awaiting_fallback,
    }
    return data


def get_status_text() -> str:
    if not _enabled:
        return "Ronin autonomy: manual control."
    if keyboard is None:
        return "Ronin autonomy: keyboard driver unavailable."
    return "Ronin autonomy active. Watching Titanfall telemetry."


def trigger_callout(tag: str, status: Optional[dict[str, Any]] = None) -> bool:
    """Execute an immediate action requested via callout (e.g., 'need backup')."""
    if not tag or not _enabled or keyboard is None:
        return False
    if _fallback_active:
        return False
    context = _context_from_status(status)
    ok = _execute_action(tag, context, strict=True, reason=f"Callout {tag}")
    if ok:
        _emit(f"Callout directive honored: {tag}", meta={"context": context})
    return ok


def is_fallback_active() -> bool:
    return _fallback_active


def is_fallback_pending() -> bool:
    return _awaiting_fallback


def approve_fallback() -> bool:
    global _fallback_active, _awaiting_fallback
    if _fallback_active:
        return False
    if not _awaiting_fallback:
        _emit("Default Titan AI requested. Enabling per owner command.", level="info")
    _awaiting_fallback = False
    _fallback_active = True
    _emit(
        "Default Titan AI engaged. Say 'Ronin resume control' when you want me back.",
        level="info",
    )
    return True


def restore_control(force: bool = False) -> bool:
    global _fallback_active, _awaiting_fallback
    if not _fallback_active and not force:
        return False
    _fallback_active = False
    _awaiting_fallback = False
    _emit("Resuming Ronin control.", level="info")
    return True


def request_fallback(reason: str = ""):
    _request_fallback(reason)


def _autonomy_loop():
    global _state_flags, _last_core_use
    while not _stop_event.is_set():
        status = _status_provider() if _status_provider else None
        if not status:
            time.sleep(0.5)
            continue
        titan = (status.get("titan") or {}) if isinstance(status, dict) else {}
        match_info = status.get("match") or {}
        if not isinstance(match_info, dict):
            match_info = {}
        ready = bool(titan.get("ready"))
        core_ready = bool(titan.get("core_ready"))
        doomed = (titan.get("status") or "").lower() in {"doomed", "destroyed"}
        context = _current_context(titan, match_info)

        if _learning:
            _maybe_capture_pattern("call_titan", ready, context)
            _maybe_capture_pattern("core", core_ready, context)
            _maybe_capture_pattern("eject", doomed, context)
            _scan_spontaneous_moves(context)

        _state_flags["titan_ready"] = ready
        _state_flags["core_ready"] = core_ready
        _state_flags["doom_alert"] = doomed

        if not _enabled or keyboard is None:
            time.sleep(0.6)
            continue
        if _fallback_active:
            time.sleep(0.6)
            continue

        actions = _decide_actions(titan, match_info, context)
        for tag, strict, reason in actions:
            _execute_action(tag, context, strict=strict, reason=reason)
        time.sleep(0.25)


def _decide_actions(
    titan: dict[str, Any], match_info: dict[str, Any], context: dict[str, Any]
) -> list[tuple[str, bool, str]]:
    actions: list[tuple[str, bool, str]] = []
    status = (titan.get("status") or "").lower()
    now = time.time()
    if titan.get("ready") and not _state_flags["titan_called"]:
        actions.append(("call_titan", False, "Titan ready"))
        _state_flags["titan_called"] = True
    if not titan.get("ready"):
        _state_flags["titan_called"] = False
    if titan.get("core_ready") and now - _last_core_use > 5:
        actions.append(("core", False, "Core ready"))
        _last_core_use = now
    if status in {"doomed", "destroyed"} and not _state_flags["eject_called"]:
        actions.append(("eject", False, "Titan doomed"))
        _state_flags["eject_called"] = True
    if status not in {"doomed", "destroyed"}:
        _state_flags["eject_called"] = False
    score = match_info.get("score") or {}
    try:
        friendly = int(score.get("friend") or score.get("friendly") or 0)
        enemy = int(score.get("foe") or score.get("enemy") or 0)
    except Exception:
        friendly = enemy = 0
    initiative = _recommend_initiative(context, friendly, enemy)
    if initiative:
        actions.append((initiative, True, "initiative call"))
    return actions


_DEFAULT_ACTIONS = {
    "call_titan": ["v"],
    "core": ["q"],
    "eject": ["e"],
    "aggressive_push": ["shift", "w", "space"],
    "defensive_block": ["s", "s", "mouse2"],
}


def _execute_action(
    tag: str,
    context: Optional[dict[str, Any]] = None,
    *,
    strict: bool = False,
    reason: str = "",
) -> bool:
    if keyboard is None:
        return False
    if _fallback_active:
        return False
    sequence, learned = _choose_sequence(tag, context, strict=strict)
    if not sequence:
        if strict:
            _request_fallback(reason or f"No pattern for {tag}")
        return False
    pressed = []
    try:
        for key in sequence:
            keyboard.press(key)
            pressed.append(key)
            time.sleep(0.03)
        time.sleep(0.12)
    except Exception:
        pass
    finally:
        for key in reversed(pressed):
            try:
                keyboard.release(key)
            except Exception:
                pass
    _emit(
        f"Ronin action executed: {tag}", meta={"sequence": sequence, "learned": learned}
    )
    global _last_dash
    if tag in {"aggressive_push", "defensive_block"}:
        _last_dash = time.time()
    return True


def _choose_sequence(
    tag: str, context: Optional[dict[str, Any]] = None, *, strict: bool = False
) -> tuple[Optional[list[str]], bool]:
    patterns = [
        entry for entry in _profile.get("patterns", []) if entry.get("tag") == tag
    ]
    context = context or {}
    best_seq: Optional[list[str]] = None
    best_score = -1.0
    for entry in reversed(patterns):
        seq = entry.get("sequence")
        if not seq:
            continue
        score = _context_similarity(
            context, entry.get("context") or {}, entry.get("timestamp")
        )
        if score > best_score:
            best_score = score
            best_seq = list(seq)
    if best_seq:
        return best_seq, True
    if strict:
        return None, False
    default = _DEFAULT_ACTIONS.get(tag)
    if default:
        return default[:], False
    return None, False


def _maybe_capture_pattern(
    tag: str, condition: bool, context: Optional[dict[str, Any]] = None
):
    if not condition:
        return
    now = time.time()
    if now - _last_pattern_capture.get(tag, 0.0) < 8:
        return
    _last_pattern_capture[tag] = now
    window = _recent_keys(1.6)
    if not window:
        return
    _record_playstyle(tag, window[-12:], context)


def _scan_spontaneous_moves(context: dict[str, Any]):
    if _enabled:
        return
    now = time.time()
    window = _recent_keys(1.2)
    if len(window) < 4:
        return
    forward = sum(1 for key in window if key in {"w", "space", "shift"})
    backward = sum(1 for key in window if key in {"s", "ctrl", "mouse2"})
    diff = context.get("score_diff", 0)
    if diff <= -12 and forward >= 3:
        if now - _last_pattern_capture.get("aggressive_push", 0.0) >= 6:
            _last_pattern_capture["aggressive_push"] = now
            _record_playstyle("aggressive_push", window[-10:], context)
    elif diff >= 12 and backward >= 3:
        if now - _last_pattern_capture.get("defensive_block", 0.0) >= 6:
            _last_pattern_capture["defensive_block"] = now
            _record_playstyle("defensive_block", window[-10:], context)


def _record_playstyle(
    tag: str, sequence: list[str], context: Optional[dict[str, Any]] = None
):
    entry = {
        "tag": tag,
        "sequence": list(sequence),
        "context": context or {},
        "timestamp": time.time(),
    }
    _profile.setdefault("patterns", []).append(entry)
    _profile["patterns"] = _profile["patterns"][-_PLAYBOOK_LIMIT:]
    stats = _profile.setdefault("stats", {"samples": 0, "heatmap": {}, "captures": 0})
    stats["captures"] = int(stats.get("captures") or 0) + 1
    _save_profile()
    _emit(
        f"Captured Ronin pattern: {tag}",
        meta={"sequence": entry["sequence"], "context": entry["context"]},
    )


def _recent_keys(window: float) -> list[str]:
    now = time.time()
    return [key for ts, key in list(_key_history) if now - ts <= window]


def _load_profile():
    global _profile
    if not os.path.exists(PROFILE_PATH):
        return
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            _profile = data
        _profile.setdefault("patterns", [])
        _profile.setdefault("stats", {"samples": 0, "heatmap": {}, "captures": 0})
    except Exception:
        _profile = {"patterns": [], "stats": {"samples": 0, "heatmap": {}}}


def _save_profile():
    tmp_path = PROFILE_PATH + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(_profile, handle, indent=2, ensure_ascii=False)
        os.replace(tmp_path, PROFILE_PATH)
    except Exception:
        pass


def _emit(text: str, level: str = "info", meta: Optional[dict[str, Any]] = None):
    if not text:
        return
    if _event_callback:
        try:
            _event_callback(text, level, meta or {"source": "ronin"})
            return
        except Exception:
            pass
    print(f"[Ronin] {text}")


def _current_context(
    titan: dict[str, Any], match_info: dict[str, Any]
) -> dict[str, Any]:
    score = match_info.get("score") or {}
    try:
        friendly = int(
            score.get("friend") or score.get("friendly") or score.get("team") or 0
        )
    except Exception:
        friendly = 0
    try:
        enemy = int(
            score.get("foe") or score.get("enemy") or score.get("opponent") or 0
        )
    except Exception:
        enemy = 0
    return {
        "map": match_info.get("map"),
        "mode": match_info.get("mode"),
        "playlist": match_info.get("playlist"),
        "team": match_info.get("team"),
        "score_diff": friendly - enemy,
        "friendly": friendly,
        "enemy": enemy,
        "titan_status": (titan.get("status") or "").lower(),
        "titan_health": int(titan.get("health") or titan.get("hp") or 0),
        "titan_shield": int(titan.get("shield") or titan.get("shield_hp") or 0),
        "titan_ready": bool(titan.get("ready")),
        "core_ready": bool(titan.get("core_ready")),
        "battery": int(titan.get("battery") or 0),
        "players": int(match_info.get("players") or 0),
        "time_remaining": match_info.get("time_remaining"),
    }


def _context_similarity(
    current: dict[str, Any], saved: dict[str, Any], timestamp: Optional[float]
) -> float:
    if not saved:
        return 0.2
    score = 0.0
    if current.get("map") and current.get("map") == saved.get("map"):
        score += 2.0
    if current.get("mode") and current.get("mode") == saved.get("mode"):
        score += 1.0
    if current.get("titan_status") == saved.get("titan_status"):
        score += 1.2
    if current.get("titan_ready") == saved.get("titan_ready"):
        score += 0.5
    if current.get("core_ready") == saved.get("core_ready"):
        score += 0.5
    diff = abs((current.get("score_diff") or 0) - (saved.get("score_diff") or 0))
    score += max(0.0, 3.0 - (diff / 8.0))
    health_diff = abs(
        (current.get("titan_health") or 0) - (saved.get("titan_health") or 0)
    )
    score += max(0.0, 2.0 - (health_diff / 150.0))
    shield_diff = abs(
        (current.get("titan_shield") or 0) - (saved.get("titan_shield") or 0)
    )
    score += max(0.0, 1.0 - (shield_diff / 150.0))
    recency = 0.5
    if timestamp:
        recency = max(0.2, 1.2 - (time.time() - timestamp) / 180.0)
    return score + recency


def _context_from_status(status: Optional[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(status, dict):
        titan = status.get("titan") or {}
        match_info = status.get("match") or {}
    else:
        titan = {}
        match_info = {}
    if not isinstance(titan, dict):
        titan = {}
    if not isinstance(match_info, dict):
        match_info = {}
    return _current_context(titan, match_info)


def _request_fallback(reason: str):
    global _awaiting_fallback, _last_fallback_request
    now = time.time()
    if _fallback_active:
        return
    if _awaiting_fallback and now - _last_fallback_request < 10:
        return
    _awaiting_fallback = True
    _last_fallback_request = now
    msg = "I'm unsure how to respond — may I hand control to the default Titan AI?"
    if reason:
        msg = f"{msg} ({reason})"
    _emit(msg, level="warn")


def _recommend_initiative(
    context: dict[str, Any], friendly: int, enemy: int
) -> Optional[str]:
    global _last_initiative
    now = time.time()
    if now - _last_initiative < 3.5:
        return None
    diff = friendly - enemy
    tag: Optional[str] = None
    if diff <= -15:
        tag = "aggressive_push"
    elif diff >= 20:
        tag = "defensive_block"
    if not tag or not _has_context_pattern(tag):
        return None
    if _choose_sequence(tag, context):
        _last_initiative = now
        return tag
    return None


def _has_context_pattern(tag: str) -> bool:
    try:
        return any(
            entry.get("tag") == tag and entry.get("context")
            for entry in _profile.get("patterns", [])
        )
    except Exception:
        return False
