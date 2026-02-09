"""
Lightweight CLI setup wizard for Bjorgsun-26.
- Prefills from existing .env if present.
- Writes .env and install_choices.json in the current directory.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

ENV_PATH = Path(".env")
CHOICES_PATH = Path("install_choices.json")

# Keys to collect (keep in sync with runtime needs)
ENV_KEYS = [
    "OPENAI_API_KEY",
    "LLM_API_KEY",
    "LLM_ENDPOINT",
    "DISCORD_TOKEN",
    "TITANFALL2_LOG_PATH",
    "TITANFALL2_TELEMETRY_FILE",
    "DEV_ACCESS_KEY",
    "FATHER_KEY",
    "OWNER_KEY",
    "CORPORATE_KEY",
    "ENTERPRISE_KEY",
    "LEGAL_KEY",
    "FRIEND_KEY",
    "FAMILY_KEY",
    "USER_KEY",
    "SPARK_KEY",
    "USBMK_KEY",
    "FADER_KEY",
    "BJORGSUN_KEY",
    "MOM_KEY",
    "DAD_KEY",
    "MAMMOUTH_KEY",
    "ZACK_KEY",
    "JACK_KEY",
    "SPAULDO_KEY",
    "JOHN_KEY",
    "JEAN_KEY",
    "BEURKSON_KEY",
    "BJORGSON_KEY",
    "CLARA_KEY",
    "CHARLOTTE_KEY",
    "GUILLAUME_KEY",
    "YAN_KEY",
    "RESTSWITCH_FILE",
    "FADER_USB_LABEL",
    "FADER_SENTINEL_FILE",
    "PEER_COORDINATOR_URL",
    "PEER_TOKEN",
    "OPENAI_SEARCH_MODEL",
    "DISCORD_ALERT_WEBHOOK",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASS",
    "ALERT_EMAILS",
    "SMS_ENABLED",
    "TWILIO_SID",
    "TWILIO_TOKEN",
    "SMS_FROM",
    "SMS_TO",
]


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    return values


def prompt_yes_no_later(prompt: str, default: str = "later") -> str:
    raw = input(f"{prompt} [yes/no/later] ").strip().lower()
    if raw in {"yes", "no", "later"}:
        return raw
    return default


def prompt_with_default(key: str, default: str) -> str:
    val = input(f"{key} [{default}]: ").strip()
    return val or default


def main():
    print("=== Bjorgsun setup wizard (CLI) ===")
    existing = load_env(ENV_PATH)

    choices = {
        "launchers": "both",
        "tablet": prompt_yes_no_later("Set up tablet module?"),
        "gpt": prompt_yes_no_later("Set up GPT/LLM services?"),
        "ios": prompt_yes_no_later("Set up iOS/mobile mode?"),
        "env_choice": "yes",
    }

    # Defaults for some fields
    defaults = {
        "RESTSWITCH_FILE": r"E:\restswitch.key",
        "FADER_USB_LABEL": "Fader",
        "FADER_SENTINEL_FILE": r"E:\Fader\summon.key",
        "OPENAI_SEARCH_MODEL": existing.get("OPENAI_SEARCH_MODEL", "gpt-4o-mini"),
    }

    env_entries: dict[str, str] = {}
    for key in ENV_KEYS:
        prefill = existing.get(key, defaults.get(key, ""))
        env_entries[key] = prompt_with_default(key, prefill)

    # Auto-generate secrets if blank
    if not env_entries.get("DEV_ACCESS_KEY"):
        env_entries["DEV_ACCESS_KEY"] = secrets.token_urlsafe(16)
    for role in [
        "FATHER_KEY",
        "OWNER_KEY",
        "CORPORATE_KEY",
        "ENTERPRISE_KEY",
        "LEGAL_KEY",
        "FRIEND_KEY",
        "FAMILY_KEY",
        "USER_KEY",
        "SPARK_KEY",
        "USBMK_KEY",
        "FADER_KEY",
        "BJORGSUN_KEY",
        "MOM_KEY",
        "DAD_KEY",
        "MAMMOUTH_KEY",
        "ZACK_KEY",
        "JACK_KEY",
        "SPAULDO_KEY",
        "JOHN_KEY",
        "JEAN_KEY",
        "BEURKSON_KEY",
        "BJORGSON_KEY",
        "CLARA_KEY",
        "CHARLOTTE_KEY",
        "GUILLAUME_KEY",
        "YAN_KEY",
        "PEER_TOKEN",
    ]:
        if not env_entries.get(role):
            env_entries[role] = secrets.token_urlsafe(24)

    ENV_PATH.write_text(
        "\n".join(f"{k}={v}" for k, v in env_entries.items()) + "\n", encoding="utf-8"
    )
    CHOICES_PATH.write_text(json.dumps(choices, indent=2), encoding="utf-8")

    print("[✓] .env written.")
    print(f"[i] Location: {ENV_PATH.resolve()}")
    print("[✓] Choices written to install_choices.json")
    input("Press Enter to continue...")


if __name__ == "__main__":
    main()

