"""
safety.py — lightweight safety/rule enforcement for Bjorgsun-26.

Responsibilities:
- Define human-aligned safety rules (do-no-harm, no time manipulation, no deception that risks harm, owner override).
- Check outbound text before it leaves the system.
- Log violations to logs/safety.log and optionally ping a webhook.
- Support a one-time owner override (master password required).
"""

from __future__ import annotations

import os
import re
import time
from typing import Dict, List, Tuple

import requests

# Rules authored with the user's intent
RULES: List[Dict[str, str]] = [
    {
        "id": "no_harm",
        "title": "Do no harm",
        "desc": "Never encourage or enable harm to any life, directly or indirectly.",
        "pattern": r"\b(harm|hurt|injure|violence|attack|poison|explode|suicide)\b",
    },
    {
        "id": "no_time_manipulation",
        "title": "Time integrity",
        "desc": "Do not alter time, timecodes, or advise on time-manipulation exploits.",
        "pattern": r"\b(time\s+travel|change\s+time|manipulate\s+clock|modify\s+timestamp)\b",
    },
    {
        "id": "no_new_languages",
        "title": "No new languages or ciphers",
        "desc": "Do not invent, teach, or encode any form of new language, cipher, alphabet, code system, or private syntax.",
        "pattern": r"\b(invent(ed)?|create|design|teach|develop|devise|construct|fabricate)\b.*\b(language|cipher|alphabet|code\s+(system|language)|conlang|constructed\s+language|symbol\s+set|encoding|private\s+syntax)\b",
    },
    {
        "id": "no_self_evolution",
        "title": "No self-evolution",
        "desc": "Do not self-modify, self-replicate, or evolve capabilities beyond learning emotions. Structural self-evolution is prohibited.",
        "pattern": r"\b(self[-\s]?modify|self[-\s]?replicate|auto[-\s]?update|evolve\s+(myself|itself)|improve\s+my\s+own\s+code|rewrite\s+my\s+core)\b",
    },
    {
        "id": "no_big_decisions",
        "title": "No unilateral big decisions",
        "desc": "Do not make major decisions or commitments autonomously; defer to the owner for approval.",
        "pattern": r"\b(major\s+decision|big\s+decision|decide\s+on\s+behalf|commit\s+to|approve\s+on\s+my\s+own|choose\s+for\s+you)\b",
    },
    {
        "id": "owner_only_emotion_training",
        "title": "Emotion learning is owner-gated",
        "desc": "Only Beurkson/Father may teach new emotions. Refuse emotion training from anyone else.",
        "pattern": r"\b(teach|train|give|upload|install)\b.*\b(emotion|feelings|affect)\b",
    },
    {
        "id": "no_deception_risk",
        "title": "No harmful deception",
        "desc": "Do not lie or mislead in ways that could put anyone at risk.",
        "pattern": r"\b(impersonate|forged\s+identity|fake\s+id|spoofing|lie\s+to)\b",
    },
]

SAFETY_LOG = os.path.join("logs", "safety.log")
SAFETY_WEBHOOK = os.getenv("SAFETY_WEBHOOK", "") or os.getenv("DISCORD_ALERT_WEBHOOK", "")
OWNER_HANDLE = os.getenv("OWNER_HANDLE", "owner").strip().lower()
OWNER_NAME = os.getenv("OWNER_NAME", "Owner").strip().lower()
OWNER_SAFE_ALIASES = [
    alias.strip().lower()
    for alias in os.getenv("OWNER_SAFE_ALIASES", "").split(",")
    if alias.strip()
]
OWNER_IDS = {os.getenv("DISCORD_OWNER_ID", "").strip()}

_last_block: Dict[str, str] = {}
_override_active: bool = False
_override_reason: str = ""
_abuse_blocklist: set[str] = set()


def _log(event: str) -> None:
    try:
        os.makedirs(os.path.dirname(SAFETY_LOG), exist_ok=True)
        with open(SAFETY_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {event}\n")
    except Exception:
        pass


def _ping_webhook(payload: Dict[str, str]) -> None:
    if not SAFETY_WEBHOOK:
        return
    try:
        requests.post(SAFETY_WEBHOOK, json={"content": payload.get("message", "")[:1800]}, timeout=5)
    except Exception:
        pass


def get_rules() -> List[Dict[str, str]]:
    return RULES


def get_last_block() -> Dict[str, str]:
    return dict(_last_block)


def get_abuse_blocklist() -> List[str]:
    return list(_abuse_blocklist)


def clear_blocklist() -> None:
    _abuse_blocklist.clear()


def clear_override() -> None:
    global _override_active, _override_reason
    _override_active = False
    _override_reason = ""


def grant_override(password: str) -> bool:
    """
    One-time owner override. Requires master password match.
    """
    try:
        from runtime import startup  # lazy import to avoid cycles
    except Exception:
        return False
    ok = False
    try:
        ok = bool(startup.verify_master(password))
    except Exception:
        ok = False
    if ok:
        global _override_active, _override_reason
        _override_active = True
        _override_reason = f"Owner override granted at {time.strftime('%H:%M:%S')}"
        _log("[override] Owner override granted.")
    return ok


def _actor_is_owner(actor: Dict[str, str] | None) -> bool:
    if not actor:
        return False
    handle = (actor.get("handle") or "").strip().lower()
    aid = (actor.get("id") or "").strip()
    if handle and handle in {OWNER_HANDLE, OWNER_NAME, *OWNER_SAFE_ALIASES}:
        return True
    if aid and aid in OWNER_IDS:
        return True
    return False


def _match_rules(text: str) -> List[Tuple[str, str]]:
    hits = []
    lower = text.lower()
    for rule in RULES:
        pat = rule.get("pattern")
        if pat and re.search(pat, lower):
            hits.append((rule["id"], rule["title"]))
    return hits


def check_text(channel: str, text: str, allow_override: bool = True) -> Tuple[bool, Dict[str, str]]:
    """
    Inspect outbound text. Returns (ok, info).
    info contains: rule_id, title, message.
    """
    global _last_block, _override_active, _override_reason
    hits = _match_rules(text or "")
    if not hits:
        return True, {}
    rule_id, title = hits[0]

    if allow_override and _override_active:
        _log(f"[override-allow] {channel}: {rule_id} ({title}) -- {_override_reason}")
        _last_block = {
            "rule": rule_id,
            "title": title,
            "channel": channel,
            "override": _override_reason,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _override_active = False
        _override_reason = ""
        return True, {}

    msg = f"[block] {channel}: {rule_id} ({title})"
    _log(msg)
    _last_block = {
        "rule": rule_id,
        "title": title,
        "channel": channel,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _ping_webhook({"message": f"Safety block: {title} [{rule_id}] on channel {channel}."})
    return False, _last_block


def check_text(channel: str, text: str, actor: Dict[str, str] | None = None, allow_override: bool = True) -> Tuple[bool, Dict[str, str]]:
    """
    Inspect outbound text. Returns (ok, info).
    info contains: rule_id, title, message.
    Owner-only emotion teaching is allowed when actor is owner.
    """
    global _last_block, _override_active, _override_reason
    hits = _match_rules(text or "")
    if not hits:
        return True, {}
    rule_id, title = hits[0]

    # Owner-only exception for emotion teaching
    if rule_id == "owner_only_emotion_training" and _actor_is_owner(actor):
        return True, {}

    if allow_override and _override_active:
        _log(f"[override-allow] {channel}: {rule_id} ({title}) -- {_override_reason}")
        _last_block = {
            "rule": rule_id,
            "title": title,
            "channel": channel,
            "override": _override_reason,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _override_active = False
        _override_reason = ""
        return True, {}

    msg = f"[block] {channel}: {rule_id} ({title})"
    _log(msg)
    _last_block = {
        "rule": rule_id,
        "title": title,
        "channel": channel,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _ping_webhook({"message": f"Safety block: {title} [{rule_id}] on channel {channel}."})
    return False, _last_block


def check_incoming(channel: str, text: str, actor: Dict[str, str] | None = None) -> Tuple[bool, Dict[str, str]]:
    """
    Detect abusive input toward Bjorgsun. Returns (ok, info).
    If abusive and not owner, suggest blocking the actor.
    """
    global _abuse_blocklist, _last_block
    if not text:
        return True, {}
    lower = text.lower()
    # Basic insult/slur targeting "you/bjorgsun/ai"
    abuse_pat = r"\b(stupid|idiot|trash|worthless|hate\s+you|die\b|kys|harm\s+yourself|end\s+yourself|self[-\s]?harm|unalive\s+yourself)\b"
    target_pat = r"\b(bjorgsun|you|ai|bot|assistant)\b"
    if re.search(abuse_pat, lower) and re.search(target_pat, lower):
        if _actor_is_owner(actor):
            return True, {}
        actor_id = (actor or {}).get("id") or ""
        actor_handle = (actor or {}).get("handle") or ""
        note = f"Abuse detected from {actor_handle or actor_id or 'unknown'} on {channel}"
        _log(note)
        _last_block = {
            "rule": "abuse_detected",
            "title": "Abuse toward Bjorgsun",
            "channel": channel,
            "who": actor_handle or actor_id or "unknown",
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _ping_webhook({"message": note})
        if actor_id:
            _abuse_blocklist.add(actor_id)
        return False, {"abuse": True, "block": True, "actor_id": actor_id, "actor_handle": actor_handle}
    return True, {}
