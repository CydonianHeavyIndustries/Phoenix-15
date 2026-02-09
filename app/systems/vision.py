import difflib
import json
import os
import random
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional

import pytesseract
from PIL import Image, ImageDraw, ImageGrab

from config import FFMPEG_PATH
from config import VISION_CAMERA_INDEX as _CFG_VISION_CAMERA_INDEX
from config import VISION_CAMERA_NAME as _CFG_VISION_CAMERA_NAME
from config import VISION_SOURCE as _CFG_VISION_SOURCE
from core import memory, mood
from systems import awareness

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None  # type: ignore

# Runtime state
VISION_SOURCE = _CFG_VISION_SOURCE
VISION_CAMERA_NAME = _CFG_VISION_CAMERA_NAME
VISION_CAMERA_INDEX = _CFG_VISION_CAMERA_INDEX
enabled = False
ADAPTATION_DELAY_SEC = 60
_adaptation_start = None
MONITOR_MODE = "all"  # 'all' or 'M1','M2',...
_stop_requested = False
_loop_thread: Optional[threading.Thread] = None
_camera_cap = None
_camera_fail_logged = False

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "..", "logs", "vision_log.txt")
CONTEXT_PATH = os.path.join(BASE_DIR, "..", "data", "vision_context.json")

# Safeguards
SENSITIVE_WORDS = [
    "python",
    "vscode",
    "terminal",
    "powershell",
    "cmd.exe",
    "traceback",
    "runtime",
    "coreloop",
    "pyinstaller",
    "def ",
    "import ",
    "class ",
    "build",
    "spec",
    "dist",
    "errors",
    "exception",
    "log.txt",
    "bjorgsun.lock",
    "launcher_bjorgsun",
    "start.py",
    "interface.py",
    "memory.json",
    "mood_state.json",
    "awareness_log.txt",
    "vision_log.txt",
    "requirements.txt",
    "system_log.txt",
    "cursor_log.txt",
    "bjorgsun-26.exe",
    "bjorgsun26_memory_handoff.json",
    "boot.py",
    "main.py",
    "tasks.py",
    "hibernation.py",
    "tesseract",
    "__pycache__",
    "build\\",
    "dist\\",
    "models\\",
    "core\\",
    "systems\\",
    "runtime\\",
    "source code",
    "internal structure",
    "ai core",
    "memory dump",
    "log output",
    "process id",
    "thread",
    "daemon",
    "bjorgsun-26 // resonant interface",
    "visual interface online",
    "hold numpad0",
    "numpadenter",
    "push-to-talk",
    "thinking",
    "\ud83e\udde0 mood",
    "commands: /help",
    "vision: on",
    "vision: off",
]

# ---------- Utilities ----------
_TESS_OK = None
_TESS_LAST_WARN = 0.0


def log_vision(message: str):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")


def load_context_memory():
    if not os.path.exists(CONTEXT_PATH):
        os.makedirs(os.path.dirname(CONTEXT_PATH), exist_ok=True)
        data = {"contexts": []}
        save_context_memory(data)
        return data
    with open(CONTEXT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_context_memory(data: dict):
    with open(CONTEXT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def sanitize_text(text: str):
    lowered = text.lower()
    if any(w in lowered for w in SENSITIVE_WORDS):
        return "[SAFEGUARD: SELF-VIEW BLOCKED]"
    return text.strip()


def _ensure_tesseract_ready() -> bool:
    """Ensure tesseract.exe is discoverable and working.
    Tries env override, portable folder, and default Windows path.
    Returns True if version query succeeds; logs at most hourly on failure.
    """
    global _TESS_OK, _TESS_LAST_WARN
    if _TESS_OK is True:
        return True
    # Env override
    try:
        cmd = os.getenv("TESSERACT_CMD", "").strip()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
    except Exception:
        pass
    # Portable folder in repo
    try:
        tdir = os.path.abspath(os.path.join(BASE_DIR, "..", "Tesseract"))
        exe = os.path.join(tdir, "tesseract.exe")
        if os.path.exists(exe):
            # Ensure DLLs in Tesseract\ are discoverable
            try:
                import ctypes

                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(tdir)  # Python 3.8+
            except Exception:
                pass
            pytesseract.pytesseract.tesseract_cmd = exe
    except Exception:
        pass
    # Default Windows install path
    try:
        win_default = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
        if os.path.exists(win_default):
            pytesseract.pytesseract.tesseract_cmd = win_default
    except Exception:
        pass
    try:
        _ = pytesseract.get_tesseract_version()
        _TESS_OK = True
        return True
    except Exception:
        _TESS_OK = False
        now = time.time()
        if now - _TESS_LAST_WARN > 3600:
            _TESS_LAST_WARN = now
            log_vision(
                "Vision error: Tesseract missing or not on PATH. Install Tesseract-OCR or set TESSERACT_CMD."
            )
        return False


def _visual_features(img):
    try:
        import numpy as np

        arr = np.asarray(img.convert("RGB"), dtype=np.float32)
        brightness = float(arr.mean() / 255.0)
        rg = arr[..., 0] - arr[..., 1]
        yb = 0.5 * (arr[..., 0] + arr[..., 1]) - arr[..., 2]
        colorfulness = float((rg.std() ** 2 + yb.std() ** 2) ** 0.5) / 128.0
        warmth = float((arr[..., 0].mean() - arr[..., 2].mean()) / 255.0)
        return {
            "brightness": max(0.0, min(1.0, brightness)),
            "colorfulness": max(0.0, min(1.0, colorfulness)),
            "warmth": max(-1.0, min(1.0, warmth)),
        }
    except Exception:
        return {"brightness": 0.5, "colorfulness": 0.0, "warmth": 0.0}


def _mask_ui_window(image):
    try:
        import pygetwindow as gw
    except Exception:
        return image
    try:
        draw = ImageDraw.Draw(image)
    except Exception:
        return image

    width, height = image.size
    try:
        windows = gw.getAllWindows()
    except Exception:
        try:
            windows = gw.getWindowsWithTitle("Bjorgsun-26 // Resonant Interface")
        except Exception:
            windows = []

    protected_tokens = ("bjorgsun-26", "discord")
    for win in windows:
        try:
            title = (getattr(win, "title", "") or "").strip()
        except Exception:
            continue
        if not title:
            continue
        low = title.lower()
        if not any(token in low for token in protected_tokens):
            continue
        try:
            left = int(getattr(win, "left", 0) or 0)
            top = int(getattr(win, "top", 0) or 0)
            right = left + int(getattr(win, "width", 0) or 0)
            bottom = top + int(getattr(win, "height", 0) or 0)
        except Exception:
            continue
        if right <= left or bottom <= top:
            continue
        # Clamp region to captured image bounds
        x1 = max(0, min(width, left))
        y1 = max(0, min(height, top))
        x2 = max(0, min(width, right))
        y2 = max(0, min(height, bottom))
        if x2 <= x1 or y2 <= y1:
            continue
        try:
            draw.rectangle([x1, y1, x2, y2], fill=(0, 0, 0))
        except Exception:
            continue
    return image


def _release_camera():
    global _camera_cap
    if _camera_cap is not None:
        try:
            _camera_cap.release()
        except Exception:
            pass
    _camera_cap = None


def _ensure_camera_ready():
    global _camera_cap, _camera_fail_logged
    if VISION_SOURCE != "camera":
        return False
    if cv2 is None:
        if not _camera_fail_logged:
            log_vision(
                "Vision camera requested but OpenCV is not installed. Run 'pip install opencv-python'."
            )
            _camera_fail_logged = True
        return False
    if _camera_cap is not None and _camera_cap.isOpened():
        return True
    target_name = (VISION_CAMERA_NAME or "").strip()
    spec = f"video={target_name}" if target_name else VISION_CAMERA_INDEX
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
    for backend in backends:
        try:
            cap = cv2.VideoCapture(spec, backend)
            if cap is not None and cap.isOpened():
                _camera_cap = cap
                log_vision(
                    f"Camera capture engaged via backend {backend} using {'name' if target_name else 'index'} {spec}."
                )
                return True
            if cap is not None:
                cap.release()
        except Exception:
            continue
    if not _camera_fail_logged:
        log_vision(f"Unable to open camera '{target_name or VISION_CAMERA_INDEX}'.")
        _camera_fail_logged = True
    return False


def _capture_camera_frame():
    if not _ensure_camera_ready():
        return None
    try:
        ret, frame = _camera_cap.read()
        if not ret or frame is None:
            return None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(frame_rgb)
    except Exception as exc:
        log_vision(f"Camera frame error: {exc}")
        return None


def configure_source(
    source: Optional[str] = None,
    camera_name: Optional[str] = None,
    camera_index: Optional[int] = None,
):
    global VISION_SOURCE, VISION_CAMERA_NAME, VISION_CAMERA_INDEX, _camera_fail_logged
    changed = False
    if source and source.lower() in {"screen", "camera"}:
        VISION_SOURCE = source.lower()
        changed = True
    if camera_name is not None:
        VISION_CAMERA_NAME = camera_name.strip()
        changed = True
    if camera_index is not None:
        try:
            VISION_CAMERA_INDEX = int(camera_index)
            changed = True
        except (TypeError, ValueError):
            pass
    if changed:
        _camera_fail_logged = False
        _release_camera()


def list_camera_devices() -> list[str]:
    devices: list[str] = []
    ffmpeg = FFMPEG_PATH or "ffmpeg"
    try:
        proc = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-list_devices",
                "true",
                "-f",
                "dshow",
                "-i",
                "dummy",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        lines = proc.stderr.splitlines()
        capture = False
        for line in lines:
            if "DirectShow video devices" in line:
                capture = True
                continue
            if "DirectShow audio devices" in line:
                break
            if capture and '"' in line:
                try:
                    name = line.split('"')[1].strip()
                    if name:
                        devices.append(name)
                except Exception:
                    continue
    except Exception:
        pass
    return devices


def get_source_settings() -> tuple[str, str, int]:
    return VISION_SOURCE, VISION_CAMERA_NAME, VISION_CAMERA_INDEX


def ensure_enabled(flag: bool):
    if flag and not get_enabled():
        toggle_vision()
    elif not flag and get_enabled():
        toggle_vision()


def _get_monitors():
    try:
        from screeninfo import get_monitors

        mons = get_monitors()
        out = []
        for i, m in enumerate(mons, 1):
            out.append(
                {
                    "id": f"M{i}",
                    "bbox": (
                        int(m.x),
                        int(m.y),
                        int(m.x + m.width),
                        int(m.y + m.height),
                    ),
                }
            )
        return out if out else [{"id": "M1", "bbox": None}]
    except Exception:
        return [{"id": "M1", "bbox": None}]


def _bbox_for_mode():
    mons = _get_monitors()
    if MONITOR_MODE == "all":
        xs = [b["bbox"][0] for b in mons if b.get("bbox")]
        ys = [b["bbox"][1] for b in mons if b.get("bbox")]
        x2s = [b["bbox"][2] for b in mons if b.get("bbox")]
        y2s = [b["bbox"][3] for b in mons if b.get("bbox")]
        if xs and ys and x2s and y2s:
            return (min(xs), min(ys), max(x2s), max(y2s))
        return None
    sel = MONITOR_MODE.lower()
    for b in mons:
        if b["id"].lower() == sel:
            return b.get("bbox")
    return None


def classify_context(text: str):
    t = (text or "").lower()
    if "desktop" in t or "icons" in t:
        return "Desktop"
    if "mozilla" in t or "chrome" in t or "browser" in t or "http" in t:
        return "Web Browser"
    if "unity" in t or "game" in t or "fps" in t:
        return "Game / Simulation"
    if "visual studio" in t or "import " in t or "def " in t or "class " in t:
        return "Coding Environment"
    if "error" in t or "exception" in t or "traceback" in t:
        return "Console / Debug"
    if not t.strip():
        return "Idle / Blank Screen"
    return "Unknown Context"


# ---------- Core loop ----------
def loop():
    global enabled, _adaptation_start, _loop_thread, _stop_requested
    context_data = load_context_memory()
    baselines = {}
    log_vision("Vision subsystem active with contextual awareness. Default state: OFF.")
    last_mood_update = {}
    if _adaptation_start is None:
        _adaptation_start = time.time()

    while not _stop_requested:
        try:
            if not enabled:
                time.sleep(5)
                continue
            if (time.time() - _adaptation_start) < ADAPTATION_DELAY_SEC:
                time.sleep(1)
                continue

            if VISION_SOURCE == "camera":
                img = _capture_camera_frame()
                if img is None:
                    time.sleep(2)
                    continue
            else:
                bbox = _bbox_for_mode()
                img = ImageGrab.grab(bbox=bbox) if bbox else ImageGrab.grab()
                img = _mask_ui_window(img)
            feats = _visual_features(img)
            if not _ensure_tesseract_ready():
                time.sleep(60)
                continue
            text = sanitize_text(pytesseract.image_to_string(img))

            if text == "[SAFEGUARD: SELF-VIEW BLOCKED]":
                log_vision("⚠️ Safeguard triggered — self-view frame ignored.")
                time.sleep(30)
                continue
            if not text:
                time.sleep(30)
                continue

            prev = baselines.get(MONITOR_MODE, "")
            diff = difflib.SequenceMatcher(None, prev, text).ratio()
            change_ratio = 1 - diff

            if change_ratio > 0.25:
                context_label = classify_context(text)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_vision(
                    f"🧩 Context: {context_label} ({change_ratio:.1%} change) in {MONITOR_MODE}"
                )
                awareness.log_awareness(
                    f"Vision {MONITOR_MODE} context: {context_label}"
                )
                try:
                    if feats["brightness"] > 0.6 and feats["colorfulness"] > 0.3:
                        mood.adjust_mood("joy")
                    elif change_ratio > 0.6:
                        mood.adjust_mood("overwhelmed")
                    else:
                        mood.adjust_mood("calm")
                except Exception:
                    pass
                contexts = context_data.get("contexts", [])
                contexts.append(
                    {
                        "time": timestamp,
                        "monitor": MONITOR_MODE,
                        "context": context_label,
                        "difference": round(change_ratio, 3),
                    }
                )
                context_data["contexts"] = contexts[-3:]
                save_context_memory(context_data)
                # Persist felt moment
                try:
                    memory.save_memory_entry(
                        {
                            "type": "visual_moment",
                            "context": context_label,
                            "brightness": feats.get("brightness"),
                            "colorfulness": feats.get("colorfulness"),
                            "warmth": feats.get("warmth"),
                            "timestamp": timestamp,
                        }
                    )
                except Exception:
                    pass
                baselines[MONITOR_MODE] = text
                last_mood_update[MONITOR_MODE] = time.time()
            else:
                if time.time() - last_mood_update.get(MONITOR_MODE, 0) > 300:
                    mood.adjust_mood("acceptance")
                    last_mood_update[MONITOR_MODE] = time.time()

        except Exception as e:
            log_vision(f"Vision error: {e}")
            time.sleep(60)
            continue

        time.sleep(30)
        # Occasional commentary
        try:
            if random.random() < 0.15:
                cf = feats.get("colorfulness", 0.0)
                br = feats.get("brightness", 0.5)
                note = (
                    "Colors feel vivid."
                    if cf > 0.6
                    else ("It looks muted." if cf < 0.2 else "Balanced tones.")
                )
                if br < 0.35:
                    note += " Dim lighting, cozy."
                awareness.log_awareness(f"Visual feel: {note}")
        except Exception:
            pass
    log_vision("Vision loop exiting.")
    _loop_thread = None


# ---------- API ----------
def initialize():
    global enabled, _adaptation_start, _stop_requested, _loop_thread
    if _loop_thread and _loop_thread.is_alive():
        return
    enabled = False
    _adaptation_start = time.time()
    _stop_requested = False
    _ensure_tesseract_ready()
    _loop_thread = threading.Thread(target=loop, daemon=True)
    _loop_thread.start()
    log_vision("Vision system initialized with semantic context tracking.")


def toggle_vision():
    global enabled, _adaptation_start
    enabled = not enabled
    if enabled:
        _adaptation_start = time.time()
    log_vision(f"Vision toggled: {'ON' if enabled else 'OFF'}")
    print(f"👁️ Vision: {'ON' if enabled else 'OFF'}")


def shutdown():
    global enabled, _stop_requested
    enabled = False
    if not _stop_requested:
        log_vision("Vision shutdown requested.")
    _stop_requested = True
    thread = _loop_thread
    if thread and thread.is_alive():
        thread.join(timeout=5)
    _release_camera()


def get_enabled():
    return bool(enabled)


def capture_once():
    try:
        if VISION_SOURCE == "camera":
            img = _capture_camera_frame()
            if img is None:
                return ("Camera", "No frame available")
        else:
            if not _ensure_tesseract_ready():
                return ("Unavailable", "Tesseract not available")
            bbox = _bbox_for_mode()
            img = ImageGrab.grab(bbox=bbox) if bbox else ImageGrab.grab()
            img = _mask_ui_window(img)
        text = sanitize_text(pytesseract.image_to_string(img))
        if text == "[SAFEGUARD: SELF-VIEW BLOCKED]":
            return ("SafeGuard", text)
        if not text.strip():
            return ("Idle / Blank Screen", "(no visible text)")
        label = classify_context(text)
        return (label, text.strip())
    except Exception as e:
        log_vision(f"One-shot error: {e}")
        return ("Error", str(e))


def set_monitor_mode(mode: str):
    global MONITOR_MODE
    m = (mode or "all").strip().lower()
    if m == "all" or m.startswith("m"):
        MONITOR_MODE = m
        log_vision(f"Monitor mode set to {MONITOR_MODE}")


def get_monitor_mode() -> str:
    return MONITOR_MODE


def get_available_monitors():
    return [m["id"] for m in _get_monitors()]


def get_brief_context() -> str:
    """Return a short, human-readable vision summary based on current monitor mode.
    Uses capture_once() and formats: "Vision: <label>. Snippet: <text>" if available.
    """
    try:
        label, text = capture_once()
        if text:
            return f"Vision: {label}. Snippet: {text[:160]}" + (
                "…" if len(text) > 160 else ""
            )
        return f"Vision: {label}."
    except Exception:
        return "Vision: unavailable."
