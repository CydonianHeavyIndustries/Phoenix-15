import json
import math
import os
import random
import threading
import time

import numpy as np
import sounddevice as sd

from core import memory, mood
from systems import audio as audio_tts
from systems import awareness

try:
    # Reuse STT config and helpers (device hint, WASAPI loopback)
    from systems.stt import SAMPLE_RATE, get_desktop_hint
except Exception:
    SAMPLE_RATE = 16000

    def get_desktop_hint():
        return ""


_thread = None
_running = False
_mode = "mic"  # 'mic' | 'desktop'
_comments_enabled = False
_last_comment_ts = 0.0
_last_memory_log_ts = 0.0
_last_context = {
    "label": "idle",
    "rms": 0.0,
    "centroid": 0.0,
    "flatness": 0.0,
    "zcr": 0.0,
    "time": 0.0,
}
_prev_label = "idle"
_last_calc_ts = 0.0
ANALYZE_INTERVAL = 0.12
MEMORY_LOG_INTERVAL = float(os.getenv("BJORGSUN_AUDIO_MEM_INTERVAL", "120") or 120)

DATA_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "sound_signatures.json"
)


def _load_db():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"sounds": []}


def _save_db(db):
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)
    except Exception:
        pass


def _classify(rms, centroid, flatness, zcr):
    if rms < 0.005:
        return "silence"
    # Noise is flat/chaotic: high flatness and high zcr
    if flatness > 0.5 and zcr > 0.12:
        return "noise/ambient"
    # Laughter heuristic
    if (
        0.006 <= rms <= 0.12
        and 0.4 <= flatness <= 0.85
        and 600 <= centroid <= 2800
        and zcr >= 0.12
    ):
        return "laughter"
    # Speech tends to have mid centroid, mid zcr, moderate flatness
    if 400 < centroid < 2500 and 0.04 < zcr < 0.15 and flatness < 0.55:
        return "speech"
    # Music/structured audio: lower flatness with higher centroid swings
    if flatness < 0.4 and (centroid > 1500 or zcr < 0.06):
        return "music"
    return "sound"


def _feature_frame(block):
    # block: (n, 1) float32
    if block.size == 0:
        return 0.0, 0.0, 0.0, 0.0
    x = block.astype(np.float32).flatten()
    rms = float(np.sqrt(np.mean(np.square(x))))
    # FFT features
    try:
        spec = np.fft.rfft(x * np.hanning(x.size))
        mag = np.abs(spec) + 1e-12
        freqs = np.fft.rfftfreq(x.size, d=1.0 / SAMPLE_RATE)
        centroid = float(np.sum(freqs * mag) / np.sum(mag)) if np.sum(mag) > 0 else 0.0
        # Spectral flatness (geometric mean / arithmetic mean)
        flatness = float(np.exp(np.mean(np.log(mag))) / (np.mean(mag) + 1e-12))
    except Exception:
        centroid, flatness = 0.0, 0.0
    # Zero crossing rate
    zc = np.mean(np.abs(np.diff(np.sign(x)))) / 2.0
    return rms, centroid, flatness, float(zc)


def _signature_from_context(ctx: dict):
    return [
        float(ctx.get("rms", 0.0)),
        float(ctx.get("centroid", 0.0)),
        float(ctx.get("flatness", 0.0)),
        float(ctx.get("zcr", 0.0)),
    ]


def remember(label: str):
    """Store the current audio signature under a label."""
    db = _load_db()
    sig = _signature_from_context(get_last_context())
    db.setdefault("sounds", []).append({"label": label.strip(), "signature": sig})
    _save_db(db)
    awareness.log_awareness(f"Learned sound signature: {label.strip()}")


def identify() -> tuple[str | None, float]:
    """Return closest known sound label and distance; (None, inf) if none."""
    db = _load_db()
    cur = np.array(_signature_from_context(get_last_context()), dtype=float)
    best_label, best_d = None, float("inf")
    for s in db.get("sounds", []):
        sig = np.array(s.get("signature", []), dtype=float)
        if sig.size != cur.size:
            continue
        d = float(np.linalg.norm(cur - sig))
        if d < best_d:
            best_d, best_label = d, s.get("label")
    return best_label, best_d


def _loop():
    global _running, _last_context, _prev_label, _last_calc_ts
    block_size = 2048
    channels = 1

    # Desktop loopback settings (Windows WASAPI)
    device = None
    extra = None
    channels = 1
    if _mode == "desktop":
        try:
            from systems.stt import _find_output_device_by_hint

            hint = get_desktop_hint()
            device = _find_output_device_by_hint(hint)
            # Prefer 2ch, but fall back to 1ch if needed when stream opens
            channels = 2
        except Exception:
            device = None

    def cb(indata, frames, time_info, status):
        try:
            now = time.time()
            if now - _last_calc_ts < ANALYZE_INTERVAL:
                return
            _last_calc_ts = now
            rms, centroid, flatness, zcr = _feature_frame(indata[:, :1])
            label = _classify(rms, centroid, flatness, zcr)
            _last_context = {
                "label": label,
                "rms": rms,
                "centroid": centroid,
                "flatness": flatness,
                "zcr": zcr,
                "time": time.time(),
            }
            # Hooks on label change
            if label != _prev_label:
                _prev_label = label
                # Mood adjustment mapping
                try:
                    if label == "music":
                        mood.adjust_mood("joy")
                    elif label == "speech":
                        mood.adjust_mood("pride")
                    elif label == "noise/ambient":
                        mood.adjust_mood("calm")
                except Exception:
                    pass
                # Persist felt moment
                try:
                    global _last_memory_log_ts
                    now_ts = time.time()
                    if (now_ts - _last_memory_log_ts) >= MEMORY_LOG_INTERVAL:
                        _last_memory_log_ts = now_ts
                        memory.save_memory_entry(
                            {
                                "type": "audio_moment",
                                "label": label,
                                "rms": rms,
                                "centroid": centroid,
                                "flatness": flatness,
                                "zcr": zcr,
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            }
                        )
                except Exception:
                    pass
                # Optional commentary (user-controlled), rate-limited
                try:
                    global _last_comment_ts
                    if _comments_enabled and (time.time() - _last_comment_ts) > 120:
                        awareness.log_awareness(f"Audio context shift: {label}")
                        line = {
                            "music": "Sounds lively — I like the rhythm.",
                            "laughter": "I hear laughter — that’s a good sign.",
                            "speech": "I hear voices — staying focused.",
                            "noise/ambient": "Ambient noise rolling by.",
                            "silence": "Quiet for now.",
                        }.get(label, f"Hearing {label}.")
                        _last_comment_ts = time.time()
                        try:
                            audio_tts.speak(line)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    try:
        # Try opening with chosen channels, fall back to mono if needed
        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=channels,
                dtype="float32",
                callback=cb,
                blocksize=block_size,
                device=device,
            ):
                while _running:
                    time.sleep(0.05)
        except Exception:
            try:
                with sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    callback=cb,
                    blocksize=block_size,
                    device=device,
                ):
                    while _running:
                        time.sleep(0.05)
            except Exception:
                _running = False
    except Exception:
        _running = False


def start(mode: str = "mic"):
    """Start ambient audio sensing. mode: 'mic' or 'desktop'"""
    global _thread, _running, _mode
    if _running:
        return
    _mode = "desktop" if str(mode).lower() == "desktop" else "mic"
    _running = True
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()


def stop():
    global _running
    _running = False


def is_running() -> bool:
    return bool(_running)


def get_mode() -> str:
    return _mode


def get_last_context():
    return dict(_last_context)


def set_comments_enabled(flag: bool):
    global _comments_enabled
    _comments_enabled = bool(flag)


def get_comments_enabled() -> bool:
    return bool(_comments_enabled)


def summarize_last() -> str:
    c = get_last_context()
    label = c.get("label", "idle")
    rms = c.get("rms", 0.0)
    centroid = c.get("centroid", 0.0)
    mood_hint = (
        "calm"
        if label in ("silence", "sound") and rms < 0.02
        else (
            "alert"
            if label == "speech"
            else "bright" if label == "music" and centroid > 1800 else "neutral"
        )
    )
    return f"Audio context: {label} | energy {rms:.2f} | tone {centroid:.0f} Hz • mood {mood_hint}"
