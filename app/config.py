"""
Lightweight config shims for Bjorgsun-26.

Reads settings from environment variables (.env is already loaded by runtime/startup).
Provides defaults to avoid import errors when a value is missing.
"""

import os
from typing import List


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key, "")
    if not val:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(key: str) -> List[str]:
    val = os.getenv(key, "")
    if not val:
        return []
    return [item.strip() for item in val.split(",") if item.strip()]


# Core identity/owner
OWNER_NAME = _env("OWNER_NAME", "Owner")
OWNER_HANDLE = _env("OWNER_HANDLE", "owner")
OWNER_LAST_CODE = _env("OWNER_LAST_CODE", "")
OWNER_SAFE_ALIASES = _env_list("OWNER_SAFE_ALIASES")
FATHER_TITLES = _env_list("FATHER_TITLES")

# Auth / hotkeys
HOTKEY_PTT = _env("HOTKEY_PTT", "f9")
PRIVATE_MODE = _env_bool("PRIVATE_MODE", False)

# USB / activation
BJORGSUN_REQUIRE_USB = _env_bool("BJORGSUN_REQUIRE_USB", False)
BJORGSUN_USB_LABEL = _env("BJORGSUN_USB_LABEL", "USBMK")
BJORGSUN_USB_SENTINEL = _env("BJORGSUN_USB_SENTINEL", "")
OFFLINE_MODE = _env_bool("OFFLINE_MODE", False)

# Discord
DISCORD_BOT_TOKEN = _env("DISCORD_TOKEN", "")
DISCORD_ALLOWED_GUILD_IDS = _env_list("DISCORD_ALLOWED_GUILD_IDS")
DISCORD_GROUNDED = _env_bool("DISCORD_GROUNDED", False)
DISCORD_GUILD_ID = _env("DISCORD_GUILD_ID", "")
DISCORD_OWNER_ID = _env("DISCORD_OWNER_ID", "")
DISCORD_TEXT_CHANNEL_ID = _env("DISCORD_TEXT_CHANNEL_ID", "")
DISCORD_VOICE_CHANNEL_ID = _env("DISCORD_VOICE_CHANNEL_ID", "")

# Audio / video
FFMPEG_PATH = _env("FFMPEG_PATH", "ffmpeg")

# Titanfall / gaming defaults
GAME_KEY_MODE = _env("GAME_KEY_MODE", "owner")
GAME_MODE_ENABLED = _env_bool("GAME_MODE_ENABLED", False)
TITANFALL2_ENABLED = _env_bool("TITANFALL2_ENABLED", False)
TITANFALL2_CALLSIGN = _env("TITANFALL2_CALLSIGN", "")
TITANFALL2_AUTOVOICE = _env_bool("TITANFALL2_AUTOVOICE", False)
TITANFALL2_AUTOPILOT = _env_bool("TITANFALL2_AUTOPILOT", False)
TITANFALL2_LOG_PATH = _env("TITANFALL2_LOG_PATH", "")
TITANFALL2_TELEMETRY_FILE = _env("TITANFALL2_TELEMETRY_FILE", "")
TITANFALL2_COMMAND_FILE = _env("TITANFALL2_COMMAND_FILE", "")
# Discord integration IDs (set in .env for auto-join/callouts)
TITANFALL2_DISCORD_CHANNEL_ID = _env("TITANFALL2_DISCORD_CHANNEL_ID", "")
TITANFALL2_BRIEFING_CHANNEL_ID = _env("TITANFALL2_BRIEFING_CHANNEL_ID", "")
TITANFALL2_REPORT_CHANNEL_ID = _env("TITANFALL2_REPORT_CHANNEL_ID", "")
TITANFALL2_IDLE_CHANNEL_ID = _env("TITANFALL2_IDLE_CHANNEL_ID", "")

# Overlay / VR defaults
VR_OVERLAY_ENABLED = _env_bool("VR_OVERLAY_ENABLED", False)
VR_OVERLAY_PORT = int(_env("VR_OVERLAY_PORT", "0") or 0)

# Defaults for any missing attributes
def __getattr__(name: str):
    # Return env value if present, else empty string/False
    val = os.getenv(name)
    if val is not None:
        return val
    return ""
# Voice defaults
VOICE_RATE = float(_env("VOICE_RATE", "1.0") or 1.0)
VOICE_PITCH = float(_env("VOICE_PITCH", "0.0") or 0.0)
TTS_VOICE = _env("TTS_VOICE", "alloy")

# Local model defaults
OLLAMA_MODEL = _env("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_MODEL_CHAT = _env("OLLAMA_MODEL_CHAT", OLLAMA_MODEL)

# OpenAI models (defaults can be overridden via .env)
OPENAI_MODEL_CHAT = _env("OPENAI_MODEL_CHAT", "gpt-4.1")
OPENAI_MODEL_TTS = _env("OPENAI_MODEL_TTS", "tts-1")
OPENAI_SEARCH_MODEL = _env("OPENAI_SEARCH_MODEL", "gpt-5.1")
SAFETY_WEBHOOK = _env("SAFETY_WEBHOOK", "")
