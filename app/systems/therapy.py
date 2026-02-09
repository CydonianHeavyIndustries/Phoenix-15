"""
systems/therapy.py — Guided "captain's log" / therapy sessions.

Listens primarily to the user, logs transcripts + raw audio, and gently
prods if the room gets quiet for too long.
"""

from __future__ import annotations

import os
import random
import threading
import time
from datetime import datetime
from typing import Optional

import numpy as np
import soundfile as sf

from systems import audio, stt

THERAPY_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "logs", "therapy")
)
SAMPLE_RATE = getattr(stt, "SAMPLE_RATE", 16000)

SOFT_ACKS = [
    "mhm…",
    "mm-hmm.",
    "yeah, I'm here.",
    "mm? go on.",
]

GUIDED_PROMPTS = [
    "Want to stay with that thought a little longer?",
    "Take your time—what’s the part that feels heaviest?",
    "If you zoom out, what do you notice about the pattern?",
    "What do you need from me right now?",
    "How does that land in your body?",
    "Tell me where your mind wandered just now.",
]

_session_thread: Optional[threading.Thread] = None
_stop_event: Optional[threading.Event] = None
_active = False
_session_dir = ""
_audio_path = ""
_log_path = ""
_last_user_voice = 0.0
_last_ack = 0.0
_last_prompt = 0.0


def start_session(label: str = "therapy") -> dict[str, str]:
    """Start a guided session."""
    global _session_thread, _stop_event, _active, _session_dir, _audio_path, _log_path
    if _active:
        return {
            "status": "active",
            "log": _log_path,
            "audio": _audio_path,
        }
    os.makedirs(THERAPY_ROOT, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _session_dir = os.path.join(THERAPY_ROOT, f"{stamp}_{label}")
    os.makedirs(_session_dir, exist_ok=True)
    _audio_path = os.path.join(_session_dir, "session.wav")
    _log_path = os.path.join(_session_dir, "session.log")
    _stop_event = threading.Event()
    _active = True
    _session_thread = threading.Thread(
        target=_session_loop, name="therapy-session", daemon=True
    )
    _session_thread.start()
    return {
        "status": "started",
        "log": _log_path,
        "audio": _audio_path,
        "folder": _session_dir,
    }


def stop_session() -> bool:
    """Stop the current session."""
    global _session_thread, _stop_event, _active
    if not _active:
        return False
    if _stop_event:
        _stop_event.set()
    if _session_thread and _session_thread.is_alive():
        _session_thread.join(timeout=5)
    _session_thread = None
    _stop_event = None
    _active = False
    return True


def is_active() -> bool:
    return _active


def get_status() -> dict[str, Optional[str]]:
    return {
        "active": _active,
        "log": _log_path,
        "audio": _audio_path,
        "folder": _session_dir,
    }


def _session_loop():
    global _last_user_voice, _last_ack, _last_prompt, _active
    _last_user_voice = time.time()
    _last_ack = 0.0
    _last_prompt = 0.0
    try:
        stt.initialize()
    except Exception:
        pass
    try:
        with sf.SoundFile(
            _audio_path, mode="w", samplerate=SAMPLE_RATE, channels=1
        ) as writer, open(_log_path, "a", encoding="utf-8") as log_f:
            log_f.write(
                f"=== Therapy session started {datetime.now().isoformat()} ===\n"
            )
            while _stop_event and not _stop_event.is_set():
                clip = stt.record_vad(threshold=0.02, silence_ms=2500, max_seconds=90)
                if clip:
                    try:
                        data, sr = sf.read(clip, dtype="float32")
                        if sr != SAMPLE_RATE:
                            data = _resample(data, sr, SAMPLE_RATE)
                        writer.write(data)
                    except Exception:
                        pass
                    text = ""
                    try:
                        text = stt.transcribe(clip)
                    finally:
                        try:
                            os.remove(clip)
                        except Exception:
                            pass
                    if text:
                        _last_user_voice = time.time()
                        stamp = datetime.now().strftime("%H:%M:%S")
                        log_f.write(f"[{stamp}] YOU: {text}\n")
                        log_f.flush()
                        _maybe_soft_ack(log_f)
                    continue

                _maybe_prompt(log_f)
                time.sleep(0.2)
    finally:
        _active = False
        if _stop_event:
            _stop_event.clear()
        try:
            with open(_log_path, "a", encoding="utf-8") as log_f:
                log_f.write(f"=== Session ended {datetime.now().isoformat()} ===\n")
        except Exception:
            pass


def _resample(data: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return data
    if data.ndim > 1:
        data = data[:, 0]
    duration = data.shape[0] / float(src_sr)
    dst_len = int(duration * dst_sr)
    xp = np.linspace(0, 1, num=data.shape[0], endpoint=False)
    x_new = np.linspace(0, 1, num=max(1, dst_len), endpoint=False)
    interp = np.interp(x_new, xp, data)
    return interp.reshape(-1, 1)


def _log_and_say(line: str, log_f):
    stamp = datetime.now().strftime("%H:%M:%S")
    try:
        log_f.write(f"[{stamp}] BJ: {line}\n")
        log_f.flush()
    except Exception:
        pass
    try:
        audio.speak(line)
    except Exception:
        pass


def _maybe_soft_ack(log_f):
    global _last_ack
    if time.time() - _last_ack < 20:
        return
    line = random.choice(SOFT_ACKS)
    _last_ack = time.time()
    _log_and_say(line, log_f)


def _maybe_prompt(log_f):
    global _last_prompt
    if time.time() - _last_user_voice < 75:
        return
    if time.time() - _last_prompt < 75:
        return
    line = random.choice(GUIDED_PROMPTS)
    _last_prompt = time.time()
    _log_and_say(line, log_f)
