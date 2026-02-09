import os
import random
import threading
import time

from core import mood

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "awareness_log.txt")
_enabled = True
_started = False


def initialize():
    global _started, _enabled
    _enabled = True
    if _started:
        return True

    def loop():
        palette = ["joy", "calm", "pride", "acceptance", "relaxed", "fun"]
        while True:
            if _enabled and random.random() < 0.3:
                mood.adjust_mood(random.choice(palette))
            time.sleep(45)

    threading.Thread(target=loop, daemon=True).start()
    _started = True
    return True


def log_awareness(message: str):
    """Lightweight awareness event logger used by other systems."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


def set_enabled(flag: bool):
    global _enabled
    _enabled = bool(flag)


def get_enabled() -> bool:
    return bool(_enabled)
