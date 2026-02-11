from __future__ import annotations

import json
import logging
import os
import threading
import time
import wave
from difflib import SequenceMatcher
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import sounddevice as sd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .assistant import AssistantEngine, EQ_BANDS, suggest_eq_from_spectrum
from . import eq_system
from .audio_control import (
    PYCAW_AVAILABLE,
    get_master_state,
    list_sessions,
    list_system_devices,
    set_master_state,
    set_session_state,
)
from .hearing_test import HearingTestStore, summarize_results
from .profiles import ProfileStore

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_SETTINGS_PATH = DATA_DIR / "audio_settings.json"
EQ_STATE_PATH = DATA_DIR / "eq_state.json"
HEARING_TEST_PATH = DATA_DIR / "hearing_tests.json"

AUDIO_SETTINGS_DEFAULTS = {
    "system_sounds": True,
    "voice_feedback": True,
    "reply_chime": True,
    "volume": 70,
    "chime_volume": 35,
    "hush": False,
    "system_alerts": True,
    "process_warnings": True,
    "update_notices": True,
    "voice": "en-US-JennyNeural",
    "rate": "-5%",
    "pitch": "+2%",
    "eq_apo_config_path": "",
    "media_source": "spotify",
    "spotify_url": "",
}

logger = logging.getLogger("audio_profile")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_DIR / "audio_profile.log", maxBytes=1_000_000, backupCount=3)
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

HOST = os.getenv("AUDIO_PROFILE_HOST", "127.0.0.1")
PORT = int(os.getenv("AUDIO_PROFILE_PORT", "5714"))

VOSK_AVAILABLE = False
try:
    import vosk  # type: ignore

    VOSK_AVAILABLE = True
except Exception:
    vosk = None

VOSK_MODEL_PATH = os.getenv("AUDIO_PROFILE_VOSK_MODEL", "")
_VOSK_MODEL = None


class ToneRequest(BaseModel):
    kind: str = "sine"
    frequency: float = 440.0
    duration: float = 1.0
    amplitude: float = 0.2
    device: Optional[int] = None
    start_frequency: Optional[float] = None
    end_frequency: Optional[float] = None


class DeviceSelection(BaseModel):
    input: Optional[int] = None
    output: Optional[int] = None


class MasterRequest(BaseModel):
    volume: Optional[float] = None
    mute: Optional[bool] = None
    direction: str = "output"


class SessionRequest(BaseModel):
    session_id: str
    volume: Optional[float] = None
    mute: Optional[bool] = None


class EqRequest(BaseModel):
    target: str = "output"
    bands: List[float]


class EqApplyRequest(BaseModel):
    target: str = "output"
    bands: Optional[List[float]] = None


class ProfileRequest(BaseModel):
    name: str
    eq: Optional[Dict[str, List[float]]] = None
    notes: Optional[str] = None


class ProfileApplyRequest(BaseModel):
    name: str


class AssistantRequest(BaseModel):
    text: str


class VoiceRequest(BaseModel):
    duration: float = 3.0
    device: Optional[int] = None
    auto_respond: bool = True


class HearingTestRequest(BaseModel):
    user: Optional[str] = None
    test_type: Optional[str] = None
    target: str = "output"
    frequency: Optional[float] = None
    response: str
    volume: Optional[float] = None
    notes: Optional[str] = None
    expected: Optional[str] = None
    received: Optional[str] = None
    correct: Optional[bool] = None
    similarity: Optional[float] = None


class VoiceCalibrationRequest(BaseModel):
    duration: float = 3.0
    device: Optional[int] = None
    prefs: Optional[Dict[str, float]] = None


class VoiceRepeatRequest(BaseModel):
    expected: str
    duration: float = 3.0
    device: Optional[int] = None


class AudioCapture:
    def __init__(self, blocksize: int = 2048, bins: int = 64) -> None:
        self._blocksize = blocksize
        self._bins = bins
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()
        self._last_bins = [-120.0] * bins
        self._last_rms = 0.0
        self._last_peak = 0.0
        self._last_spectrum: List[Dict[str, float]] = []
        self._last_main = 0.0
        self._last_low = 0.0
        self._last_high = 0.0
        self._last_centroid = 0.0
        self._last_rolloff = 0.0
        self._last_duration = 0.0
        self._last_peaks: List[Dict[str, float]] = []
        self._last_band_energy: List[Dict[str, float]] = []
        self._last_emotion = ""
        self._sample_rate = 48000.0

    def start(self, input_device: Optional[int], sample_rate: Optional[float] = None) -> None:
        self.stop()
        self._sample_rate = sample_rate or get_device_samplerate(input_device) or 48000.0
        try:
            self._stream = sd.InputStream(
                device=input_device,
                channels=1,
                samplerate=self._sample_rate,
                blocksize=self._blocksize,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
            logger.info("Input stream started (device=%s, sample_rate=%.1f)", input_device, self._sample_rate)
        except Exception as exc:
            logger.exception("Failed to start input stream: %s", exc)
            self._stream = None

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                logger.exception("Failed stopping input stream")
            self._stream = None

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "bins": list(self._last_bins),
                "rms": float(self._last_rms),
                "peak": float(self._last_peak),
                "sample_rate": float(self._sample_rate),
                "spectrum": list(self._last_spectrum),
                "main_frequency_hz": float(self._last_main),
                "lowest_frequency_hz": float(self._last_low),
                "highest_frequency_hz": float(self._last_high),
                "centroid_hz": float(self._last_centroid),
                "rolloff_hz": float(self._last_rolloff),
                "duration_sec": float(self._last_duration),
                "sr": float(self._sample_rate),
                "name": "Live input",
                "channels": 1,
                "analysis_blocks": 1,
                "peaks": list(self._last_peaks),
                "band_energy": list(self._last_band_energy),
                "matched_emotions": [],
                "suggested_emotion": self._last_emotion,
                "live": True,
            }

    def _callback(self, indata: np.ndarray, frames: int, time_info: Dict[str, Any], status: sd.CallbackFlags) -> None:
        if status:
            logger.warning("Input stream status: %s", status)
        if frames <= 0:
            return
        mono = indata[:, 0]
        if mono.size == 0:
            return
        rms = np.sqrt(np.mean(mono * mono))
        peak = float(np.max(np.abs(mono)))
        window = np.hanning(len(mono))
        spectrum = np.fft.rfft(mono * window)
        mag = np.abs(spectrum)
        freqs = np.fft.rfftfreq(len(mono), d=1.0 / self._sample_rate)
        mag_db = 20.0 * np.log10(np.maximum(mag, 1e-10))
        bins = compress_spectrum(mag_db, self._bins)
        spectrum_bins: List[Dict[str, float]] = []
        if mag_db.size:
            step = max(1, len(freqs) // self._bins)
            for idx in range(0, len(freqs), step):
                chunk = mag_db[idx : idx + step]
                if chunk.size == 0:
                    continue
                hz = float(np.mean(freqs[idx : idx + step]))
                spectrum_bins.append({"hz": hz, "db": float(np.mean(chunk))})
        peaks: List[Dict[str, float]] = []
        if mag.size:
            top_n = 5
            idx = np.argsort(mag)[::-1][: top_n * 3]
            for i in idx:
                hz = float(freqs[i])
                if hz <= 1.0:
                    continue
                peaks.append({"hz": hz, "amplitude": float(mag[i])})
                if len(peaks) >= top_n:
                    break
        main_frequency = float(peaks[0]["hz"]) if peaks else 0.0
        max_mag = float(np.max(mag)) if mag.size else 0.0
        threshold = max_mag * 0.02
        significant = freqs[(freqs >= 20.0) & (mag >= threshold)]
        lowest_frequency = float(significant.min()) if significant.size else main_frequency
        highest_frequency = float(significant.max()) if significant.size else main_frequency
        if mag.sum() > 0:
            centroid = float((freqs * mag).sum() / mag.sum())
            cumulative = np.cumsum(mag)
            rolloff_idx = np.where(cumulative >= 0.85 * mag.sum())[0]
            rolloff = float(freqs[rolloff_idx[0]]) if rolloff_idx.size else main_frequency
        else:
            centroid = main_frequency
            rolloff = main_frequency
        bands = [
            (20, 60, "sub"),
            (60, 120, "bass"),
            (120, 180, "low_mid"),
            (180, 300, "mid"),
            (300, 500, "upper_mid"),
            (500, 1000, "presence"),
            (1000, 4000, "brilliance"),
        ]
        band_energy: List[Dict[str, float]] = []
        for lo, hi, label in bands:
            mask = (freqs >= lo) & (freqs < hi)
            energy = float(mag[mask].sum()) if mask.any() else 0.0
            band_energy.append({"label": label, "lo": lo, "hi": hi, "energy": energy})
        emotion = ""
        if centroid:
            if centroid < 200:
                emotion = "calm"
            elif centroid < 600:
                emotion = "grounded"
            elif centroid < 2000:
                emotion = "focused"
            elif centroid < 5000:
                emotion = "energized"
            else:
                emotion = "airy"
        with self._lock:
            self._last_bins = bins
            self._last_rms = float(rms)
            self._last_peak = peak
            self._last_spectrum = spectrum_bins
            self._last_main = main_frequency
            self._last_low = lowest_frequency
            self._last_high = highest_frequency
            self._last_centroid = centroid
            self._last_rolloff = rolloff
            self._last_duration = float(len(mono) / self._sample_rate) if self._sample_rate else 0.0
            self._last_peaks = peaks
            self._last_band_energy = band_energy
            self._last_emotion = emotion


class AudioState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.input_device: Optional[int] = None
        self.output_device: Optional[int] = None
        self.capture = AudioCapture()
        self.eq: Dict[str, List[float]] = {
            "input": [0.0] * len(EQ_BANDS),
            "output": [0.0] * len(EQ_BANDS),
        }


class AudioSettingsRequest(BaseModel):
    system_sounds: Optional[bool] = None
    voice_feedback: Optional[bool] = None
    reply_chime: Optional[bool] = None
    volume: Optional[int] = None
    chime_volume: Optional[int] = None
    hush: Optional[bool] = None
    system_alerts: Optional[bool] = None
    process_warnings: Optional[bool] = None
    update_notices: Optional[bool] = None
    voice: Optional[str] = None
    rate: Optional[str] = None
    pitch: Optional[str] = None
    eq_apo_config_path: Optional[str] = None
    media_source: Optional[str] = None
    spotify_url: Optional[str] = None


def clamp(value: float, min_value: float, max_value: float) -> float:
    return float(max(min_value, min(max_value, value)))


def _normalize_audio_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(AUDIO_SETTINGS_DEFAULTS)
    merged.update(data or {})
    try:
        merged["volume"] = int(clamp(float(merged.get("volume", 70)), 0, 100))
    except Exception:
        merged["volume"] = AUDIO_SETTINGS_DEFAULTS["volume"]
    try:
        merged["chime_volume"] = int(clamp(float(merged.get("chime_volume", 35)), 0, 100))
    except Exception:
        merged["chime_volume"] = AUDIO_SETTINGS_DEFAULTS["chime_volume"]
    for key in (
        "system_sounds",
        "voice_feedback",
        "reply_chime",
        "hush",
        "system_alerts",
        "process_warnings",
        "update_notices",
    ):
        merged[key] = bool(merged.get(key, AUDIO_SETTINGS_DEFAULTS[key]))
    for key in ("voice", "rate", "pitch"):
        merged[key] = str(merged.get(key, AUDIO_SETTINGS_DEFAULTS[key]) or "").strip()
        if not merged[key]:
            merged[key] = AUDIO_SETTINGS_DEFAULTS[key]
    merged["eq_apo_config_path"] = str(merged.get("eq_apo_config_path", "") or "").strip()
    merged["spotify_url"] = str(merged.get("spotify_url", "") or "").strip()
    media_source = str(merged.get("media_source", "") or "").strip().lower()
    if media_source not in {"spotify", "none"}:
        media_source = AUDIO_SETTINGS_DEFAULTS["media_source"]
    merged["media_source"] = media_source
    return merged


def _load_audio_settings() -> Dict[str, Any]:
    if not AUDIO_SETTINGS_PATH.exists():
        return dict(AUDIO_SETTINGS_DEFAULTS)
    try:
        raw = AUDIO_SETTINGS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
        return _normalize_audio_settings(data if isinstance(data, dict) else {})
    except Exception:
        return dict(AUDIO_SETTINGS_DEFAULTS)


def _save_audio_settings(settings: Dict[str, Any]) -> None:
    AUDIO_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIO_SETTINGS_PATH.write_text(
        json.dumps(_normalize_audio_settings(settings), indent=2, sort_keys=False),
        encoding="utf-8",
    )


def normalize_eq(bands: List[float]) -> List[float]:
    if not bands:
        return [0.0] * len(EQ_BANDS)
    trimmed = list(bands[: len(EQ_BANDS)])
    if len(trimmed) < len(EQ_BANDS):
        trimmed.extend([0.0] * (len(EQ_BANDS) - len(trimmed)))
    return [clamp(float(value), -12.0, 12.0) for value in trimmed]


HEARING_RESPONSE_WEIGHTS = {
    "not_heard": 4.0,
    "unpleasant": -3.0,
    "pleasant": 1.5,
    "heard": 0.0,
    "neutral": 0.0,
    "yes": 0.0,
    "no": 4.0,
    "speech_correct": 0.0,
    "speech_incorrect": 2.0,
    "repeat_correct": 0.0,
    "repeat_incorrect": 2.0,
}


def _normalize_hearing_response(value: Optional[str]) -> str:
    response = (value or "").strip().lower()
    if response in {"ok", "okay", "clear"}:
        return "heard"
    if response in {"too_loud", "loud", "harsh", "pain", "painful"}:
        return "unpleasant"
    if response in {"missed", "nope", "cant_hear", "can't hear", "silent"}:
        return "not_heard"
    if response in {"no"}:
        return "no"
    if response in {"yes", "yep", "yeah"}:
        return "yes"
    if response in {"good", "pleasant", "nice"}:
        return "pleasant"
    if response in {"neutral", "fine"}:
        return "neutral"
    return response


def _nearest_band_index(freq: float) -> int:
    return min(range(len(EQ_BANDS)), key=lambda idx: abs(EQ_BANDS[idx] - freq))


def suggest_eq_from_hearing_results(results: List[Dict[str, Any]]) -> List[float]:
    if not results:
        return [0.0] * len(EQ_BANDS)
    totals = [0.0] * len(EQ_BANDS)
    counts = [0] * len(EQ_BANDS)

    def apply_weight(freqs: List[float], weight: float) -> None:
        for freq in freqs:
            idx = _nearest_band_index(freq)
            totals[idx] += weight
            counts[idx] += 1

    for item in results:
        response = _normalize_hearing_response(item.get("response"))
        test_type = (item.get("test_type") or "").strip().lower()
        correct = item.get("correct")
        if response in {"speech_correct", "speech_incorrect", "repeat_correct", "repeat_incorrect"} or test_type == "speech":
            if response.endswith("incorrect") or (isinstance(correct, bool) and not correct):
                weight = 2.0
            else:
                weight = 0.0
            apply_weight([2000, 4000], weight)
            apply_weight([8000, 16000], weight * 0.8)
            continue
        try:
            freq = float(item.get("frequency"))
        except (TypeError, ValueError):
            continue
        response = _normalize_hearing_response(item.get("response"))
        if response not in HEARING_RESPONSE_WEIGHTS:
            continue
        if freq <= 0.0:
            continue
        idx = _nearest_band_index(freq)
        totals[idx] += HEARING_RESPONSE_WEIGHTS[response]
        counts[idx] += 1
    adjustments = []
    for idx, total in enumerate(totals):
        if counts[idx] == 0:
            adjustments.append(0.0)
        else:
            adjustments.append(clamp(total / counts[idx], -6.0, 6.0))
    smoothed = []
    for idx, value in enumerate(adjustments):
        neighbors = []
        if idx > 0:
            neighbors.append(adjustments[idx - 1])
        if idx + 1 < len(adjustments):
            neighbors.append(adjustments[idx + 1])
        if neighbors:
            blended = (value * 0.7) + (sum(neighbors) / len(neighbors)) * 0.3
        else:
            blended = value
        smoothed.append(clamp(blended, -6.0, 6.0))
    return smoothed


def generate_sine(frequency: float, duration: float, sample_rate: float, amplitude: float) -> np.ndarray:
    frames = int(sample_rate * duration)
    t = np.linspace(0.0, duration, frames, endpoint=False)
    wave_data = np.sin(2.0 * np.pi * frequency * t) * amplitude
    return wave_data.astype(np.float32)


def generate_sweep(start_freq: float, end_freq: float, duration: float, sample_rate: float, amplitude: float) -> np.ndarray:
    frames = int(sample_rate * duration)
    t = np.linspace(0.0, duration, frames, endpoint=False)
    if start_freq <= 0.0 or end_freq <= 0.0:
        return generate_sine(440.0, duration, sample_rate, amplitude)
    k = np.log(end_freq / start_freq) / duration
    phase = 2.0 * np.pi * start_freq * (np.exp(k * t) - 1.0) / k
    wave_data = np.sin(phase) * amplitude
    return wave_data.astype(np.float32)


def compress_spectrum(values: np.ndarray, target_bins: int) -> List[float]:
    if target_bins <= 0:
        return []
    values = np.asarray(values)
    total = values.size
    if total == 0:
        return [-120.0] * target_bins
    step = max(1, total // target_bins)
    bins: List[float] = []
    for idx in range(target_bins):
        start = idx * step
        end = min(start + step, total)
        if start >= total:
            bins.append(-120.0)
        else:
            bins.append(float(np.mean(values[start:end])))
    return bins


def normalize_text(text: Optional[str]) -> str:
    raw = (text or "").lower()
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in raw)
    return " ".join(cleaned.split()).strip()


def transcript_similarity(expected: Optional[str], received: Optional[str]) -> float:
    expected_norm = normalize_text(expected)
    received_norm = normalize_text(received)
    if not expected_norm or not received_norm:
        return 0.0
    return float(SequenceMatcher(None, expected_norm, received_norm).ratio())


def analyze_voice(audio: np.ndarray, sample_rate: float) -> Dict[str, Any]:
    rms = float(np.sqrt(np.mean(audio * audio))) if audio.size else 0.0
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    window = np.hanning(len(audio)) if audio.size else np.array([])
    spectrum = np.fft.rfft(audio * window) if audio.size else np.array([])
    mag = np.abs(spectrum) if spectrum.size else np.array([1e-10])
    mag_db = 20.0 * np.log10(np.maximum(mag, 1e-10))
    bins = compress_spectrum(mag_db, 64)
    suggested = suggest_eq_from_spectrum(bins)
    freqs = np.fft.rfftfreq(len(audio), d=1.0 / sample_rate) if audio.size else np.array([])
    band_levels = []
    if freqs.size:
        overall = float(np.mean(mag_db))
        for band in EQ_BANDS:
            low = band / np.sqrt(2.0)
            high = band * np.sqrt(2.0)
            mask = (freqs >= low) & (freqs <= high)
            level = float(np.mean(mag_db[mask])) if np.any(mask) else overall
            band_levels.append(level)
        overall = float(np.mean(band_levels))

        def band_avg(indices: List[int]) -> float:
            return float(np.mean([band_levels[idx] for idx in indices]))

        low_level = band_avg([0, 1, 2])
        low_mid = band_avg([3, 4])
        presence = band_avg([6, 7])
        air = band_avg([8, 9])
        adjustments = list(suggested)

        def bump(freqs_to_bump: List[int], delta: float) -> None:
            for freq in freqs_to_bump:
                idx = _nearest_band_index(freq)
                adjustments[idx] = clamp(adjustments[idx] + delta, -6.0, 6.0)

        if low_level - overall > 4.0:
            bump([31, 62, 125], -1.5)
        elif low_level - overall < -4.0:
            bump([31, 62, 125], 1.5)

        if low_mid - overall > 4.0:
            bump([250, 500], -1.0)
        elif low_mid - overall < -4.0:
            bump([250, 500], 1.0)

        if presence - overall < -3.0:
            bump([2000, 4000], 1.5)
        elif presence - overall > 4.0:
            bump([2000, 4000], -1.2)

        if air - overall > 4.0:
            bump([8000, 16000], -1.5)
        elif air - overall < -4.0:
            bump([8000, 16000], 1.0)
        suggested = adjustments
    return {
        "rms": rms,
        "peak": peak,
        "sample_rate": sample_rate,
        "bins": bins,
        "band_levels": band_levels,
        "suggested_eq": suggested,
    }


def list_devices() -> List[Dict[str, Any]]:
    hostapis = sd.query_hostapis()
    host_names = {idx: api.get("name", "unknown") for idx, api in enumerate(hostapis)}
    devices = []
    for idx, device in enumerate(sd.query_devices()):
        devices.append(
            {
                "id": idx,
                "name": device.get("name"),
                "hostapi": device.get("hostapi"),
                "hostapi_name": host_names.get(device.get("hostapi"), "unknown"),
                "max_input_channels": device.get("max_input_channels"),
                "max_output_channels": device.get("max_output_channels"),
                "default_samplerate": device.get("default_samplerate"),
            }
        )
    return devices


def get_default_devices() -> tuple[Optional[int], Optional[int]]:
    input_device: Optional[int]
    output_device: Optional[int]
    try:
        input_device, output_device = sd.default.device
    except Exception:
        input_device, output_device = None, None
    return input_device, output_device


def get_device_samplerate(device_index: Optional[int]) -> Optional[float]:
    try:
        if device_index is None:
            return float(sd.default.samplerate) if sd.default.samplerate else None
        info = sd.query_devices(device_index)
        return float(info.get("default_samplerate"))
    except Exception:
        return None


def record_voice(duration: float, device: Optional[int]) -> tuple[np.ndarray, float]:
    sample_rate = get_device_samplerate(device) or 16000.0
    frames = int(sample_rate * duration)
    audio = sd.rec(
        frames,
        samplerate=int(sample_rate),
        channels=1,
        dtype="float32",
        device=device,
    )
    sd.wait()
    return audio.reshape(-1), sample_rate


def save_wav(path: Path, audio: np.ndarray, sample_rate: float) -> None:
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(int(sample_rate))
        handle.writeframes(pcm.tobytes())


def _get_vosk_model() -> Optional[Any]:
    global _VOSK_MODEL
    if not VOSK_AVAILABLE or not VOSK_MODEL_PATH:
        return None
    if _VOSK_MODEL is None:
        _VOSK_MODEL = vosk.Model(VOSK_MODEL_PATH)
    return _VOSK_MODEL


def transcribe_audio(path: Path, sample_rate: float) -> Optional[str]:
    model = _get_vosk_model()
    if model is None:
        return None
    recognizer = vosk.KaldiRecognizer(model, sample_rate)
    with wave.open(str(path), "rb") as handle:
        while True:
            data = handle.readframes(4000)
            if len(data) == 0:
                break
            recognizer.AcceptWaveform(data)
    result = json.loads(recognizer.FinalResult())
    text = result.get("text", "").strip()
    return text or None


state = AudioState()
profile_store = ProfileStore(Path(__file__).resolve().parent / "data" / "profiles.json")
profile_store.ensure_defaults()
hearing_store = HearingTestStore(HEARING_TEST_PATH)
assistant_engine = AssistantEngine(profile_store, state.capture.snapshot, logger)
audio_settings = _load_audio_settings()

app = FastAPI(title="Audio Profile API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    input_device, output_device = get_default_devices()
    state.input_device = input_device
    state.output_device = output_device
    state.capture.start(input_device)

    active = profile_store.active_profile()
    if active:
        profile = profile_store.get_profile(active)
        if profile and profile.get("eq"):
            eq = profile["eq"]
            state.eq["input"] = normalize_eq(eq.get("input", []))
            state.eq["output"] = normalize_eq(eq.get("output", []))

    logger.info("Backend started (input=%s, output=%s)", input_device, output_device)


@app.on_event("shutdown")
def on_shutdown() -> None:
    state.capture.stop()
    sd.stop()
    logger.info("Backend shutdown")


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/devices")
def devices() -> Dict[str, Any]:
    devices_list = list_devices()
    input_device, output_device = get_default_devices()
    return {
        "devices": devices_list,
        "default_input": input_device,
        "default_output": output_device,
    }


@app.get("/api/status")
def status() -> Dict[str, Any]:
    return {
        "input_device": state.input_device,
        "output_device": state.output_device,
        "pycaw_available": PYCAW_AVAILABLE,
    }


@app.get("/api/settings")
def get_settings() -> Dict[str, Any]:
    return {"settings": dict(audio_settings)}


@app.post("/api/settings")
def update_settings(request: AudioSettingsRequest) -> Dict[str, Any]:
    global audio_settings
    payload = request.model_dump(exclude_none=True)
    if payload:
        audio_settings = _normalize_audio_settings({**audio_settings, **payload})
        _save_audio_settings(audio_settings)
    return {"settings": dict(audio_settings)}


@app.post("/api/active-device")
def active_device(selection: DeviceSelection) -> Dict[str, Any]:
    input_device = selection.input
    output_device = selection.output
    if input_device is None and output_device is None:
        raise HTTPException(status_code=400, detail="No device selection provided")

    with state.lock:
        if input_device is not None:
            state.input_device = input_device
        if output_device is not None:
            state.output_device = output_device

    state.capture.start(state.input_device)
    logger.info("Active devices updated (input=%s, output=%s)", state.input_device, state.output_device)
    return {
        "input_device": state.input_device,
        "output_device": state.output_device,
        "sample_rate": state.capture.snapshot().get("sample_rate"),
    }


@app.post("/api/tone")
def tone(request: ToneRequest) -> Dict[str, Any]:
    kind = request.kind.lower().strip()
    duration = clamp(request.duration, 0.1, 10.0)
    amplitude = clamp(request.amplitude, 0.0, 1.0)

    output_device = request.device if request.device is not None else state.output_device
    sample_rate = get_device_samplerate(output_device) or 48000.0

    if kind == "sine":
        frequency = clamp(request.frequency, 20.0, 20000.0)
        samples = generate_sine(frequency, duration, sample_rate, amplitude)
        label = f"sine {frequency:.1f}Hz"
    elif kind == "sweep":
        start_freq = clamp(request.start_frequency or request.frequency, 20.0, 20000.0)
        end_freq = clamp(request.end_frequency or 16000.0, 20.0, 20000.0)
        samples = generate_sweep(start_freq, end_freq, duration, sample_rate, amplitude)
        label = f"sweep {start_freq:.1f}-{end_freq:.1f}Hz"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported tone kind: {kind}")

    sd.stop()
    sd.play(samples, int(sample_rate), device=output_device, blocking=False)

    logger.info(
        "Tone played (kind=%s, duration=%.2f, amplitude=%.2f, output=%s)",
        kind,
        duration,
        amplitude,
        output_device,
    )

    return {
        "status": "playing",
        "kind": kind,
        "label": label,
        "duration": duration,
        "amplitude": amplitude,
        "output_device": output_device,
    }


@app.post("/api/stop")
def stop() -> Dict[str, str]:
    sd.stop()
    logger.info("Tone stopped")
    return {"status": "stopped"}


@app.get("/api/spectrum")
def spectrum() -> Dict[str, Any]:
    snapshot = state.capture.snapshot()
    snapshot["timestamp"] = time.time()
    return snapshot


@app.get("/api/eq")
def eq() -> Dict[str, Any]:
    return {"bands": EQ_BANDS, "input": state.eq["input"], "output": state.eq["output"]}


@app.post("/api/eq")
def update_eq(request: EqRequest) -> Dict[str, Any]:
    target = request.target
    if target not in state.eq:
        raise HTTPException(status_code=400, detail="Invalid EQ target")
    state.eq[target] = normalize_eq(request.bands)
    return eq()


@app.get("/api/eq/engine")
def eq_engine_status() -> Dict[str, Any]:
    global audio_settings
    status = eq_system.get_engine_status(audio_settings.get("eq_apo_config_path"))
    if not audio_settings.get("eq_apo_config_path") and status.get("config_path"):
        audio_settings = _normalize_audio_settings(
            {**audio_settings, "eq_apo_config_path": status["config_path"]}
        )
        _save_audio_settings(audio_settings)
    last = eq_system.get_last_applied(EQ_STATE_PATH)
    return {"status": status, "last": last}


@app.post("/api/eq/apply")
def apply_eq(request: EqApplyRequest) -> Dict[str, Any]:
    target = (request.target or "output").strip().lower()
    if target not in state.eq:
        raise HTTPException(status_code=400, detail="Invalid EQ target")
    if request.bands:
        state.eq[target] = normalize_eq(request.bands)
    config_override = audio_settings.get("eq_apo_config_path")
    result = eq_system.apply_system_eq(state.eq[target], EQ_STATE_PATH, config_override)
    return {"status": result, "eq": state.eq[target]}


@app.get("/api/hearing/tests")
def hearing_tests(user: Optional[str] = None, target: Optional[str] = None) -> Dict[str, Any]:
    tests = hearing_store.list_tests()
    if user:
        tests = [item for item in tests if (item.get("user") or "").strip() == user]
    if target:
        target_clean = target.strip().lower()
        tests = [
            item
            for item in tests
            if (item.get("target") or "").strip().lower() == target_clean
        ]
    return {"tests": tests}


@app.post("/api/hearing/tests")
def add_hearing_test(request: HearingTestRequest) -> Dict[str, Any]:
    target = (request.target or "output").strip().lower()
    if target not in {"input", "output"}:
        raise HTTPException(status_code=400, detail="Invalid hearing test target")
    response = _normalize_hearing_response(request.response)
    if response not in HEARING_RESPONSE_WEIGHTS:
        raise HTTPException(status_code=400, detail="Invalid hearing response")
    test_type = (request.test_type or "").strip().lower()
    frequency = None
    if request.frequency is not None:
        frequency = clamp(request.frequency, 20.0, 20000.0)
    elif test_type != "speech":
        raise HTTPException(status_code=400, detail="Frequency required for tone tests")
    volume = None
    if request.volume is not None:
        try:
            volume = float(request.volume)
        except (TypeError, ValueError):
            volume = None
    payload = {
        "user": (request.user or "").strip(),
        "test_type": test_type,
        "target": target,
        "frequency": frequency,
        "response": response,
        "volume": volume,
        "notes": (request.notes or "").strip(),
        "expected": (request.expected or "").strip(),
        "received": (request.received or "").strip(),
        "correct": request.correct,
        "similarity": request.similarity,
    }
    record = hearing_store.add_test(payload)
    return {"test": record}


@app.get("/api/hearing/summary")
def hearing_summary(user: Optional[str] = None, target: Optional[str] = None) -> Dict[str, Any]:
    tests = hearing_store.list_tests()
    if user:
        tests = [item for item in tests if (item.get("user") or "").strip() == user]
    if target:
        target_clean = target.strip().lower()
        tests = [
            item
            for item in tests
            if (item.get("target") or "").strip().lower() == target_clean
        ]
    summary = summarize_results(tests)
    suggested = suggest_eq_from_hearing_results(tests)
    return {
        "summary": summary,
        "suggested_eq": suggested,
        "count": len(tests),
        "user": user or "",
        "target": target or "all",
    }


@app.post("/api/voice/calibrate")
def voice_calibrate(request: VoiceCalibrationRequest) -> Dict[str, Any]:
    duration = clamp(request.duration, 0.5, 8.0)
    capture_device = request.device if request.device is not None else state.input_device
    state.capture.stop()
    try:
        audio, sample_rate = record_voice(duration, capture_device)
    finally:
        state.capture.start(state.input_device)
    if audio.size == 0:
        raise HTTPException(status_code=500, detail="No audio captured")
    metrics = analyze_voice(audio, sample_rate)
    return {
        "metrics": metrics,
        "suggested_eq": metrics["suggested_eq"],
    }


@app.post("/api/voice/repeat")
def voice_repeat(request: VoiceRepeatRequest) -> Dict[str, Any]:
    expected = (request.expected or "").strip()
    if not expected:
        raise HTTPException(status_code=400, detail="Expected phrase required")
    duration = clamp(request.duration, 0.5, 8.0)
    capture_device = request.device if request.device is not None else state.input_device
    state.capture.stop()
    try:
        audio, sample_rate = record_voice(duration, capture_device)
    finally:
        state.capture.start(state.input_device)
    if audio.size == 0:
        raise HTTPException(status_code=500, detail="No audio captured")
    wav_path = LOG_DIR / f"repeat_{int(time.time())}.wav"
    save_wav(wav_path, audio, sample_rate)
    transcript = transcribe_audio(wav_path, sample_rate) if VOSK_AVAILABLE else None
    try:
        wav_path.unlink()
    except Exception:
        pass
    similarity = transcript_similarity(expected, transcript)
    match = similarity >= 0.75
    metrics = analyze_voice(audio, sample_rate)
    return {
        "transcript": transcript,
        "match": match,
        "similarity": similarity,
        "vosk_available": VOSK_AVAILABLE and bool(VOSK_MODEL_PATH),
        "metrics": metrics,
        "suggested_eq": metrics["suggested_eq"],
    }


@app.get("/api/profiles")
def profiles() -> Dict[str, Any]:
    return {"profiles": profile_store.list_profiles(), "active": profile_store.active_profile()}


@app.post("/api/profiles")
def save_profile(request: ProfileRequest) -> Dict[str, Any]:
    eq_payload = request.eq or {"input": state.eq["input"], "output": state.eq["output"]}
    profile = profile_store.upsert_profile(
        {
            "name": request.name,
            "eq": {
                "input": normalize_eq(eq_payload.get("input", [])),
                "output": normalize_eq(eq_payload.get("output", [])),
            },
            "notes": request.notes or "",
        }
    )
    return {"profile": profile}


@app.get("/api/profiles/active")
def active_profile() -> Dict[str, Any]:
    return {"active": profile_store.active_profile()}


@app.post("/api/profiles/active")
def set_active_profile(request: ProfileApplyRequest) -> Dict[str, Any]:
    if not profile_store.set_active(request.name):
        raise HTTPException(status_code=404, detail="Profile not found")
    profile = profile_store.get_profile(request.name)
    if profile and profile.get("eq"):
        eq_payload = profile["eq"]
        state.eq["input"] = normalize_eq(eq_payload.get("input", []))
        state.eq["output"] = normalize_eq(eq_payload.get("output", []))
    return {"active": request.name, "eq": state.eq}


@app.get("/api/system/devices")
def system_devices() -> Dict[str, Any]:
    return list_system_devices()


@app.get("/api/system/master")
def system_master(direction: str = Query("output")) -> Dict[str, Any]:
    return get_master_state(direction=direction)


@app.post("/api/system/master")
def set_system_master(request: MasterRequest) -> Dict[str, Any]:
    direction = request.direction or "output"
    volume = None if request.volume is None else clamp(request.volume, 0.0, 1.0)
    return set_master_state(direction=direction, volume=volume, mute=request.mute)


@app.get("/api/system/sessions")
def system_sessions() -> Dict[str, Any]:
    return list_sessions()


@app.post("/api/system/session")
def update_session(request: SessionRequest) -> Dict[str, Any]:
    if request.volume is None and request.mute is None:
        raise HTTPException(status_code=400, detail="No session update provided")
    volume = None if request.volume is None else clamp(request.volume, 0.0, 1.0)
    ok = set_session_state(request.session_id, volume=volume, mute=request.mute)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok"}


@app.post("/api/assistant/text")
def assistant_text(request: AssistantRequest) -> Dict[str, Any]:
    result = assistant_engine.handle_text(request.text)
    return result


@app.get("/api/assistant/history")
def assistant_history() -> Dict[str, Any]:
    return {"history": assistant_engine.get_history()}


@app.post("/api/assistant/voice")
def assistant_voice(request: VoiceRequest) -> Dict[str, Any]:
    duration = clamp(request.duration, 0.5, 8.0)
    capture_device = request.device if request.device is not None else state.input_device
    state.capture.stop()
    try:
        audio, sample_rate = record_voice(duration, capture_device)
    finally:
        state.capture.start(state.input_device)
    wav_path = LOG_DIR / f"voice_{int(time.time())}.wav"
    save_wav(wav_path, audio, sample_rate)

    transcript = transcribe_audio(wav_path, sample_rate) if VOSK_AVAILABLE else None
    response = None
    if request.auto_respond and transcript:
        response = assistant_engine.handle_text(transcript)

    return {
        "transcript": transcript,
        "response": response,
        "audio_path": str(wav_path),
        "vosk_available": VOSK_AVAILABLE and bool(VOSK_MODEL_PATH),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=HOST, port=PORT, reload=False)
