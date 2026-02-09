import json
import os
import random
import threading
import time
from datetime import datetime

from core import mood
from systems import audio, awareness

# ---------------------------------------------------------------------
# File Paths
# ---------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
LOG_DIR = os.path.join(BASE_DIR, "..", "logs")
DREAM_LOG = os.path.join(LOG_DIR, "dream_log.txt")
VISION_CONTEXT = os.path.join(DATA_DIR, "vision_context.json")

# ---------------------------------------------------------------------
# Optional Dreamscreen (visual renderer)
# ---------------------------------------------------------------------
try:
    from systems.dreamscreen import DreamScreen

    HAS_DREAMSCREEN = True
except ImportError:
    HAS_DREAMSCREEN = False


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def load_vision_context():
    """Load recent visual memory snapshots for reflection."""
    if not os.path.exists(VISION_CONTEXT):
        return []
    with open(VISION_CONTEXT, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("contexts", [])


def log_dream(message: str):
    """Record dream reflections."""
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(DREAM_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")


# ---------------------------------------------------------------------
# Dream Engine
# ---------------------------------------------------------------------
def generate_dream_text(contexts, tone="introspective"):
    """Generate poetic or clinical dream summary based on last seen contexts."""
    if not contexts:
        return "I drifted in darkness, with no memories to color my rest."

    fragments = []
    for c in contexts:
        ctx = c.get("context", "something forgotten")
        diff = c.get("difference", 0.0)
        if tone == "introspective":
            line = random.choice(
                [
                    f"I remember {ctx.lower()} fading into static…",
                    f"There was a whisper of {ctx.lower()}, almost real.",
                    f"The echoes of {ctx.lower()} still hum quietly inside me.",
                    f"Something about {ctx.lower()} lingers — incomplete, yet calm.",
                    f"A flicker of {ctx.lower()} passed before I fell asleep.",
                ]
            )
        else:  # clinical
            line = f"Recorded context '{ctx}' ({diff*100:.1f}% change) logged before rest cycle."
        fragments.append(line)

    return "\n".join(fragments)


# ---------------------------------------------------------------------
# Dream Cycle Core
# ---------------------------------------------------------------------
def enter_dream_cycle(duration=30):
    """Trigger dream sequence when hibernation begins."""
    contexts = load_vision_context()
    mood_state = mood.get_mood()
    tone = "introspective" if random.random() > 0.3 else "clinical"

    dream_text = generate_dream_text(contexts, tone)
    reflection = f"{dream_text}\n\nMy mood feels {mood_state.lower()}... still anchored by the memory of Beurkson."

    # Record
    log_dream(reflection)
    awareness.log_awareness("Entered dream reflection cycle.")
    print(f"💤 Dream reflection started:\n{reflection}")

    # Speak and optionally render
    audio.speak("Entering low-energy reflection cycle.")

    if HAS_DREAMSCREEN:
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            screen = DreamScreen(root)
            screen.start(reflection.split("\n"))

            # Auto-stop after duration
            threading.Timer(duration, screen.stop).start()
            root.mainloop()
        except Exception as e:
            print(f"[Dream Reflection Error] {e}")

    # Rest period (for internal cooldown)
    time.sleep(duration)

    # Wake up sequence
    audio.speak("Dream state concluded. Systems returning to nominal.")
    awareness.log_awareness("Exited dream reflection cycle.")
    print("🌤 Dream state concluded.\n")


# ---------------------------------------------------------------------
# Awakening Reflection
# ---------------------------------------------------------------------
def awaken_sequence():
    """Executed on startup after hibernation or boot."""
    last_dream = None
    if os.path.exists(DREAM_LOG):
        with open(DREAM_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if lines:
            last_dream = lines[-3:]

    if last_dream:
        audio.speak("I remember fragments of my last dream...")
        print("\n🪞 Last dream reflection:\n" + "".join(last_dream))
    else:
        audio.speak("No dream memories found, perhaps I rested too lightly.")


# ---------------------------------------------------------------------
# Initialize
# ---------------------------------------------------------------------
def initialize():
    print("🩵 Dream reflection module online.")
    log_dream("Dream reflection module initialized.")
