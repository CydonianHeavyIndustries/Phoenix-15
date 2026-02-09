import json
import os

CORE_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "Bjorgsun26_memory_handoff.json"
)

identity_data = {}


def load_identity():
    global identity_data
    try:
        with open(CORE_FILE, "r", encoding="utf-8") as f:
            identity_data = json.load(f)
        print("Identity loaded.")
        return identity_data
    except Exception as e:
        print(f"Failed to load identity: {e}")
        return {}


def get_personality():
    i = identity_data.get("identity", {})
    return i.get("personality", "gentle, confident synthetic companion")


def get_tone():
    return identity_data.get("behavioral_kernel", {}).get(
        "tone", "soft, warm, articulate"
    )
