"""
Titanfall / Northstar AI coach bridge

Watches nslog for `[AI_COACH_TELEMETRY]{...}` lines, posts telemetry to the local
coach endpoint, and writes the returned tip to an outbox file for the mod.

Defaults:
  - Log file:  C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2\\R2Northstar\\nslog.txt
  - Outbox:    C:\\Program Files (x86)\\Steam\\steamapps\\common\\Titanfall2\\R2Northstar\\mods\\AIAdaptiveCoach\\tools\\coach_reply.txt
  - Endpoint:  http://127.0.0.1:1326/tf2/coach

Run: python bridge.py
Stop: Ctrl+C
"""
import json
import os
import re
import sys
import time
import requests
from pathlib import Path

# Configuration (override via env if needed)
LOG_PATH = Path(
    os.getenv(
        "TF2_NSLOG",
        r"C:\Program Files (x86)\Steam\steamapps\common\Titanfall2\R2Northstar\nslog.txt",
    )
)
OUTBOX_PATH = Path(
    os.getenv(
        "TF2_COACH_OUTBOX",
        r"C:\Program Files (x86)\Steam\steamapps\common\Titanfall2\R2Northstar\mods\AIAdaptiveCoach\tools\coach_reply.txt",
    )
)
COACH_ENDPOINT = os.getenv("TF2_COACH_ENDPOINT", "http://127.0.0.1:1326/tf2/coach")
POLL_INTERVAL = float(os.getenv("TF2_COACH_POLL_SEC", "1.0"))
LOG_MARKER = "[AI_COACH_TELEMETRY]"

LOGFILE = Path(__file__).resolve().parent.parent / "logs" / "bridge_titanfall.log"
LOGFILE.parent.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line)
    try:
        with LOGFILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def tail_lines(path: Path, offset: int) -> tuple[list[str], int]:
    if not path.exists():
        return [], offset
    size = path.stat().st_size
    if offset > size:
        offset = 0
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        f.seek(offset)
        lines = f.readlines()
        new_offset = f.tell()
    return lines, new_offset


def parse_telemetry(line: str) -> dict | None:
    if LOG_MARKER not in line:
        return None
    try:
        _, json_part = line.split(LOG_MARKER, 1)
        return json.loads(json_part.strip())
    except Exception:
        return None


def post_coach(payload: dict) -> str | None:
    try:
        resp = requests.post(COACH_ENDPOINT, json=payload, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("tip") or data.get("result") or data.get("reply")
        log(f"Coach endpoint error {resp.status_code}: {resp.text[:200]}")
    except Exception as exc:
        log(f"Coach request failed: {exc}")
    return None


def write_outbox(tip: str) -> None:
    try:
        OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTBOX_PATH.write_text(tip, encoding="utf-8")
        log(f"Wrote tip to outbox: {tip}")
    except Exception as exc:
        log(f"Failed to write outbox: {exc}")


def main():
    log(f"Bridge starting. Log={LOG_PATH} Outbox={OUTBOX_PATH} Endpoint={COACH_ENDPOINT}")
    offset = 0
    while True:
        try:
            lines, offset = tail_lines(LOG_PATH, offset)
            for line in lines:
                telem = parse_telemetry(line)
                if telem:
                    tip = post_coach(telem)
                    if tip:
                        write_outbox(tip)
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            log("Bridge stopped by user.")
            break
        except Exception as exc:
            log(f"Loop error: {exc}")
            time.sleep(1.0)


if __name__ == "__main__":
    main()
