from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PROFILE_NAMES = ["Flat", "Music", "Game", "Movie"]


def build_default_profiles() -> List[Dict[str, Any]]:
    return [
        {"name": name, "eq": {"input": [0.0] * 10, "output": [0.0] * 10}}
        for name in DEFAULT_PROFILE_NAMES
    ]


class ProfileStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {
                "active": "Flat",
                "profiles": [self._with_meta(profile) for profile in build_default_profiles()],
            }
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save(self) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2, sort_keys=False)

    def _with_meta(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(profile)
        payload.setdefault("created_at", time.time())
        payload.setdefault("notes", "")
        return payload

    def list_profiles(self) -> List[Dict[str, Any]]:
        return list(self._data.get("profiles", []))

    def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        for profile in self._data.get("profiles", []):
            if profile.get("name") == name:
                return profile
        return None

    def active_profile(self) -> Optional[str]:
        return self._data.get("active")

    def set_active(self, name: str) -> bool:
        if self.get_profile(name) is None:
            return False
        self._data["active"] = name
        self._save()
        return True

    def upsert_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        name = profile.get("name")
        if not name:
            raise ValueError("Profile name required")
        existing = self.get_profile(name)
        if existing:
            existing.update(profile)
            existing["updated_at"] = time.time()
        else:
            payload = self._with_meta(profile)
            self._data.setdefault("profiles", []).append(payload)
        self._save()
        return self.get_profile(name) or profile

    def ensure_defaults(self) -> None:
        if not self._data.get("profiles"):
            self._data = {
                "active": "Flat",
                "profiles": [self._with_meta(profile) for profile in build_default_profiles()],
            }
            self._save()
