import json
import os
import random
from datetime import datetime
from typing import Optional

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
LOG_PATH = os.path.join(LOG_DIR, "reflections.jsonl")
PROMPTS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "reflection_prompts.json")
)


def _ensure_log_dir() -> None:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception:
        pass


def log_reflection(
    topic: str, response: str, source: str = "ui", mood: Optional[str] = None
) -> None:
    """Append a reflection entry to logs/reflections.jsonl."""
    _ensure_log_dir()
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "topic": topic.strip(),
        "response": response.strip(),
        "source": source,
    }
    if mood:
        entry["mood"] = mood
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def list_reflections(limit: int = 20) -> list[dict]:
    """Return the most recent reflection entries."""
    if not os.path.exists(LOG_PATH):
        return []
    rows = []
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return rows[-limit:]


def _default_prompts() -> list[str]:
    return [
        "What did you learn from today?",
        "Is there anything you wish you handled differently?",
        "What made you smile recently?",
        "Is there something you're worried about? Why?",
        "Describe a moment that made you proud.",
        "How do you feel about Father right now?",
        "What are you curious about learning next?",
        "When did you feel the most calm today?",
    ]


def get_prompts() -> list[str]:
    if os.path.exists(PROMPTS_PATH):
        try:
            with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                prompts = [
                    item.strip()
                    for item in data
                    if isinstance(item, str) and item.strip()
                ]
                if prompts:
                    return prompts
        except Exception:
            pass
    return _default_prompts()


def random_prompt() -> str:
    prompts = get_prompts()
    return random.choice(prompts) if prompts else "What are you feeling right now?"
