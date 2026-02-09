"""
systems/timekeeper.py — Alarms, Timers, and Chrono (Stopwatch)

Provides a lightweight time-based event engine with:
- Alarms at specific clock times (optionally repeat later)
- Timers aligned to the next minute boundary (per user request)
- Chronometers (start/stop/reset)
- Current time helper

Fires events via a simple callback and also speaks/notifies by default.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from systems import audio

try:
    from systems import notify
except Exception:  # notify is optional
    notify = None  # type: ignore


# --------------------------- State -----------------------------------
_lock = threading.Lock()
_running = False
_cb: Optional[Callable[[str, str], None]] = None  # (event, label)

# Alarms are absolute times
_alarms: List[Dict] = []  # {id,label,when: iso,repeat: None|daily|weekday,active:bool}

# Timers are duration-based but start on next minute boundary
_timers: Dict[str, Dict] = (
    {}
)  # id -> {label,start_at,end_at,state:'scheduled'|'running',duration_sec}

# Chronometers (stopwatches)
_chronos: Dict[str, Dict] = {}  # label -> {running:bool,start_ts:float,elapsed:float}

_id_seq = 0


def _next_id(prefix: str) -> str:
    global _id_seq
    with _lock:
        _id_seq += 1
        return f"{prefix}-{_id_seq}"


def set_callback(cb: Callable[[str, str], None]):
    """Set a callback invoked on events: ('alarm'|'timer'|'chrono'), label."""
    global _cb
    _cb = cb


def _speak_and_notify(
    text: str, title: str = "Bjorgsun-26", tone: bool = False
) -> None:
    try:
        if tone:
            audio.play_alarm_tone()
        audio.alert_speak(text)
    except Exception:
        try:
            audio.speak(text)
        except Exception:
            pass
    try:
        if notify is not None:
            notify.notify(title, text, duration=6)
    except Exception:
        pass


# --------------------------- Helpers ---------------------------------
def current_time_string() -> str:
    now = datetime.now()
    return now.strftime("%I:%M %p on %A, %B %d").lstrip("0")


def _minute_boundary_after(dt: datetime) -> datetime:
    base = dt.replace(second=0, microsecond=0)
    return base + timedelta(minutes=1)


# --------------------------- API: Alarms ------------------------------
def add_alarm(label: str, hour: int, minute: int, repeat: Optional[str] = None) -> str:
    now = datetime.now()
    hh = int(hour) % 24
    mm = int(minute) % 60
    t = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if t <= now:
        t = t + timedelta(days=1)
    aid = _next_id("alarm")
    with _lock:
        _alarms.append(
            {
                "id": aid,
                "label": (label or "Alarm").strip() or "Alarm",
                "when": t.isoformat(),
                "repeat": (repeat if repeat in {None, "daily", "weekday"} else None),
                "active": True,
            }
        )
    return aid


def remove_alarm(aid_or_label: str) -> bool:
    key = (aid_or_label or "").strip().lower()
    with _lock:
        for i, a in enumerate(list(_alarms)):
            if key in (a.get("id", "").lower(), a.get("label", "").strip().lower()):
                _alarms.pop(i)
                return True
    return False


def list_alarms() -> List[Dict]:
    with _lock:
        return [a.copy() for a in _alarms]


# --------------------------- API: Timers ------------------------------
def start_timer(label: str, minutes: int, align_to_next_minute: bool = True) -> Dict:
    now = datetime.now()
    start_at = _minute_boundary_after(now) if align_to_next_minute else now
    end_at = start_at + timedelta(minutes=int(minutes))
    tid = _next_id("timer")
    data = {
        "id": tid,
        "label": (label or "Timer").strip() or "Timer",
        "start_at": start_at.timestamp(),
        "end_at": end_at.timestamp(),
        "duration_sec": int(minutes) * 60,
        "state": "scheduled" if align_to_next_minute else "running",
    }
    with _lock:
        _timers[tid] = data
    # Announce plan per request
    try:
        s = start_at.strftime("%H:%M")
        e = end_at.strftime("%H:%M")
        _speak_and_notify(
            f"Timer '{data['label']}' — starting at {s}, ringing at {e}.", tone=False
        )
    except Exception:
        pass
    return data.copy()


def cancel_timer(tid_or_label: str) -> bool:
    key = (tid_or_label or "").strip().lower()
    with _lock:
        for k, v in list(_timers.items()):
            if key in (k.lower(), v.get("label", "").strip().lower()):
                _timers.pop(k, None)
                return True
    return False


def get_timer_status(tid_or_label: Optional[str] = None) -> List[Dict]:
    with _lock:
        items = list(_timers.values())
    out = []
    now = time.time()
    for t in items:
        rem = max(0, int(t.get("end_at", now) - now))
        out.append(
            {
                "id": t.get("id"),
                "label": t.get("label"),
                "state": t.get("state"),
                "remaining_sec": rem,
            }
        )
    if tid_or_label:
        key = tid_or_label.strip().lower()
        out = [x for x in out if key in (x["id"].lower(), x["label"].strip().lower())]
    return out


# --------------------------- API: Chrono ------------------------------
def chrono_start(label: str = "Stopwatch") -> str:
    lab = (label or "Stopwatch").strip() or "Stopwatch"
    with _lock:
        c = _chronos.get(lab) or {"running": False, "start_ts": 0.0, "elapsed": 0.0}
        if not c["running"]:
            c["running"] = True
            c["start_ts"] = time.time()
        _chronos[lab] = c
    return lab


def chrono_stop(label: str = "Stopwatch") -> float:
    lab = (label or "Stopwatch").strip() or "Stopwatch"
    with _lock:
        c = _chronos.get(lab)
        if not c:
            return 0.0
        if c["running"]:
            c["elapsed"] += time.time() - c["start_ts"]
            c["running"] = False
        return c["elapsed"]


def chrono_reset(label: str = "Stopwatch") -> None:
    lab = (label or "Stopwatch").strip() or "Stopwatch"
    with _lock:
        _chronos[lab] = {"running": False, "start_ts": 0.0, "elapsed": 0.0}


def chrono_elapsed(label: str = "Stopwatch") -> float:
    lab = (label or "Stopwatch").strip() or "Stopwatch"
    with _lock:
        c = _chronos.get(lab)
        if not c:
            return 0.0
        el = c["elapsed"]
        if c["running"]:
            el += time.time() - c["start_ts"]
        return el


# --------------------------- Threads ---------------------------------
def _minute_loop():
    while _running:
        try:
            now = datetime.now()
            # Fire alarms
            fired: List[Dict] = []
            with _lock:
                for a in _alarms:
                    if not a.get("active", True):
                        continue
                    at = datetime.fromisoformat(a.get("when"))
                    if now >= at:
                        fired.append(a)
            for a in fired:
                label = a.get("label") or "Alarm"
                _speak_and_notify(f"Alarm: {label}", tone=True)
                if _cb:
                    try:
                        _cb("alarm", label)
                    except Exception:
                        pass
                # Reschedule repeats or deactivate
                rep = a.get("repeat")
                next_when = None
                if rep == "daily":
                    next_when = datetime.fromisoformat(a["when"]) + timedelta(days=1)
                elif rep == "weekday":
                    t = datetime.fromisoformat(a["when"]) + timedelta(days=1)
                    while t.weekday() >= 5:
                        t = t + timedelta(days=1)
                    next_when = t
                with _lock:
                    if next_when is None:
                        a["active"] = False
                    else:
                        a["when"] = next_when.isoformat()
        except Exception:
            pass
        # Sleep to next minute boundary
        try:
            now = datetime.now()
            nxt = _minute_boundary_after(now)
            time.sleep(max(1e-3, (nxt - now).total_seconds()))
        except Exception:
            time.sleep(60)


def _timer_loop():
    while _running:
        try:
            now = time.time()
            to_fire: List[Dict] = []
            with _lock:
                for t in _timers.values():
                    st = float(t.get("start_at", now))
                    en = float(t.get("end_at", now))
                    if t.get("state") == "scheduled" and now >= st:
                        t["state"] = "running"
                    if t.get("state") == "running" and now >= en:
                        to_fire.append(t)
            for t in to_fire:
                label = t.get("label") or "Timer"
                _speak_and_notify(f"Timer done: {label}", tone=True)
                if _cb:
                    try:
                        _cb("timer", label)
                    except Exception:
                        pass
                with _lock:
                    _timers.pop(t.get("id"), None)
        except Exception:
            pass
        time.sleep(0.5)


def initialize() -> bool:
    global _running
    if _running:
        return True
    _running = True
    threading.Thread(target=_minute_loop, daemon=True).start()
    threading.Thread(target=_timer_loop, daemon=True).start()
    return True
