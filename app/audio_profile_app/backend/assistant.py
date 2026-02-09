from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .audio_control import list_sessions, set_master_state, set_session_state
from .profiles import ProfileStore

EQ_BANDS = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]


def clamp(value: float, min_value: float, max_value: float) -> float:
    return float(max(min_value, min(max_value, value)))


def suggest_eq_from_spectrum(bins: List[float]) -> List[float]:
    if not bins:
        return [0.0] * len(EQ_BANDS)
    values = np.array(bins, dtype=np.float32)
    mean = float(np.mean(values))
    normalized = values - mean
    positions = np.linspace(0.0, 1.0, len(values))
    band_positions = np.linspace(0.0, 1.0, len(EQ_BANDS))
    band_values = np.interp(band_positions, positions, normalized)
    adjustments = -band_values / 4.0
    return [clamp(float(value), -6.0, 6.0) for value in adjustments]


class AssistantEngine:
    def __init__(
        self,
        profile_store: ProfileStore,
        get_spectrum: Callable[[], Dict[str, Any]],
        logger: Any,
    ) -> None:
        self.profile_store = profile_store
        self.get_spectrum = get_spectrum
        self.logger = logger
        self.history: List[Dict[str, Any]] = []
        self.last_eq: Optional[List[float]] = None

    def handle_text(self, text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        if not cleaned:
            return {
                "reply": "Say a command like 'set volume to 60%' or 'auto optimize'.",
                "actions": [],
            }

        lower = cleaned.lower()
        actions: List[Dict[str, Any]] = []
        reply = ""

        if "auto optimize" in lower or "auto-optimize" in lower:
            spectrum = self.get_spectrum()
            bins = spectrum.get("bins") or []
            self.last_eq = suggest_eq_from_spectrum(bins)
            profile_name = f"Auto-{int(time.time())}"
            profile = {
                "name": profile_name,
                "eq": {"input": [0.0] * 10, "output": self.last_eq},
                "notes": "Auto-optimized from live spectrum.",
            }
            self.profile_store.upsert_profile(profile)
            actions.append({"type": "profile_created", "name": profile_name})
            reply = (
                "Auto-optimized EQ generated and saved as profile "
                f"'{profile_name}'. You can apply it from the profiles list."
            )

        elif "explain" in lower and self.last_eq is not None:
            reply = (
                "I analyzed the live spectrum and suggested small EQ trims to "
                "flatten peaks and lift dips. Use the profile to audition and tweak."
            )

        if "mute" in lower and "unmute" not in lower:
            set_master_state(mute=True)
            actions.append({"type": "set_master_mute", "value": True})
            reply = reply or "Master output muted."

        if "unmute" in lower:
            set_master_state(mute=False)
            actions.append({"type": "set_master_mute", "value": False})
            reply = reply or "Master output unmuted."

        volume_match = re.search(r"(\d{1,3})\s*%", lower)
        if "volume" in lower and volume_match:
            volume_value = clamp(float(volume_match.group(1)) / 100.0, 0.0, 1.0)
            set_master_state(volume=volume_value)
            actions.append({"type": "set_master_volume", "value": volume_value})
            reply = reply or f"Master volume set to {int(volume_value * 100)}%."

        session_target = _find_session_target(lower)
        if session_target:
            session_name = session_target["name"]
            session_volume = _extract_volume(lower)
            if session_volume is not None:
                ok = set_session_state(session_target["id"], volume=session_volume)
                if ok:
                    actions.append(
                        {
                            "type": "set_session_volume",
                            "session": session_name,
                            "value": session_volume,
                        }
                    )
                    reply = reply or (
                        f"Set {session_name} volume to {int(session_volume * 100)}%."
                    )

        if not reply:
            reply = (
                "I can adjust master volume, mute, or auto-optimize EQ. "
                "Try 'auto optimize' or 'set volume to 70%'."
            )

        self._push_history("user", cleaned)
        self._push_history("assistant", reply)
        return {"reply": reply, "actions": actions, "last_eq": self.last_eq}

    def _push_history(self, role: str, text: str) -> None:
        self.history.append({"role": role, "text": text, "timestamp": time.time()})
        if len(self.history) > 200:
            self.history = self.history[-200:]

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self.history)


def _extract_volume(text: str) -> Optional[float]:
    match = re.search(r"(\d{1,3})\s*%", text)
    if not match:
        return None
    return clamp(float(match.group(1)) / 100.0, 0.0, 1.0)


def _find_session_target(text: str) -> Optional[Dict[str, Any]]:
    sessions_data = list_sessions()
    if not sessions_data.get("available"):
        return None
    sessions = sessions_data.get("sessions", [])
    tokens = [token for token in re.split(r"\\W+", text) if len(token) > 2]
    for session in sessions:
        name = (session.get("name") or "").lower()
        if not name:
            continue
        if name in text:
            return session
        if any(token in name for token in tokens):
            return session
    return None
