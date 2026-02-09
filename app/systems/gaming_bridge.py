"""
Gaming integration bridge.

 - Watches Minecraft log file for interesting events
 - Monitors optional stream status JSON file (e.g., written by Streamlabs OBS)
 - Tracks WASD/space key usage while game mode is enabled
 - Surfaces recent events for UI and provides hooks to nudge Discord presence
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import Counter, deque
from datetime import datetime
from typing import Any, Optional

from config import (GAME_KEY_MODE, GAME_MODE_ENABLED, MINECRAFT_LOG_PATH,
                    STREAM_STATUS_FILE, TITANFALL2_AUTOVOICE,
                    TITANFALL2_BRIEFING_CHANNEL_ID,
                    TITANFALL2_DISCORD_CHANNEL_ID, TITANFALL2_IDLE_CHANNEL_ID,
                    TITANFALL2_REPORT_CHANNEL_ID)
from systems import ronin_ai, titanfall

try:
    import keyboard  # type: ignore
except Exception:
    keyboard = None  # type: ignore

_events: "deque[dict[str, Any]]" = deque(maxlen=200)
_log_thread: Optional[threading.Thread] = None
_stream_thread: Optional[threading.Thread] = None
_key_thread: Optional[threading.Thread] = None
_stop = False
_game_mode = GAME_MODE_ENABLED
_stream_live = False
_stream_title = ""
_stream_game = ""
_stream_url = ""
_key_counter = Counter()
_last_key_event = 0.0
_key_mode = GAME_KEY_MODE if GAME_KEY_MODE in {"learning", "keepawake"} else "keepawake"
_session_thread: Optional[threading.Thread] = None
_session_stop = threading.Event()
_mission_active = False
_mission_state = "offline"
_autovoice_enabled = bool(TITANFALL2_AUTOVOICE)
_voice_channel_id = None
_idle_voice_channel_id = None
_autovoice_joined: Optional[int] = None
try:
    _voice_channel_id = (
        int(TITANFALL2_DISCORD_CHANNEL_ID) if TITANFALL2_DISCORD_CHANNEL_ID else None
    )
except Exception:
    _voice_channel_id = None
try:
    _briefing_channel_id = (
        int(TITANFALL2_BRIEFING_CHANNEL_ID) if TITANFALL2_BRIEFING_CHANNEL_ID else None
    )
except Exception:
    _briefing_channel_id = None
try:
    _report_channel_id = (
        int(TITANFALL2_REPORT_CHANNEL_ID) if TITANFALL2_REPORT_CHANNEL_ID else None
    )
except Exception:
    _report_channel_id = None
try:
    _idle_voice_channel_id = (
        int(TITANFALL2_IDLE_CHANNEL_ID) if TITANFALL2_IDLE_CHANNEL_ID else None
    )
except Exception:
    _idle_voice_channel_id = None
_callouts_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "titanfall_callouts.json")
)
os.makedirs(os.path.dirname(_callouts_path), exist_ok=True)
_callout_map: dict[str, dict[str, Any]] = {}
_callout_loaded = False
_default_callouts = {
    "aggressive_push": [
        "need backup",
        "with me",
        "on me",
        "push with me",
        "enemy contact",
        "hostiles on me",
        "need you with me",
        "move up",
        "advance",
    ],
    "defensive_block": [
        "watch your six",
        "watch your back",
        "cover me",
        "need cover",
        "fall back",
        "pull back",
        "hold position",
        "defend here",
        "hold this point",
        "behind me",
    ],
}
_last_callout = {"phrase": "", "tag": "", "time": 0.0}
_fallback_yes = [
    "fallback granted",
    "default control",
    "give default control",
    "you can fall back",
    "hand it to default",
    "use default ai",
    "stand down",
    "bjorgsun stand down",
    "let default drive",
]
_fallback_resume = [
    "resume control",
    "take over again",
    "back on you",
    "i need you back",
    "ronin resume control",
    "bjorgsun resume control",
    "take the controls",
]


def start():
    global _log_thread, _stream_thread, _key_thread, _stop, _session_thread
    _stop = False
    if MINECRAFT_LOG_PATH and os.path.exists(MINECRAFT_LOG_PATH) and not _log_thread:
        _log_thread = threading.Thread(target=_watch_minecraft_log, daemon=True)
        _log_thread.start()
        add_event("Gaming bridge watching Minecraft log.", level="info")
    if STREAM_STATUS_FILE and not _stream_thread:
        _stream_thread = threading.Thread(target=_watch_stream_status, daemon=True)
        _stream_thread.start()
        add_event("Stream status monitor active.", level="info")
    if keyboard and not _key_thread:
        _key_thread = threading.Thread(target=_watch_keys, daemon=True)
        _key_thread.start()
    try:
        titanfall.start(add_event)
    except Exception as exc:
        add_event(f"Titanfall integration unavailable: {exc}", level="warn")
    try:
        ronin_ai.start(lambda: titanfall.get_status(), add_event)
    except Exception as exc:
        add_event(f"Ronin controller unavailable: {exc}", level="warn")
    if _session_thread is None or not _session_thread.is_alive():
        _session_stop.clear()
        _session_thread = threading.Thread(target=_watch_titanfall_session, daemon=True)
        _session_thread.start()
    try:
        _handle_voice_link(_mission_active)
    except Exception:
        pass


def stop():
    global _stop, _log_thread, _stream_thread, _key_thread, _session_thread
    _stop = True
    for th_name in ("_log_thread", "_stream_thread", "_key_thread"):
        th = globals().get(th_name)
        if th and th.is_alive():
            try:
                th.join(timeout=2)
            except Exception:
                pass
        globals()[th_name] = None
    _session_stop.set()
    if _session_thread and _session_thread.is_alive():
        try:
            _session_thread.join(timeout=2)
        except Exception:
            pass
    _session_thread = None
    try:
        titanfall.stop()
    except Exception:
        pass
    try:
        ronin_ai.stop()
    except Exception:
        pass


def add_event(text: str, level: str = "info", meta: Optional[dict] = None):
    entry = {
        "time": time.time(),
        "text": text.strip(),
        "level": level,
        "meta": meta or {},
    }
    _events.append(entry)


def get_recent_events(limit: int = 50) -> list[dict]:
    if limit <= 0:
        return list(_events)
    return list(_events)[-limit:]


def is_stream_live() -> bool:
    return _stream_live


def get_stream_info() -> dict:
    return {
        "live": _stream_live,
        "title": _stream_title,
        "game": _stream_game,
        "url": _stream_url,
    }


def set_game_mode(flag: bool):
    global _game_mode
    _game_mode = bool(flag)
    add_event(f"Game mode {'enabled' if flag else 'disabled'}.", level="info")


def get_game_mode() -> bool:
    return _game_mode


def get_key_heatmap() -> dict[str, int]:
    return dict(_key_counter)


def refresh_sources(minecraft: Optional[str] = None, stream: Optional[str] = None):
    global MINECRAFT_LOG_PATH, STREAM_STATUS_FILE
    changed = False
    if minecraft is not None and minecraft != MINECRAFT_LOG_PATH:
        MINECRAFT_LOG_PATH = minecraft
        changed = True
    if stream is not None and stream != STREAM_STATUS_FILE:
        STREAM_STATUS_FILE = stream
        changed = True
    if changed:
        stop()
        start()


def get_key_mode() -> str:
    return _key_mode


def set_key_mode(mode: str):
    global _key_mode
    value = (mode or "").strip().lower()
    if value not in {"learning", "keepawake"}:
        return
    if value == _key_mode:
        return
    _key_mode = value
    add_event(f"Key capture mode set to {_key_mode}.", level="info")


def configure_titanfall(
    *,
    log_path: Optional[str] = None,
    telemetry_path: Optional[str] = None,
    callsign: Optional[str] = None,
    enabled: Optional[bool] = None,
    voice_channel_id: Optional[str | int] = None,
    auto_voice: Optional[bool] = None,
    briefing_channel_id: Optional[str | int] = None,
    report_channel_id: Optional[str | int] = None,
    idle_voice_channel_id: Optional[str | int] = None,
):
    try:
        titanfall.configure(
            log_path=log_path,
            telemetry_path=telemetry_path,
            callsign=callsign,
            enabled=enabled,
        )
    except Exception as exc:
        add_event(f"Titanfall config update failed: {exc}", level="warn")
    if voice_channel_id is not None:
        _set_voice_channel(voice_channel_id)
        if _autovoice_enabled:
            _handle_voice_link(_mission_active)
    if auto_voice is not None:
        _set_autovoice(auto_voice)
    if briefing_channel_id is not None:
        _set_briefing_channel(briefing_channel_id)
    if report_channel_id is not None:
        _set_report_channel(report_channel_id)
    if idle_voice_channel_id is not None:
        _set_idle_voice_channel(idle_voice_channel_id)
        if _autovoice_enabled:
            _handle_voice_link(_mission_active)


def set_ronin_autonomy(flag: bool):
    try:
        ronin_ai.set_enabled(flag)
    except Exception as exc:
        add_event(f"Ronin autonomy toggle failed: {exc}", level="warn")


def set_ronin_learning(flag: bool):
    try:
        ronin_ai.set_learning(flag)
    except Exception as exc:
        add_event(f"Ronin learning toggle failed: {exc}", level="warn")


def get_ronin_profile() -> dict[str, Any]:
    try:
        return ronin_ai.get_profile()
    except Exception:
        return {}


def get_ronin_status_text() -> str:
    try:
        return ronin_ai.get_status_text()
    except Exception:
        return "Ronin autonomy unavailable."


def get_titanfall_status() -> dict[str, Any]:
    try:
        return titanfall.get_status()
    except Exception:
        return {}


def get_titanfall_orders() -> dict[str, Any]:
    try:
        return titanfall.get_orders_state()
    except Exception:
        return {}


def set_titanfall_autopilot(flag: bool) -> bool:
    try:
        titanfall.set_autopilot_enabled(flag)
        add_event(
            f"Titanfall autopilot {'enabled' if flag else 'disabled'}.", level="info"
        )
        return True
    except Exception as exc:
        add_event(f"Titanfall autopilot toggle failed: {exc}", level="warn")
        return False


def add_titanfall_order(
    text: str,
    *,
    tag: str | None = None,
    priority: int = 5,
    overwrite: bool = False,
):
    try:
        order = titanfall.add_order(
            text, tag=tag, priority=priority, context={}, overwrite=overwrite
        )
        if order:
            add_event(
                f"Order sent to Titan: {order.get('text')}", level="event", meta=order
            )
    except Exception as exc:
        add_event(f"Titanfall order failed: {exc}", level="warn")


def set_titanfall_orders(orders: list[dict | str]):
    try:
        titanfall.set_orders(orders)
    except Exception as exc:
        add_event(f"Titanfall orders update failed: {exc}", level="warn")


def clear_titanfall_orders():
    try:
        titanfall.clear_orders()
    except Exception as exc:
        add_event(f"Titanfall orders clear failed: {exc}", level="warn")


def send_titanfall_radio(text: str, contextual: bool = True):
    try:
        titanfall.send_radio_message(text, contextual=contextual)
        add_event(f"Titanfall radio: {text}", level="info")
    except Exception as exc:
        add_event(f"Titanfall radio failed: {exc}", level="warn")


def reissue_titanfall_orders() -> bool:
    try:
        return titanfall.reissue_orders()
    except Exception as exc:
        add_event(f"Titanfall reissue failed: {exc}", level="warn")
        return False


def get_titanfall_mission_state() -> str:
    return _mission_state


def is_titanfall_in_mission() -> bool:
    return _mission_active


def get_last_callout() -> dict[str, Any]:
    return dict(_last_callout)


def handle_voice_callout(text: str, meta: Optional[dict[str, Any]] = None) -> bool:
    """Handle owner voice commands from Discord voice chat."""
    if not text:
        return False
    norm = _normalize_phrase(text)
    if _process_briefing_voice(norm, text):
        return True
    if not _mission_active:
        return False
    if _handle_fallback_command(norm):
        return True
    if ronin_ai.is_fallback_active():
        add_event(
            "Default Titan AI currently in control. Say 'Ronin resume control' when you need me back.",
            level="info",
        )
        return False
    if ronin_ai.is_fallback_pending():
        add_event(
            "Awaiting permission to hand control to default Titan AI.", level="warn"
        )
    tag, key_phrase = _match_callout(text, norm)
    if not tag:
        return False
    try:
        status = titanfall.get_status()
    except Exception:
        status = {}
    context = status if isinstance(status, dict) else {}
    triggered = ronin_ai.trigger_callout(tag, context)
    if not triggered:
        return False
    phrase = key_phrase or text.strip()
    _last_callout.update({"phrase": phrase, "tag": tag, "time": time.time()})
    add_event(
        f"Callout '{phrase}' acknowledged → {tag.replace('_', ' ')}.", level="event"
    )
    return True


def _watch_titanfall_session():
    global _mission_state, _mission_active, _session_thread
    last_state = ""
    last_active = None
    last_snapshot: Optional[dict[str, Any]] = None
    while not _session_stop.is_set():
        try:
            status = titanfall.get_status()
        except Exception:
            status = {}
        mission_state = (status.get("mission_state") or "offline").strip().lower()
        active = bool(status.get("in_mission"))
        if mission_state != last_state:
            _mission_state = mission_state
            last_state = mission_state
            label = mission_state.replace("_", " ").title()
            add_event(f"Titanfall mission state: {label}", level="info")
            if mission_state == "staging" and _mission_state not in {"in_mission"}:
                _offer_briefing(status)
            if mission_state == "in_mission" and _briefing_active:
                _complete_briefing(forced=True)
        if active != last_active:
            _mission_active = active
            last_active = active
            _handle_voice_link(active)
            if not active and last_snapshot:
                _post_battle_report(last_snapshot)
        time.sleep(1.5)
        last_snapshot = status
    _session_thread = None


def _handle_voice_link(active: bool):
    if not _autovoice_enabled:
        return
    target = _voice_channel_id if active else _idle_voice_channel_id
    if target:
        if _autovoice_joined == target:
            return
        label = "mission" if active else "idle"
        _connect_voice(target, label)
    else:
        _release_voice_link()


def _release_voice_link():
    global _autovoice_joined
    if _autovoice_joined is None:
        return
    bridge = _get_discord_bridge()
    ok = False
    if bridge:
        try:
            ok = bridge.leave_voice()
        except Exception:
            ok = False
    if ok:
        _autovoice_joined = None
        add_event("Discord voice released.", level="info")


def _connect_voice(channel_id: int, mode_label: str = "") -> bool:
    global _autovoice_joined
    bridge = _get_discord_bridge()
    if not bridge:
        add_event("Discord bridge unavailable; cannot join voice.", level="warn")
        return False
    try:
        ok = bridge.join_owner_or_channel(channel_id)
    except Exception as exc:
        add_event(f"Discord voice join failed: {exc}", level="warn")
        ok = False
    if ok:
        _autovoice_joined = channel_id
        if mode_label:
            add_event(f"Discord voice linked ({mode_label}).", level="info")
    return ok


def join_voice_channel(mode: str = "mission") -> bool:
    mode = (mode or "mission").strip().lower()
    target = _voice_channel_id if mode == "mission" else _idle_voice_channel_id
    if not target:
        add_event(f"No voice channel configured for {mode} state.", level="warn")
        return False
    if _autovoice_joined == target:
        add_event(f"Already connected to {mode} voice channel.", level="info")
        return True
    return _connect_voice(target, mode)


def leave_voice_channel():
    _release_voice_link()


def _set_voice_channel(value: str | int):
    global _voice_channel_id
    parsed = _parse_voice_channel(value)
    if parsed == _voice_channel_id:
        return
    _voice_channel_id = parsed
    if parsed:
        add_event(f"Titanfall voice target set to channel {parsed}.", level="info")
    else:
        add_event("Titanfall voice target set to owner presence.", level="info")


def _set_briefing_channel(value: str | int | None):
    global _briefing_channel_id
    parsed = _parse_voice_channel(value)
    if parsed == _briefing_channel_id:
        return
    _briefing_channel_id = parsed
    if parsed:
        add_event(f"Misson briefing channel set to {parsed}.", level="info")
    else:
        add_event("Mission briefing channel cleared.", level="info")


def _set_report_channel(value: str | int | None):
    global _report_channel_id
    parsed = _parse_voice_channel(value)
    if parsed == _report_channel_id:
        return
    _report_channel_id = parsed
    if parsed:
        add_event(f"Battle report channel set to {parsed}.", level="info")
    else:
        add_event("Battle report channel cleared.", level="info")


def _set_idle_voice_channel(value: str | int | None):
    global _idle_voice_channel_id
    parsed = _parse_voice_channel(value)
    if parsed == _idle_voice_channel_id:
        return
    _idle_voice_channel_id = parsed
    if parsed:
        add_event(f"Idle voice channel set to {parsed}.", level="info")
    else:
        add_event("Idle voice channel cleared.", level="info")
    if _autovoice_enabled:
        _handle_voice_link(_mission_active)


def _parse_voice_channel(value: str | int | None) -> Optional[int]:
    if value is None:
        return None
    try:
        token = str(value).strip()
    except Exception:
        return None
    if not token:
        return None
    token = token.replace("<", "").replace(">", "").replace("#", "")
    try:
        return int(token)
    except Exception:
        return None


def _set_autovoice(flag: bool):
    global _autovoice_enabled
    if _autovoice_enabled == bool(flag):
        return
    _autovoice_enabled = bool(flag)
    note = (
        "Auto voice enabled for Titanfall missions."
        if _autovoice_enabled
        else "Auto voice disabled."
    )
    add_event(note, level="info")
    if not _autovoice_enabled:
        _release_voice_link()
    else:
        _handle_voice_link(_mission_active)


def _normalize_phrase(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _match_callout(
    text: str, norm: Optional[str] = None
) -> tuple[Optional[str], Optional[str]]:
    norm = norm or _normalize_phrase(text)
    if not norm:
        return None, None
    _load_callouts()
    for phrase, meta in _callout_map.items():
        if phrase and phrase in norm:
            return meta.get("tag"), phrase
    for tag, phrases in _default_callouts.items():
        for phrase in phrases:
            if phrase in norm:
                _learn_callout(norm, tag)
                return tag, phrase
    if "enemy contact" in norm or "contact on me" in norm:
        _learn_callout(norm, "aggressive_push")
        return "aggressive_push", "enemy contact"
    if "need backup" in norm or "with me" in norm:
        _learn_callout(norm, "aggressive_push")
        return "aggressive_push", "need backup"
    if "watch your six" in norm or "cover me" in norm or "fall back" in norm:
        _learn_callout(norm, "defensive_block")
        return "defensive_block", "watch your six"
    return None, None


def _learn_callout(phrase: str, tag: str):
    if not phrase or not tag:
        return
    _load_callouts()
    entry = _callout_map.setdefault(phrase, {"tag": tag, "count": 0})
    entry["tag"] = tag
    entry["count"] = int(entry.get("count") or 0) + 1
    _save_callouts()


def _load_callouts():
    global _callout_loaded, _callout_map
    if _callout_loaded:
        return
    if os.path.exists(_callouts_path):
        try:
            with open(_callouts_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                _callout_map = data
        except Exception:
            _callout_map = {}
    _callout_loaded = True


def _save_callouts():
    try:
        with open(_callouts_path, "w", encoding="utf-8") as fh:
            json.dump(_callout_map, fh, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _get_discord_bridge():
    try:
        from systems import discord_bridge as _db
    except Exception:
        return None
    return _db


def _handle_fallback_command(norm: str) -> bool:
    if not norm:
        return False
    for phrase in _fallback_yes:
        if phrase in norm:
            if ronin_ai.approve_fallback():
                add_event("Default Titan AI granted by owner command.", level="info")
            return True
    for phrase in _fallback_resume:
        if phrase in norm:
            if ronin_ai.restore_control(force=True):
                add_event("Ronin back at the controls.", level="info")
            return True
    return False


def _offer_briefing(status: Optional[dict[str, Any]]):
    global _briefing_pending, _briefing_active, _briefing_buffer, _last_briefing_prompt
    if not _briefing_channel_id or _briefing_pending or _briefing_active:
        return
    _briefing_buffer = []
    _briefing_pending = True
    _last_briefing_prompt = time.time()
    add_event(
        "Mission briefing requested. Say 'start briefing' or 'skip briefing'.",
        level="info",
    )
    _speak("Mission briefing ready. Say 'start briefing' or 'skip briefing'.")


def _begin_briefing():
    global _briefing_pending, _briefing_active, _briefing_buffer
    if not _briefing_pending:
        return
    _briefing_pending = False
    _briefing_active = True
    _briefing_buffer = []
    add_event("Recording mission briefing…", level="info")
    _speak("Recording briefing. Say 'briefing complete' when finished.")


def _cancel_briefing(reason: str = ""):
    global _briefing_pending, _briefing_active, _briefing_buffer
    if not (_briefing_pending or _briefing_active):
        return
    _briefing_pending = False
    _briefing_active = False
    _briefing_buffer = []
    note = "Mission briefing skipped."
    if reason:
        note = f"{note} ({reason})"
    add_event(note, level="info")


def _append_briefing_line(text: str):
    if not _briefing_active or not text.strip():
        return
    _briefing_buffer.append({"time": time.time(), "text": text.strip()})


def _complete_briefing(forced: bool = False):
    global _briefing_active, _briefing_pending, _briefing_buffer
    if not _briefing_active:
        if forced:
            _briefing_pending = False
        return
    _briefing_active = False
    _briefing_pending = False
    if not _briefing_buffer:
        add_event("Briefing closed (no content).", level="info")
        return
    lines = []
    for item in _briefing_buffer:
        stamp = datetime.fromtimestamp(item["time"]).strftime("%H:%M:%S")
        lines.append(f"[{stamp}] {item['text']}")
    payload = "Mission Briefing\n" + "\n".join(lines)
    if _post_to_channel(_briefing_channel_id, payload, "Briefing"):
        add_event("Mission briefing posted.", level="info")
    _briefing_buffer = []


def _process_briefing_voice(norm: str, raw: str) -> bool:
    if not norm:
        return False
    if _briefing_pending:
        if (
            "start briefing" in norm
            or "begin briefing" in norm
            or ("briefing" in norm and "yes" in norm)
        ):
            _begin_briefing()
            return True
        if "skip briefing" in norm or ("briefing" in norm and "no" in norm):
            _cancel_briefing("owner declined")
            return True
    elif _briefing_active:
        if (
            "briefing complete" in norm
            or "end briefing" in norm
            or "briefing done" in norm
        ):
            _complete_briefing()
            _speak("Briefing saved.")
            return True
        _append_briefing_line(raw)
        return True
    return False


def _post_battle_report(status: Optional[dict[str, Any]]):
    global _last_report_time
    if not _report_channel_id or not status:
        return
    now = time.time()
    if now - _last_report_time < 5:
        return
    match_info = status.get("match") or {}
    titan = status.get("titan") or {}
    score = match_info.get("score") or {}
    friend = score.get("friend") or score.get("friendly") or 0
    foe = score.get("foe") or score.get("enemy") or 0
    map_name = match_info.get("map") or "Unknown"
    mode = match_info.get("mode") or ""
    status_line = status.get("mission_state") or "menu"
    callout = _last_callout.get("phrase")
    callout_tag = _last_callout.get("tag")
    profile = ronin_ai.get_profile()
    fallback = profile.get("fallback") or {}
    fallback_state = (
        "active"
        if fallback.get("active")
        else "awaiting" if fallback.get("awaiting") else "off"
    )
    lines = [
        f"Mission complete at {datetime.fromtimestamp(now).strftime('%H:%M:%S')}",
        f"Map: {map_name} ({mode})",
        f"Score: {friend}-{foe}",
        f"Mission state: {status_line}",
        f"Titan: {titan.get('chassis') or 'Unknown'} HP {titan.get('health') or '?'} Shield {titan.get('shield') or '?'}",
        f"Last callout: {callout or 'none'} ({callout_tag or 'n/a'})",
        f"Fallback state: {fallback_state}",
        f"Patterns known: {len(profile.get('patterns') or [])} contexts {profile.get('contexts', 0)}",
    ]
    text = "\n".join(lines)
    if _post_to_channel(_report_channel_id, text, "Battle report"):
        _last_report_time = now


def _post_to_channel(channel_id: Optional[int], text: str, label: str = "") -> bool:
    if not channel_id or not text.strip():
        return False
    bridge = _get_discord_bridge()
    if not bridge:
        return False
    try:
        ok = bridge.post_system_message(channel_id, text)
    except Exception:
        ok = False
    if ok and label:
        add_event(f"{label} posted to Discord.", level="info")
    return ok


def _speak(text: str):
    if not text:
        return
    try:
        from systems import audio as _audio

        _audio.alert_speak(text)
    except Exception:
        add_event(text, level="info")


def _watch_minecraft_log():
    path = MINECRAFT_LOG_PATH
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            while not _stop:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                line = line.strip()
                if not line:
                    continue
                event = _parse_minecraft_line(line)
                if event:
                    add_event(
                        event["text"], level=event.get("level", "info"), meta=event
                    )
    except FileNotFoundError:
        add_event("Minecraft log path not found.", level="warn")
    except Exception as exc:
        add_event(f"Minecraft log watcher error: {exc}", level="error")


def _parse_minecraft_line(line: str) -> Optional[dict]:
    lower = line.lower()
    if "[chat]" in lower:
        msg = line.split("]:", 1)[-1].strip()
        return {"text": f"Chat: {msg}", "level": "chat"}
    if "joined the game" in lower:
        player = line.split(">", 1)[-1].replace("joined the game", "").strip()
        return {"text": f"{player} joined the server.", "level": "event"}
    if "left the game" in lower:
        player = line.split(">", 1)[-1].replace("left the game", "").strip()
        return {"text": f"{player} left the server.", "level": "event"}
    if (
        "was slain" in lower
        or "fell" in lower
        or "burned" in lower
        or "drowned" in lower
    ):
        return {
            "text": f"Death event: {line.split(']:',1)[-1].strip()}",
            "level": "warn",
        }
    if "[advancements]" in lower or "has made the advancement" in lower:
        msg = line.split("]:", 1)[-1].strip()
        return {"text": f"Advancement: {msg}", "level": "info"}
    return None


def _watch_stream_status():
    global _stream_live, _stream_title, _stream_game, _stream_url
    last_mtime = 0.0
    while not _stop:
        path = STREAM_STATUS_FILE
        if not path:
            break
        try:
            mtime = os.path.getmtime(path)
        except FileNotFoundError:
            if _stream_live:
                set_stream_status(False)
            time.sleep(5)
            continue
        except Exception:
            time.sleep(5)
            continue
        if mtime == last_mtime:
            time.sleep(2)
            continue
        last_mtime = mtime
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            add_event(f"Stream status parse error: {exc}", level="warn")
            time.sleep(2)
            continue
        live = bool(data.get("live"))
        title = data.get("title") or ""
        game = data.get("game") or ""
        url = data.get("url") or ""
        set_stream_status(live, title, game, url)
        time.sleep(2)


def _watch_keys():
    if keyboard is None:
        return
    watch_keys = {"w", "a", "s", "d", "space", "shift"}

    def _on_key(event):
        if not _game_mode:
            return
        name = event.name.lower()
        if name in watch_keys:
            _key_counter[name] += 1
            global _last_key_event
            _last_key_event = time.time()
            if _key_mode == "learning":
                add_event(
                    f"Key input detected: {name}",
                    level="input",
                    meta={"key": name, "time": _last_key_event},
                )
            try:
                ronin_ai.record_manual_key(name)
            except Exception:
                pass

    try:
        keyboard.on_press(_on_key)
        while not _stop:
            time.sleep(1)
    except Exception:
        pass


def set_stream_status(live: bool, title: str = "", game: str = "", url: str = ""):
    global _stream_live, _stream_title, _stream_game, _stream_url
    changed = live != _stream_live or title != _stream_title or game != _stream_game
    _stream_live = bool(live)
    _stream_title = title or ""
    _stream_game = game or ""
    _stream_url = url or ""
    if changed:
        if _stream_live:
            label = _stream_title or _stream_game or "Streaming"
            add_event(f"Stream live: {label}", level="info")
        else:
            add_event("Stream offline.", level="info")
    try:
        from systems import discord_bridge

        if _stream_live:
            label = _stream_title or _stream_game or "Streaming"
            discord_bridge.set_presence("online", label, stream_url=_stream_url or "")
        else:
            discord_bridge.set_presence("online", "")
    except Exception:
        pass


_briefing_pending = False
_briefing_active = False
_briefing_buffer: list[dict[str, Any]] = []
_last_briefing_prompt = 0.0
_last_report_time = 0.0
