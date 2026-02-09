# -------------------------------------------------------------------------
# systems/tasks.py — Task & Reminder System for Bjorgsun-26
# -------------------------------------------------------------------------
import difflib
import json
import os
import threading
import time
from datetime import datetime, timedelta

from systems import audio, notify

try:
    from systems import hibernation
except Exception:
    hibernation = None

TASK_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "tasks.json")
os.makedirs(os.path.dirname(TASK_FILE), exist_ok=True)

_tasks = {}
_lock = threading.RLock()
_running = False
_started = False


# -------------------------------------------------------------------------
# CORE FUNCTIONS
# -------------------------------------------------------------------------
def load_tasks():
    global _tasks
    if os.path.exists(TASK_FILE):
        try:
            with open(TASK_FILE, "r", encoding="utf-8") as f:
                _tasks = json.load(f)
            if not isinstance(_tasks, dict):
                _tasks = {}
        except Exception:
            # Corrupt file? Reset to empty to keep system functional
            _tasks = {}
    else:
        _tasks = {}
    # Deduplicate exact (message+time) pairs
    try:
        seen = set()
        to_del = []
        for k, v in _tasks.items():
            sig = ((v.get("message") or "").strip(), (v.get("time") or "").strip())
            if sig in seen:
                to_del.append(k)
            else:
                seen.add(sig)
        if to_del:
            with _lock:
                for k in to_del:
                    _tasks.pop(k, None)
            save_tasks()
    except Exception:
        pass
    print(f"📘 Loaded {_tasks.__len__()} saved tasks.")


def save_tasks():
    with _lock:
        with open(TASK_FILE, "w", encoding="utf-8") as f:
            json.dump(_tasks, f, indent=2, ensure_ascii=False)


def add_task(name, delay_minutes: int, message=None):
    """Add a timed reminder."""
    when = datetime.now() + timedelta(minutes=delay_minutes)
    # Ensure unique key so multiple reminders for similar names don't overwrite
    base = name.strip() or "Reminder"
    key = base
    suffix = 2
    with _lock:
        # Deduplicate: if identical pending task exists, reuse it
        msg = (message or base).strip()
        for k, v in _tasks.items():
            try:
                if (
                    not v.get("done")
                    and (v.get("message") or "").strip() == msg
                    and (v.get("time") or "") == when.isoformat()
                ):
                    print(
                        f"🛈 Duplicate reminder ignored: '{msg}' at {when.strftime('%H:%M:%S')}"
                    )
                    return when
            except Exception:
                continue
        while key in _tasks:
            key = f"{base} ({suffix})"
            suffix += 1
        _tasks[key] = {"time": when.isoformat(), "message": msg, "done": False}
        save_tasks()
    print(f"🕒 Task added: '{key}' at {when.strftime('%H:%M:%S')}")
    return when


def add_alarm_time(label: str, hour: int, minute: int) -> str:
    from datetime import datetime, timedelta

    now = datetime.now()
    hh = int(hour) % 24
    mm = int(minute) % 60
    dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if dt <= now:
        dt = dt + timedelta(days=1)
    base = (label or "Alarm").strip() or "Alarm"
    key = base
    suffix = 2
    while key in _tasks:
        key = f"{base} ({suffix})"
        suffix += 1
    with _lock:
        _tasks[key] = {
            "time": dt.isoformat(),
            "message": base,
            "done": False,
            "alarm": True,
        }
        save_tasks()
    return key


def add_alarm_in(label: str, minutes: int) -> str:
    from datetime import datetime, timedelta

    dt = datetime.now() + timedelta(minutes=int(minutes))
    base = (label or "Alarm").strip() or "Alarm"
    key = base
    suffix = 2
    while key in _tasks:
        key = f"{base} ({suffix})"
        suffix += 1
    with _lock:
        _tasks[key] = {
            "time": dt.isoformat(),
            "message": base,
            "done": False,
            "alarm": True,
        }
        save_tasks()
    return key


def remove_task(name) -> bool:
    """Remove a task by its exact key. Returns True if removed."""
    removed = False
    with _lock:
        if name in _tasks:
            del _tasks[name]
            removed = True
            try:
                with open(TASK_FILE, "w", encoding="utf-8") as f:
                    json.dump(_tasks, f, indent=2, ensure_ascii=False)
            except Exception:
                # Fall back to normal saver
                save_tasks()
    if removed:
        print(f"🗑️ Task removed: {name}")
    return removed


def remove_task_fuzzy(query: str) -> tuple[bool, str | None]:
    key = _best_match_key(query)
    if not key:
        return False, None
    ok = remove_task(key)
    return ok, key if ok else (False, None)


def list_tasks():
    """Return a human-readable summary."""
    if not _tasks:
        return "No active tasks."
    lines = []
    now = datetime.now()
    for k, v in _tasks.items():
        t = datetime.fromisoformat(v["time"])
        rem = (t - now).total_seconds() / 60
        lines.append(
            f"{k} → in {rem:.1f} min  |  {'✅ done' if v['done'] else '⏳ pending'}"
        )
    return "\n".join(lines)


def get_all_tasks():
    """Return a list of tasks with fields: name,time,done,message."""
    out = []
    for k, v in _tasks.items():
        out.append(
            {
                "name": k,
                "time": v.get("time"),
                "done": bool(v.get("done")),
                "message": v.get("message", k),
            }
        )
    # Sort by time
    try:
        out.sort(key=lambda x: x["time"] or "")
    except Exception:
        pass
    return out


def mark_done(name):
    with _lock:
        if name in _tasks:
            _tasks[name]["done"] = True
            with open(TASK_FILE, "w", encoding="utf-8") as f:
                json.dump(_tasks, f, indent=2, ensure_ascii=False)
            return True
    return False


def _best_match_key(query: str) -> str | None:
    """Return the best matching task key for a user query.
    Matches against both task keys and their message fields.
    """
    if not query:
        return None
    q = query.strip().lower()
    if not _tasks:
        return None
    # Exact or substring matches first
    exact = [
        k
        for k, v in _tasks.items()
        if k.lower() == q or (v.get("message") or "").strip().lower() == q
    ]
    if exact:
        return exact[0]
    sub = [
        k
        for k, v in _tasks.items()
        if q in k.lower() or q in (v.get("message") or "").lower()
    ]
    if sub:
        try:
            sub.sort(key=lambda kk: _tasks[kk].get("time") or "")
        except Exception:
            pass
        return sub[0]
    # Fuzzy against names + messages
    pool = []
    for k, v in _tasks.items():
        pool.append(k)
        m = (v.get("message") or "").strip()
        if m and m.lower() != k.lower():
            pool.append(m)
    best = difflib.get_close_matches(q, pool, n=1, cutoff=0.6)
    if best:
        b = best[0]
        for k, v in _tasks.items():
            if b == k or b == (v.get("message") or "").strip():
                return k
    return None


def mark_done_fuzzy(query: str) -> tuple[bool, str | None]:
    """Mark a task done using fuzzy lookup. Returns (ok, key)."""
    key = _best_match_key(query)
    if not key:
        return False, None
    _tasks[key]["done"] = True
    save_tasks()
    return True, key


# ---- New helpers: reschedule, snooze, repeat ----
def _parse_dt_local(h: int, m: int) -> str:
    from datetime import datetime, timedelta

    now = datetime.now()
    dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if dt < now:
        dt = dt + timedelta(days=1)
    return dt.isoformat()


def reschedule_task(name: str, new_iso_time: str) -> bool:
    with _lock:
        if name in _tasks:
            _tasks[name]["time"] = new_iso_time
            _tasks[name]["done"] = False
            save_tasks()
            return True
    return False


def reschedule_fuzzy(query: str, h: int, m: int) -> tuple[bool, str | None]:
    key = _best_match_key(query)
    if not key:
        return False, None
    ok = reschedule_task(key, _parse_dt_local(h, m))
    return ok, key if ok else (False, None)


def snooze_fuzzy(query: str | None, minutes: int) -> tuple[bool, str | None]:
    from datetime import datetime, timedelta

    key = _best_match_key(query or "") if query else None
    if not key and _tasks:
        key = sorted(_tasks.items(), key=lambda kv: kv[1].get("time") or "")[0][0]
    if not key:
        return False, None
    with _lock:
        cur = _tasks.get(key)
        if not cur:
            return False, None
        base = datetime.fromisoformat(cur.get("time") or datetime.now().isoformat())
        newt = (base + timedelta(minutes=int(minutes))).isoformat()
        _tasks[key]["time"] = newt
        _tasks[key]["done"] = False
        save_tasks()
        return True, key


def set_repeat_fuzzy(query: str, mode: str) -> tuple[bool, str | None]:
    mode = (mode or "").lower()
    if mode not in {"none", "daily", "weekday"}:
        return False, None
    key = _best_match_key(query)
    if not key:
        return False, None
    with _lock:
        _tasks[key]["repeat"] = None if mode == "none" else mode
        save_tasks()
        return True, key


# -------------------------------------------------------------------------
# BACKGROUND THREAD
# -------------------------------------------------------------------------
def _task_watcher():
    global _running
    _running = True
    print("🧩 Task reminder thread started.")
    while _running:
        now = datetime.now()
        due = []
        with _lock:
            for name, task in list(_tasks.items()):
                try:
                    if task.get("done"):
                        continue
                    t = datetime.fromisoformat(task.get("time"))
                    if now >= t:
                        due.append(task)
                except Exception:
                    continue
        # Fire outside the lock
        changed = False
        for task in due:
            msg = task.get("message")
            print(f"🔔 Reminder: {msg}")
            try:
                audio.play_alarm_tone()
            except Exception:
                pass
            try:
                if hibernation:
                    hibernation.wake_for_reminder(msg)
                else:
                    audio.alert_speak(f"Reminder: {msg}")
            except Exception:
                audio.alert_speak(f"Reminder: {msg}")
            try:
                notify.notify("Reminder", msg, duration=6)
            except Exception:
                pass
            # Update scheduling under lock (no nested save)
            with _lock:
                try:
                    t = datetime.fromisoformat(task.get("time"))
                except Exception:
                    continue
                rep = task.get("repeat") or None
                if rep:
                    from datetime import timedelta

                    if rep == "daily":
                        t = t + timedelta(days=1)
                    elif rep == "weekday":
                        t = t + timedelta(days=1)
                        while t.weekday() >= 5:
                            t = t + timedelta(days=1)
                    task["time"] = t.isoformat()
                    task["done"] = False
                else:
                    task["done"] = True
                changed = True
        if changed:
            save_tasks()
        # Poll more frequently to ensure timely reminders and UI updates
        time.sleep(5)
    print("🧩 Task watcher stopped.")


def initialize():
    global _started
    load_tasks()
    if not _started:
        threading.Thread(target=_task_watcher, daemon=True).start()
        _started = True
    print("✅ Task system online.")
    return True


def set_enabled(flag: bool):
    """Enable/disable reminders runtime."""
    global _running, _started
    if flag and not _running:
        # Restart watcher
        threading.Thread(target=_task_watcher, daemon=True).start()
        _started = True
    else:
        _running = False


def get_enabled() -> bool:
    return bool(_running)
