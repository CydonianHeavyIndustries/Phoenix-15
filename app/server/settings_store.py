import json
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    "systemSounds": True,
    "voiceMode": False,
    "replyChime": True,
    "volume": 75,
    "chimeVolume": 60,
    "systemAlerts": True,
    "processWarnings": True,
    "updateNotices": False,
    "notifications": True,
    "animations": True,
    "grid": False,
    "opacity": 90,
    "processingMode": "BALANCED",
    "hardwareAccel": True,
    "backgroundProc": True,
    "devEnabled": False,
    "debugOverlay": False,
    "preferredInputId": None,
    "themeBg": "#061923",
    "themePanel": "#0b1f2a",
    "themeBorder": "#1e6b73",
    "themeText": "#9fe7df",
    "themeAccent": "#28e6d4",
    "themeAccent2": "#7cf7ff",
    "usbLocalBootEnabled": False,
    "usbLocalBootPath": str(DEFAULT_ROOT),
    "usbIncludeOs": False,
    "usbIncludeApp": True,
    "usbIncludeMemory": True,
    "usbIncludeUserData": True,
    "usbCopyPreset": "full",
    "remoteUiEnabled": False,
    "remoteUiHost": "CHII.inc",
    "remoteTunnelEnabled": False,
    "desktopViewEnabled": False,
    "desktopViewMonitors": [],
    "performanceFocusEnabled": True,
}


class SettingsStore:
    def __init__(self, path: Path):
        self.path = path
        self.data: Dict[str, Any] = DEFAULTS.copy()
        self.load()

    def load(self):
        try:
            if not self.path.exists():
                return
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            merged = DEFAULTS.copy()
            # Back-compat: older key name
            if "voiceFeedback" in raw and "voiceMode" not in raw:
                raw["voiceMode"] = raw.get("voiceFeedback")
            merged.update(raw)
            merged.pop("usbSyncEnabled", None)
            self.data = merged
        except Exception:
            self.data = DEFAULTS.copy()

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get(self) -> Dict[str, Any]:
        return self.data

    def set(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(updates, dict):
            return self.data
        merged = self.data.copy()
        updates = updates.copy()
        updates.pop("usbSyncEnabled", None)
        merged.update(updates)
        merged.pop("usbSyncEnabled", None)
        self.data = merged
        self.save()
        return self.data


_store_cache: SettingsStore | None = None


def get_store(path: Path) -> SettingsStore:
    global _store_cache
    if _store_cache is None:
        _store_cache = SettingsStore(path)
    return _store_cache
