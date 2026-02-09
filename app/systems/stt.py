"""
systems/stt.py — Speech-to-Text module (Whisper)

Make heavy deps optional at import time so the app can still launch
even if packaging misses a backend. We lazily import faster_whisper
inside initialize()/transcribe().
"""

import os
import tempfile
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

from config import (DESKTOP_CAPTURE_ENABLED, DESKTOP_CAPTURE_SECONDS,
                    DESKTOP_DEVICE_HINT, HOTKEY_PTT)

try:
    import ctypes as _ct

    _GetAsyncKeyState = (
        getattr(getattr(_ct, "windll", None), "user32", None).GetAsyncKeyState
        if hasattr(getattr(_ct, "windll", None), "user32")
        else None
    )
except Exception:
    _GetAsyncKeyState = None
try:
    import mouse as _mouse_lib
except Exception:
    _mouse_lib = None
try:
    from pynput import mouse as _pynput_mouse
except Exception:
    _pynput_mouse = None
_mouse_listener = None
_mouse4_state = False
_mouse5_state = False

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
SAMPLE_RATE = 16000

_default_threads = max(2, min(8, os.cpu_count() or 4))
_stt_model_name = os.getenv("STT_MODEL", "distil-small.en").strip() or "distil-small.en"
_stt_device = os.getenv("STT_DEVICE", "cpu").strip() or "cpu"
_stt_compute_type = os.getenv("STT_COMPUTE_TYPE", "int8").strip() or "int8"
try:
    _stt_cpu_threads = max(
        1,
        int(
            os.getenv("STT_CPU_THREADS", str(_default_threads)).strip()
            or _default_threads
        ),
    )
except Exception:
    _stt_cpu_threads = _default_threads
try:
    _stt_beam_size = max(1, int(os.getenv("STT_BEAM_SIZE", "1").strip() or "1"))
except Exception:
    _stt_beam_size = 1
_stt_language = os.getenv("STT_LANGUAGE", "en").strip() or "en"
_stt_force_vad = os.getenv("STT_VAD", "").strip().lower() in {"1", "true", "yes", "on"}

model = None
level_callback = None
_desktop_hint = DESKTOP_DEVICE_HINT
_desktop_once_error = None  # type: str | None
_vad_filter_enabled = True
_recording_flag = False
_monitor_thread = None
_monitor_stop = False


# -------------------------------------------------------------------------
# INITIALIZATION
# -------------------------------------------------------------------------
def _ensure_mouse_listener():
    global _mouse_listener, _mouse4_state, _mouse5_state
    if _pynput_mouse is None:
        return
    if HOTKEY_PTT not in {"mouse4", "mouse5", "mouse45"}:
        return
    if _mouse_listener is not None:
        return
    try:

        def _on_click(x, y, button, pressed):
            global _mouse4_state, _mouse5_state
            try:
                if button == getattr(_pynput_mouse.Button, "x1", None):
                    _mouse4_state = bool(pressed)
                if button == getattr(_pynput_mouse.Button, "x2", None):
                    _mouse5_state = bool(pressed)
            except Exception:
                pass

        _mouse_listener = _pynput_mouse.Listener(on_click=_on_click)
        _mouse_listener.daemon = True
        _mouse_listener.start()
    except Exception:
        _mouse_listener = None


def initialize():
    """Initialize Whisper STT model."""
    global model
    try:
        print(f"🧩 Loading Whisper model ({_stt_model_name}) on {_stt_device}...")
        # Lazy import to avoid hard failure at module import time
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as e:
            print("❌ faster_whisper not available:", e)
            return False
        model = WhisperModel(
            _stt_model_name,
            device=_stt_device,
            compute_type=_stt_compute_type,
            cpu_threads=_stt_cpu_threads,
            download_root=MODEL_DIR,
        )
        print("✅ STT system ready.")
        try:
            _start_level_monitor()
        except Exception:
            pass
        return True
    except Exception as e:
        print("❌ Failed to initialize STT:", e)
        return False


def set_level_callback(cb):
    global level_callback
    level_callback = cb


def set_vad_filter_enabled(flag: bool):
    global _vad_filter_enabled
    _vad_filter_enabled = bool(flag)


def get_vad_filter_enabled() -> bool:
    return bool(_vad_filter_enabled)


# -------------------------------------------------------------------------
# PASSIVE LEVEL MONITOR (mic LEDs without recording)
# -------------------------------------------------------------------------
def _start_level_monitor():
    global _monitor_thread, _monitor_stop
    if _monitor_thread and _monitor_thread.is_alive():
        return
    _monitor_stop = False

    def _loop():
        import sounddevice as sd

        while not _monitor_stop:
            try:
                if _recording_flag:
                    time.sleep(0.05)
                    continue
                buf_level = 0.0

                def cb(indata, frames, time_info, status):
                    nonlocal buf_level
                    try:
                        rms = float(np.sqrt(np.mean(np.square(indata))))
                        # Boost LED sensitivity for better visibility
                        lvl = min(1.0, rms * 6.0)
                        buf_level = max(
                            buf_level * 0.5, lvl
                        )  # quick decay, more reactive
                    except Exception:
                        pass

                with sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    callback=cb,
                    blocksize=1024,
                ):
                    t0 = time.time()
                    while (
                        time.time() - t0 < 0.4
                        and not _monitor_stop
                        and not _recording_flag
                    ):
                        try:
                            if level_callback is not None and buf_level > 0:
                                level_callback(buf_level)
                        except Exception:
                            pass
                        time.sleep(0.05)
                # small idle update to let bar decay
                try:
                    if level_callback is not None:
                        level_callback(0.0)
                except Exception:
                    pass
            except Exception:
                time.sleep(0.2)

    import threading

    _monitor_thread = threading.Thread(target=_loop, daemon=True)
    _monitor_thread.start()


# -------------------------------------------------------------------------
# RECORDING
# -------------------------------------------------------------------------
def _ptt_label() -> str:
    m = (HOTKEY_PTT or "ctrl+space").lower()
    if m == "num0+numenter":
        return "Numpad0 + NumpadEnter"
    if m == "right+numenter":
        return "Right Arrow + Numpad Enter"
    if m == "mouse4":
        return "Mouse Button 4"
    if m == "mouse5":
        return "Mouse Button 5"
    if m == "mouse45":
        return "Mouse Buttons 4+5"
    return "Ctrl + Space"


def get_ptt_label() -> str:
    """Return the friendly hotkey label for UI text/instructions."""
    try:
        return _ptt_label()
    except Exception:
        return "Ctrl + Space"


def _ptt_down() -> bool:
    import keyboard

    m = (HOTKEY_PTT or "ctrl+space").lower()

    def _vk_down(*codes: int) -> bool:
        if not _GetAsyncKeyState:
            return False
        try:
            return any(bool(_GetAsyncKeyState(code) & 0x8000) for code in codes)
        except Exception:
            return False

    try:
        _ensure_mouse_listener()
        if m == "num0+numenter":
            ok0 = keyboard.is_pressed("num 0")
            okenter = keyboard.is_pressed("num enter")
            if not ok0:
                ok0 = _vk_down(0x60)  # VK_NUMPAD0
            if not okenter:
                okenter = _vk_down(0x0D) or _vk_down(0x9C)  # Enter / Numpad Enter
            return ok0 and okenter
        if m == "right+numenter":
            ok_right = keyboard.is_pressed("right")
            ok_enter = keyboard.is_pressed("num enter")
            if not ok_right:
                ok_right = _vk_down(0x27)
            if not ok_enter:
                ok_enter = _vk_down(0x0D) or _vk_down(0x9C)
            return ok_right and ok_enter
        if m == "mouse4":
            if _mouse4_state:
                return True
            if _GetAsyncKeyState and (_GetAsyncKeyState(0x05) & 0x8000):
                return True
            if _mouse_lib is not None:
                return (
                    _mouse_lib.is_pressed("x")
                    or _mouse_lib.is_pressed("x1")
                    or _mouse_lib.is_pressed("back")
                )
            return False
        if m == "mouse5":
            if _mouse5_state:
                return True
            if _GetAsyncKeyState and (_GetAsyncKeyState(0x06) & 0x8000):
                return True
            if _mouse_lib is not None:
                return _mouse_lib.is_pressed("x2") or _mouse_lib.is_pressed("forward")
            return False
        if m == "mouse45":
            ok4 = bool(_mouse4_state)
            ok5 = bool(_mouse5_state)
            if _GetAsyncKeyState:
                ok4 = ok4 or bool(_GetAsyncKeyState(0x05) & 0x8000)
                ok5 = ok5 or bool(_GetAsyncKeyState(0x06) & 0x8000)
            if _mouse_lib is not None:
                ok4 = ok4 or (
                    _mouse_lib.is_pressed("x")
                    or _mouse_lib.is_pressed("x1")
                    or _mouse_lib.is_pressed("back")
                )
                ok5 = ok5 or (
                    _mouse_lib.is_pressed("x2") or _mouse_lib.is_pressed("forward")
                )
            return ok4 and ok5
        # default ctrl+space
        ctrl = keyboard.is_pressed("ctrl")
        space = keyboard.is_pressed("space")
        if not ctrl:
            ctrl = _vk_down(0x11, 0xA2, 0xA3)  # generic/left/right ctrl
        if not space:
            space = _vk_down(0x20)
        return ctrl and space
    except Exception:
        return False


def is_ptt_down() -> bool:
    """Public helper so other systems can detect the configured push-to-talk hotkey."""
    try:
        return _ptt_down()
    except Exception:
        return False


def record():
    """Record audio via push-to-talk keybind."""
    print(f"\n🎧 Hold {_ptt_label()} to speak…")
    while not _ptt_down():
        time.sleep(0.03)
    print("🎙️ Recording…")

    buf = []

    def cb(indata, frames, time_info, status):
        buf.append(indata.copy())
        try:
            if level_callback is not None:
                rms = float(np.sqrt(np.mean(np.square(indata))))
                # Boost displayed level for visibility in UI
                lvl = rms * 4.0
                if lvl > 1.0:
                    lvl = 1.0
                level_callback(lvl)
        except Exception:
            pass

    global _recording_flag
    _recording_flag = True
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=cb
        ):
            while _ptt_down():
                time.sleep(0.03)
    finally:
        _recording_flag = False

    a = np.concatenate(buf, axis=0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, a, SAMPLE_RATE)
    print("🛑 Recording stopped.")
    try:
        if level_callback is not None:
            level_callback(0.0)
    except Exception:
        pass
    return tmp.name


def is_recording() -> bool:
    """Return True while push-to-talk stream is active."""
    return bool(_recording_flag)


# -------------------------------------------------------------------------
# VOICE ACTIVITY RECORDING (MIC)
# -------------------------------------------------------------------------
_last_vad_reason = ""


def get_last_vad_reason() -> str:
    return _last_vad_reason


def record_vad(
    threshold: float = 0.03, silence_ms: int = 600, max_seconds: int = 15
) -> str:
    """Capture from default mic using simple RMS voice activity.
    Starts when RMS >= threshold, stops after 'silence_ms' of silence or max_seconds.
    Returns wav path or '' if nothing captured.
    """
    global _last_vad_reason
    _last_vad_reason = ""
    buf = []
    started = False
    last_voice_t = time.time()
    first_voice_t = None
    suspected_non_speech = False
    suspected_laugh = False
    non_speech_frames = 0

    def cb(indata, frames, time_info, status):
        nonlocal started, last_voice_t, first_voice_t, suspected_non_speech
        x = indata.copy()
        rms = float(np.sqrt(np.mean(np.square(x))))
        if not started and rms >= threshold:
            started = True
            first_voice_t = time.time()
        if started:
            buf.append(x)
            if rms >= threshold * 0.6:
                last_voice_t = time.time()
            # Lightweight spectral features to catch throat-clear / non-speech bursts
            try:
                xx = x.astype(np.float32).flatten()
                if xx.size > 64:
                    spec = np.fft.rfft(xx * np.hanning(xx.size))
                    mag = np.abs(spec) + 1e-12
                    freqs = np.fft.rfftfreq(xx.size, d=1.0 / SAMPLE_RATE)
                    centroid = (
                        float(np.sum(freqs * mag) / np.sum(mag))
                        if np.sum(mag) > 0
                        else 0.0
                    )
                    flatness = float(
                        np.exp(np.mean(np.log(mag))) / (np.mean(mag) + 1e-12)
                    )
                    # Zero-crossing rate for noisiness / laughter detection
                    zcr = float(np.mean(np.abs(np.diff(np.sign(xx))))) / 2.0
                    # Heuristic: short burst, low/medium centroid, relatively tonal => likely throat clear
                    dur = (
                        0.0 if first_voice_t is None else (time.time() - first_voice_t)
                    )
                    if dur < 0.8 and 150.0 <= centroid <= 1200.0 and flatness < 0.5:
                        non_speech_frames += 1
                    # Heuristic: laughter — mid centroid, medium-high flatness, higher ZCR, short-to-mid duration
                    if (
                        0.45 <= flatness <= 0.9
                        and 600.0 <= centroid <= 2800.0
                        and zcr >= 0.14
                        and 0.2 < dur < 3.5
                    ):
                        non_speech_frames += 1
            except Exception:
                pass
        try:
            if level_callback is not None:
                lvl = min(1.0, rms * 3.0)
                level_callback(lvl)
        except Exception:
            pass

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=cb
        ):
            t0 = time.time()
            while True:
                time.sleep(0.03)
                if started and (time.time() - last_voice_t) * 1000.0 > silence_ms:
                    break
                if time.time() - t0 > max_seconds:
                    break
    except Exception:
        return ""

    try:
        if level_callback is not None:
            level_callback(0.0)
    except Exception:
        pass

    if not buf:
        return ""
    # Drop likely throat-clear / laughter bursts only if the filter is enabled and
    # we observed multiple frames matching the non-speech pattern.
    if _vad_filter_enabled and non_speech_frames >= 3:
        # prefer laugh over non_speech label if we had higher flatness/zcr in last check
        if suspected_laugh:
            _last_vad_reason = "laugh"
        else:
            _last_vad_reason = "non_speech"
        return ""
    a = np.concatenate(buf, axis=0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, a, SAMPLE_RATE)
    return tmp.name


# -------------------------------------------------------------------------
# DESKTOP (LOOPBACK) CAPTURE
# -------------------------------------------------------------------------
def _find_output_device_by_hint(hint: str | None):
    """Pick an output-capable device by hint or default output device.
    Returns device index or None.
    """
    try:
        devices = sd.query_devices()
        apis = sd.query_hostapis()
        hint_l = (hint or "").lower()
        # First pass: WASAPI only
        for i, d in enumerate(devices):
            if d.get("max_output_channels", 0) <= 0:
                continue
            name = str(d.get("name", ""))
            hostapi = apis[d["hostapi"]]["name"] if "hostapi" in d else ""
            if "wasapi" not in hostapi.lower():
                continue
            if not hint_l or hint_l in name.lower() or hint_l in hostapi.lower():
                return i
        # Second pass: any hostapi
        for i, d in enumerate(devices):
            if d.get("max_output_channels", 0) <= 0:
                continue
            name = str(d.get("name", ""))
            hostapi = apis[d["hostapi"]]["name"] if "hostapi" in d else ""
            if not hint_l or hint_l in name.lower() or hint_l in hostapi.lower():
                return i
        # Default output index
        try:
            default_out = sd.default.device[1]
            if isinstance(default_out, int) and default_out >= 0:
                d = devices[default_out]
                if d.get("max_output_channels", 0) > 0:
                    return default_out
        except Exception:
            pass
        # Fallback first output device
        for i, d in enumerate(devices):
            if d.get("max_output_channels", 0) > 0:
                return i
    except Exception:
        pass
    return None


def _resample_mono(x: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Linear-resample 1D audio to target_sr."""
    if orig_sr == target_sr or x.size == 0:
        return x.astype(np.float32)
    ratio = float(target_sr) / float(orig_sr)
    n_out = int(round(x.shape[0] * ratio))
    if n_out <= 1:
        return x.astype(np.float32)
    xp = np.linspace(0.0, 1.0, num=x.shape[0], endpoint=True)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=True)
    y = np.interp(x_new, xp, x.astype(np.float32))
    return y.astype(np.float32)


def _wasapi_supported() -> bool:
    """Detect if WASAPI + loopback are available once per process."""
    global _desktop_once_error
    try:
        # Check host APIs
        names = [h.get("name", "") for h in sd.query_hostapis()]
        if not any("WASAPI" in (n or "") for n in names):
            _desktop_once_error = "WASAPI host API not present."
            return False
        # Check settings class
        from sounddevice import WasapiSettings  # noqa: F401

        return True
    except Exception as e:
        _desktop_once_error = f"WASAPI check failed: {e}"
        return False


def record_desktop(duration_sec: int | None = None, seconds: int | None = None):
    """Record system audio via WASAPI loopback (Windows). Returns wav path or ''."""
    if not DESKTOP_CAPTURE_ENABLED:
        print("[Desktop capture disabled] Set DESKTOP_CAPTURE_ENABLED=1 to enable.")
        return ""
    # Accept both parameter names; UI may pass 'seconds='
    duration = int(
        (seconds if seconds is not None else duration_sec)
        or DESKTOP_CAPTURE_SECONDS
        or 10
    )
    if not _wasapi_supported():
        if _desktop_once_error:
            print(f"[Desktop capture] { _desktop_once_error }")
        else:
            print("[Desktop capture] WASAPI not available on this system.")
        return ""

    dev_index = _find_output_device_by_hint(_desktop_hint)
    if dev_index is None:
        print("[Desktop capture] No output device found for loopback.")
        return ""
    dev_info = sd.query_devices(dev_index)
    sr_out = int(dev_info.get("default_samplerate", 48000) or 48000)
    # Build candidate channel counts (robust to device quirks)
    cand = []
    try:
        mi = int(dev_info.get("max_input_channels", 0) or 0)
        mo = int(dev_info.get("max_output_channels", 0) or 0)
        for v in (mi, mo, 2, 1):
            if v and v > 0 and v not in cand:
                cand.append(v)
    except Exception:
        cand = [2, 1]

    try:
        last_err = None
        a = None
        for ch in cand:
            for sr_try in (sr_out, 48000, 44100):
                buf = []

                def cb(indata, frames, time_info, status):
                    buf.append(indata.copy())
                    try:
                        if level_callback is not None:
                            rms = float(np.sqrt(np.mean(np.square(indata))))
                            lvl = min(1.0, rms * 2.5)
                            level_callback(lvl)
                    except Exception:
                        pass

                try:
                    extra = None
                    try:
                        ws = sd.WasapiSettings(exclusive=False)
                        # Enable loopback if attribute exists (sounddevice 0.5+)
                        if hasattr(ws, "loopback"):
                            ws.loopback = True
                        extra = ws
                    except Exception:
                        extra = None
                    # Try plain device index
                    try:
                        with sd.InputStream(
                            samplerate=sr_try,
                            channels=ch,
                            dtype="float32",
                            callback=cb,
                            device=dev_index,
                            extra_settings=extra,
                        ):
                            t0 = time.time()
                            while time.time() - t0 < duration:
                                time.sleep(0.05)
                    except Exception as e1:
                        # Try tuple device forms used by some PortAudio builds
                        opened = False
                        for dv in ((None, dev_index), (dev_index, dev_index)):
                            try:
                                with sd.InputStream(
                                    samplerate=sr_try,
                                    channels=ch,
                                    dtype="float32",
                                    callback=cb,
                                    device=dv,
                                    extra_settings=extra,
                                ):
                                    t0 = time.time()
                                    while time.time() - t0 < duration:
                                        time.sleep(0.05)
                                opened = True
                                break
                            except Exception as e2:
                                last_err = e2
                                continue
                        if not opened:
                            raise e1
                    a = (
                        np.concatenate(buf, axis=0)
                        if buf
                        else np.zeros((0,), dtype="float32")
                    )
                    sr_out = sr_try
                    break
                except Exception as e:
                    last_err = e
                    continue
            if a is not None:
                break

        if a is None:
            print(f"[Desktop capture error] {last_err}")
            return _record_desktop_soundcard_fallback(
                (_desktop_hint or "").lower(), duration
            )
        try:
            chs = a.shape[1] if isinstance(a, np.ndarray) and a.ndim == 2 else 1
        except Exception:
            chs = 1
        print(
            f"[Desktop capture] Using '{dev_info.get('name','?')}' {chs}ch @ {sr_out} Hz"
        )
        # Downmix to mono
        if a.ndim == 2 and a.shape[1] > 1:
            a = a.mean(axis=1)
        else:
            a = a.reshape(-1)
        mono = _resample_mono(a, sr_out, SAMPLE_RATE)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, mono, SAMPLE_RATE)
        print(
            f"[Desktop capture] Saved loopback audio from '{dev_info.get('name','?')}' at {SAMPLE_RATE} Hz."
        )
        try:
            if level_callback is not None:
                level_callback(0.0)
        except Exception:
            pass
        return tmp.name
    except Exception as e:
        print(f"[Desktop capture error] {e}")
        return ""


def list_output_devices():
    """Return a list of (name, hostapi) for output-capable devices."""
    try:
        devices = sd.query_devices()
        out = []
        for d in devices:
            if d.get("max_output_channels", 0) > 0:
                name = str(d.get("name", ""))
                hostapi_name = (
                    sd.query_hostapis()[d["hostapi"]]["name"] if "hostapi" in d else ""
                )
                label = f"{name} ({hostapi_name})" if hostapi_name else name
                out.append(label)
        # Unique preserve order
        seen = set()
        uniq = []
        for x in out:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        return uniq
    except Exception:
        return []


def set_desktop_hint(hint: str):
    global _desktop_hint
    _desktop_hint = (hint or "").strip()


def get_desktop_hint() -> str:
    return _desktop_hint


# -------------------------------------------------------------------------
# TRANSCRIPTION
# -------------------------------------------------------------------------
def transcribe(path):
    """Convert recorded speech to text."""
    global model
    if not model:
        if not initialize():
            return ""
    try:
        beam = max(1, _stt_beam_size)
        apply_vad = _stt_force_vad or _vad_filter_enabled
        segments, _ = model.transcribe(
            path,
            beam_size=beam,
            vad_filter=apply_vad,
            language=_stt_language or "en",
        )
        text = "".join(seg.text for seg in segments).strip()
        text = _normalize_transcript(text)
        print("🗣️ You said:", text)
        return text
    except Exception as e:
        print("❌ Transcription failed:", e)
        return ""


def _normalize_transcript(text: str) -> str:
    """Lightweight correction for common mis-recognitions of 'Bjorgsun'."""
    try:
        t = text
        repl = {
            "georgian": "Bjorgsun",
            "georgia": "Bjorgsun",
            "george sun": "Bjorgsun",
            "bjorg son": "Bjorgsun",
            "b yorxson": "Bjorgsun",
        }
        low = t.lower()
        for k, v in repl.items():
            if k in low:
                import re as _re

                t = _re.sub(k, v, t, flags=_re.I)
        # Capitalize standalone 'bjorgsun'
        if "bjorgsun" in t.lower():
            t = "".join([v if i else v.capitalize() for i, v in enumerate([t])])
        return t
    except Exception:
        return text


def _wasapi_supported() -> bool:
    global _desktop_once_error
    try:
        # Check host APIs
        names = [h.get("name", "") for h in sd.query_hostapis()]
        if not any("WASAPI" in (n or "") for n in names):
            _desktop_once_error = "WASAPI host API not present."
            return False
        # Check settings class
        from sounddevice import WasapiSettings  # noqa: F401

        return True
    except Exception as e:
        _desktop_once_error = f"WASAPI check failed: {e}"
        return False


def _record_desktop_soundcard_fallback(hint_l: str, duration: float) -> str:
    """Fallback: capture loopback via 'soundcard' library.
    Returns wav path or '' on failure. Non-destructive; does not print noisy errors.
    """
    try:
        try:
            import soundcard as sc  # type: ignore
        except Exception:
            # Security policy: no auto-install. Inform caller by returning ''.
            return ""
        speakers = sc.all_speakers()
        sel = None
        for s in speakers:
            nm = (getattr(s, "name", "") or "").lower()
            if not hint_l or hint_l in nm:
                sel = s
                break
        if sel is None:
            sel = sc.default_speaker()
        if sel is None:
            return ""
        sr_try = 48000
        ch_try = 2
        try:
            with sel.recorder(samplerate=sr_try, channels=ch_try) as rec:
                data = rec.record(int(sr_try * duration))
        except Exception:
            ch_try = 1
            with sel.recorder(samplerate=sr_try, channels=ch_try) as rec:
                data = rec.record(int(sr_try * duration))
        a = data.astype("float32")
        if a.ndim == 2 and a.shape[1] > 1:
            a = a.mean(axis=1)
        else:
            a = a.reshape(-1)
        mono = _resample_mono(a, sr_try, SAMPLE_RATE)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, mono, SAMPLE_RATE)
        print(
            f"[Desktop capture] soundcard backend from '{getattr(sel,'name','?')}' at {SAMPLE_RATE} Hz."
        )
        try:
            if level_callback is not None:
                level_callback(0.0)
        except Exception:
            pass
        return tmp.name
    except Exception:
        return ""
        return False
