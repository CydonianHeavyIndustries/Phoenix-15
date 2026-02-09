"""
Titanfall 2 integration helpers.

This module tails the Titanfall 2 (or Northstar) log file for cinematic cues and,
optionally, ingests a telemetry JSON file produced by the community telemetry mod.

- Log tailing catches high-level "Titan ready / doom / destroy" style lines.
- Telemetry parsing keeps track of map/mode, scores, pilot stats, and Titan vitals.
- Status snapshots are exposed to the UI via systems.gaming_bridge.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time
import uuid
from typing import Any, Callable, Optional

from config import (TITANFALL2_CALLSIGN, TITANFALL2_COMMAND_FILE,
                    TITANFALL2_ENABLED, TITANFALL2_LOG_PATH,
                    TITANFALL2_TELEMETRY_FILE, TITANFALL2_AUTOPILOT)

EventCallback = Callable[[str, str, Optional[dict[str, Any]]], None]

_event_cb: EventCallback


def _noop_event(text: str, level: str = "info", meta: Optional[dict[str, Any]] = None):
    return None


_event_cb = _noop_event
_status_lock = threading.RLock()
_stop = False
_running = False
_log_thread: Optional[threading.Thread] = None
_state_thread: Optional[threading.Thread] = None
_log_path = TITANFALL2_LOG_PATH
_telemetry_path = TITANFALL2_TELEMETRY_FILE
_enabled_flag = bool(TITANFALL2_ENABLED)
_error_marks: dict[str, float] = {"log": 0.0, "telemetry": 0.0, "parse": 0.0}
_telemetry_prev = {"titan_status": "", "core_ready": False, "titan_ready": False}
_order_lock = threading.RLock()
_command_thread: Optional[threading.Thread] = None
_orders_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "titanfall_orders.json")
)
_command_path = (
    TITANFALL2_COMMAND_FILE
    or os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "titanfall_commands.json")
    )
)
os.makedirs(os.path.dirname(_orders_path), exist_ok=True)
os.makedirs(os.path.dirname(_command_path), exist_ok=True)
_orders_state: dict[str, Any] = {
    "version": 1,
    "autopilot_enabled": bool(TITANFALL2_AUTOPILOT),
    "orders": [],
    "radio_queue": [],
    "last_updated": 0.0,
    "last_written": 0.0,
}

_status = {
    "callsign": TITANFALL2_CALLSIGN or "Bjorgsun-26",
    "connected": False,
    "log_connected": False,
    "telemetry_connected": False,
    "last_event": "",
    "last_event_level": "info",
    "last_update": 0.0,
    "pilot": {
        "name": "",
        "callsign": TITANFALL2_CALLSIGN or "Bjorgsun-26",
        "loadout": "",
        "elims": 0,
        "deaths": 0,
        "streak": 0,
    },
    "titan": {
        "chassis": "",
        "loadout": "",
        "core": "",
        "status": "offline",
        "health": 0,
        "shield": 0,
        "battery": 0,
        "cooldown": 0.0,
        "ready": False,
        "core_ready": False,
    },
    "match": {
        "state": "idle",
        "map": "",
        "mode": "",
        "server": "",
        "playlist": "",
        "team": "",
        "players": 0,
        "time_remaining": "",
        "score": {"friend": 0, "foe": 0},
    },
    "mission_state": "offline",
    "in_mission": False,
}


def _load_orders_state():
    global _orders_state
    if not os.path.exists(_orders_path):
        return
    try:
        with open(_orders_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            with _order_lock:
                for key, val in data.items():
                    if key in {"orders", "radio_queue"} and not isinstance(val, list):
                        continue
                    _orders_state[key] = val
    except Exception:
        pass


def _persist_orders_state():
    snapshot = get_orders_state()
    tmp = _orders_path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, _orders_path)
    except Exception:
        pass


_load_orders_state()


def start(event_callback: Optional[EventCallback] = None) -> bool:
    """Start Titanfall threads. Returns True if any watcher was launched."""
    global _event_cb, _stop, _running, _log_thread, _state_thread
    if event_callback is not None:
        _event_cb = event_callback
    _stop = False
    if not _should_run():
        _running = False
        return False
    started = False
    if _log_path and not _log_thread:
        _log_thread = threading.Thread(target=_watch_log, daemon=True)
        _log_thread.start()
        started = True
    if _telemetry_path and not _state_thread:
        _state_thread = threading.Thread(target=_watch_telemetry, daemon=True)
        _state_thread.start()
        started = True
    if _ensure_command_thread():
        started = True
    _running = started
    if started:
        _status_message("Titanfall link armed.", level="info")
    return started


def stop():
    """Stop all watchers."""
    global _stop, _log_thread, _state_thread, _running
    _stop = True
    for name in ("_log_thread", "_state_thread"):
        th = globals().get(name)
        if th and th.is_alive():
            try:
                th.join(timeout=2)
            except Exception:
                pass
        globals()[name] = None
    _stop_command_thread()
    _running = False
    _set_connected("log", False)
    _set_connected("telemetry", False)


def configure(
    *,
    log_path: Optional[str] = None,
    telemetry_path: Optional[str] = None,
    callsign: Optional[str] = None,
    enabled: Optional[bool] = None,
):
    """Update runtime settings."""
    global _log_path, _telemetry_path, _enabled_flag
    changed = False
    if log_path is not None and log_path != _log_path:
        _log_path = log_path.strip()
        changed = True
    if telemetry_path is not None and telemetry_path != _telemetry_path:
        _telemetry_path = telemetry_path.strip()
        changed = True
    if enabled is not None:
        flag = bool(enabled)
        if flag != _enabled_flag:
            _enabled_flag = flag
            changed = True
    if callsign is not None:
        _set_callsign(callsign)
    if changed:
        _restart_threads()


def set_callsign(value: str):
    _set_callsign(value)


def get_status() -> dict[str, Any]:
    with _status_lock:
        return copy.deepcopy(_status)


def is_running() -> bool:
    return _running


# --------------------------------------------------------------------------
# Autopilot orders + command channel
# --------------------------------------------------------------------------
def get_orders_state() -> dict[str, Any]:
    with _order_lock:
        snap = copy.deepcopy(_orders_state)
    snap["callsign"] = _status.get("callsign")
    return snap


def set_autopilot_enabled(flag: bool) -> bool:
    with _order_lock:
        _orders_state["autopilot_enabled"] = bool(flag)
        _orders_state["last_updated"] = time.time()
    _persist_orders_state()
    _flush_command_file(force=True, reason="autopilot_toggle")
    _status_message(
        f"Autopilot {'enabled' if flag else 'disabled'} for Titanfall orders.",
        level="info",
    )
    return True


def set_orders(orders: list[dict[str, Any] | str]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in orders or []:
        norm = _normalize_order(item)
        if norm:
            normalized.append(norm)
    with _order_lock:
        _orders_state["orders"] = normalized
        _orders_state["last_updated"] = time.time()
    _persist_orders_state()
    _flush_command_file(force=True, reason="set_orders")
    _status_message(f"{len(normalized)} Titanfall orders now active.", level="info")
    return normalized


def add_order(
    text: str,
    *,
    tag: Optional[str] = None,
    priority: int = 5,
    context: Optional[dict[str, Any]] = None,
    overwrite: bool = False,
) -> Optional[dict[str, Any]]:
    order = _normalize_order(
        {
            "text": text,
            "tag": tag,
            "priority": priority,
            "context": context or {},
        }
    )
    if not order:
        return None
    with _order_lock:
        if overwrite:
            _orders_state["orders"] = [order]
        else:
            _orders_state.setdefault("orders", []).append(order)
        _orders_state["last_updated"] = time.time()
    _persist_orders_state()
    _flush_command_file(force=True, reason="add_order")
    _status_message(
        f"Titanfall order queued: {order.get('text')}", level="info",  # type: ignore[arg-type]
    )
    return order


def clear_orders():
    with _order_lock:
        _orders_state["orders"] = []
        _orders_state["last_updated"] = time.time()
    _persist_orders_state()
    _flush_command_file(force=True, reason="clear_orders")
    _status_message("Titanfall orders cleared.", level="info")


def send_radio_message(text: str, *, contextual: bool = True) -> bool:
    if not text:
        return False
    msg = {
        "id": f"msg-{uuid.uuid4().hex[:8]}",
        "text": text.strip(),
        "timestamp": time.time(),
        "contextual": bool(contextual),
    }
    if contextual:
        msg["context"] = _context_snapshot()
    with _order_lock:
        _orders_state.setdefault("radio_queue", []).append(msg)
        _orders_state["last_updated"] = time.time()
    _persist_orders_state()
    _flush_command_file(force=True, reason="radio")
    _status_message(f"Titanfall comms: {text}", level="info")
    return True


def reissue_orders() -> bool:
    return _flush_command_file(force=True, reason="manual_reissue")


def _set_callsign(value: Optional[str]):
    call = (value or "").strip() or "Bjorgsun-26"
    with _status_lock:
        _status["callsign"] = call
        _status["pilot"]["callsign"] = call


def _should_run() -> bool:
    return bool(_enabled_flag or _log_path or _telemetry_path)


def _restart_threads():
    prev_cb = _event_cb
    was_running = _running
    stop()
    if was_running or _should_run():
        start(prev_cb)


def _normalize_order(entry: dict[str, Any] | str) -> Optional[dict[str, Any]]:
    if isinstance(entry, str):
        if not entry.strip():
            return None
        entry = {"text": entry.strip()}
    if not isinstance(entry, dict):
        return None
    text = (entry.get("text") or "").strip()
    if not text:
        return None
    tag = (entry.get("tag") or "").strip().lower() or None
    try:
        priority = int(entry.get("priority") or 5)
    except Exception:
        priority = 5
    priority = max(1, min(priority, 9))
    payload = {
        "id": entry.get("id") or f"ord-{uuid.uuid4().hex[:8]}",
        "text": text,
        "tag": tag,
        "priority": priority,
        "issued_at": entry.get("issued_at") or time.time(),
        "updated_at": time.time(),
        "context": entry.get("context") or {},
        "persist": True,
    }
    return payload


def _context_snapshot() -> dict[str, Any]:
    with _status_lock:
        titan = copy.deepcopy(_status.get("titan") or {})
        match_info = copy.deepcopy(_status.get("match") or {})
        mission_state = _status.get("mission_state")
    return {
        "mission_state": mission_state,
        "titan": titan,
        "match": match_info,
    }


def _ensure_command_thread() -> bool:
    global _command_thread
    if _command_thread and _command_thread.is_alive():
        return False
    _command_thread = threading.Thread(
        target=_command_loop, name="TitanfallCommandLoop", daemon=True
    )
    _command_thread.start()
    return True


def _stop_command_thread():
    global _command_thread
    if _command_thread and _command_thread.is_alive():
        try:
            _command_thread.join(timeout=1.5)
        except Exception:
            pass
    _command_thread = None


def _command_loop():
    while not _stop:
        _flush_command_file()
        time.sleep(2.5)


def _flush_command_file(force: bool = False, reason: str = "") -> bool:
    now = time.time()
    with _order_lock:
        last_written = float(_orders_state.get("last_written") or 0.0)
        last_updated = float(_orders_state.get("last_updated") or 0.0)
        autopilot = bool(_orders_state.get("autopilot_enabled", True))
        radio = list(_orders_state.get("radio_queue") or [])
        orders = list(_orders_state.get("orders") or [])
    changed = last_updated > last_written
    heartbeat_due = now - last_written >= 8.0
    if not force and not changed and not heartbeat_due:
        return False
    packet = {
        "timestamp": now,
        "callsign": _status.get("callsign"),
        "autopilot_enabled": autopilot,
        "orders": orders,
        "remember": True,
        "context": _context_snapshot(),
    }
    if radio:
        packet["radio"] = radio
    try:
        with open(_command_path, "w", encoding="utf-8") as fh:
            json.dump(packet, fh, indent=2, ensure_ascii=False)
        with _order_lock:
            _orders_state["last_written"] = now
            _orders_state["radio_queue"] = []
        if reason:
            _status_message(f"Titanfall command sync ({reason}).", level="info")
        return True
    except Exception as exc:
        _throttled_warn("command", f"Unable to write Titanfall commands: {exc}", "warn")
    return False


def _watch_log():
    global _stop
    while not _stop:
        path = _log_path
        if not path:
            break
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(0, os.SEEK_END)
                _set_connected("log", True)
                _status_message("Titanfall log linked.", level="info")
                while not _stop:
                    where = handle.tell()
                    line = handle.readline()
                    if not line:
                        _sleep(0.5)
                        handle.seek(where)
                        continue
                    line = line.strip()
                    if not line:
                        continue
                    event = _parse_log_line(line)
                    if event:
                        _apply_log_event(event)
        except FileNotFoundError:
            _set_connected("log", False)
            _throttled_warn(
                "log",
                "Titanfall log not found. Point to client_mp.log or r1pc.log.",
                "warn",
            )
            _sleep(5)
        except Exception as exc:
            _set_connected("log", False)
            _throttled_warn("log_err", f"Titanfall log monitor error: {exc}", "error")
            _sleep(3)
        else:
            break


def _watch_telemetry():
    global _stop
    last_mtime = 0.0
    while not _stop:
        path = _telemetry_path
        if not path:
            break
        try:
            mtime = os.path.getmtime(path)
        except FileNotFoundError:
            _set_connected("telemetry", False)
            _throttled_warn(
                "telemetry",
                "Telemetry file missing. Enable the Northstar telemetry mod.",
                "warn",
            )
            _sleep(3)
            continue
        except Exception as exc:
            _set_connected("telemetry", False)
            _throttled_warn("telemetry_err", f"Telemetry access error: {exc}", "error")
            _sleep(3)
            continue
        if mtime == last_mtime:
            _sleep(1.2)
            continue
        last_mtime = mtime
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception as exc:
            _throttled_warn("parse", f"Telemetry parse error: {exc}", "warn")
            _sleep(1.5)
            continue
        _set_connected("telemetry", True)
        _apply_telemetry(payload)


def _apply_log_event(event: dict[str, Any]):
    patch = event.get("status") or {}
    if patch:
        _merge_status(patch)
    meta = {"source": "titanfall", "channel": "log"}
    meta.update(event.get("meta") or {})
    delta = meta.get("delta")
    if delta:
        try:
            delta_int = int(delta)
        except Exception:
            delta_int = 0
        if delta_int:
            with _status_lock:
                current = int(_status["titan"].get("battery") or 0)
                _status["titan"]["battery"] = max(0, current + delta_int)
                _status["last_update"] = time.time()
    meta.pop("delta", None)
    _push_event(
        event.get("text") or "Titanfall update",
        level=event.get("level", "info"),
        meta=meta,
    )


def _apply_telemetry(payload: dict[str, Any]):
    match = payload.get("match") or payload.get("session") or {}
    titan = payload.get("titan") or payload.get("titanfall") or {}
    pilot = payload.get("pilot") or {}
    map_name = (
        payload.get("map")
        or match.get("map_display")
        or match.get("mapName")
        or match.get("map")
        or ""
    )
    mode = (
        payload.get("mode")
        or match.get("mode_display")
        or match.get("playlist_name")
        or match.get("mode")
        or ""
    )
    playlist = match.get("playlist") or payload.get("playlist") or ""
    server = match.get("server") or payload.get("server") or ""
    team = match.get("team") or payload.get("team") or ""
    players = (
        payload.get("players")
        or match.get("players")
        or match.get("playerCount")
        or (
            len(match.get("roster", [])) if isinstance(match.get("roster"), list) else 0
        )
    )
    time_remaining = (
        payload.get("time_remaining")
        or match.get("time_remaining")
        or match.get("timeRemaining")
        or ""
    )
    score = payload.get("score") or match.get("score") or {}
    friendly = (
        score.get("friend")
        or score.get("friendly")
        or score.get("team")
        or score.get("atlas")
        or score.get("alliance")
        or 0
    )
    enemy = (
        score.get("foe")
        or score.get("enemy")
        or score.get("opponent")
        or score.get("imc")
        or score.get("horde")
        or 0
    )
    _merge_status(
        {
            "match": {
                "map": map_name,
                "mode": mode,
                "playlist": playlist,
                "server": server,
                "team": team,
                "players": int(players or 0),
                "time_remaining": time_remaining,
                "state": payload.get("match_state")
                or match.get("state")
                or _status["match"].get("state"),
                "score": {"friend": int(friendly), "foe": int(enemy)},
            }
        }
    )
    state_token = (
        (payload.get("match_state") or match.get("state") or "").strip().lower()
    )
    titan_status = str(
        titan.get("status")
        or titan.get("state")
        or ("ready" if titan.get("ready") else "")
    ).lower()
    titan_ready = bool(
        titan.get("ready")
        or titan.get("build_percent") == 100
        or titan_status == "ready"
    )
    core_ready = bool(
        titan.get("core_ready")
        or titan.get("core") == "ready"
        or titan.get("corePercent") == 100
    )
    titan_patch = {
        "chassis": titan.get("chassis")
        or titan.get("name")
        or titan.get("title")
        or _status["titan"].get("chassis"),
        "loadout": titan.get("loadout")
        or titan.get("kit")
        or _status["titan"].get("loadout"),
        "core": titan.get("core")
        or titan.get("coreAbility")
        or _status["titan"].get("core"),
        "status": titan_status or _status["titan"].get("status"),
        "health": titan.get("health")
        or titan.get("hp")
        or _status["titan"].get("health"),
        "shield": titan.get("shield")
        or titan.get("shield_hp")
        or _status["titan"].get("shield"),
        "battery": titan.get("battery")
        or titan.get("battery_count")
        or _status["titan"].get("battery"),
        "cooldown": titan.get("build_percent")
        or titan.get("cooldown")
        or _status["titan"].get("cooldown"),
        "ready": titan_ready,
        "core_ready": core_ready,
    }
    _merge_status({"titan": titan_patch})
    pilot_patch = {
        "name": pilot.get("name")
        or payload.get("pilot_name")
        or _status["pilot"].get("name"),
        "callsign": pilot.get("callsign")
        or pilot.get("nick")
        or _status["pilot"].get("callsign"),
        "loadout": pilot.get("loadout")
        or pilot.get("kit")
        or pilot.get("class")
        or _status["pilot"].get("loadout"),
        "elims": pilot.get("elims")
        or payload.get("elims")
        or _status["pilot"].get("elims"),
        "deaths": pilot.get("deaths")
        or payload.get("deaths")
        or _status["pilot"].get("deaths"),
        "streak": pilot.get("streak")
        or payload.get("streak")
        or _status["pilot"].get("streak"),
    }
    _merge_status({"pilot": pilot_patch})
    mission_state = _compute_mission_state(
        state_token,
        map_name,
        mode,
        int(players or 0),
        bool(_status.get("connected")),
        time_remaining,
    )
    _merge_status(
        {"mission_state": mission_state, "in_mission": mission_state == "in_mission"}
    )
    _detect_telemetry_transitions(titan_status, titan_ready, core_ready)


def _detect_telemetry_transitions(
    titan_status: str, titan_ready: bool, core_ready: bool
):
    prev_status = _telemetry_prev["titan_status"]
    if titan_status and titan_status != prev_status:
        _telemetry_prev["titan_status"] = titan_status
        text = f"Titan status update: {titan_status.replace('_', ' ').title()}."
        level = "warn" if titan_status in {"doomed", "destroyed"} else "info"
        _push_event(
            text, level=level, meta={"source": "titanfall", "channel": "telemetry"}
        )
    prev_ready = _telemetry_prev["titan_ready"]
    if titan_ready and not prev_ready:
        _telemetry_prev["titan_ready"] = True
        _push_event(
            "Titanfall ready. Call him in!", level="event", meta={"source": "titanfall"}
        )
    elif not titan_ready and prev_ready:
        _telemetry_prev["titan_ready"] = False
    prev_core = _telemetry_prev["core_ready"]
    if core_ready and not prev_core:
        _telemetry_prev["core_ready"] = True
        _push_event(
            "Core systems at full charge.", level="event", meta={"source": "titanfall"}
        )
    elif not core_ready and prev_core:
        _telemetry_prev["core_ready"] = False


def _parse_log_line(line: str) -> Optional[dict[str, Any]]:
    low = line.lower()
    if "titan is ready" in low or "titan ready" in low or "titanfall ready" in low:
        return {
            "text": "Titanfall ready.",
            "level": "event",
            "status": {"titan": {"status": "ready", "ready": True}},
        }
    if "stand by for titanfall" in low or "incoming titanfall" in low:
        return {
            "text": "Standby for Titanfall!",
            "level": "event",
            "status": {"titan": {"status": "dropping"}},
        }
    if "titan doomed" in low or "is doomed" in low:
        return {
            "text": "Titan is doomed.",
            "level": "warn",
            "status": {"titan": {"status": "doomed"}},
        }
    if "titan destroyed" in low or "titan down" in low:
        return {
            "text": "Titan destroyed.",
            "level": "warn",
            "status": {"titan": {"status": "destroyed", "ready": False}},
        }
    if "core ready" in low or "core available" in low:
        return {
            "text": "Core is ready.",
            "level": "event",
            "status": {"titan": {"core_ready": True}},
        }
    if "core activated" in low or "core online" in low:
        return {
            "text": "Core activated.",
            "level": "info",
            "status": {"titan": {"core_ready": False}},
        }
    if "battery inserted" in low or "battery stolen" in low:
        delta = 1 if "inserted" in low else -1
        meta = {"delta": delta}
        return {
            "text": "Battery transfer detected.",
            "level": "info",
            "meta": meta,
        }
    if "pilot down" in low or "downed pilot" in low:
        return {"text": "Pilot down confirmed.", "level": "info"}
    if "titan down" in low or "destroyed titan" in low:
        return {"text": "Enemy Titan neutralized.", "level": "info"}
    return None


def _push_event(text: str, level: str = "info", meta: Optional[dict[str, Any]] = None):
    if not text:
        return
    meta = meta or {}
    try:
        _event_cb(text, level, meta)
    except Exception:
        try:
            _event_cb(text, level=level, meta=meta)
        except Exception:
            pass
    with _status_lock:
        _status["last_event"] = text
        _status["last_event_level"] = level
        _status["last_update"] = time.time()


def _status_message(text: str, level: str = "info"):
    _push_event(text, level=level, meta={"source": "titanfall"})


def _set_connected(kind: str, flag: bool):
    with _status_lock:
        _status[f"{kind}_connected"] = bool(flag)
        _status["connected"] = bool(
            _status.get("log_connected") or _status.get("telemetry_connected")
        )
        _status["last_update"] = time.time()


def _merge_status(patch: dict[str, Any]):
    with _status_lock:
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(_status.get(key), dict):
                for sub_key, sub_val in value.items():
                    if sub_val is None:
                        continue
                    _status[key][sub_key] = sub_val
            elif value is not None:
                _status[key] = value
        _status["connected"] = bool(
            _status.get("log_connected") or _status.get("telemetry_connected")
        )
        ms = (_status.get("mission_state") or "").strip().lower()
        if ms not in {"offline", "menu", "staging", "in_mission"}:
            ms = "menu" if _status["connected"] else "offline"
        _status["mission_state"] = ms
        _status["in_mission"] = ms == "in_mission"
        _status["last_update"] = time.time()


def _throttled_warn(slot: str, text: str, level: str = "warn", interval: float = 20.0):
    now = time.time()
    prev = _error_marks.get(slot, 0.0)
    if now - prev >= interval:
        _error_marks[slot] = now
        _status_message(text, level=level)


def _sleep(seconds: float):
    end = time.time() + max(0.0, seconds)
    while not _stop and time.time() < end:
        time.sleep(0.2)


def _compute_mission_state(
    token: str,
    map_name: str,
    mode: str,
    players: int,
    connected: bool,
    time_remaining: str,
) -> str:
    token = (token or "").strip().lower()
    playing = {
        "ingame",
        "in_game",
        "in-match",
        "match",
        "playing",
        "combat",
        "live",
        "fight",
    }
    staging = {
        "loading",
        "spawning",
        "dropping",
        "staging",
        "pre_match",
        "pre-match",
        "starting",
    }
    menus = {"menu", "title", "lobby", "frontier", "hangar", "garage"}
    if token in playing:
        return "in_mission"
    if token in staging:
        return "staging"
    if token in menus:
        return "menu"
    if time_remaining and ":" in time_remaining:
        try:
            mins = int(time_remaining.split(":", 1)[0])
        except Exception:
            mins = 0
        if mins > 0 and players >= 2:
            return "in_mission"
    if map_name and players >= 2 and (mode or "").strip():
        return "in_mission"
    if connected:
        return "menu"
    return "offline"
