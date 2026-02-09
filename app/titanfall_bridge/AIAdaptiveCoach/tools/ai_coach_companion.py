#!/usr/bin/env python3
"""
AI Adaptive Coach companion.
- Watches the latest Northstar nslog for lines starting with [AI_COACH_TELEMETRY]{...}
- Sends the payload to OpenAI (if OPENAI_API_KEY is set) and writes advice/bot tuning JSON.

Requirements: pip install openai python-dotenv
Usage: OPENAI_API_KEY=sk-... python ai_coach_companion.py
"""

import json
import os
import re
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda *args, **kwargs: None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import tkinter as tk
    from tkinter import simpledialog, messagebox
except ImportError:
    tk = None


LOG_DIR = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Titanfall2\R2Northstar\logs")
OUT_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "TF2AI"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ADVICE_FILE = OUT_DIR / "advice.json"
BOT_FILE = OUT_DIR / "bot_tuning.json"
ENV_FILE = Path(__file__).resolve().parent / ".env"
MARKER = "[AI_COACH_TELEMETRY]"


def find_latest_log():
    logs = sorted(LOG_DIR.glob("nslog*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def stream_lines(path, seek_end=True):
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        if seek_end:
            f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            yield line.strip()


def call_openai(api_key, telemetry):
    if OpenAI is None:
        print("openai package not installed; skipping API call.")
        return None
    client = OpenAI(api_key=api_key)
    prompt = f"""You are a Titanfall 2 pilot coach. Given telemetry JSON, return a short JSON with:
- "advice": 3 concise tips.
- "bot_tuning": dict of numeric weights for aggression (0-1), evasiveness (0-1), and range_preference ("close"|"mid"|"long"). Keep it minimal.

Telemetry: {json.dumps(telemetry)}
Return ONLY JSON."""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a concise coach; respond only with JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print("Failed to parse OpenAI response:", content)
        return None


def prompt_for_key():
    if tk is None:
        return None
    root = tk.Tk()
    root.withdraw()
    key = simpledialog.askstring(
        "AI Coach",
        "Enter your OpenAI API key (saved locally, used only by this companion):",
        show="*",
        parent=root,
    )
    if key:
        try:
            ENV_FILE.write_text(f"OPENAI_API_KEY={key.strip()}\n", encoding="utf-8")
            messagebox.showinfo("AI Coach", "API key saved. You won't be prompted again.")
        except Exception as e:
            messagebox.showerror("AI Coach", f"Failed to save key: {e}")
    root.destroy()
    return key


def load_api_key():
    # Load from .env next to the script
    load_dotenv(ENV_FILE)
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    # If no key and tkinter is available, prompt once and save to .env
    return prompt_for_key()


def main():
    api_key = load_api_key()
    if api_key:
        print("OpenAI key detected. Coach responses will be generated.")
    else:
        print("No OPENAI_API_KEY set. Telemetry will be logged only.")

    latest = find_latest_log()
    if not latest:
        print("No Northstar logs found. Start the game once, then rerun.")
        return
    print(f"Watching log: {latest}")

    for line in stream_lines(latest, seek_end=True):
        if MARKER not in line:
            continue
        m = re.search(r"\[AI_COACH_TELEMETRY\](\{.*\})", line)
        if not m:
            continue
        raw = m.group(1)
        try:
            telemetry = json.loads(raw)
        except json.JSONDecodeError:
            print("Bad telemetry JSON:", raw)
            continue

        print("Telemetry:", telemetry)
        advice = None
        if api_key:
            advice = call_openai(api_key, telemetry)
        if advice:
            ADVICE_FILE.write_text(json.dumps(advice, indent=2), encoding="utf-8")
            if "bot_tuning" in advice:
                BOT_FILE.write_text(json.dumps(advice["bot_tuning"], indent=2), encoding="utf-8")
            print("Wrote advice to", ADVICE_FILE)
        else:
            # Drop a placeholder so the UI has something to read.
            placeholder = {
                "advice": [
                    "Keep moving: slide-hop and wallrun to reduce deaths.",
                    "Use cover and pre-aim common angles on " + telemetry.get("map", "the map"),
                    "Focus on one weapon to improve accuracy this match."
                ],
                "bot_tuning": {
                    "aggression": 0.5,
                    "evasiveness": 0.5,
                    "range_preference": "mid"
                }
            }
            ADVICE_FILE.write_text(json.dumps(placeholder, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
