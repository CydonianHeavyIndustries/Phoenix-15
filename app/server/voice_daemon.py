import json
import time
from dataclasses import dataclass
from typing import Optional

import requests

SERVER_URL = "http://127.0.0.1:1326"


@dataclass
class RecognizedCommand:
    text: str
    source: str


def send_voice_event(text: str, source: str = "manual") -> None:
    try:
        resp = requests.post(
            f"{SERVER_URL}/voice/event",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"text": text}),
            timeout=5.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"[{source}] -> server:", data.get("message"))
        else:
            print(f"[{source}] server error {resp.status_code}: {resp.text}")
    except Exception as exc:
        print(f"[{source}] failed to reach server: {exc}")


def recognize_with_whisper_api() -> Optional[RecognizedCommand]:
    return None


def recognize_with_windows_sapi() -> Optional[RecognizedCommand]:
    return None


def recognize_with_vosk() -> Optional[RecognizedCommand]:
    return None


def fallback_recognize() -> Optional[RecognizedCommand]:
    for recognizer in [
        recognize_with_whisper_api,
        recognize_with_windows_sapi,
        recognize_with_vosk,
    ]:
        cmd = recognizer()
        if cmd is not None:
            return cmd
    return None


def manual_loop() -> None:
    print("=== Bjorgsun Voice Daemon (manual test mode) ===")
    print("Type commands like:\n  you're grounded\n  unhush\n  always listen")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting voice daemon.")
            break

        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            print("Goodbye.")
            break

        send_voice_event(line, source="manual")
        time.sleep(0.1)


if __name__ == "__main__":
    manual_loop()
