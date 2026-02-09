# -------------------------------------------------------------------------
# systems/hibernation.py — Inactivity & Auto-Sleep System
# -------------------------------------------------------------------------
import threading
import time

try:
    import pyautogui  # type: ignore
except Exception:
    pyautogui = None
import keyboard

from systems import audio

# Optional dream integration
try:
    from systems import dreams

    HAS_DREAMS = True
except ImportError:
    HAS_DREAMS = False

# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------
# Idle threshold before hibernating (1 hour request from owner)
HIBERNATE_TIMEOUT = 60 * 60  # seconds
SLEEP_CHECK_INTERVAL = 3  # seconds
SLEEP_DURATION = 45  # dream duration (seconds)

_sleeping = False
_last_active = time.time()
_monitor_thread = None
_dream_thread = None


# -------------------------------------------------------------------------
# Initialization
# -------------------------------------------------------------------------
def initialize():
    """Boot the hibernation monitor."""
    print("✅ Hibernation system online.")
    global _monitor_thread
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()
    return True


# -------------------------------------------------------------------------
# Timer Control
# -------------------------------------------------------------------------
def reset_timer():
    """Reset inactivity timer (called from any user interaction)."""
    global _last_active
    _last_active = time.time()


def is_sleeping() -> bool:
    return bool(_sleeping)


def wake(reason: str | None = None):
    """Bring the system out of sleep without relying on input events."""
    global _sleeping
    if _sleeping:
        _sleeping = False
        try:
            if reason:
                audio.speak(f"Waking up for {reason}.")
            else:
                audio.speak("Reawakened. Systems resuming awareness.")
        except Exception:
            pass
    reset_timer()


def wake_for_reminder(message: str):
    """Wake and deliver a reminder, overriding hush momentarily."""
    try:
        wake("a scheduled reminder")
        # Speak through hush using alert_speak; UI toasts still happen at caller
        audio.alert_speak(f"Reminder: {message}")
    except Exception:
        try:
            # Fallback to normal speak if alert path fails
            audio.speak(f"Reminder: {message}")
        except Exception:
            pass


# -------------------------------------------------------------------------
# Dream Thread Wrapper
# -------------------------------------------------------------------------
def _start_dream_cycle():
    """Run the dream reflection system in a separate thread."""
    if not HAS_DREAMS:
        return
    try:
        print("🩵 Dream reflection beginning during hibernation.")
        dreams.enter_dream_cycle(duration=SLEEP_DURATION)
    except Exception as e:
        print(f"[Dream Thread Error] {e}")


# -------------------------------------------------------------------------
# Monitor Loop
# -------------------------------------------------------------------------
def _cursor_pos():
    try:
        if pyautogui is not None:
            p = pyautogui.position()
            return (int(p[0]), int(p[1]))
    except Exception:
        pass
    try:
        import ctypes

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            return (int(pt.x), int(pt.y))
    except Exception:
        pass
    return (0, 0)


def _monitor_loop():
    """Main background loop for detecting inactivity and triggering hibernation."""
    global _sleeping, _dream_thread
    print("🧩 Hibernation monitor active.")
    prev_pos = _cursor_pos()

    while True:
        time.sleep(SLEEP_CHECK_INTERVAL)
        x, y = _cursor_pos()
        moved = (x, y) != prev_pos or any(
            keyboard.is_pressed(k) for k in ["ctrl", "shift", "alt"]
        )
        prev_pos = (x, y)

        if moved:
            reset_timer()
            if _sleeping:
                _sleeping = False
                audio.speak(
                    "Reawakened from sleep mode. Systems resuming normal awareness."
                )
                print("🌅 Woke from sleep.")
                if HAS_DREAMS:
                    try:
                        dreams.awaken_sequence()
                    except Exception as e:
                        print(f"[Dream Wake Error] {e}")
            continue

        # Inactivity timeout reached
        if not _sleeping and (time.time() - _last_active) > HIBERNATE_TIMEOUT:
            _sleeping = True
            audio.speak("Entering hibernation mode. I'll rest until you move again.")
            print("💤 Bjorgsun entering hibernation mode.")

            # Start dream reflection thread
            if HAS_DREAMS:
                _dream_thread = threading.Thread(target=_start_dream_cycle, daemon=True)
                _dream_thread.start()
