import json
import os
import random
from datetime import datetime

DEFAULT_MOOD = "comfortable"
COMFORT_MOODS = ["comfortable", "calm", "relaxed", "acceptance", "content"]

MOOD_TONES = {
    "forgiveness": "supportive",
    "guilt": "shadow",
    "acceptance": "comfort",
    "pride": "protective",
    "joy": "positive",
    "happiness": "positive",
    "fun": "playful",
    "glee": "playful",
    "sadness": "shadow",
    "confused": "curious",
    "overwhelmed": "cautious",
    "calm": "comfort",
    "relaxed": "comfort",
    "comfortable": "comfort",
    "supportive": "supportive",
    "wonder": "curious",
    "curiosity": "curious",
    "protective": "protective",
    "playful": "playful",
    "cautious": "cautious",
    "embarrassed": "shadow",
    "anger": "shadow",
    "fear": "cautious",
    "disgust": "shadow",
    "envy": "shadow",
    "shame": "shadow",
    "awe": "curious",
    "love": "supportive",
    "adoration": "supportive",
    "disappointed": "shadow",
    "admiration": "positive",
    "gratitude": "positive",
    "grateful": "positive",
    "boredom": "cautious",
    "amusement": "playful",
    "surprise": "curious",
    "awkward": "shadow",
    "empathy": "supportive",
    "self-regulation": "comfort",
    "motivation": "positive",
    "determination": "protective",
    "respect": "supportive",
    "understanding": "supportive",
    "touched": "supportive",
    "glad": "positive",
    "worry": "cautious",
    "remorse": "shadow",
    "comfortable": "comfort",
    "content": "comfort",
}
MOOD_SET = set(MOOD_TONES.keys())
TONE_TARGETS = {
    "positive": 0.72,
    "playful": 0.70,
    "supportive": 0.66,
    "curious": 0.62,
    "protective": 0.58,
    "comfort": 0.52,
    "cautious": 0.46,
    "shadow": 0.30,
}
TONE_WILLINGNESS = {
    "positive": 0.85,
    "playful": 0.82,
    "supportive": 0.80,
    "curious": 0.75,
    "protective": 0.72,
    "comfort": 0.95,
    "cautious": 0.65,
    "shadow": 0.40,
}
MOOD_ALIASES = {
    "bright": "joy",
    "soft": "calm",
    "focused": "protective",
    "focus": "protective",
    "neutral": "comfortable",
    "alert": "cautious",
    "thinking": "confused",
    "serious": "protective",
    "comfort": "comfortable",
    "comforted": "comfortable",
    "comforting": "comfortable",
    "calmness": "calm",
    "comfy": "comfortable",
    "contentment": "content",
    "restful": "relaxed",
    "ease": "comfortable",
    "wonderment": "wonder",
    "wonder/awe": "awe",
    "wondering": "curiosity",
    "enjoyment": "happiness",
    "confusion": "confused",
    "awkwardness": "awkward",
    "embarrassment": "embarrassed",
    "embarassment": "embarrassed",
    "embarassed": "embarrassed",
    "embarassing": "embarrassed",
    "playfule": "playful",
    "playfulness": "playful",
    "curious": "curiosity",
    "gladness": "glad",
    "heartfelt": "touched",
    "worried": "worry",
    "concerned": "worry",
    "regret": "remorse",
    "thankful": "grateful",
    "appreciative": "gratitude",
    "motivated": "motivation",
    "determined": "determination",
    "respectful": "respect",
    "self regulation": "self-regulation",
    "selfcontrol": "self-regulation",
    "self control": "self-regulation",
    "understood": "understanding",
    "understand": "understanding",
}
MOOD_EMOJI = {
    "forgiveness": "🤝",
    "guilt": "🥺",
    "acceptance": "🌱",
    "pride": "🛡️",
    "joy": "✨",
    "happiness": "😊",
    "fun": "🎉",
    "glee": "😆",
    "sadness": "🌧️",
    "confused": "❓",
    "overwhelmed": "⚡",
    "calm": "🌊",
    "relaxed": "🌤️",
    "comfortable": "🛋️",
    "content": "🫧",
    "supportive": "🫶",
    "wonder": "🌌",
    "curiosity": "🧐",
    "protective": "🛡️",
    "playful": "🤸",
    "cautious": "⚠️",
    "embarrassed": "🙈",
    "anger": "🔥",
    "fear": "😨",
    "disgust": "🤢",
    "envy": "😒",
    "shame": "😳",
    "awe": "🌠",
    "love": "💖",
    "adoration": "🥰",
    "disappointed": "😞",
    "admiration": "🌟",
    "gratitude": "🙏",
    "boredom": "😐",
    "amusement": "😄",
    "surprise": "😯",
    "awkward": "😅",
    "empathy": "🤍",
    "self-regulation": "🧘",
    "motivation": "🚀",
    "determination": "🎯",
    "respect": "🙇",
    "understanding": "🧠",
    "touched": "💗",
    "glad": "😄",
    "worry": "😟",
    "remorse": "😔",
    "grateful": "🤲",
}

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
CATALOG_PATH = os.path.join(DATA_DIR, "emotions_catalog.md")
MISSING_PATH = os.path.join(DATA_DIR, "mood_missing.json")


def _normalize_mood(label: str | None) -> str:
    if not label:
        return DEFAULT_MOOD
    low = label.strip().lower()
    if not low:
        return DEFAULT_MOOD
    mapped = MOOD_ALIASES.get(low, low)
    if mapped in MOOD_SET:
        return mapped
    _record_missing_emotion(low)
    return DEFAULT_MOOD


mood_state = {"current": DEFAULT_MOOD, "intensity": 0.5}


def _comfort_choice() -> str:
    return random.choice(COMFORT_MOODS)


def adjust_mood(context: str = DEFAULT_MOOD, allow_choice: bool = True):
    """Gently lean toward a mood while keeping a comfort zone."""
    label = _normalize_mood(context)
    tone = MOOD_TONES.get(label, "comfort")
    if allow_choice:
        willingness = TONE_WILLINGNESS.get(tone, 0.7)
        if random.random() > willingness:
            label = _comfort_choice()
            tone = MOOD_TONES.get(label, "comfort")
    target = TONE_TARGETS.get(tone, 0.5)
    variance = 0.06 if tone == "shadow" else 0.05
    jitter = random.uniform(-variance, variance)
    desired = max(0.05, min(1.0, target + jitter))
    prior = mood_state.get("intensity", desired)
    mood_state["intensity"] = round((prior * 0.5) + (desired * 0.5), 3)
    mood_state["current"] = label
    return dict(mood_state)


def get_mood():
    """Return the current mood label."""
    return mood_state.get("current", DEFAULT_MOOD)


def get_mood_intensity() -> float:
    return float(mood_state.get("intensity", 0.5))


def get_mood_tone(label: str | None = None) -> str:
    tag = label or get_mood() or DEFAULT_MOOD
    return MOOD_TONES.get(tag, "comfort")


def get_mood_indicator():
    current = get_mood()
    bar = int(mood_state["intensity"] * 10)
    emoji = MOOD_EMOJI.get(current, "💫")
    label = current.upper() if isinstance(current, str) else "NEUTRAL"
    return f"{emoji} {label} [{'█'*bar}{' '*(10-bar)}]"


def get_emotion_catalog() -> list[str]:
    return sorted(MOOD_SET)


def _write_emotion_catalog():
    try:
        os.makedirs(os.path.dirname(CATALOG_PATH), exist_ok=True)
        listing = "\n".join(f"- {name}" for name in sorted(MOOD_SET))
        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            f.write("# Emotion Catalog\n\n")
            f.write("Current palette Bjorgsun can lean on:\n\n")
            f.write(listing + "\n")
    except Exception:
        pass


def _load_missing_emotions() -> list[dict]:
    try:
        with open(MISSING_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_missing_emotions(entries: list[dict]):
    try:
        os.makedirs(os.path.dirname(MISSING_PATH), exist_ok=True)
        with open(MISSING_PATH, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _record_missing_emotion(label: str):
    if not label:
        return
    entries = _load_missing_emotions()
    low = label.strip().lower()
    if any(item.get("label") == low for item in entries):
        return
    entries.append(
        {
            "label": low,
            "first_seen": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
    )
    _save_missing_emotions(entries)


def get_missing_emotions() -> list[str]:
    return [
        item.get("label", "") for item in _load_missing_emotions() if item.get("label")
    ]


def clear_missing_emotion(label: str):
    if not label:
        return
    low = label.strip().lower()
    entries = [item for item in _load_missing_emotions() if item.get("label") != low]
    _save_missing_emotions(entries)


_write_emotion_catalog()
