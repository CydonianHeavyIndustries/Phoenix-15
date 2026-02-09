# --- Bjorgsun Memory Boot Utility ---
# Author: Jean-Sébastien Céré & GPT-5
# Purpose: Initialize memory from fallback if none exists.

import gzip
import json
import os
import shutil

FALLBACK = "memory_fallback.json.gz"
MEMORY = "memory.json"


def initialize_memory():
    if os.path.exists(MEMORY):
        print(f"✅ Found existing {MEMORY}. No action needed.")
        return

    if not os.path.exists(FALLBACK):
        print(f"⚠️ No fallback file found: {FALLBACK}")
        return

    try:
        with gzip.open(FALLBACK, "rt", encoding="utf-8") as f:
            data = json.load(f)

        with open(MEMORY, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"🧠 Memory initialized from {FALLBACK} → {MEMORY}")
    except Exception as e:
        print(f"❌ Failed to initialize memory: {e}")


if __name__ == "__main__":
    initialize_memory()
