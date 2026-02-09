import asyncio

import keyboard

from config import HOTKEY_PTT
from core import memory, mood
from systems import audio, stt


def main_loop():
    print("Commands: /shutdown /voice /vision /help")
    try:
        label = {
            "num0+numenter": "Numpad0 + NumpadEnter",
            "right+numenter": "Right Arrow + Numpad Enter",
            "mouse4": "Mouse Button 4",
            "mouse5": "Mouse Button 5",
            "mouse45": "Mouse Buttons 4+5",
        }.get((HOTKEY_PTT or "ctrl+space").lower(), "Ctrl + Space")
        print(f"Hotkey: Hold {label} to talk.")
    except Exception:
        print("Hotkey: Hold Ctrl + Space to talk.")
    while True:
        if stt._ptt_down():
            wav = stt.record()
            text = stt.transcribe(wav)
            memory.log_conversation("user", text)
            response = audio.think(text)
            audio.speak(response)
        else:
            msg = input("> ").strip()
            if msg.lower() in ("/quit", "/shutdown"):
                print("Shutting down.")
                break
            memory.log_conversation("user", msg)
            response = audio.think(msg)
            audio.speak(response)
