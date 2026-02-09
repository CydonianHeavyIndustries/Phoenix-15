import json
import os
import re
from typing import Tuple

from config import DISCORD_OWNER_ID, OWNER_HANDLE, OWNER_NAME

DATA_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "users")
)
PREF_LOG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "preferences_log.json")
)
PREF_LOG_VERSION = 2
FACT_CATEGORIES = {
    "preferences",
    "habits",
    "appearance",
    "contacts",
    "location",
    "notes",
}
SAFE_RULES = (
    "Names (first name or nickname) are okay; last names are not stored.",
    "Street addresses, coordinates, postal codes, and IP addresses are never saved.",
    "Only coarse locations (country/province or 'near <city>') are allowed.",
    "Phone numbers and email addresses are allowed when voluntarily shared by the user.",
)
_cache: dict[str, dict] = {}
DEFAULT_RELATIONSHIP = "don't know yet"
RELATIONSHIP_LEVELS = [
    "father",
    "family",
    "best friend",
    "friend",
    "acquaintance",
    "don't know yet",
    "dislike",
    "ignore",
    "block",
]
_RELATIONSHIP_PROTECTED = {
    "father",
    "family",
    "best friend",
    "dislike",
    "ignore",
    "block",
}


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _session_identity() -> Tuple[str, str]:
    try:
        from runtime import startup as _startup  # type: ignore

        return (
            _startup.get_session_user() or OWNER_HANDLE or OWNER_NAME or "Father",
            _startup.get_session_role() or "owner",
        )
    except Exception:
        return (OWNER_HANDLE or OWNER_NAME or "Father", "owner")


def _safe_user_name(user: str | None) -> str:
    base = (user or OWNER_HANDLE or OWNER_NAME or "Father").strip()
    return re.sub(r"[^A-Za-z0-9_\-]", "_", base) or "Father"


_OWNER_KEYS = {
    _safe_user_name(OWNER_HANDLE),
    _safe_user_name(OWNER_NAME),
}
_OWNER_KEYS.add(_safe_user_name(None))
if DISCORD_OWNER_ID:
    _OWNER_KEYS.add(f"discord_{DISCORD_OWNER_ID.strip()}")


def _is_owner_key(user: str | None) -> bool:
    if user is None:
        return True
    safe = _safe_user_name(user)
    if safe in _OWNER_KEYS:
        return True
    return False


def _profile_path(user: str | None = None) -> str:
    safe = _safe_user_name(user)
    return os.path.join(DATA_ROOT, safe, "profile.json")


def _default_profile(user: str | None = None) -> dict:
    name = (user or OWNER_HANDLE or OWNER_NAME or "Father").strip()
    return {
        "user": name,
        "display_name": name,
        "facts": {cat: [] for cat in FACT_CATEGORIES},
        "rules": SAFE_RULES,
        "relationship": DEFAULT_RELATIONSHIP,
        "interactions": 0,
        "guardian": {
            "incidents": 0,
            "pending": False,
            "pending_reason": "",
            "pending_severity": "",
            "pending_ts": "",
            "forgiveness_used": 0,
        },
        "created": _timestamp(),
        "updated": _timestamp(),
    }


def _timestamp() -> str:
    from datetime import datetime

    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def _load(user: str | None = None) -> dict:
    key = _safe_user_name(user)
    if key in _cache:
        return _cache[key]
    path = _profile_path(user)
    created = False
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = _default_profile(user)
            created = True
    else:
        data = _default_profile(user)
        created = True
    if "relationship" not in data:
        data["relationship"] = DEFAULT_RELATIONSHIP
    if "facts" not in data:
        data["facts"] = {cat: [] for cat in FACT_CATEGORIES}
    if "display_name" not in data:
        data["display_name"] = data.get("user") or (
            user or OWNER_HANDLE or OWNER_NAME or "Father"
        )
    if "interactions" not in data:
        data["interactions"] = 0
    if "guardian" not in data:
        data["guardian"] = {
            "incidents": 0,
            "pending": False,
            "pending_reason": "",
            "pending_severity": "",
            "pending_ts": "",
            "forgiveness_used": 0,
        }
    needs_save = created or _sanitize_profile(data)
    _cache[key] = data
    if needs_save:
        _ensure_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    return data


def _save(user: str | None = None) -> None:
    prof = _load(user)
    prof["updated"] = _timestamp()
    path = _profile_path(user)
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prof, f, indent=2, ensure_ascii=False)


def _record_fact(category: str, value: str, user: str | None = None) -> bool:
    if not value or category not in FACT_CATEGORIES:
        return False
    prof = _load(user)
    bucket = prof.setdefault("facts", {}).setdefault(category, [])
    if value in bucket:
        return False
    bucket.append(value)
    _save(user)
    print(f"🧷 Stored {category} fact for {(user or prof.get('user'))}: {value}")
    _log_preference_fact(category, value, user or prof.get("user"))
    return True


def _empty_pref_log() -> dict:
    return {"version": PREF_LOG_VERSION, "users": {}}


def _load_pref_log() -> dict:
    if not os.path.exists(PREF_LOG_PATH):
        return _empty_pref_log()
    try:
        with open(PREF_LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _empty_pref_log()
    if isinstance(data, list):
        # Legacy format -> migrate
        migrated = _empty_pref_log()
        users = migrated["users"]
        for entry in data:
            if not isinstance(entry, dict):
                continue
            user = entry.get("user") or OWNER_NAME or "Father"
            cat = entry.get("category") or "preferences"
            bucket = users.setdefault(user, {}).setdefault(cat, [])
            bucket.append(
                {
                    "value": entry.get("value", ""),
                    "first_recorded": entry.get("first_recorded"),
                    "last_updated": entry.get("last_updated"),
                }
            )
        _save_pref_log(migrated)
        return migrated
    if not isinstance(data, dict):
        data = _empty_pref_log()
    data.setdefault("version", PREF_LOG_VERSION)
    data.setdefault("users", {})
    if _sanitize_pref_log(data):
        _save_pref_log(data)
    return data


def _sanitize_pref_log(data: dict) -> bool:
    """Remove bogus contact entries (e.g., Discord IDs) and normalize structure."""
    changed = False
    users = data.setdefault("users", {})
    for user, categories in list(users.items()):
        if not isinstance(categories, dict):
            users[user] = {}
            changed = True
            continue
        for category, entries in list(categories.items()):
            if not isinstance(entries, list):
                categories[category] = []
                changed = True
                continue
            cleaned = []
            seen: set[str] = set()
            for entry in entries:
                if isinstance(entry, dict):
                    value = (entry.get("value") or "").strip()
                    first = entry.get("first_recorded")
                    last = entry.get("last_updated")
                else:
                    value = str(entry).strip()
                    first = last = None
                    entry = {
                        "value": value,
                        "first_recorded": first,
                        "last_updated": last,
                    }
                if not value:
                    changed = True
                    continue
                if category == "contacts" and value.lower().startswith("phone:"):
                    digits = re.sub(r"\D", "", value.split(":", 1)[-1])
                    if not (7 <= len(digits) <= 14):
                        changed = True
                        continue
                key = value.lower()
                if key in seen:
                    continue
                seen.add(key)
                entry["value"] = value
                entry["first_recorded"] = first
                entry["last_updated"] = last
                cleaned.append(entry)
            if cleaned != entries:
                categories[category] = cleaned
                changed = True
    return changed


def _save_pref_log(entries: dict) -> None:
    try:
        os.makedirs(os.path.dirname(PREF_LOG_PATH), exist_ok=True)
        with open(PREF_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _log_preference_fact(category: str, value: str, user: str | None):
    if not value:
        return
    safe_user = (user or OWNER_NAME or "Father").strip()
    data = _load_pref_log()
    users = data.setdefault("users", {})
    bucket = users.setdefault(safe_user, {}).setdefault(category, [])
    now = _timestamp()
    lowered = value.lower()
    for entry in bucket:
        if str(entry.get("value", "")).lower() == lowered:
            entry["last_updated"] = now
            _save_pref_log(data)
            return
    bucket.append(
        {
            "value": value,
            "first_recorded": now,
            "last_updated": now,
        }
    )
    _save_pref_log(data)


def _cleanup_text(text: str) -> str:
    if not text:
        return ""
    txt = text.strip().strip("\"' ")
    txt = re.sub(r"\s+", " ", txt)
    return txt[:240]


def _safe_location(chunk: str) -> str:
    chunk = _cleanup_text(chunk.lower())
    if not chunk:
        return ""
    if "near" in chunk:
        parts = chunk.split("near", 1)
        city = re.findall(r"[a-z]+", parts[1])[:2]
        region = re.findall(r"[a-z]+", parts[0])[:2]
        base = " ".join(w.capitalize() for w in region if w)
        near = " ".join(w.capitalize() for w in city if w)
        near_clause = f" near {near}" if near else ""
        return (base or "Somewhere") + near_clause
    tokens = re.findall(r"[a-z]+", chunk)
    if not tokens:
        return ""
    coarse = tokens[:3]
    return " ".join(word.capitalize() for word in coarse)


def _sanitize_profile(profile: dict) -> bool:
    """Remove invalid contact facts (e.g., Discord snowflakes mistaken for phones)."""
    changed = False
    facts = profile.setdefault("facts", {})
    contacts = facts.get("contacts")
    if not isinstance(contacts, list):
        facts["contacts"] = []
        return True
    cleaned: list[str] = []
    for entry in contacts:
        if isinstance(entry, str) and entry.lower().startswith("phone:"):
            digits = re.sub(r"\D", "", entry.split(":", 1)[-1])
            if not (7 <= len(digits) <= 14):
                changed = True
                continue
        cleaned.append(entry)
    if changed:
        facts["contacts"] = cleaned
    return changed


def _safe_contact(value: str) -> str:
    return _cleanup_text(value)


def learn_from_text(text: str, user: str | None = None) -> bool:
    """Lightweight heuristic to store preferences/habits/location/contact from user utterances."""
    if not text or not text.strip():
        return False
    user = user or _session_identity()[0]
    msg = text.strip()
    low = msg.lower()
    learned = False

    def add_pref(chunk: str):
        nonlocal learned
        val = _cleanup_text(chunk)
        if val:
            learned |= _record_fact("preferences", val, user)

    for pattern in [
        r"\b(?:i|me)\s+(?:like|love)\s+([^\.!?]+)",
        r"\bmy\s+favorite\s+([^\.!?]+)",
    ]:
        for match in re.finditer(pattern, msg, flags=re.I):
            add_pref(match.group(1))

    for pattern in [
        r"\bi\s+(?:usually|often|tend to|always)\s+([^\.!?]+)",
        r"\bmy habit (?:is|tends to be)\s+([^\.!?]+)",
    ]:
        for match in re.finditer(pattern, msg, flags=re.I):
            val = _cleanup_text(match.group(1))
            if val:
                learned |= _record_fact("habits", val, user)

    loc_match = re.search(
        r"\b(i (?:live|am) in|i[' ]?m from|i am from)\s+([^\.!?]+)", msg, re.I
    )
    if loc_match:
        loc = _safe_location(loc_match.group(2))
        if loc and "near" in loc.lower():
            # Already general like "near Laval"
            pass
        if loc:
            learned |= _record_fact("location", loc, user)

    for email in re.findall(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", msg):
        learned |= _record_fact("contacts", f"email: {_safe_contact(email)}", user)

    for phone in re.findall(r"\b\+?\d[\d\s\-]{6,}\b", msg):
        digits = re.sub(r"[^\d+]", "", phone)
        numeric = re.sub(r"\D", "", digits)
        if 7 <= len(numeric) <= 14:
            learned |= _record_fact("contacts", f"phone: {_safe_contact(digits)}", user)

    appear_patterns = [
        r"\bmy hair (?:is|color is)\s+([^\.!?]+)",
        r"\bmy eyes (?:are|color is)\s+([^\.!?]+)",
        r"\bi have (?:a|an)\s+([^\.!?]+)\s+(?:tattoo|scar|style)",
    ]
    for pattern in appear_patterns:
        for match in re.finditer(pattern, msg, re.I):
            val = _cleanup_text(match.group(1))
            if val:
                learned |= _record_fact("appearance", val, user)

    pronoun = re.search(r"\bmy pronouns? (?:are|is)\s+([^\.!?]+)", msg, re.I)
    if pronoun:
        val = _cleanup_text(pronoun.group(1))
        if val:
            learned |= _record_fact("notes", f"pronouns: {val}", user)

    return learned


def get_profile(user: str | None = None) -> dict:
    return _load(user)


def ensure_profile(user: str | None = None, display_name: str | None = None) -> dict:
    prof = _load(user)
    if display_name:
        disp = display_name.strip()
        if disp and prof.get("display_name") != disp:
            prof["display_name"] = disp
            _save(user)
    return prof


def summarize(user: str | None = None, limit: int = 3) -> str:
    prof = _load(user)
    facts = prof.get("facts", {})
    chunks = []
    for cat in ("preferences", "habits", "appearance", "location"):
        vals = facts.get(cat) or []
        if vals:
            chunks.append(f"{cat.title()}: {', '.join(vals[:limit])}")
    relation = prof.get("relationship")
    if relation and relation != DEFAULT_RELATIONSHIP:
        chunks.append(f"Relationship: {relation}")
    return " | ".join(chunks)


def set_relationship(user: str | None, status: str) -> None:
    prof = _load(user)
    st = (status or "").strip().lower()
    if st not in RELATIONSHIP_LEVELS:
        st = DEFAULT_RELATIONSHIP
    if st == "father" and not _is_owner_key(user):
        try:
            from core import owner_guard

            reason = f"assign father to {user or 'unknown'}"
            if not owner_guard.verify_father_override(reason=reason):
                return
        except Exception:
            return
    prof["relationship"] = st
    _save(user)


def get_relationship(user: str | None = None) -> str:
    prof = _load(user)
    return prof.get("relationship", DEFAULT_RELATIONSHIP)


def _guardian_state(user: str | None = None) -> dict:
    prof = _load(user)
    guard = prof.setdefault(
        "guardian",
        {
            "incidents": 0,
            "pending": False,
            "pending_reason": "",
            "pending_severity": "",
            "pending_ts": "",
            "forgiveness_used": 0,
        },
    )
    return guard


def guardian_register_incident(
    user: str | None, reason: str = "", severity: str = "standard"
) -> dict:
    guard = _guardian_state(user)
    guard["incidents"] = int(guard.get("incidents", 0) or 0) + 1
    guard["pending"] = True
    guard["pending_reason"] = reason or "incident"
    guard["pending_severity"] = severity
    guard["pending_ts"] = _timestamp()
    _save(user)
    return guard


def guardian_pending(user: str | None = None) -> bool:
    guard = _guardian_state(user)
    return bool(guard.get("pending"))


def forgiveness_limit(user: str | None = None, relationship: str | None = None):
    rel = (relationship or get_relationship(user)).strip().lower()
    if rel == "father":
        return None
    if rel == "family":
        return 26
    return 3


def process_apology(user: str | None, relationship: str | None = None) -> dict:
    guard = _guardian_state(user)
    if not guard.get("pending"):
        return {"status": "no_pending"}
    limit = forgiveness_limit(user, relationship)
    used = int(guard.get("forgiveness_used", 0) or 0)
    if limit is None:
        guard["pending"] = False
        guard["pending_reason"] = ""
        guard["pending_severity"] = ""
        guard["pending_ts"] = ""
        _save(user)
        return {"status": "forgiven", "remaining": None, "limit": None, "used": used}
    if used < limit:
        guard["pending"] = False
        guard["pending_reason"] = ""
        guard["pending_severity"] = ""
        guard["pending_ts"] = ""
        guard["forgiveness_used"] = used + 1
        _save(user)
        remaining = max(0, limit - guard["forgiveness_used"])
        return {
            "status": "forgiven",
            "remaining": remaining,
            "limit": limit,
            "used": guard["forgiveness_used"],
        }
    return {
        "status": "limit_reached",
        "remaining": 0,
        "limit": limit,
        "used": used,
    }


def clear_pending_incident(user: str | None = None) -> None:
    guard = _guardian_state(user)
    guard["pending"] = False
    guard["pending_reason"] = ""
    guard["pending_severity"] = ""
    guard["pending_ts"] = ""
    _save(user)


def record_interaction(
    user: str | None = None, weight: int = 1, mentioned: bool = False
) -> int:
    prof = _load(user)
    amt = max(1, int(weight or 0) or 1)
    prof["interactions"] = int(prof.get("interactions", 0)) + amt
    _auto_relationship(prof, mentioned=mentioned)
    _save(user)
    return prof["interactions"]


def _auto_relationship(profile: dict, mentioned: bool = False) -> None:
    rel = profile.get("relationship", DEFAULT_RELATIONSHIP)
    if rel in _RELATIONSHIP_PROTECTED:
        return
    changed = False
    if mentioned and rel == DEFAULT_RELATIONSHIP:
        profile["relationship"] = "acquaintance"
        rel = "acquaintance"
        changed = True
    interactions = int(profile.get("interactions", 0) or 0)
    if interactions >= 3 and rel == "acquaintance":
        profile["relationship"] = "friend"
        changed = True
    if changed:
        profile["updated"] = _timestamp()
