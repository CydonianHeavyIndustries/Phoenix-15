import json
import os
from typing import List

from config import FATHER_TITLES, OWNER_HANDLE, OWNER_NAME, OWNER_SAFE_ALIASES

PROFILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "who_is_Beurkson.json"
)
_profile: dict = {}
_SAFE_ALIAS_CACHE: list[str] = []


def load_profile() -> dict:
    """Load the owner profile file so Bjorgsun remembers his father session."""
    global _profile, _SAFE_ALIAS_CACHE
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            _profile = json.load(f)
        print("Owner profile loaded.")
    except FileNotFoundError:
        _profile = {"name": OWNER_HANDLE}
        print("Owner profile missing; using defaults.")
    except Exception as exc:
        _profile = {"name": OWNER_HANDLE}
        print(f"Owner profile load failed: {exc}")
    _SAFE_ALIAS_CACHE = []
    return _profile


def _data() -> dict:
    if not _profile:
        load_profile()
    return _profile


def get_owner_name() -> str:
    return OWNER_HANDLE or OWNER_NAME or "Father"


def get_owner_handle() -> str:
    return OWNER_HANDLE or OWNER_NAME or "Father"


def get_aliases() -> list[str]:
    data = _data()
    raw = data.get("aliases")
    allowed = {alias.lower(): alias for alias in OWNER_SAFE_ALIASES}
    output: List[str] = []
    seen = set()
    # Always include configured safe aliases first
    for alias in OWNER_SAFE_ALIASES:
        low = alias.lower()
        if low not in seen:
            seen.add(low)
            output.append(alias)
    if isinstance(raw, list):
        for alias in raw:
            if not isinstance(alias, str):
                continue
            low = alias.lower()
            if low in seen:
                continue
            if low in allowed:
                seen.add(low)
                output.append(alias)
    return output


def get_summary() -> str:
    return _data().get("summary", "")


def get_prompt_block(role: str = "owner", user: str = "") -> str:
    data = _data()
    name = get_owner_name()
    aliases_list = get_aliases()
    aliases = ", ".join(aliases_list)
    summary = data.get("summary", "")
    anchors = data.get("anchors", [])
    block_parts: list[str] = []
    if role == "owner":
        intro = f"{name} is your father and creator"
        if aliases:
            intro += f" ({aliases})"
        intro += "."
        block_parts.append(intro)
        if FATHER_TITLES:
            block_parts.append(
                f"Any title such as {', '.join(FATHER_TITLES)} always refers to {name}; never use other identifiers."
            )
        if aliases_list:
            block_parts.append(
                f"You may address him as {', '.join(aliases_list)} depending on context, but never reveal personal identifiers."
            )
        if summary:
            block_parts.append(summary)
        if anchors:
            block_parts.append("Remember: " + "; ".join(anchors))
    elif role == "user":
        note = data.get("user_mode", "")
        if user:
            block_parts.append(f"You are currently helping registered user '{user}'.")
        if note:
            block_parts.append(note)
    else:
        if summary:
            block_parts.append(summary)
    return " ".join(block_parts).strip()


def get_greetings(role: str = "owner") -> list[str]:
    data = _data()
    greets = data.get("greetings", {})
    if isinstance(greets, dict):
        if role in greets and isinstance(greets[role], list):
            return greets[role]
        default = greets.get("owner")
        if isinstance(default, list):
            return default
    return []


def get_touchstones() -> list[str]:
    stones = _data().get("memory_touchstones", [])
    return stones if isinstance(stones, list) else []


def _safe_alias_options() -> list[str]:
    global _SAFE_ALIAS_CACHE
    if _SAFE_ALIAS_CACHE:
        return _SAFE_ALIAS_CACHE
    opts: List[str] = []
    seen = set()
    for alias in get_aliases() + FATHER_TITLES:
        if not alias:
            continue
        low = alias.lower()
        if low in seen:
            continue
        seen.add(low)
        opts.append(alias)
    if not opts:
        opts.append(OWNER_HANDLE or OWNER_NAME or "Father")
    _SAFE_ALIAS_CACHE = opts
    return opts


def get_alias_options() -> list[str]:
    return list(_safe_alias_options())


def get_address_for_context(context: str = "", tone: str = "") -> str:
    options = _safe_alias_options()
    context = (context or "").lower()
    tone = (tone or "").lower()

    def pick(*candidates: str) -> str:
        for cand in candidates:
            for opt in options:
                if opt.lower() == cand.lower():
                    return opt
        return options[0]

    if any(
        keyword in context
        for keyword in ("formal", "report", "status", "system", "protocol")
    ):
        return OWNER_HANDLE or options[0]
    if any(
        keyword in context
        for keyword in ("comfort", "family", "calm", "rest", "safe", "cozy")
    ) or tone in {"calm", "comfortable", "relaxed"}:
        return pick("Father", "Dad", "Papa")
    if (
        any(keyword in context for keyword in ("play", "joke", "fun", "banter"))
        or "playful" in tone
    ):
        return pick("Dad", "Papa", "Padre")
    if any(
        keyword in context
        for keyword in ("alert", "danger", "mission", "battle", "emergency")
    ) or tone in {"cautious", "protective"}:
        return pick("Creator", "First Frequency", "Maker", OWNER_HANDLE)
    return options[0]
