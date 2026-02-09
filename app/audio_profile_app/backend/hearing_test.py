from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List


class HearingTestStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save(self, data: List[Dict[str, Any]]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=False)

    def list_tests(self) -> List[Dict[str, Any]]:
        return self._load()

    def add_test(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = self._load()
        payload.setdefault("created_at", time.time())
        data.append(payload)
        self._save(data)
        return payload


def summarize_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        "total": len(results),
        "heard": 0,
        "not_heard": 0,
        "pleasant": 0,
        "neutral": 0,
        "unpleasant": 0,
        "yes": 0,
        "no": 0,
        "speech_correct": 0,
        "speech_incorrect": 0,
        "repeat_correct": 0,
        "repeat_incorrect": 0,
    }
    for item in results:
        response = (item.get("response") or "").lower()
        if response in summary:
            summary[response] += 1
    return summary
