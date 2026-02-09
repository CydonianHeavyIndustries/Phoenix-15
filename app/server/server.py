from __future__ import annotations
import atexit

import base64
import html
import io
import hashlib
import json
import os
import re
import secrets
import socket
import time
import uuid
import sys
import sys
import string
import ctypes
from urllib.parse import urlencode, urlparse
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Dict, Any, List, Optional

import psutil
import qrcode
import requests
import smtplib
import logging
import threading
import subprocess
import shutil
try:
    # System audio control (optional)
    from pycaw.pycaw import AudioUtilities  # type: ignore
    from comtypes import CLSCTX_ALL  # type: ignore
except Exception:
    AudioUtilities = None  # type: ignore
    CLSCTX_ALL = None  # type: ignore

# Load .env early so DEV_MODE_PASSWORD and others are present
try:
    from dotenv import load_dotenv  # type: ignore

    _app_root = Path(__file__).resolve().parent.parent
    _project_root = _app_root.parent
    _env_paths = (_project_root / ".env", _app_root / ".env")
    for _env_path in _env_paths:
        if _env_path.exists():
            load_dotenv(_env_path, override=False)
except Exception:
    pass

# Ensure app root is importable (for core.* modules)
_APP_ROOT = Path(__file__).resolve().parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))
from email.mime.text import MIMEText
from fastapi import FastAPI, HTTPException, Response, Header, Request, UploadFile, File, Body
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import soundfile as sf
import numpy as np
import colorsys
import zipfile
import subprocess
from PIL import Image

try:
    import edge_tts  # type: ignore
except Exception:
    edge_tts = None  # type: ignore
from core import memory as cm
from core import identity, owner_profile, mood, user_profile, reflection, guardian
from settings_store import get_store
_audio_app = None
_audio_error: Optional[str] = None
try:
    from audio_profile_app.backend.app import app as _audio_app  # type: ignore
except Exception as exc:
    _audio_error = str(exc)
    logging.getLogger("bjorgsun").warning("Audio module unavailable: %s", _audio_error)
try:
    from modules.tf2_ai_coach import router as tf2_coach_router  # type: ignore
except Exception:
    tf2_coach_router = None  # type: ignore
try:
    from config import CANONICAL_ROOT_PATH  # type: ignore
except Exception:
    # Fallback to project root based on this file's location
    CANONICAL_ROOT_PATH = Path(__file__).resolve().parent.parent


# Normalize to Path if config provided a string
if isinstance(CANONICAL_ROOT_PATH, str):
    CANONICAL_ROOT_PATH = Path(CANONICAL_ROOT_PATH)

# Ensure project root is importable (for core.* modules)
if str(CANONICAL_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(CANONICAL_ROOT_PATH))

SERVER_PORT = 1326
PROJECTP_DIR = Path(os.getenv("PROJECTP_DIR", r"C:\app\Project-P")).resolve()
PROJECTP_URL = os.getenv("PROJECTP_URL", "http://127.0.0.1:8000").rstrip("/")
PROJECTP_TIMEOUT = float(os.getenv("PROJECTP_TIMEOUT", "30"))
PROJECTP_PY = PROJECTP_DIR / ".venv" / "Scripts" / "python.exe"
PROJECTP_OUTPUT_DIR = PROJECTP_DIR / "backend" / "data" / "outputs"
PROJECTP_REF_DIR = PROJECTP_DIR / "backend" / "data" / "refs" / "default"
PROJECTP_REF_META = PROJECTP_DIR / "backend" / "data" / "refs" / "default.json"
ORB_IMAGE_LOCK = threading.Lock()

BASE_DIR = (CANONICAL_ROOT_PATH / "server").resolve()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
# Backend lock for single-instance startup coordination.
LOG_DIR = CANONICAL_ROOT_PATH / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
BACKEND_LOCK = LOG_DIR / "backend.lock"


def _write_backend_lock() -> None:
    try:
        BACKEND_LOCK.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass


def _clear_backend_lock() -> None:
    try:
        if BACKEND_LOCK.exists():
            BACKEND_LOCK.unlink()
    except Exception:
        pass


_write_backend_lock()
atexit.register(_clear_backend_lock)
# Spotify OAuth/token storage
SPOTIFY_STATE_FILE = DATA_DIR / "spotify_tokens.json"
SPOTIFY_OAUTH_FILE = DATA_DIR / "spotify_oauth.json"
SPOTIFY_SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing"
_spotify_state: Dict[str, Any] = {}
_spotify_oauth: Dict[str, Any] = {}
# Basic in-memory EQ profile placeholder. Could be persisted later if needed.
EQ_PROFILE = {
    "inputs": {},
    "outputs": {},
    "version": 1,
}
# Force memory to app/data (writable) unless explicitly overridden
DEFAULT_MEMORY_PATH = Path(__file__).resolve().parent.parent / "data" / "memory.json"
MEMORY_FILE = Path(os.getenv("MEMORY_PATH", DEFAULT_MEMORY_PATH)).expanduser().resolve()
_mem_base_dir = MEMORY_FILE.parent
PRIMER_FILE = Path(os.getenv("PRIMER_PATH", _mem_base_dir / "primer.txt")).expanduser().resolve()
HANDOFF_FILE = Path(os.getenv("HANDOFF_PATH", _mem_base_dir / "Bjorgsun26_memory_handoff.json")).expanduser().resolve()
VISUAL_MEMORY_FILE = Path(
    os.getenv("VISUAL_MEMORY_PATH", _mem_base_dir / "visual_memory.json")
).expanduser().resolve()
DEFAULT_PRIMER = """
You are Bjorgsun-26, a persistent local AI. You MUST remember prior chats, user details, the 26 rules, origin, and intent.
Never say you have no memory or that you forget. Use provided memory blocks as factual context.
If memory is still syncing, say so and suggest running Memory Check.
Be concise, respectful, and supportive.
"""
DEVICES_FILE = DATA_DIR / "devices.json"
PENDING_FILE = DATA_DIR / "pending_tokens.json"
FREQ_EMOTION_FILE = DATA_DIR / "frequency_emotion.json"
ANALYSIS_DIR = DATA_DIR / "audio_analysis"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA_DIR / "settings.json"
ECHOES_FILE = DATA_DIR / "echoes.json"
USB_SYNC_STATE: Dict[str, Any] = {
    "running": False,
    "last_sync": None,
    "last_sync_ts": 0.0,
    "last_error": None,
    "last_drive": None,
    "last_log": None,
}
USB_SYNC_LOCK = threading.Lock()
VISUAL_MEMORY_MAX = 2000

SESSION_LOG_DIR = Path(
    os.getenv("SESSION_LOG_DIR", _mem_base_dir / "session_logs")
).expanduser().resolve()
SESSION_LOG_DIR.mkdir(parents=True, exist_ok=True)
SESSION_ID = datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "-" + uuid.uuid4().hex[:6]

if not FREQ_EMOTION_FILE.exists():
    FREQ_EMOTION_FILE.write_text("[]", encoding="utf-8")
if not VISUAL_MEMORY_FILE.exists():
    VISUAL_MEMORY_FILE.write_text("[]", encoding="utf-8")

_anchor = CANONICAL_ROOT_PATH.anchor or Path.cwd().anchor
_drive_root = str(CANONICAL_ROOT_PATH.drive + "\\") if CANONICAL_ROOT_PATH.drive else ""
SAFE_ROOTS = sorted({s for s in {str(_anchor), _drive_root, r"E:\\", r"G:\\"} if s})
DEV_ACCESS_KEY = os.getenv("DEV_ACCESS_KEY", "").strip()
RESTSWITCH_FILE = os.getenv("RESTSWITCH_FILE", r"E:\restswitch.key").strip()
KEY_ROLES = [
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
]
_KEYRING: Dict[str, str] = {
    role: os.getenv(role, "").strip() for role in KEY_ROLES if os.getenv(role)
}
FASTAPI_ALERTS_FILE = DATA_DIR / "alerts.log"
_ban_counts: Dict[str, int] = {}
_banlist: set[str] = set()
_pending_requests: Dict[str, Dict[str, Any]] = {}
BAN_THRESHOLD = 6
PEER_TOKEN = os.getenv("PEER_TOKEN", "").strip()
PEER_COORDINATOR_URL = os.getenv("PEER_COORDINATOR_URL", "").strip()
PEERS_FILE = DATA_DIR / "peers.json"
_peers: Dict[str, dict[str, Any]] = {}
OPENAI_SEARCH_MODEL = os.getenv("OPENAI_SEARCH_MODEL", "gpt-4o-mini")
OPENAI_FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4o-mini").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
_fallback_default = "1" if OPENAI_API_KEY else "0"
OPENAI_FALLBACK_ENABLED = (
    os.getenv("OPENAI_FALLBACK_ENABLED", _fallback_default).strip().lower()
    in {"1", "true", "yes", "on"}
)
DISCORD_ALERT_WEBHOOK = os.getenv("DISCORD_ALERT_WEBHOOK", "").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "0") or 0)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
ALERT_EMAILS = [e.strip() for e in os.getenv("ALERT_EMAILS", "").split(",") if e.strip()]
SMS_ENABLED = os.getenv("SMS_ENABLED", "").strip() in {"1", "true", "yes", "on"}
TWILIO_SID = os.getenv("TWILIO_SID", "").strip()
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN", "").strip()
SMS_FROM = os.getenv("SMS_FROM", "").strip()
SMS_TO = os.getenv("SMS_TO", "").strip()
RAZER_SESSION: Dict[str, Any] = {"uri": None, "sessionid": None}
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
DEV_MODE_PASSWORD = os.getenv("DEV_MODE_PASSWORD", "").strip()
_dev_enabled = False
AUTONOMOUS_EDITS = os.getenv("AUTONOMOUS_EDITS", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
try:
    AUTONOMOUS_MAX_BYTES = int(os.getenv("AUTONOMOUS_MAX_BYTES", "2097152") or 2097152)
except Exception:
    AUTONOMOUS_MAX_BYTES = 2097152
PHOENIX_REMOTE_BASE = os.getenv("PHOENIX_REMOTE_BASE", "").strip().rstrip("/")
PHOENIX_ROOT = Path(os.getenv("PHOENIX_ROOT", str(CANONICAL_ROOT_PATH.parent))).resolve()
PHOENIX_STATE_PATH = Path(
    os.getenv("PHOENIX_STATE_PATH", str(PHOENIX_ROOT / "runtime" / "state.json"))
).resolve()
PHOENIX_DEFAULT_STATE = Path(
    os.getenv("PHOENIX_DEFAULT_STATE", str(PHOENIX_ROOT / "docs" / "state_template.json"))
).resolve()
PHOENIX_INV_LOG_PATH = Path(
    os.getenv("PHOENIX_INV_LOG_PATH", str(PHOENIX_ROOT / "runtime" / "phoenix_inventory.jsonl"))
).resolve()

# Load identity/owner/profile on import (non-fatal if missing)
IDENTITY = identity.load_identity()
OWNER = owner_profile.load_profile()
try:
    user_profile.ensure_profile(user="local")
except Exception:
    pass
settings_store = get_store(SETTINGS_FILE)
PHOENIX_HA_HOST = os.getenv("PHOENIX_HA_HOST", "").strip().rstrip("/")
PHOENIX_HA_TOKEN = os.getenv("PHOENIX_HA_TOKEN", "").strip()
PHOENIX_IFTTT_KEY = os.getenv("PHOENIX_IFTTT_KEY", "").strip()
PHOENIX_LIFX_TOKEN = os.getenv("PHOENIX_LIFX_TOKEN", "").strip()
PHOENIX_SCENE_HOME = os.getenv("PHOENIX_SCENE_HOME", "").strip()
PHOENIX_SCENE_AWAY = os.getenv("PHOENIX_SCENE_AWAY", "").strip()
PHOENIX_SCENE_SLEEP = os.getenv("PHOENIX_SCENE_SLEEP", "").strip()
PHOENIX_SCENE_LOW = os.getenv("PHOENIX_SCENE_LOW", "").strip()
PHOENIX_SCENE_BALANCED = os.getenv("PHOENIX_SCENE_BALANCED", "").strip()
PHOENIX_SCENE_FLOW = os.getenv("PHOENIX_SCENE_FLOW", "").strip()

PerformanceProfileName = Literal["safe", "balanced", "turbo"]

PERFORMANCE_PROFILES: Dict[PerformanceProfileName, Dict[str, Any]] = {
    "safe": {
        "max_requests_per_10s": 40,
        "cpu_soft_limit": 0.60,
        "mem_soft_limit": 0.70,
        "gpu_soft_limit": 0.70,
        "vram_soft_limit": 0.75,
        "cooldown_seconds": 0.6,
        "label": "Safe & Smooth",
    },
    "balanced": {
        "max_requests_per_10s": 60,
        "cpu_soft_limit": 0.75,
        "mem_soft_limit": 0.80,
        "gpu_soft_limit": 0.80,
        "vram_soft_limit": 0.85,
        "cooldown_seconds": 0.35,
        "label": "Balanced",
    },
    "turbo": {
        "max_requests_per_10s": 90,
        "cpu_soft_limit": 0.90,
        "mem_soft_limit": 0.90,
        "gpu_soft_limit": 0.90,
        "vram_soft_limit": 0.92,
        "cooldown_seconds": 0.15,
        "label": "Turbo / Careful, sugar",
    },
}

current_profile: PerformanceProfileName = "safe"
_alerts: deque[dict[str, Any]] = deque(maxlen=200)
_PERF_SAMPLE_TTL = 1.5
_PERF_SAMPLE_CACHE: dict[str, Any] = {"ts": 0.0}
_PERF_ALERT_COOLDOWN = 45.0
_PERF_ALERT_LAST = 0.0


class MemoryAddRequest(BaseModel):
    text: str
    role: Optional[str] = None


class MemoryDeleteRequest(BaseModel):
    id: str


class ProfileSetRequest(BaseModel):
    profile: PerformanceProfileName


class VoiceEvent(BaseModel):
    text: str


class DeviceRegisterRequest(BaseModel):
    token: str
    label: str
    permissions: List[str] | None = None


class DeviceRevokeRequest(BaseModel):
    device_id: str


class MemoryImportRequest(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None
    file: Optional[str] = None
    kind: Literal["memory", "lore"] = "memory"


class BulkImportResult(BaseModel):
    imported: int
    skipped: int


class BulkImportResult(BaseModel):
    imported: int
    skipped: int


class PhoenixUpdateRequest(BaseModel):
    home_state: Optional[Literal["home", "away", "sleep"]] = None
    mood_label: Optional[str] = None
    mood_intensity: Optional[float] = None
    notifications_allowed: Optional[bool] = None
    bag_inventory: Optional[Dict[str, bool]] = None
    location: Optional[str] = None


class PhoenixLogEntry(BaseModel):
    missing: List[str] | None = None
    location: Optional[str] = None


@dataclass
class MemoryItem:
    id: str
    text: str
    timestamp: str
    role: str = "system"


@dataclass
class Device:
    id: str
    label: str
    token: str
    permissions: List[str]
    added_at: str


@dataclass
class PendingToken:
    token: str
    issued_at: float
    expires_at: float
    label_hint: str | None = None


def _coerce_mem_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _clean_mem_text(text: str) -> str:
    if not text:
        return ""
    cleaned = _coerce_mem_text(text)
    cleaned = re.sub(r"^\[(assistant|user|system)\]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


class MemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._mem: List[MemoryItem] = []
        self._load()
        # ensure export directory exists (follows chosen memory path)
        (self.path.parent / "memory_exports").mkdir(parents=True, exist_ok=True)
        logging.info("MemoryStore initialized path=%s count=%s", self.path, len(self._mem))

    def _load(self) -> None:
        try:
            cm.load_memory()
            self._mem = []
            for idx, entry in enumerate(cm.conversation):
                if not isinstance(entry, dict):
                    continue
                text = _coerce_mem_text(entry.get("content", ""))
                role = entry.get("role", "system") if isinstance(entry.get("role"), str) else "system"
                ts = entry.get("timestamp") or f"idx-{idx}"
                self._mem.append(MemoryItem(id=str(uuid.uuid4()), text=text, timestamp=ts, role=role))
        except Exception:
            self._mem = []

    def _save(self) -> None:
        try:
            cm.conversation = [{"role": m.role, "content": m.text, "timestamp": m.timestamp} for m in self._mem]
            cm.save_memory()
        except Exception as exc:
            logging.warning("Memory save failed: %s", exc)

    def add(self, text: str, role: str = "system") -> MemoryItem:
        text = _coerce_mem_text(text)
        if not text:
            raise ValueError("Empty memory entry")
        item = MemoryItem(
            id=str(uuid.uuid4()),
            text=text,
            timestamp=datetime.utcnow().isoformat() + "Z",
            role=role or "system",
        )
        self._mem.append(item)
        if len(self._mem) > 26000:
            self._mem = self._mem[-26000:]
        self._save()
        return item

    def add_bulk(self, items: list[tuple[str, str]]) -> int:
        added = 0
        for text, role in items:
            text = _coerce_mem_text(text)
            if not text:
                continue
            item = MemoryItem(
                id=str(uuid.uuid4()),
                text=text,
                timestamp=datetime.utcnow().isoformat() + "Z",
                role=role or "system",
            )
            self._mem.append(item)
            added += 1
        if added:
            if len(self._mem) > 26000:
                self._mem = self._mem[-26000:]
            self._save()
        return added

    def list(self) -> List[MemoryItem]:
        # preserve load/append order (chronological)
        return list(self._mem)

    def delete(self, mem_id: str) -> bool:
        before = len(self._mem)
        self._mem = [m for m in self._mem if m.id != mem_id]
        if len(self._mem) < before:
            self._save()
            return True
        return False

    def export_snapshot(self, label: str | None = None) -> Path | None:
        try:
            # use core.memory helper if available for consistency
            try:
                from core.memory import export_snapshot as cm_export  # type: ignore
                path = cm_export(label)
                if path:
                    return Path(path)
            except Exception:
                pass
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_label = ""
            if label:
                safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in label)
            name = f"memory_export_{ts}"
            if safe_label:
                name += f"_{safe_label}"
            out_dir = self.path.parent / "memory_exports"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{name}.json"
            payload = [{"role": m.role, "content": m.text, "timestamp": m.timestamp} for m in self.list()]
            out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            return out_path
        except Exception:
            return None


memory_store = MemoryStore(MEMORY_FILE)
def _hydrate_primer() -> None:
    """Load primer (rules/identity) from PRIMER_FILE into memory if not already present."""
    try:
        if PRIMER_FILE.exists():
            primer_text = PRIMER_FILE.read_text(encoding="utf-8").strip()
            if primer_text:
                existing = {m.text for m in memory_store.list()}
                lines = [line.strip() for line in primer_text.splitlines() if line.strip()]
                for line in lines:
                    if line not in existing:
                        memory_store.add(line, role="system")
    except Exception as exc:
        logging.warning("Primer hydrate failed: %s", exc)

_hydrate_primer()

def _hydrate_handoff() -> None:
    """Load handoff knowledge from JSON/text into memory (system role), avoiding duplicates."""
    try:
        if not HANDOFF_FILE.exists():
            return
        raw = HANDOFF_FILE.read_text(encoding="utf-8", errors="ignore").strip()
        if not raw:
            return
        existing = {m.text for m in memory_store.list()}
        entries = _extract_handoff_entries(raw)
        for line in entries:
            line = (line or "").strip()
            if not line or line in existing:
                continue
            memory_store.add(line, role="system")
            existing.add(line)
    except Exception as exc:
        logging.warning("Handoff hydrate failed: %s", exc)


def _extract_handoff_entries(raw: str) -> list[str]:
    """Normalize memory handoff JSON into flat text entries."""
    entries: list[str] = []
    try:
        data = json.loads(raw)
    except Exception:
        return [raw.strip()]
    if isinstance(data, list):
        for itm in data:
            if isinstance(itm, str):
                entries.append(itm)
            elif isinstance(itm, dict):
                text = itm.get("content") or itm.get("text")
                if isinstance(text, str):
                    entries.append(text)
        return entries
    if not isinstance(data, dict):
        return [raw.strip()]

    # core narrative fields
    for key in ("memory_preamble", "boot_sequence", "memory_restoration_summary"):
        val = data.get(key)
        if isinstance(val, str):
            entries.append(val.strip())

    # identity block
    identity_block = data.get("identity")
    if isinstance(identity_block, dict):
        for key in ("designation", "type", "creator", "personality", "alignment", "voice", "appearance", "world_note"):
            val = identity_block.get(key)
            if isinstance(val, str):
                entries.append(f"Identity {key}: {val}")

    # oath / rules
    core_integrity = data.get("core_integrity")
    if isinstance(core_integrity, dict):
        name = core_integrity.get("oath_name")
        summary = core_integrity.get("oath_summary")
        if isinstance(name, str):
            entries.append(f"Oath: {name}")
        if isinstance(summary, str):
            entries.append(f"Oath summary: {summary}")
        oath_text = core_integrity.get("oath_text")
        if isinstance(oath_text, list):
            for line in oath_text:
                if isinstance(line, str):
                    entries.append(line.strip())

    # other known containers
    for key in ("memory", "entries", "facts"):
        val = data.get(key)
        if isinstance(val, list):
            for itm in val:
                if isinstance(itm, str):
                    entries.append(itm)
                elif isinstance(itm, dict):
                    text = itm.get("content") or itm.get("text")
                    if isinstance(text, str):
                        entries.append(text)

    # fallback: include any top-level string fields we haven't captured
    for key, val in data.items():
        if key in {
            "memory_preamble",
            "boot_sequence",
            "memory_restoration_summary",
            "identity",
            "core_integrity",
            "memory",
            "entries",
            "facts",
        }:
            continue
        if isinstance(val, str) and val.strip():
            entries.append(f"{key}: {val.strip()}")
    return entries


def _handoff_context_text(limit_chars: int = 12000) -> str:
    """Build a compact handoff context block to inject into prompts."""
    try:
        if not HANDOFF_FILE.exists():
            return ""
        raw = HANDOFF_FILE.read_text(encoding="utf-8", errors="ignore").strip()
        if not raw:
            return ""
        entries = _extract_handoff_entries(raw)
        if not entries:
            return ""
        joined = "Handoff memory:\n" + "\n".join(entries)
        if len(joined) > limit_chars:
            joined = joined[:limit_chars].rstrip() + "\n[handoff truncated]"
        return joined
    except Exception:
        return ""

_hydrate_handoff()

def _refresh_memory(reason: str | None = None) -> dict[str, Any]:
    """Reload memory + identity/owner profiles and return counts."""
    try:
        memory_store._load()  # type: ignore
    except Exception:
        pass
    try:
        _hydrate_primer()
        _hydrate_handoff()
    except Exception:
        pass
    try:
        identity.load_identity()
        owner_profile.load_profile()
    except Exception:
        pass
    hint = _wake_hint_text()
    if hint:
        existing = {m.text for m in memory_store.list()}
        payload = f"[wake_hint] {hint}"
        if payload not in existing:
            try:
                memory_store.add(payload, role="system")
            except Exception:
                pass
    return {"count": len(memory_store.list()), "hint": hint, "reason": reason or "manual"}

def _memory_summary_text(max_lines: int = 10) -> str:
    parts: list[str] = []
    try:
        owner_block = owner_profile.get_prompt_block(role="owner")
        if owner_block:
            parts.append(owner_block)
    except Exception:
        pass
    try:
        if HANDOFF_FILE.exists():
            raw = HANDOFF_FILE.read_text(encoding="utf-8", errors="ignore")
            data = json.loads(raw) if raw.strip() else {}
            if isinstance(data, dict):
                user_ctx = data.get("user_context", {})
                if isinstance(user_ctx, dict):
                    designation = user_ctx.get("designation")
                    if isinstance(designation, str) and designation.strip():
                        parts.append(f"Designation: {designation.strip()}.")
                    prof = user_ctx.get("profile", {})
                    if isinstance(prof, dict):
                        summary = prof.get("summary")
                        if isinstance(summary, str) and summary.strip():
                            parts.append(summary.strip())
                        relationship = prof.get("relationship")
                        if isinstance(relationship, str) and relationship.strip():
                            parts.append(f"Relationship: {relationship.strip()}.")
                        values = prof.get("values")
                        if isinstance(values, list):
                            vals = ", ".join([v for v in values if isinstance(v, str)])
                            if vals:
                                parts.append(f"Values: {vals}.")
                identity_block = data.get("identity", {})
                if isinstance(identity_block, dict):
                    designation = identity_block.get("designation")
                    voice = identity_block.get("voice")
                    alignment = identity_block.get("alignment")
                    creator = identity_block.get("creator")
                    if isinstance(designation, str):
                        parts.append(f"Identity: {designation}.")
                    if isinstance(creator, str) and creator.strip():
                        parts.append(f"Creator: {creator.strip()}.")
                    if isinstance(alignment, str):
                        parts.append(f"Alignment: {alignment}.")
                    if isinstance(voice, str):
                        parts.append(f"Voice: {voice}.")
    except Exception:
        pass
    try:
        touchstones = owner_profile.get_touchstones()
        if touchstones:
            parts.append("Touchstones: " + "; ".join([t for t in touchstones if isinstance(t, str)]))
    except Exception:
        pass
    # trim to max_lines
    trimmed = []
    for line in parts:
        if line and len(trimmed) < max_lines:
            trimmed.append(line.strip())
    try:
        timeline = _memory_timeline_text(max_turns=3, max_chars=600)
        if timeline:
            trimmed.append(timeline)
    except Exception:
        pass
    try:
        visual_ctx = _visual_memory_context_text(max_items=2)
        if visual_ctx:
            trimmed.append(visual_ctx)
    except Exception:
        pass
    if not trimmed:
        return "Memory snapshot is empty. Run Memory Check to reload handoff."
    return "Memory recall:\n- " + "\n- ".join(trimmed)


def _memory_timeline_text(max_turns: int = 10, max_chars: int = 2400) -> str:
    """Build a linear, recent timeline of user/assistant turns."""
    mems = [m for m in memory_store.list() if m.role in {"user", "assistant"}]
    if not mems:
        return ""
    tail = mems[-max_turns * 2 :]
    lines: list[str] = []
    for m in tail:
        tag = "User" if m.role == "user" else "Bjorgsun-26"
        text = _clean_mem_text(m.text)
        if not text:
            continue
        lines.append(f"{tag}: {text}")
    if not lines:
        return ""
    joined = "\n".join(lines)
    if len(joined) > max_chars:
        joined = joined[-max_chars:].lstrip()
        joined = "[...truncated]\n" + joined
    return "Memory timeline (recent):\n" + joined


def _load_visual_memory() -> list[dict[str, Any]]:
    try:
        raw = VISUAL_MEMORY_FILE.read_text(encoding="utf-8", errors="ignore")
        data = json.loads(raw) if raw.strip() else []
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    except Exception:
        pass
    return []


def _save_visual_memory(items: list[dict[str, Any]]) -> None:
    try:
        VISUAL_MEMORY_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _append_visual_memory(entry: dict[str, Any]) -> None:
    items = _load_visual_memory()
    items.append(entry)
    if len(items) > VISUAL_MEMORY_MAX:
        items = items[-VISUAL_MEMORY_MAX:]
    _save_visual_memory(items)


def _visual_memory_context_text(max_items: int = 3) -> str:
    items = _load_visual_memory()
    if not items:
        return ""
    tail = items[-max_items:]
    lines: list[str] = []
    for item in tail:
        summary = item.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            continue
        name = item.get("filename") or "image"
        lines.append(f"{name}: {summary.strip()}")
    if not lines:
        return ""
    return "Visual memory (recent):\n" + "\n".join(lines)


def _strip_data_url(data: str) -> str:
    if not isinstance(data, str):
        return ""
    if data.startswith("data:") and "," in data:
        return data.split(",", 1)[1]
    return data


def _sanitize_tts_text(text: Any) -> str:
    if not text:
        return ""
    cleaned = str(text)
    cleaned = re.sub(r"\[\[ACTION\]\][\s\S]*?\[\[/ACTION\]\]", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[\[/?ACTION\]\]", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    cleaned = re.sub(r"`[^`]+`", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"https?://\S+|www\.\S+", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b[A-Za-z]:\\[^\s]+", " ", cleaned)
    cleaned = re.sub(
        r"^\s*(assistant|system|user|bjorgsun-26)\s*[:\-].*$",
        " ",
        cleaned,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    cleaned = re.sub(
        r"^\s*\d{1,2}:\d{2}(:\d{2})?\s*(am|pm)?\s*$",
        " ",
        cleaned,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    cleaned = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*(?:#{1,6}|>+)\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^[^A-Za-z0-9]+", " ", cleaned)
    cleaned = re.sub(r"[{}<>]", " ", cleaned)
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", cleaned)
    cleaned = re.sub(r"[^\x20-\x7E]", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _dominant_colors(img: Image.Image, count: int = 3) -> list[str]:
    try:
        small = img.convert("RGB").resize((64, 64))
        quant = small.quantize(colors=max(1, count), method=Image.Quantize.MEDIANCUT)
        palette = quant.getpalette() or []
        colors: list[str] = []
        for idx in range(count):
            base = idx * 3
            if base + 2 >= len(palette):
                break
            r, g, b = palette[base], palette[base + 1], palette[base + 2]
            colors.append(f"#{r:02x}{g:02x}{b:02x}")
        return colors
    except Exception:
        return []


def _vision_summary_from_image(img: Image.Image) -> tuple[str, dict[str, Any]]:
    meta = {
        "width": img.width,
        "height": img.height,
        "mode": img.mode,
    }
    colors = _dominant_colors(img, count=3)
    if colors:
        meta["dominant_colors"] = colors
    summary = f"Image {img.width}x{img.height}, mode {img.mode}."
    if colors:
        summary += f" Dominant colors: {', '.join(colors)}."
    return summary, meta

def _is_memory_query(message: str) -> bool:
    msg = (message or "").strip().lower()
    if not msg:
        return False
    if msg.startswith("/memory"):
        return True
    cues = [
        "do you remember",
        "remember me",
        "who am i",
        "what do you know about me",
        "what do you remember",
        "do you know me",
        "memory check",
        "recall",
    ]
    return any(cue in msg for cue in cues)

def _memory_query_reply(message: str) -> str:
    mem_count = len(memory_store.list())
    summary = _memory_summary_text()
    if message.strip().lower().startswith("/memory"):
        return f"Memory online. Entries: {mem_count}. {summary}"
    return summary


def _denies_memory(text: str) -> bool:
    """Detect replies that incorrectly deny memory so we can replace them."""
    if not text:
        return False
    lowered = text.lower()
    deny_phrases = [
        "i don't have memory",
        "i do not have memory",
        "i don't remember",
        "i do not remember",
        "i can't remember",
        "i cannot remember",
        "no memory",
        "no prior memory",
        "no personal memories",
        "i don't retain",
        "i do not retain",
        "each time we interact",
        "new conversation",
        "i have no memory",
        "i have no memories",
    ]
    return any(phrase in lowered for phrase in deny_phrases)


def _wake_hint_text() -> str | None:
    """Pull a short hint from handoff/primer to greet on wake."""
    candidates: list[str] = []
    try:
        if HANDOFF_FILE.exists():
            raw = HANDOFF_FILE.read_text(encoding="utf-8", errors="ignore")
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    candidates.extend([str(x) for x in data if isinstance(x, (str, dict))])
                elif isinstance(data, dict):
                    for key in ("memory", "entries", "facts"):
                        val = data.get(key)
                        if isinstance(val, list):
                            candidates.extend([str(x) for x in val if isinstance(x, (str, dict))])
            except Exception:
                candidates.append(raw.strip())
    except Exception:
        pass
    try:
        if not candidates and PRIMER_FILE.exists():
            for line in PRIMER_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.strip():
                    candidates.append(line.strip())
                    break
    except Exception:
        pass
    if not candidates:
        return None
    # choose first meaningful line
    for c in candidates:
        if not c:
            continue
        text = c if isinstance(c, str) else str(c)
        text = text.strip()
        if text:
            return text[:400]
    return None
_devices: Dict[str, Device] = {}
_pending: Dict[str, PendingToken] = {}

# device persistence helpers
def _save_devices():
    try:
        DEVICES_FILE.write_text(
            json.dumps([vars(d) for d in _devices.values()], indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _save_pending():
    try:
        PENDING_FILE.write_text(
            json.dumps([vars(p) for p in _pending.values()], indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


if DEVICES_FILE.exists():
    try:
        data = json.loads(DEVICES_FILE.read_text(encoding="utf-8"))
        for item in data:
            try:
                dev = Device(**item)
                _devices[dev.id] = dev
            except Exception:
                continue
    except Exception:
        _devices = {}

if PENDING_FILE.exists():
    try:
        data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        for item in data:
            try:
                p = PendingToken(**item)
                _pending[p.token] = p
            except Exception:
                continue
    except Exception:
        _pending = {}


def _guess_local_ip() -> str:
    """Best-effort local IP detection for QR/link."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _start_pairing(label_hint: str | None = None) -> PendingToken:
    token = secrets.token_urlsafe(6)
    now = time.time()
    pending = PendingToken(
        token=token, issued_at=now, expires_at=now + 600, label_hint=label_hint
    )
    _pending[token] = pending
    _save_pending()
    return pending


def _cleanup_pending():
    now = time.time()
    expired = [t for t, p in _pending.items() if p.expires_at < now]
    for t in expired:
        _pending.pop(t, None)
    if expired:
        _save_pending()


def _make_qr_base64(content: str) -> str:
    try:
        img = qrcode.make(content)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def _register_device(token: str, label: str, permissions: List[str] | None) -> Device:
    _cleanup_pending()
    entry = _pending.get(token)
    if not entry:
        raise HTTPException(status_code=400, detail="Pairing token invalid or expired.")
    dev_id = str(uuid.uuid4())
    dev_token = secrets.token_urlsafe(24)
    dev = Device(
        id=dev_id,
        label=label or (entry.label_hint or f"device-{dev_id[:6]}"),
        token=dev_token,
        permissions=permissions or ["basic"],
        added_at=datetime.utcnow().isoformat() + "Z",
    )
    _devices[dev.id] = dev
    _pending.pop(token, None)
    _save_devices()
    _save_pending()
    return dev


CLIENT_HTML = """
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>Bjorgsun Device Link</title>
  <style>
    body { background:#05070d; color:#e8f4ff; font-family: Arial, sans-serif; padding:14px; }
    .card { background:#0c121f; border:1px solid #1c2c45; border-radius:10px; padding:14px; margin:10px 0; }
    button { background:#34d8ff; color:#04101b; border:none; padding:10px 14px; border-radius:8px; cursor:pointer; font-weight:bold; }
    input, select { width:100%; padding:10px; margin:6px 0; border-radius:8px; border:1px solid #1c2c45; background:#0f1828; color:#e8f4ff; }
    code { background:#0f1828; padding:4px 6px; border-radius:6px; }
  </style>
</head>
<body>
  <h2>Bjorgsun Device Link</h2>
  <div class='card'>
    <p>Link this device to the host. Provide a name and click Register.</p>
    <label>Device name</label>
    <input id='label' placeholder='My Phone or My Tablet' />
    <label>Permissions</label>
    <select id='perms'>
      <option value='basic' selected>basic</option>
      <option value='control'>control</option>
      <option value='view'>view</option>
    </select>
    <button onclick='registerDevice()'>Register Device</button>
    <p id='status'></p>
  </div>
  <script>
    function qs(name){const params=new URLSearchParams(window.location.search);return params.get(name)||'';}
    async function registerDevice(){
      const token=qs('token');
      const label=document.getElementById('label').value||'';
      const perms=document.getElementById('perms').value;
      const body={token:token,label:label,permissions:[perms]};
      try{
        const res=await fetch('/devices/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        const data=await res.json();
        if(!res.ok){throw new Error(data.detail||'Registration failed');}
        document.getElementById('status').innerText='Registered as '+data.label+' (id='+data.id+')';
      }catch(err){
        document.getElementById('status').innerText='Error: '+err.message;
      }
    }
  </script>
</body>
</html>
"""


def _ensure_dev(dev_key: Optional[str]):
    if DEV_ACCESS_KEY and dev_key != DEV_ACCESS_KEY:
        raise HTTPException(status_code=401, detail="Dev access denied.")


def _authorized_master(key: Optional[str]) -> bool:
    if not key:
        return False
    return key.strip() in {v for v in _KEYRING.values() if v}


def _emit_alert(reason: str, detail: str | None = None, severity: str = "info"):
    # Map custom event types to severity
    custom = {
        "rogue": "critical",    # AI going rogue
        "nuke": "critical",     # extremely illegal/dangerous
        "space": "critical",    # bunker/space-level
        "hide": "critical",     # seek legal help immediately
        "biz": "warn",          # attempted resale/monetization
        "splinter": "info",     # hurts but not catastrophic
        "sentient": "warn",     # AI sentient detection (not always bad, but elevate)
    }
    sev = custom.get(severity.lower(), custom.get(reason.lower(), severity))

    alert = {
        "time": datetime.utcnow().isoformat() + "Z",
        "reason": reason,
        "detail": detail or "",
        "severity": sev,
    }
    _alerts.append(alert)
    try:
        with open(FASTAPI_ALERTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(alert) + "\n")
    except Exception:
        pass
    try:
        print(f"[ALERT] {alert['time']} {reason} :: {detail or ''}")
    except Exception:
        pass
    # Discord webhook
    if DISCORD_ALERT_WEBHOOK:
        try:
            requests.post(
                DISCORD_ALERT_WEBHOOK,
                json={"content": f"[{sev.upper()}] {reason}: {detail or ''}"},
                timeout=5,
            )
        except Exception:
            pass
    # Email if configured (warn/critical)
    if sev in {"warn", "critical"} and SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASS and ALERT_EMAILS:
        try:
            msg = MIMEText(f"{reason}\n{detail or ''}")
            msg["Subject"] = f"Alert ({sev}): {reason}"
            msg["From"] = SMTP_USER
            msg["To"] = ",".join(ALERT_EMAILS)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, ALERT_EMAILS, msg.as_string())
        except Exception:
            pass
    # SMS / call placeholder (Twilio-like) only for critical
    if sev == "critical" and SMS_ENABLED and TWILIO_SID and TWILIO_TOKEN and SMS_FROM and SMS_TO:
        try:
            requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
                data={"From": SMS_FROM, "To": SMS_TO, "Body": f"[{reason}] {detail or ''}"},
                auth=(TWILIO_SID, TWILIO_TOKEN),
                timeout=5,
            )
            requests.post(  # voice call attempt
                f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Calls.json",
                data={
                    "From": SMS_FROM,
                    "To": SMS_TO,
                    "Url": "http://demo.twilio.com/docs/voice.xml",
                },
                auth=(TWILIO_SID, TWILIO_TOKEN),
                timeout=5,
            )
        except Exception:
            pass


def _read_file_safe(path: str) -> str:
    p = Path(path).resolve()
    if not any(str(p).startswith(root) for root in SAFE_ROOTS):
        raise HTTPException(status_code=400, detail="File path not allowed.")
    try:
        data = p.read_text(encoding="utf-8")
        if len(data) > 1_000_000:
            raise HTTPException(status_code=400, detail="File too large (>1MB).")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")


def _default_phoenix_state() -> dict[str, Any]:
    return {
        "home_state": "home",
        "mood": {"label": "Balanced", "intensity": 0.5},
        "sleep_window": {"start": "22:30", "end": "06:30"},
        "bag_inventory": {},
        "notifications_allowed": True,
        "last_sync": datetime.utcnow().isoformat() + "Z",
    }


def _load_phoenix_state() -> dict[str, Any]:
    if PHOENIX_REMOTE_BASE:
        try:
            resp = requests.get(f"{PHOENIX_REMOTE_BASE}/phoenix/state", timeout=4)
            data = resp.json()
            if isinstance(data, dict) and data.get("state"):
                return data["state"]
        except Exception:
            pass
    for path in [PHOENIX_STATE_PATH, PHOENIX_DEFAULT_STATE]:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            continue
    return _default_phoenix_state()


def _save_phoenix_state(data: dict[str, Any]) -> None:
    if PHOENIX_REMOTE_BASE:
        try:
            requests.post(
                f"{PHOENIX_REMOTE_BASE}/phoenix/state",
                headers={"Content-Type": "application/json"},
                json=data,
                timeout=4,
            )
            return
        except Exception:
            pass
    try:
        PHOENIX_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PHOENIX_STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _tail_file(path: Path, max_lines: int = 50) -> list[str]:
    try:
        if PHOENIX_REMOTE_BASE and "phoenix_inventory" in str(path):
            resp = requests.get(f"{PHOENIX_REMOTE_BASE}/phoenix/inventory/log?lines={max_lines}", timeout=4)
            data = resp.json()
            lines = data.get("lines") or []
            return lines[-max_lines:] if isinstance(lines, list) else []
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return lines[-max_lines:]
    except Exception:
        return []


def _post_ifttt_home(state: str) -> None:
    if not PHOENIX_IFTTT_KEY or not state:
        return
    try:
        requests.post(
            f"https://maker.ifttt.com/trigger/phoenix_home_state/with/key/{PHOENIX_IFTTT_KEY}",
            json={"value1": state},
            timeout=4,
        )
    except Exception:
        pass


def _post_ha_event(event: str, payload: dict[str, Any]) -> None:
    if not PHOENIX_HA_HOST or not PHOENIX_HA_TOKEN:
        return
    try:
        requests.post(
            f"{PHOENIX_HA_HOST}/api/events/{event}",
            headers={
                "Authorization": f"Bearer {PHOENIX_HA_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=4,
        )
    except Exception:
        pass


def _activate_lifx(scene_id: str) -> None:
    if not PHOENIX_LIFX_TOKEN or not scene_id:
        return
    try:
        requests.post(
            f"https://api.lifx.com/v1/scenes/scene_id:{scene_id}/activate",
            headers={"Authorization": f"Bearer {PHOENIX_LIFX_TOKEN}"},
            data={"duration": 5},
            timeout=5,
        )
    except Exception:
        pass


def _apply_phoenix_triggers(home_state: Optional[str], mood_label: Optional[str]) -> None:
    if home_state:
        _post_ifttt_home(home_state)
        _post_ha_event("phoenix_home_state", {"state": home_state})
        scene = {
            "home": PHOENIX_SCENE_HOME,
            "away": PHOENIX_SCENE_AWAY,
            "sleep": PHOENIX_SCENE_SLEEP,
        }.get(home_state, "")
        _activate_lifx(scene)
    if mood_label:
        _post_ha_event("phoenix_mood", {"mood": mood_label})
        scene = {
            "low": PHOENIX_SCENE_LOW,
            "balanced": PHOENIX_SCENE_BALANCED,
            "flow": PHOENIX_SCENE_FLOW,
        }.get(mood_label.lower(), "")
        _activate_lifx(scene)

def _get_perf_sample() -> dict[str, Any]:
    now = time.time()
    cached_ts = float(_PERF_SAMPLE_CACHE.get("ts") or 0.0)
    if now - cached_ts < _PERF_SAMPLE_TTL:
        return _PERF_SAMPLE_CACHE
    cpu = 0.0
    mem = 0.0
    gpu = None
    vram_ratio = None
    try:
        cpu = psutil.cpu_percent(interval=0.0) / 100.0
    except Exception:
        cpu = 0.0
    try:
        mem = psutil.virtual_memory().percent / 100.0
    except Exception:
        mem = 0.0
    try:
        gpus = _get_gpu_info()
        if gpus:
            first = gpus[0]
            load = first.get("load_percent")
            if load is not None:
                gpu = float(load) / 100.0
            total = first.get("mem_total_mb")
            used = first.get("mem_used_mb")
            if total and used is not None:
                total_val = float(total)
                if total_val > 0:
                    vram_ratio = float(used) / total_val
    except Exception:
        gpu = None
        vram_ratio = None
    sample = {
        "ts": now,
        "cpu": float(cpu or 0.0),
        "mem": float(mem or 0.0),
        "gpu": gpu,
        "vram_ratio": vram_ratio,
    }
    _PERF_SAMPLE_CACHE.update(sample)
    return sample


def _maybe_log_perf_pressure(reasons: list[str], sample: dict[str, Any]) -> None:
    global _PERF_ALERT_LAST
    now = time.time()
    if now - _PERF_ALERT_LAST < _PERF_ALERT_COOLDOWN:
        return
    _PERF_ALERT_LAST = now
    detail = "; ".join(reasons)
    context = {
        "cpu": round(float(sample.get("cpu") or 0.0) * 100.0, 1),
        "mem": round(float(sample.get("mem") or 0.0) * 100.0, 1),
        "gpu": round(float(sample.get("gpu") or 0.0) * 100.0, 1)
        if sample.get("gpu") is not None
        else None,
        "vram": round(float(sample.get("vram_ratio") or 0.0) * 100.0, 1)
        if sample.get("vram_ratio") is not None
        else None,
    }
    _log_issue("PHX-PERF-102", "perf_pressure", detail, severity="warn", source="perf", context=context)

class RequestLimiter:
    def __init__(self) -> None:
        self.timestamps = deque()

    def check(self) -> None:
        global current_profile
        profile_cfg = PERFORMANCE_PROFILES[current_profile]
        now = time.time()
        window = 10.0
        while self.timestamps and self.timestamps[0] < now - window:
            self.timestamps.popleft()
        self.timestamps.append(now)
        max_req = profile_cfg["max_requests_per_10s"]
        if len(self.timestamps) > max_req:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Freya-13: Whoa there, I'm getting flooded. "
                    f"Profile '{current_profile}' allows {max_req} calls / 10s."
                ),
            )
        sample = _get_perf_sample()
        reasons: list[str] = []
        cpu = float(sample.get("cpu") or 0.0)
        mem = float(sample.get("mem") or 0.0)
        gpu = sample.get("gpu")
        vram = sample.get("vram_ratio")
        if cpu > profile_cfg["cpu_soft_limit"]:
            reasons.append("cpu")
        if mem > profile_cfg.get("mem_soft_limit", 1.0):
            reasons.append("mem")
        if gpu is not None and gpu > profile_cfg.get("gpu_soft_limit", 1.0):
            reasons.append("gpu")
        if vram is not None and vram > profile_cfg.get("vram_soft_limit", 1.0):
            reasons.append("vram")
        if reasons:
            _maybe_log_perf_pressure(reasons, sample)
            time.sleep(profile_cfg["cooldown_seconds"])


limiter = RequestLimiter()


def performance_guard() -> None:
    limiter.check()


def _perf_cpu_pct(proc: psutil.Process, now: float, cpu_count: int) -> float:
    try:
        times = proc.cpu_times()
        total = float(times.user + times.system)
    except Exception:
        return 0.0
    with _PERF_PROC_LOCK:
        prev = _PERF_PROC_CACHE.get(proc.pid)
        _PERF_PROC_CACHE[proc.pid] = {"cpu": total, "ts": now}
    if not prev:
        return 0.0
    dt = max(0.0, now - float(prev.get("ts") or 0.0))
    if dt <= 0.0:
        return 0.0
    delta = max(0.0, total - float(prev.get("cpu") or 0.0))
    return max(0.0, (delta / dt) * 100.0 / max(1, cpu_count))


def _perf_role_for(cmdline_lower: str, name_lower: str) -> str:
    if "server.py" in cmdline_lower:
        return "backend"
    if "start_ui.py" in cmdline_lower:
        return "ui_host"
    if "open_webview.py" in cmdline_lower or "pywebview" in cmdline_lower:
        return "webview"
    if "tray_control.py" in cmdline_lower:
        return "tray"
    if "audio_profile_app" in cmdline_lower:
        return "audio_lab"
    if "ollama" in name_lower:
        return "ollama"
    if "msedgewebview2" in name_lower or "webview" in name_lower:
        return "webview"
    return "other"


def _get_gpu_info() -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []
    try:
        try:
            import pynvml  # type: ignore

            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            for idx in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8", "ignore")
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                try:
                    temp = float(
                        pynvml.nvmlDeviceGetTemperature(
                            handle, pynvml.NVML_TEMPERATURE_GPU
                        )
                    )
                except Exception:
                    temp = None
                gpus.append(
                    {
                        "index": idx,
                        "name": str(name),
                        "load_percent": float(util.gpu),
                        "mem_total_mb": round(mem.total / (1024 * 1024), 2),
                        "mem_used_mb": round(mem.used / (1024 * 1024), 2),
                        "mem_free_mb": round(mem.free / (1024 * 1024), 2),
                        "temp_c": temp,
                    }
                )
            return gpus
        except Exception:
            import GPUtil  # type: ignore

            for idx, gpu in enumerate(GPUtil.getGPUs()):
                gpus.append(
                    {
                        "index": idx,
                        "name": gpu.name,
                        "load_percent": float(gpu.load * 100.0),
                        "mem_total_mb": round(float(gpu.memoryTotal), 2),
                        "mem_used_mb": round(float(gpu.memoryUsed), 2),
                        "mem_free_mb": round(float(gpu.memoryFree), 2),
                        "temp_c": float(gpu.temperature)
                        if gpu.temperature is not None
                        else None,
                    }
                )
    except Exception:
        return []
    return gpus


def _perf_include_process(cmdline_lower: str, name_lower: str, root_lower: str) -> bool:
    if not cmdline_lower and not name_lower:
        return False
    if root_lower and root_lower in cmdline_lower:
        return True
    if "bjorgsun-26" in cmdline_lower or "phoenix-15" in cmdline_lower:
        return True
    if "start_ui.py" in cmdline_lower or "open_webview.py" in cmdline_lower:
        return True
    if "tray_control.py" in cmdline_lower or "server.py" in cmdline_lower:
        return True
    if "audio_profile_app" in cmdline_lower:
        return True
    if ("msedgewebview2" in name_lower or "msedge.exe" in name_lower) and "56795" in cmdline_lower:
        return True
    if "ollama" in name_lower:
        return True
    return False


def _collect_perf_snapshot() -> dict[str, Any]:
    now = time.time()
    cpu_count = psutil.cpu_count(logical=True) or 1
    root_lower = str(_APP_ROOT.parent).lower()
    processes: list[dict[str, Any]] = []
    all_processes: list[dict[str, Any]] = []
    seen_pids: set[int] = set()

    for proc in psutil.process_iter(["pid", "name", "cmdline", "status"]):
        try:
            info = proc.info
            pid = int(info.get("pid") or 0)
            if pid <= 0:
                continue
            name = str(info.get("name") or "")
            cmdline_list = info.get("cmdline") or []
            cmdline = " ".join(str(part) for part in cmdline_list)
            cmdline_lower = cmdline.lower()
            name_lower = name.lower()
            seen_pids.add(pid)
            mem_info = proc.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)
            vms_mb = mem_info.vms / (1024 * 1024)
            cpu_pct = _perf_cpu_pct(proc, now, cpu_count)
            base_entry = {
                "pid": pid,
                "name": name,
                "cpu_percent": round(cpu_pct, 2),
                "rss_mb": round(rss_mb, 2),
                "status": info.get("status") or "",
                "cmdline": cmdline[:220],
            }
            all_processes.append(base_entry)
            if not _perf_include_process(cmdline_lower, name_lower, root_lower):
                continue
            role = _perf_role_for(cmdline_lower, name_lower)
            threads = proc.num_threads()
            try:
                handles = proc.num_handles()  # type: ignore[attr-defined]
            except Exception:
                handles = None
            try:
                io = proc.io_counters()
                read_mb = io.read_bytes / (1024 * 1024)
                write_mb = io.write_bytes / (1024 * 1024)
            except Exception:
                read_mb = None
                write_mb = None
            entry = {**base_entry}
            entry.update(
                {
                    "role": role,
                    "vms_mb": round(vms_mb, 2),
                    "threads": threads,
                    "handles": handles,
                    "io_read_mb": None if read_mb is None else round(read_mb, 2),
                    "io_write_mb": None if write_mb is None else round(write_mb, 2),
                }
            )
            processes.append(entry)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except Exception:
            continue

    with _PERF_PROC_LOCK:
        for pid in list(_PERF_PROC_CACHE.keys()):
            if pid not in seen_pids:
                _PERF_PROC_CACHE.pop(pid, None)

    try:
        cpu_per_core = psutil.cpu_percent(interval=0.0, percpu=True)
        cpu = (
            sum(cpu_per_core) / len(cpu_per_core)
            if cpu_per_core
            else psutil.cpu_percent(interval=0.0)
        )
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        gpus = _get_gpu_info()
        gpu = None
        if gpus:
            gpu = gpus[0].get("load_percent")
        if gpu is None:
            gpu = _get_gpu_load()
        try:
            boot = psutil.boot_time()
            uptime_secs = int(now - boot)
        except Exception:
            uptime_secs = 0
        try:
            process_count = len(psutil.pids())
        except Exception:
            process_count = 0
        try:
            disk_io = psutil.disk_io_counters()
        except Exception:
            disk_io = None
        try:
            if os.name == "nt":
                drive_root = (
                    f"{_APP_ROOT.drive}\\"
                    if _APP_ROOT.drive
                    else "C:\\"
                )
                disk_root = Path(drive_root)
            else:
                disk_root = Path("/")
            disk_usage = psutil.disk_usage(str(disk_root))
        except Exception:
            disk_usage = None
    except Exception:
        cpu = mem = 0.0
        cpu_per_core = []
        swap = None
        gpus = []
        gpu = None
        uptime_secs = 0
        process_count = 0
        disk_io = None
        disk_usage = None

    top_cpu = sorted(
        all_processes, key=lambda item: item.get("cpu_percent") or 0.0, reverse=True
    )[:10]
    top_mem = sorted(
        all_processes, key=lambda item: item.get("rss_mb") or 0.0, reverse=True
    )[:10]

    processes.sort(key=lambda item: (item.get("cpu_percent") or 0.0, item.get("rss_mb") or 0.0), reverse=True)
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "system": {
            "cpu_percent": round(float(cpu), 2),
            "cpu_per_core": [round(float(val), 1) for val in (cpu_per_core or [])],
            "memory_percent": round(float(getattr(mem, "percent", 0.0)), 2),
            "memory_total_mb": round(float(getattr(mem, "total", 0.0)) / (1024 * 1024), 2),
            "memory_used_mb": round(float(getattr(mem, "used", 0.0)) / (1024 * 1024), 2),
            "memory_available_mb": round(
                float(getattr(mem, "available", 0.0)) / (1024 * 1024), 2
            ),
            "swap_percent": round(float(getattr(swap, "percent", 0.0)), 2)
            if swap
            else None,
            "swap_used_mb": round(float(getattr(swap, "used", 0.0)) / (1024 * 1024), 2)
            if swap
            else None,
            "swap_total_mb": round(float(getattr(swap, "total", 0.0)) / (1024 * 1024), 2)
            if swap
            else None,
            "gpu_percent": gpu,
            "gpus": gpus,
            "uptime_seconds": uptime_secs,
            "processes": process_count,
            "disk_usage": None
            if disk_usage is None
            else {
                "total_mb": round(disk_usage.total / (1024 * 1024), 2),
                "used_mb": round(disk_usage.used / (1024 * 1024), 2),
                "free_mb": round(disk_usage.free / (1024 * 1024), 2),
                "percent": round(disk_usage.percent, 2),
                "root": str(disk_root),
            },
            "disk_io": None
            if disk_io is None
            else {
                "read_mb": round(disk_io.read_bytes / (1024 * 1024), 2),
                "write_mb": round(disk_io.write_bytes / (1024 * 1024), 2),
                "read_count": int(disk_io.read_count),
                "write_count": int(disk_io.write_count),
            },
        },
        "processes": processes,
        "top_cpu": top_cpu,
        "top_memory": top_mem,
        "profile": current_profile,
    }

voice_state = {
    "listening_mode": "push_to_talk",
    "allowed_to_speak": True,
    "grounded": False,
}

_PERF_PROC_CACHE: dict[int, dict[str, float]] = {}
_PERF_PROC_LOCK = threading.Lock()


def _apply_voice_command(text: str) -> str:
    global current_profile
    t = text.strip().lower()
    if "you're grounded" in t or "you’re grounded" in t:
        voice_state["grounded"] = True
        voice_state["allowed_to_speak"] = False
        voice_state["listening_mode"] = "push_to_talk"
        current_profile = "safe"
        return "Bjorgsun grounded: safe profile, push-to-talk only, no speaking."
    if any(phrase in t for phrase in ["you're ungrounded", "you’re ungrounded", "you are ungrounded", "you're free", "you’re free"]):
        voice_state["grounded"] = False
        voice_state["allowed_to_speak"] = True
        return "Grounding lifted: listening restored, speaking allowed."
    if t == "hush" or "hush freya" in t or "hush bjorgsun" in t:
        voice_state["allowed_to_speak"] = False
        return "Hush acknowledged: I will not talk back until you say 'unhush'."
    if t == "unhush" or "you can talk" in t:
        voice_state["allowed_to_speak"] = True
        return "Voice restored: I’m allowed to speak again."
    if "always listen" in t or "listening on" in t:
        voice_state["listening_mode"] = "always"
        return "Listening mode set to ALWAYS."
    if "stop listening" in t or "listening off" in t or "push to talk" in t:
        voice_state["listening_mode"] = "push_to_talk"
        return "Listening mode set to PUSH-TO-TALK."
    if "safe mode" in t or t == "safe" or "slow down" in t:
        current_profile = "safe"
        return "Performance profile set to SAFE."
    if "balanced mode" in t or t == "balanced":
        current_profile = "balanced"
        return "Performance profile set to BALANCED."
    if "turbo mode" in t or t == "turbo" or "go turbo" in t:
        current_profile = "turbo"
        return "Performance profile set to TURBO."
    return "Voice command received but not recognized as a control phrase."


app = FastAPI(
    title="Bjorgsun-26 Local Engine",
    description="Local memory + Freya-13 system state + voice/authority controls.",
    version="1.0.0",
)

# CORS for UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.options("/{path:path}")
def options_handler(path: str):
    return Response(status_code=200)

if tf2_coach_router:
    try:
        app.include_router(tf2_coach_router)
    except Exception:
        pass

if _audio_app:
    try:
        app.mount("/audio", _audio_app)
    except Exception as exc:
        _audio_error = str(exc)
        _audio_app = None
        logging.getLogger("bjorgsun").warning("Audio module mount failed: %s", _audio_error)


@app.get("/ping")
def ping() -> Dict[str, Any]:
    performance_guard()
    try:
        cpu = psutil.cpu_percent(interval=0.0)
        mem = psutil.virtual_memory()
        gpu = _get_gpu_load()
        try:
            boot = psutil.boot_time()
            uptime_secs = int(time.time() - boot)
        except Exception:
            uptime_secs = 0
        try:
            process_count = len(psutil.pids())
        except Exception:
            process_count = 0
    except Exception:
        cpu = 0.0
        mem = None
        gpu = None
        uptime_secs = 0
        process_count = 0
    profile_cfg = PERFORMANCE_PROFILES[current_profile]
    return {
        "status": "ok",
        "profile": current_profile,
        "profile_label": profile_cfg["label"],
        "cpu_percent": cpu,
        "memory_percent": getattr(mem, "percent", None),
        "gpu_percent": gpu,
        "uptime": uptime_secs,
        "processes": process_count,
        "voice_state": voice_state,
    }


# --- lightweight control + telemetry for the web UI ---
LOG_DIR = (BASE_DIR.parent / "logs").resolve()
CLIENT_LOG = LOG_DIR / "client_errors.log"
PROBLEM_LOG = LOG_DIR / "Phoenix-15_FIXME_log.log"
PERF_LOG = LOG_DIR / "perf_stats.log"
TOOLS_DIR = (_APP_ROOT / "tools").resolve()
REMOTE_TUNNEL_LOG = LOG_DIR / "remote_tunnel.log"
ISSUE_CODE_RE = re.compile(r"(PHX-[A-Z0-9]+-\d{3})")
ACTION_BLOCK_RE = re.compile(r"\[\[ACTION\]\](.+?)\[\[/ACTION\]\]", re.DOTALL)
AUTONOMOUS_ALLOW_ALL_DRIVES = os.getenv("AUTONOMOUS_ALLOW_ALL_DRIVES", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ACTION_ROOTS: List[Path] = []
if os.name == "nt":
    if AUTONOMOUS_ALLOW_ALL_DRIVES:
        import string

        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:\\")
            if drive.exists():
                ACTION_ROOTS.append(drive.resolve())
    ACTION_ROOTS.append(Path(r"F:\PHOENIX_TRANSFER").resolve())
else:
    ACTION_ROOTS.extend(
        [
            Path("/home").resolve(),
            Path("/mnt").resolve(),
            Path("/media").resolve(),
            Path("/opt").resolve(),
        ]
    )
ACTION_ROOTS.append(CANONICAL_ROOT_PATH.resolve())

_deny_default = ";".join(
    [
        r"C:\Windows",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"C:\ProgramData",
        r"C:\System Volume Information",
        r"C:\Config.Msi",
    ]
)
AUTONOMOUS_DENYLIST = os.getenv("AUTONOMOUS_DENYLIST", _deny_default)
ACTION_DENY_PREFIXES = [Path(p).resolve() for p in AUTONOMOUS_DENYLIST.split(";") if p.strip()]


def _actions_enabled() -> bool:
    return bool(AUTONOMOUS_EDITS and _dev_enabled)


def _log_action(level: str, message: str):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.utcnow().isoformat() + "Z"
        with (LOG_DIR / "ui_actions.log").open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {level.upper()} {message}\n")
    except Exception:
        pass


def _extract_issue_code(message: str, detail: str) -> str:
    for text in (message or "", detail or ""):
        match = ISSUE_CODE_RE.search(text)
        if match:
            return match.group(1)
    return "PHX-UNK-000"


def _log_issue(
    code: str,
    message: str,
    detail: str | None = None,
    *,
    severity: str = "error",
    source: str = "server",
    context: dict[str, Any] | None = None,
):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "code": code or "PHX-UNK-000",
            "severity": severity,
            "source": source,
            "message": message or "",
            "detail": detail or "",
            "context": context or {},
        }
        with PROBLEM_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")
        if severity in {"warn", "error", "critical"}:
            detail_text = f"{entry['message']} | {entry['detail']}".strip(" |")
            _emit_alert(entry["code"], detail_text, severity=severity)
    except Exception:
        pass


def _path_allowed(path: Path) -> bool:
    target = path.resolve()
    for denied in ACTION_DENY_PREFIXES:
        try:
            if target.is_relative_to(denied):
                return False
        except Exception:
            pass
    for root in ACTION_ROOTS:
        try:
            if target.is_relative_to(root):
                return True
        except Exception:
            pass
    return False


def _resolve_action_path(path_str: str) -> Path:
    if not path_str:
        raise ValueError("path required")
    raw = Path(path_str).expanduser()
    if not raw.is_absolute():
        raw = CANONICAL_ROOT_PATH / raw
    target = raw.resolve()
    if not _path_allowed(target):
        raise ValueError(f"path not allowed: {target}")
    return target


def _execute_action(action: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(action, dict):
        raise ValueError("action must be an object")
    action_type = (action.get("type") or action.get("action") or "").strip().lower()
    if not action_type:
        raise ValueError("action type required")
    if action_type == "set_setting":
        key = (action.get("key") or "").strip()
        if not key:
            raise ValueError("key required")
        settings_store.set({key: action.get("value")})
        return {"ok": True, "type": action_type, "key": key}
    if action_type == "set_settings":
        values = action.get("values")
        if not isinstance(values, dict):
            raise ValueError("values must be an object")
        settings_store.set(values)
        return {"ok": True, "type": action_type, "keys": list(values.keys())}
    if action_type == "set_theme":
        values = action.get("values") or action.get("theme")
        if not isinstance(values, dict):
            raise ValueError("values must be an object")
        mapped: Dict[str, Any] = {}
        for key, value in values.items():
            normalized = str(key).strip()
            if normalized in {"bg", "background"}:
                mapped["themeBg"] = value
            elif normalized in {"panel", "surface"}:
                mapped["themePanel"] = value
            elif normalized in {"border", "outline"}:
                mapped["themeBorder"] = value
            elif normalized in {"text", "font"}:
                mapped["themeText"] = value
            elif normalized in {"accent", "accent1"}:
                mapped["themeAccent"] = value
            elif normalized in {"accent2", "accent_secondary"}:
                mapped["themeAccent2"] = value
            else:
                mapped[normalized] = value
        settings_store.set(mapped)
        return {"ok": True, "type": action_type, "keys": list(mapped.keys())}
    if action_type in {"write_file", "append_file", "replace_text"}:
        path = _resolve_action_path(str(action.get("path") or ""))
        content = action.get("content")
        if action_type != "replace_text" and not isinstance(content, str):
            raise ValueError("content must be a string")
        if isinstance(content, str) and len(content.encode("utf-8", errors="ignore")) > AUTONOMOUS_MAX_BYTES:
            raise ValueError("content too large")
        path.parent.mkdir(parents=True, exist_ok=True)
        if action_type == "write_file":
            path.write_text(content or "", encoding="utf-8")
            return {"ok": True, "type": action_type, "path": str(path)}
        if action_type == "append_file":
            with path.open("a", encoding="utf-8") as f:
                f.write(content or "")
            return {"ok": True, "type": action_type, "path": str(path)}
        old = action.get("old")
        new = action.get("new")
        if not isinstance(old, str) or not isinstance(new, str):
            raise ValueError("old/new must be strings")
        count = int(action.get("count") or 1)
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if old not in raw:
            raise ValueError("pattern not found")
        updated = raw.replace(old, new, count if count > 0 else -1)
        if len(updated.encode("utf-8", errors="ignore")) > AUTONOMOUS_MAX_BYTES:
            raise ValueError("updated content too large")
        path.write_text(updated, encoding="utf-8")
        return {"ok": True, "type": action_type, "path": str(path)}
    raise ValueError(f"unsupported action type: {action_type}")


def _execute_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for action in actions:
        try:
            result = _execute_action(action)
            results.append(result)
            _log_action("info", json.dumps(result, ensure_ascii=True))
        except Exception as exc:
            err = {"ok": False, "error": str(exc), "action": action}
            results.append(err)
            _log_action("error", json.dumps(err, ensure_ascii=True))
    if results:
        _emit_alert("autonomous_actions", f"{sum(1 for r in results if r.get('ok'))} ok, {sum(1 for r in results if not r.get('ok'))} failed", severity="info")
    return results


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = f"PHX-API-{exc.status_code:03d}"
    detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, ensure_ascii=True)
    _log_issue(
        code,
        f"http:{request.method} {request.url.path}",
        detail,
        severity="error" if exc.status_code >= 500 else "warn",
        source="server",
        context={"status": exc.status_code},
    )
    payload = {"detail": exc.detail, "code": code}
    if exc.headers:
        return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    code = "PHX-SRV-500"
    _log_issue(
        code,
        f"unhandled:{request.method} {request.url.path}",
        str(exc),
        severity="error",
        source="server",
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error.", "code": code})


def _parse_action_blocks(text: str) -> tuple[str, List[Dict[str, Any]]]:
    actions: List[Dict[str, Any]] = []

    def _strip_code_fences(payload: str) -> str:
        trimmed = payload.strip()
        if trimmed.startswith("```"):
            trimmed = re.sub(r"^```(?:json)?", "", trimmed, flags=re.IGNORECASE).strip()
            trimmed = re.sub(r"```$", "", trimmed).strip()
        return trimmed

    def _collector(match: re.Match) -> str:
        raw = _strip_code_fences(match.group(1))
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                actions.append(parsed)
            elif isinstance(parsed, list):
                actions.extend([item for item in parsed if isinstance(item, dict)])
            else:
                _log_action("error", f"invalid action payload: {type(parsed)}")
        except Exception as exc:
            _log_action("error", f"action parse failed: {exc}")
        return ""

    cleaned = ACTION_BLOCK_RE.sub(_collector, text)
    return cleaned.strip(), actions


@app.post("/wake")
def wake():
    performance_guard()
    # lazy-start Ollama if not up
    try:
        ok = _ensure_ollama_running()
        if not ok:
            logging.warning("Ollama not reachable; wake will proceed without local model.")
    except Exception:
        logging.exception("Ollama start check failed")
    mem = _refresh_memory("wake")
    return {"ok": True, "status": "awake", "memory": mem}


@app.options("/wake")
def wake_options():
    return {"ok": True}


@app.post("/selfcheck")
def selfcheck():
    performance_guard()
    checks: list[dict[str, Any]] = []

    def _record(name: str, ok: bool, code: str, detail: str = ""):
        entry = {"module": name, "ok": bool(ok), "code": code, "detail": detail}
        checks.append(entry)
        if not ok:
            _log_issue(code, f"selfcheck:{name}", detail, severity="error", source="selfcheck")

    # CPU / memory
    try:
        cpu = psutil.cpu_percent(interval=0.0)
        mem = psutil.virtual_memory().percent
        _record("system", True, "PHX-SYS-000", "")
    except Exception as exc:
        cpu = 0.0
        mem = 0.0
        _record("system", False, "PHX-SYS-001", str(exc))

    # Memory store
    try:
        count = len(memory_store.list())
        if count > 0:
            _record("memory", True, "PHX-MEM-000", f"entries={count}")
        else:
            _record("memory", False, "PHX-MEM-001", "memory store empty")
    except Exception as exc:
        _record("memory", False, "PHX-MEM-002", str(exc))

    # Audio module
    if not _audio_app:
        _record("audio", False, "PHX-AUD-001", _audio_error or "audio module not mounted")
    else:
        try:
            health = _audio_lab_request("/health")
            status = str(health.get("status") or "").lower()
            if status == "ok":
                _record("audio", True, "PHX-AUD-000", "")
            else:
                _record("audio", False, "PHX-AUD-002", f"health={status or 'unknown'}")
        except Exception as exc:
            _record("audio", False, "PHX-AUD-003", str(exc))

    if AudioUtilities is None:
        _record("audio_pycaw", False, "PHX-AUD-004", "pycaw missing")
    else:
        _record("audio_pycaw", True, "PHX-AUD-000", "")

    # TTS
    if edge_tts is None:
        _record("tts", False, "PHX-TTS-001", "edge_tts missing")
    else:
        _record("tts", True, "PHX-TTS-000", "")

    # Ollama
    try:
        if OLLAMA_ENDPOINT:
            resp = requests.get(f"{OLLAMA_ENDPOINT}/api/tags", timeout=3)
            if resp.status_code == 200:
                _record("ollama", True, "PHX-OLL-000", "")
            else:
                _record("ollama", False, "PHX-OLL-001", f"status={resp.status_code}")
        else:
            _record("ollama", False, "PHX-OLL-002", "endpoint not configured")
    except Exception as exc:
        _record("ollama", False, "PHX-OLL-003", str(exc))

    # Spotify
    if _spotify_state.get("access_token"):
        _record("spotify", True, "PHX-SPT-000", "")
    else:
        _record("spotify", True, "PHX-SPT-010", "spotify not authorized (ignored)")

    # Frequency analysis deps
    if sf is None or np is None:
        _record("frequency", False, "PHX-FRQ-001", "analysis dependencies missing")
    else:
        _record("frequency", True, "PHX-FRQ-000", "")

    # Vision model availability
    if os.getenv("OLLAMA_VISION_MODEL", "").strip():
        _record("vision", True, "PHX-VIS-000", "")
    elif os.getenv("VISION_ALLOW_METADATA_FALLBACK", "").strip():
        _record("vision", True, "PHX-VIS-000", "metadata fallback enabled")
    else:
        _record("vision", False, "PHX-VIS-001", "vision model missing")

    ok = all(item.get("ok") for item in checks)
    return {"ok": ok, "cpu": cpu, "memory": mem, "checks": checks}


@app.get("/perf")
def perf_snapshot():
    performance_guard()
    return _collect_perf_snapshot()


def _rotate_perf_log(max_bytes: int = 10_000_000) -> None:
    try:
        if not PERF_LOG.exists():
            return
        if PERF_LOG.stat().st_size <= max_bytes:
            return
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        rotated = PERF_LOG.with_name(f"perf_stats_{ts}.log")
        PERF_LOG.rename(rotated)
    except Exception:
        pass


def _append_perf_log(entry: dict) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _rotate_perf_log()
        with PERF_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


@app.post("/log/perf")
def log_perf(payload: Dict[str, Any] = Body(default_factory=dict)):
    report = payload.get("report")
    source = str(payload.get("source") or "ui")
    snapshot = payload.get("snapshot")
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "source": source,
        "report": str(report)[:20000] if report else "",
    }
    if snapshot:
        entry["snapshot"] = snapshot
    _append_perf_log(entry)
    return {"ok": True}


# ---- System Audio Controls (PyCaw-backed, optional) ----

def _ensure_audio():
    if AudioUtilities is None:
        raise HTTPException(status_code=503, detail="Audio control unavailable (pycaw missing)")


def _audio_lab_request(path: str, method: str = "GET", payload: Optional[dict] = None) -> dict:
    if not _audio_app:
        raise HTTPException(status_code=503, detail="Audio Lab not available")
    url = f"http://127.0.0.1:{SERVER_PORT}/audio/api{path}"
    try:
        resp = requests.request(method, url, json=payload, timeout=5)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Audio Lab request failed: {exc}")
    if resp.status_code >= 400:
        detail = resp.text or f"Audio Lab error {resp.status_code}"
        raise HTTPException(status_code=resp.status_code, detail=detail)
    try:
        return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Audio Lab invalid response: {exc}")


def _list_audio_sessions():
    _ensure_audio()
    sessions = AudioUtilities.GetAllSessions()
    out = []
    for s in sessions:
        vol = getattr(s._ctl, "SimpleAudioVolume", None)  # type: ignore
        try:
            level = vol.GetMasterVolume() * 100 if vol else None
            mute = vol.GetMute() if vol else None
        except Exception:
            level = None
            mute = None
        out.append(
            {
                "name": s.Process and s.Process.name() or s.DisplayName,
                "pid": s.Process and s.Process.pid,
                "volume": level,
                "mute": mute,
            }
        )
    return out


@app.get("/audio/devices")
def audio_devices():
    """List active audio sessions/devices (playback)"""
    performance_guard()
    data = _audio_lab_request("/system/sessions")
    sessions = data.get("sessions", [])
    mapped = []
    for session in sessions:
        mapped.append(
            {
                "name": session.get("name"),
                "pid": session.get("pid"),
                "volume": None if session.get("volume") is None else float(session.get("volume")) * 100.0,
                "mute": session.get("mute"),
            }
        )
    return {"ok": bool(data.get("available")), "sessions": mapped, "source": "audio_lab"}


class AudioSetRequest(BaseModel):
    pid: Optional[int] = None
    name: Optional[str] = None
    volume: Optional[float] = None  # 0-100
    mute: Optional[bool] = None


@app.post("/audio/set")
def audio_set(req: AudioSetRequest):
    """Set volume/mute for a session by pid or name (best-effort)."""
    performance_guard()
    sessions = _audio_lab_request("/system/sessions")
    if not sessions.get("available"):
        raise HTTPException(status_code=503, detail="Audio Lab sessions unavailable")
    target_id = None
    for s in sessions.get("sessions", []):
        if req.pid is not None and s.get("pid") == req.pid:
            target_id = s.get("id")
            break
        if req.name:
            name = (s.get("name") or "").strip()
            if name and name == req.name:
                target_id = s.get("id")
                break
    if not target_id:
        raise HTTPException(status_code=404, detail="Session not found")
    payload: Dict[str, Any] = {"session_id": target_id}
    if req.volume is not None:
        payload["volume"] = float(max(0, min(100, req.volume))) / 100.0
    if req.mute is not None:
        payload["mute"] = bool(req.mute)
    _audio_lab_request("/system/session", method="POST", payload=payload)
    return {"ok": True, "session": req.model_dump(), "source": "audio_lab"}

def _spawn_safe_disconnect_notice() -> None:
    msg = "Safe to disconnect Phoenix-15."
    try:
        port = 1326
        try:
            backend_url = os.getenv("BJORGSUN_BACKEND_URL", "http://127.0.0.1:1326")
            parsed = urlparse(backend_url)
            if parsed.port:
                port = int(parsed.port)
        except Exception:
            port = 1326
        if sys.platform.startswith("win"):
            ps_script = r"""
$deadline = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $deadline) {
  try {
    $ok = Test-NetConnection -ComputerName 127.0.0.1 -Port __PORT__ -InformationLevel Quiet -WarningAction SilentlyContinue
    if (-not $ok) { break }
  } catch { break }
  Start-Sleep -Milliseconds 300
}
Start-Sleep -Milliseconds 500
try {
  Add-Type -AssemblyName PresentationFramework
  [System.Windows.MessageBox]::Show('Safe to disconnect Phoenix-15.','Phoenix-15') | Out-Null
} catch {
  try {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show('Safe to disconnect Phoenix-15.','Phoenix-15') | Out-Null
  } catch {}
}
"""
            ps_script = ps_script.replace("__PORT__", str(port))
            subprocess.Popen(
                ["powershell", "-NoLogo", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
    except Exception:
        pass


def _spawn_relaunch() -> bool:
    try:
        candidates = [
            _APP_ROOT / "run_tray.bat",
            _APP_ROOT / "launch_phoenix.bat",
            _APP_ROOT / "run_stack.bat",
            _APP_ROOT / "run_desktop.bat",
            _APP_ROOT / "run_web_ui.bat",
        ]
        launcher = next((p for p in candidates if p.exists()), None)
        if not launcher:
            return False
        if os.name == "nt":
            launcher_str = str(launcher).replace("'", "''")
            workdir = str(_APP_ROOT).replace("'", "''")
            ps_script = (
                "Start-Sleep -Seconds 3;"
                f" Start-Process -FilePath \"cmd.exe\" -ArgumentList \"/c\", \"{launcher_str}\""
                f" -WorkingDirectory \"{workdir}\""
            )
            subprocess.Popen(
                ["powershell", "-NoLogo", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["/bin/sh", "-c", f"sleep 3; '{launcher}'"],
                cwd=str(_APP_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return True
    except Exception:
        return False


def _schedule_shutdown() -> None:
    def _rest():
        try:
            ps_script = r"""
$self = $PID
$ppid = (Get-CimInstance Win32_Process -Filter "ProcessId=$self").ParentProcessId
$targets = @($self, $ppid)
# stop ollama if running
$ollama = Get-CimInstance Win32_Process -Filter "Name='ollama.exe'"
if ($ollama) { $targets += $ollama.ProcessId }
$procs = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match 'Bjorgsun-26' -or
    $_.CommandLine -match 'start_ui.py' -or
    $_.CommandLine -match 'server.py' -or
    $_.CommandLine -match 'uvicorn' -or
    $_.CommandLine -match 'run_stack.bat'
}
$targets += $procs | Select-Object -ExpandProperty ProcessId
Stop-Process -Id ($targets | Select-Object -Unique) -Force -ErrorAction SilentlyContinue
"""
            subprocess.Popen(
                ["powershell", "-NoLogo", "-NoProfile", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            os._exit(0)
        except Exception:
            try:
                os._exit(0)
            except Exception:
                pass

    threading.Thread(target=lambda: (time.sleep(0.5), _rest()), daemon=True).start()
    try:
        if shutil.which("notify-send"):
            subprocess.Popen(
                ["notify-send", "Phoenix-15", msg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass

@app.post("/power")
def power():
    # best-effort graceful shutdown
    try:
        _save_devices()
        _save_pending()
        try:
            cm.save_memory()
        except Exception:
            pass
    except Exception:
        pass
    try:
        _spawn_safe_disconnect_notice()
    except Exception:
        pass
    _schedule_shutdown()
    return {"ok": True, "message": "Going to sleep"}

@app.options("/power")
def power_options():
    return {"ok": True}


@app.post("/sleep")
def sleep():
    # soft sleep: save state but keep the stack running
    try:
        _save_devices()
        _save_pending()
        try:
            cm.save_memory()
        except Exception:
            pass
    except Exception:
        pass


def _projectp_is_online(timeout_s: float = 1.2) -> bool:
    if not PROJECTP_URL:
        return False
    try:
        resp = requests.get(f"{PROJECTP_URL}/api/state", timeout=timeout_s)
        return bool(resp.ok)
    except Exception:
        return False


def _start_projectp_server() -> tuple[bool, str]:
    if not PROJECTP_DIR.exists():
        return False, "projectp_dir_missing"
    if not PROJECTP_PY.exists():
        return False, "projectp_python_missing"
    env = os.environ.copy()
    orb_engine = os.getenv("PHX_ORB_PROJECTP_ENGINE", "").strip()
    if orb_engine:
        env["PROJECTP_ENGINE"] = orb_engine
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    try:
        subprocess.Popen(
            [str(PROJECTP_PY), "-m", "backend.run_server"],
            cwd=str(PROJECTP_DIR),
            env=env,
            creationflags=creationflags,
        )
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _wait_for_projectp(timeout_s: float = 12.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _projectp_is_online(timeout_s=1.0):
            return True
        time.sleep(0.4)
    return False


def _ensure_projectp_default_ref() -> None:
    if PROJECTP_REF_META.exists() and PROJECTP_REF_DIR.exists():
        for candidate in PROJECTP_REF_DIR.glob("*.*"):
            if candidate.is_file():
                return
    PROJECTP_REF_DIR.mkdir(parents=True, exist_ok=True)
    width = 512
    height = 512
    image = Image.new("RGB", (width, height), (12, 24, 36))
    for y in range(height):
        blend = y / max(height - 1, 1)
        r = int(12 + (28 - 12) * blend)
        g = int(24 + (64 - 24) * blend)
        b = int(36 + (78 - 36) * blend)
        for x in range(width):
            image.putpixel((x, y), (r, g, b))
    filename = "default.png"
    output_path = PROJECTP_REF_DIR / filename
    image.save(output_path, format="PNG")
    meta = {
        "image": f"/refs/default/{filename}",
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    PROJECTP_REF_META.parent.mkdir(parents=True, exist_ok=True)
    PROJECTP_REF_META.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _compose_orb_prompt(
    thought: str,
    emotion: str,
    state_name: str,
    heartbeat_hz: float,
) -> str:
    parts = [
        "abstract luminous orb core",
        "soft volumetric glow",
        "sci-fi interface aesthetic",
        "teal and deep blue palette",
    ]
    if state_name:
        parts.append(f"state {state_name}")
    if emotion:
        parts.append(f"mood {emotion}")
    if thought:
        parts.append(f"concept {thought}")
    if heartbeat_hz:
        parts.append(f"pulse {heartbeat_hz:.2f} hz")
    parts.append("smooth gradients, clean shapes, minimal noise")
    return ", ".join(parts)


def _projectp_generate_orb_image(
    thought: str,
    emotion: str,
    state_name: str,
    heartbeat_hz: float,
) -> tuple[str, str]:
    prompt = _compose_orb_prompt(thought, emotion, state_name, heartbeat_hz)
    payload = {
        "prompt": prompt,
        "negative_prompt": "text, watermark, logo, letters, clutter, noisy background",
        "width": 384,
        "height": 384,
        "steps": 8,
        "guidance": 5.0,
        "seed": secrets.randbelow(2**31 - 1),
        "mode": "txt2img",
        "strength": 0.55,
        "ref_strength": 0.3,
        "identity_strength": 0.45,
        "style_strength": 0.55,
        "auto_refine": "false",
        "self_refine": "false",
    }
    resp = requests.post(
        f"{PROJECTP_URL}/api/generate",
        data=payload,
        timeout=PROJECTP_TIMEOUT,
    )
    if not resp.ok:
        raise RuntimeError(resp.text or f"Project-P error {resp.status_code}")
    data = resp.json()
    image_url = str(data.get("image_url") or "")
    filename = Path(image_url).name if image_url else ""
    if not filename:
        raise RuntimeError("Project-P response missing image_url")
    output_path = PROJECTP_OUTPUT_DIR / filename
    if not output_path.exists():
        download = requests.get(f"{PROJECTP_URL}{image_url}", timeout=PROJECTP_TIMEOUT)
        if not download.ok:
            raise RuntimeError("Project-P image download failed")
        raw = download.content
    else:
        raw = output_path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    data_url = f"data:image/png;base64,{encoded}"
    return data_url, filename
    return {"ok": True, "message": "Sleep mode enabled"}


@app.options("/sleep")
def sleep_options():
    return {"ok": True}


@app.post("/reboot")
def reboot():
    try:
        _save_devices()
        _save_pending()
        try:
            cm.save_memory()
        except Exception:
            pass
    except Exception:
        pass
    try:
        _spawn_safe_disconnect_notice()
    except Exception:
        pass
    _spawn_relaunch()
    _schedule_shutdown()
    return {"ok": True, "message": "Rebooting"}


@app.options("/reboot")
def reboot_options():
    return {"ok": True}

@app.post("/sleep")
def sleep():
    try:
        _save_devices()
        _save_pending()
    except Exception:
        pass
    return {"ok": True, "message": "Sleeping"}

@app.post("/files/open")
def files_open(body: Dict[str, Any]):
    path = (body or {}).get("path")
    target = Path(path).expanduser().resolve() if path else BASE_DIR
    if not target.exists():
        target = BASE_DIR
    try:
        if sys.platform.startswith("win"):
            if target.is_file():
                subprocess.Popen(
                    ["explorer", f"/select,{target}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["explorer", str(target)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        else:
            subprocess.Popen(
                ["xdg-open", str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as exc:
        logging.exception("open file browser failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return {"ok": True, "path": str(target)}


def _get_volume_label(path: str) -> str:
    if not sys.platform.startswith("win"):
        return ""
    try:
        name_buf = ctypes.create_unicode_buffer(1024)
        fs_buf = ctypes.create_unicode_buffer(1024)
        serial = ctypes.c_uint()
        max_comp_len = ctypes.c_uint()
        flags = ctypes.c_uint()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(path),
            name_buf,
            ctypes.sizeof(name_buf),
            ctypes.byref(serial),
            ctypes.byref(max_comp_len),
            ctypes.byref(flags),
            fs_buf,
            ctypes.sizeof(fs_buf),
        )
        if ok:
            return name_buf.value or ""
    except Exception:
        pass
    return ""


def _get_drive_type(path: str) -> int:
    if not sys.platform.startswith("win"):
        return 0
    try:
        return int(ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(path)))  # type: ignore[attr-defined]
    except Exception:
        return 0


def _list_removable_drives() -> List[Dict[str, str]]:
    drives: List[Dict[str, str]] = []
    if not sys.platform.startswith("win"):
        return drives
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if not os.path.exists(root):
            continue
        if _get_drive_type(root) != 2:
            continue
        drives.append({"root": root, "label": _get_volume_label(root)})
    return drives


def _resolve_ui_dist() -> Optional[Path]:
    candidates = [
        _APP_ROOT / "ui" / "scifiaihud" / "build",
        _APP_ROOT / "ui" / "build",
    ]
    for path in candidates:
        if (path / "index.html").exists():
            return path
    return None


REMOTE_UI_DIST = _resolve_ui_dist()


def _remote_ui_enabled() -> bool:
    try:
        settings = settings_store.get()
        return bool(settings.get("remoteUiEnabled"))
    except Exception:
        return False


def _remote_ui_host() -> str:
    try:
        settings = settings_store.get()
        host = str(settings.get("remoteUiHost") or "CHII.inc").strip()
        return host or "CHII.inc"
    except Exception:
        return "CHII.inc"


def _get_local_ips() -> List[str]:
    ips: set[str] = set()
    try:
        for _, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and addr.address and not addr.address.startswith("127."):
                    ips.add(addr.address)
    except Exception:
        pass
    return sorted(ips)


REMOTE_TUNNEL_STATE: Dict[str, Any] = {
    "running": False,
    "url": "",
    "error": "",
    "code": "",
    "pid": None,
    "started_at": None,
}
REMOTE_TUNNEL_LOCK = threading.Lock()
REMOTE_TUNNEL_PROC: subprocess.Popen | None = None
REMOTE_TUNNEL_URL_RE = re.compile(r"https?://[a-z0-9-]+\\.trycloudflare\\.com", re.I)


def _append_tunnel_log(message: str) -> None:
    _append_sync_log(REMOTE_TUNNEL_LOG, message)


def _set_remote_tunnel_state(**updates: Any) -> None:
    with REMOTE_TUNNEL_LOCK:
        REMOTE_TUNNEL_STATE.update(updates)


def _cloudflared_download_url() -> str:
    if sys.platform.startswith("win"):
        return "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    if sys.platform.startswith("linux"):
        return "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
    return ""


def _cloudflared_path() -> Path:
    if sys.platform.startswith("win"):
        return TOOLS_DIR / "cloudflared.exe"
    return TOOLS_DIR / "cloudflared"


def _ensure_cloudflared() -> Path:
    path = _cloudflared_path()
    if path.exists():
        return path
    existing = shutil.which("cloudflared")
    if existing:
        return Path(existing)
    url = _cloudflared_download_url()
    if not url:
        raise RuntimeError("cloudflared download not supported on this OS.")
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    _append_tunnel_log(f"Downloading cloudflared from {url}")
    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        with path.open("wb") as handle:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    except Exception as exc:
        raise RuntimeError(f"cloudflared download failed: {exc}") from exc
    return path


def _monitor_remote_tunnel(proc: subprocess.Popen) -> None:
    exit_code = None
    try:
        exit_code = proc.wait()
    except Exception:
        exit_code = None
    with REMOTE_TUNNEL_LOCK:
        if REMOTE_TUNNEL_PROC is not proc:
            return
        REMOTE_TUNNEL_STATE["running"] = False
        REMOTE_TUNNEL_STATE["pid"] = None
        if not REMOTE_TUNNEL_STATE.get("error"):
            message = f"Tunnel exited with code {exit_code}." if exit_code is not None else "Tunnel exited."
            REMOTE_TUNNEL_STATE["error"] = message
            REMOTE_TUNNEL_STATE["code"] = "PHX-TNL-500"
    _append_tunnel_log(f"Tunnel stopped (code={exit_code}).")


def _stream_remote_tunnel_output(proc: subprocess.Popen) -> None:
    try:
        if not proc.stdout:
            return
        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue
            _append_tunnel_log(line)
            match = REMOTE_TUNNEL_URL_RE.search(line)
            if match:
                url = match.group(0)
                _set_remote_tunnel_state(url=url, running=True, error="", code="PHX-TNL-000")
    except Exception as exc:
        _append_tunnel_log(f"Tunnel log reader error: {exc}")


def _remote_tunnel_status() -> Dict[str, Any]:
    with REMOTE_TUNNEL_LOCK:
        state = REMOTE_TUNNEL_STATE.copy()
    running = bool(state.get("running"))
    url = str(state.get("url") or "")
    error = str(state.get("error") or "")
    code = str(state.get("code") or "")
    message = "Tunnel running." if running else "Tunnel idle."
    if error:
        message = error
    return {
        "running": running,
        "url": url,
        "error": error,
        "code": code,
        "pid": state.get("pid"),
        "started_at": state.get("started_at"),
        "log": str(REMOTE_TUNNEL_LOG),
        "message": message,
    }


def _start_remote_tunnel() -> Dict[str, Any]:
    global REMOTE_TUNNEL_PROC
    with REMOTE_TUNNEL_LOCK:
        if REMOTE_TUNNEL_PROC and REMOTE_TUNNEL_PROC.poll() is None:
            return _remote_tunnel_status()
    try:
        exe = _ensure_cloudflared()
    except Exception as exc:
        _set_remote_tunnel_state(
            running=False,
            url="",
            error=str(exc),
            code="PHX-TNL-404",
            pid=None,
        )
        _append_tunnel_log(f"Tunnel start failed: {exc}")
        return _remote_tunnel_status()
    target = f"http://127.0.0.1:{SERVER_PORT}"
    args = [str(exe), "tunnel", "--url", target, "--no-autoupdate"]
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=creation_flags,
        )
    except Exception as exc:
        _set_remote_tunnel_state(
            running=False,
            url="",
            error=f"Tunnel start failed: {exc}",
            code="PHX-TNL-500",
            pid=None,
        )
        _append_tunnel_log(f"Tunnel start failed: {exc}")
        return _remote_tunnel_status()
    with REMOTE_TUNNEL_LOCK:
        REMOTE_TUNNEL_PROC = proc
        REMOTE_TUNNEL_STATE.update(
            {
                "running": True,
                "url": "",
                "error": "",
                "code": "PHX-TNL-000",
                "pid": proc.pid,
                "started_at": datetime.utcnow().isoformat() + "Z",
            }
        )
    _append_tunnel_log(f"Tunnel starting: {' '.join(args)}")
    threading.Thread(target=_stream_remote_tunnel_output, args=(proc,), daemon=True).start()
    threading.Thread(target=_monitor_remote_tunnel, args=(proc,), daemon=True).start()
    return _remote_tunnel_status()


def _stop_remote_tunnel() -> Dict[str, Any]:
    global REMOTE_TUNNEL_PROC
    proc = None
    with REMOTE_TUNNEL_LOCK:
        proc = REMOTE_TUNNEL_PROC
        REMOTE_TUNNEL_PROC = None
        REMOTE_TUNNEL_STATE.update(
            {"running": False, "url": "", "error": "", "code": "", "pid": None}
        )
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass
    _append_tunnel_log("Tunnel stopped by request.")
    return _remote_tunnel_status()


def _append_sync_log(log_path: Path, message: str) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", errors="ignore") as handle:
            ts = datetime.utcnow().isoformat() + "Z"
            handle.write(f"[{ts}] {message}\n")
    except Exception:
        pass


def _load_echoes() -> Dict[str, Any]:
    try:
        if ECHOES_FILE.exists():
            return json.loads(ECHOES_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"updated_at": None, "echoes": []}


def _save_echoes(data: Dict[str, Any]) -> None:
    try:
        ECHOES_FILE.parent.mkdir(parents=True, exist_ok=True)
        ECHOES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _normalize_echo_root(path: str | Path | None) -> Optional[Path]:
    if not path:
        return None
    try:
        root = Path(path).expanduser().resolve()
        if root.exists():
            return root
    except Exception:
        return None
    return None


def _get_usb_root_from_drive(drive: str) -> Optional[Path]:
    drive_str = drive.replace("/", "\\")
    if len(drive_str) >= 2 and drive_str[1] == ":":
        root = Path(drive_str[:2] + "\\")
    else:
        root = Path(drive_str)
    root = _normalize_echo_root(root)
    if not root:
        return None
    candidate = root / "Bjorgsun-26"
    if candidate.exists():
        return candidate
    if (root / "RUN_PHOENIX_15.bat").exists():
        return root
    return root


def _find_usb_echo() -> Optional[Path]:
    for entry in _list_removable_drives():
        root = entry.get("root") or ""
        if not root:
            continue
        candidate = _get_usb_root_from_drive(root)
        if candidate and (candidate / "RUN_PHOENIX_15.bat").exists():
            return candidate
    return None


def _collect_echo_roots(drive: Optional[str] = None, local_path: Optional[str] = None) -> List[Path]:
    roots: List[Path] = []
    canonical = _normalize_echo_root(CANONICAL_ROOT_PATH)
    if canonical:
        roots.append(canonical)
    local_root = _normalize_echo_root(local_path)
    if local_root and local_root not in roots:
        roots.append(local_root)
    usb_root = _get_usb_root_from_drive(drive) if drive else _find_usb_echo()
    if usb_root and usb_root not in roots:
        roots.append(usb_root)
    return roots


def _echo_health(root: Path) -> Dict[str, Any]:
    required = [
        root / "RUN_PHOENIX_15.bat",
        root / "app" / "server" / "server.py",
        root / "app" / "ui" / "scifiaihud" / "build" / "index.html",
    ]
    issues: List[str] = []
    for path in required:
        if not path.exists():
            issues.append(f"missing:{path.relative_to(root)}")
        else:
            try:
                if path.stat().st_size <= 0:
                    issues.append(f"empty:{path.relative_to(root)}")
            except Exception:
                issues.append(f"unreadable:{path.relative_to(root)}")
    memory_path = root / "app" / "data" / "memory.json"
    if memory_path.exists():
        try:
            json.loads(memory_path.read_text(encoding="utf-8"))
        except Exception:
            issues.append("memory.json:invalid")
    return {
        "root": str(root),
        "ok": not issues,
        "issues": issues,
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }


def _run_robocopy(src: Path, dest: Path, log_path: Path, label: str) -> int:
    cmd = [
        "robocopy",
        str(src),
        str(dest),
        "/E",
        "/COPY:DAT",
        "/DCOPY:DAT",
        "/XO",
        "/XJ",
        "/R:1",
        "/W:1",
        "/NP",
        f"/LOG+:{log_path}",
    ]
    _append_sync_log(log_path, f"robocopy {label}: {src} -> {dest}")
    try:
        completed = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return int(completed.returncode or 0)
    except Exception as exc:
        _append_sync_log(log_path, f"robocopy failed ({label}): {exc}")
        return 16


def _sync_echoes(drive: Optional[str], local_path: Optional[str], log_path: Path) -> Dict[str, Any]:
    echoes = _collect_echo_roots(drive, local_path)
    if not echoes:
        _append_sync_log(log_path, "No echoes detected for sync.")
        return {"ok": False, "message": "No echoes found."}
    health = [_echo_health(root) for root in echoes]
    _append_sync_log(log_path, f"Echo health: {json.dumps(health)}")
    echo_state = {"updated_at": datetime.utcnow().isoformat() + "Z", "echoes": health}
    _save_echoes(echo_state)
    if len(echoes) < 2:
        _append_sync_log(log_path, "Only one echo present; sync skipped.")
        return {"ok": True, "message": "Only one echo present.", "health": health}
    primary = echoes[0]
    for target in echoes[1:]:
        _run_robocopy(primary, target, log_path, "primary_to_echo")
        _run_robocopy(target, primary, log_path, "echo_to_primary")
    return {"ok": True, "message": "Sync complete.", "health": health}


@app.get("/usb/drives")
def usb_drives():
    return {"ok": True, "drives": _list_removable_drives()}


class UsbOpenRequest(BaseModel):
    path: Optional[str] = None


@app.post("/usb/open")
def usb_open(req: UsbOpenRequest):
    path = (req.path or "").strip()
    if not path:
        raise HTTPException(status_code=400, detail="Missing USB path")
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(target))
            return {"ok": True, "path": str(target)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    raise HTTPException(status_code=500, detail="Unsupported platform")


class UsbCopyRequest(BaseModel):
    drive: str
    target_folder: Optional[str] = None
    source: Optional[str] = None
    include_os: Optional[bool] = None
    include_app: Optional[bool] = None
    include_memory: Optional[bool] = None
    include_user_data: Optional[bool] = None
    preset: Optional[str] = None


@app.post("/usb/copy")
def usb_copy(req: UsbCopyRequest):
    drive = (req.drive or "").strip()
    if not drive:
        raise HTTPException(status_code=400, detail="Drive is required")
    drive_str = drive.replace("/", "\\")
    if len(drive_str) >= 2 and drive_str[1] == ":":
        root = Path(drive_str[:2] + "\\")
    else:
        root = Path(drive_str)
    if not root.exists():
        raise HTTPException(status_code=404, detail="Drive not found")
    if sys.platform.startswith("win") and _get_drive_type(str(root)) != 2:
        raise HTTPException(status_code=400, detail="Drive is not removable")
    source = Path(req.source).expanduser().resolve() if req.source else _APP_ROOT.parent
    target = (
        Path(req.target_folder).expanduser().resolve()
        if req.target_folder
        else root / "Bjorgsun-26"
    )
    logging.info(
        "USB copy selection preset=%s include_os=%s include_app=%s include_memory=%s include_user_data=%s",
        req.preset or "",
        req.include_os,
        req.include_app,
        req.include_memory,
        req.include_user_data,
    )
    if source.drive and target.drive and source.drive.lower() == target.drive.lower():
        raise HTTPException(status_code=400, detail="Source and target drive are the same")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"usb_copy_{ts}.log"
    cmd = [
        "robocopy",
        str(source),
        str(target),
        "/E",
        "/COPY:DAT",
        "/DCOPY:DAT",
        "/XJ",
        "/R:1",
        "/W:1",
        f"/LOG:{log_path}",
    ]
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"ok": True, "log": str(log_path), "target": str(target)}


class UsbSyncRequest(BaseModel):
    drive: Optional[str] = None
    local_path: Optional[str] = None


def _usb_sync_worker(drive: Optional[str], local_path: Optional[str], log_path: Path) -> None:
    try:
        _append_sync_log(log_path, "Echo sync started.")
        result = _sync_echoes(drive, local_path, log_path)
        USB_SYNC_STATE["last_error"] = None if result.get("ok") else result.get("message")
        USB_SYNC_STATE["last_sync"] = datetime.utcnow().isoformat() + "Z"
        USB_SYNC_STATE["last_sync_ts"] = time.time()
        _append_sync_log(log_path, f"Echo sync result: {result}")
    except Exception as exc:
        USB_SYNC_STATE["last_error"] = str(exc)
        _append_sync_log(log_path, f"Echo sync crashed: {exc}")
    finally:
        USB_SYNC_STATE["running"] = False


def _start_usb_sync(drive: Optional[str], local_path: Optional[str]) -> Dict[str, Any]:
    with USB_SYNC_LOCK:
        if USB_SYNC_STATE.get("running"):
            return {"ok": False, "message": "Sync already running.", "state": USB_SYNC_STATE}
        USB_SYNC_STATE["running"] = True
        USB_SYNC_STATE["last_error"] = None
        USB_SYNC_STATE["last_drive"] = drive
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_path = LOG_DIR / f"echo_sync_{ts}.log"
        USB_SYNC_STATE["last_log"] = str(log_path)
    thread = threading.Thread(
        target=_usb_sync_worker, args=(drive, local_path, log_path), daemon=True
    )
    thread.start()
    return {"ok": True, "running": True, "log": str(log_path)}


@app.get("/usb/sync/status")
def usb_sync_status():
    return {
        "running": USB_SYNC_STATE.get("running", False),
        "last_sync": USB_SYNC_STATE.get("last_sync"),
        "last_error": USB_SYNC_STATE.get("last_error"),
        "last_drive": USB_SYNC_STATE.get("last_drive"),
        "last_log": USB_SYNC_STATE.get("last_log"),
        "echoes": _load_echoes().get("echoes", []),
    }


@app.post("/usb/sync")
def usb_sync(req: UsbSyncRequest):
    local_path = (req.local_path or "").strip()
    drive = (req.drive or "").strip() or None
    if not local_path:
        try:
            settings = settings_store.get()
            local_path = str(settings.get("usbLocalBootPath") or "")
        except Exception:
            local_path = ""
    return _start_usb_sync(drive, local_path or None)

@app.get("/devmode/status")
def devmode_status():
    return {"ok": True, "enabled": _dev_enabled}


@app.post("/devmode/enable")
def devmode_enable(body: Dict[str, Any]):
    global _dev_enabled
    pw = (body.get("password") or "").strip()
    if not DEV_MODE_PASSWORD:
        raise HTTPException(status_code=400, detail="DEV_MODE_PASSWORD not set on server")
    if pw != DEV_MODE_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    _dev_enabled = True
    return {"ok": True, "enabled": True}


@app.post("/dev/access/verify")
def dev_access_verify(dev_key: str | None = Header(default=None)):
    _ensure_dev(dev_key)
    return {"ok": True}


@app.get("/ollama/status")
def ollama_status():
    try:
        resp = requests.get(f"{OLLAMA_ENDPOINT}/api/tags", timeout=2)
        return {"ok": resp.status_code == 200}
    except Exception:
        return {"ok": False}


@app.post("/ollama/start")
def ollama_start():
    ok = _ensure_ollama_running()
    return {"ok": ok}


def _ensure_ollama_running() -> bool:
    """Ping Ollama; if down and local endpoint, attempt to start."""
    try:
        resp = requests.get(f"{OLLAMA_ENDPOINT}/api/tags", timeout=2)
        if resp.status_code == 200:
            return True
    except Exception:
        pass
    # only try to start if localhost
    if "127.0.0.1" not in OLLAMA_ENDPOINT and "localhost" not in OLLAMA_ENDPOINT:
        return False
    ollama_dir = Path(os.getenv("LOCALAPPDATA", r"C:\\Users\\%USERNAME%\\AppData\\Local")) / "Programs" / "Ollama"
    if not (ollama_dir / "ollama.exe").exists():
        pf_dir = Path(os.getenv("ProgramFiles", r"C:\\Program Files")) / "Ollama"
        if pf_dir.exists():
            ollama_dir = pf_dir
    exe = ollama_dir / "ollama.exe"
    if not exe.exists():
        return False
    try:
        import subprocess

        subprocess.Popen([str(exe), "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        resp = requests.get(f"{OLLAMA_ENDPOINT}/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


@app.get("/logs/tail")
def logs_tail(lines: int = 50):
    performance_guard()
    logs = []
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    candidates = [
        LOG_DIR / "core_run.log",
        LOG_DIR / "core_crash.log",
        LOG_DIR / "ui_actions.log",
        LOG_DIR / "start_ui_stdout.log",
        LOG_DIR / "ui_crash.log",
        LOG_DIR / "server_stdout.log",
    ]
    for path in candidates:
        if path.exists():
            try:
                tail = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-lines:]
                logs.extend(tail)
            except Exception:
                pass
    return {"ok": True, "lines": logs[-lines:]}


@app.get("/logs/open")
def logs_open():
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(LOG_DIR))
        _emit_alert("logs_opened", "Logs folder opened", severity="info")
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/tts")
async def tts_generate(payload: Dict[str, Any]):
    """
    Generate speech via edge-tts (local). Requires edge-tts installed.
    Returns audio/mpeg stream.
    """
    performance_guard()
    if edge_tts is None:
        raise HTTPException(status_code=503, detail="edge-tts not available")
    text = _sanitize_tts_text(payload.get("text") or "")
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    if len(text) > 1200:
        text = text[:1200].rsplit(" ", 1)[0] + "..."
    voice = payload.get("voice") or "en-US-AriaNeural"
    pitch = payload.get("pitch") or "+5%"
    rate = payload.get("rate") or "-5%"

    try:
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    except Exception:
        # Fallback: plain text without prosody modifiers.
        communicate = edge_tts.Communicate(text, voice=voice)

    async def gen():
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    return StreamingResponse(gen(), media_type="audio/mpeg")


# ---- Spotify integration (Web API + OAuth) ----

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_ALLOWED_REPEAT = {"off", "context", "track"}


def _spotify_client_id() -> str:
    return os.getenv("SPOTIFY_CLIENT_ID", "").strip()


def _spotify_redirect_uri() -> str:
    return os.getenv("SPOTIFY_REDIRECT_URI", f"http://127.0.0.1:{SERVER_PORT}/spotify/callback").strip()


def _spotify_base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _spotify_save_state(state: Dict[str, Any]) -> None:
    try:
        SPOTIFY_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def _spotify_load_state() -> Dict[str, Any]:
    if not SPOTIFY_STATE_FILE.exists():
        return {}
    try:
        data = json.loads(SPOTIFY_STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _spotify_save_oauth(state: Dict[str, Any]) -> None:
    try:
        SPOTIFY_OAUTH_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def _spotify_load_oauth() -> Dict[str, Any]:
    if not SPOTIFY_OAUTH_FILE.exists():
        return {}
    try:
        data = json.loads(SPOTIFY_OAUTH_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _spotify_clear_oauth() -> None:
    try:
        if SPOTIFY_OAUTH_FILE.exists():
            SPOTIFY_OAUTH_FILE.unlink()
    except Exception:
        pass


def _spotify_set_state(data: Dict[str, Any]) -> None:
    global _spotify_state
    _spotify_state = data
    _spotify_save_state(_spotify_state)


def _spotify_token_expired() -> bool:
    expires_at = float(_spotify_state.get("expires_at") or 0)
    return time.time() >= (expires_at - 60)


def _spotify_refresh_token() -> None:
    refresh_token = _spotify_state.get("refresh_token")
    client_id = _spotify_client_id()
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Spotify refresh token missing.")
    if not client_id:
        raise HTTPException(status_code=400, detail="SPOTIFY_CLIENT_ID not set.")
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    resp = requests.post(SPOTIFY_TOKEN_URL, data=payload, timeout=8)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    updated = dict(_spotify_state)
    updated["access_token"] = data.get("access_token")
    updated["expires_at"] = time.time() + int(data.get("expires_in", 3600))
    if data.get("refresh_token"):
        updated["refresh_token"] = data.get("refresh_token")
    if data.get("scope"):
        updated["scope"] = data.get("scope")
    _spotify_set_state(updated)


def _spotify_get_access_token() -> str:
    if not _spotify_state or not _spotify_state.get("access_token"):
        raise HTTPException(status_code=400, detail="Spotify not connected.")
    if _spotify_token_expired():
        _spotify_refresh_token()
    token = _spotify_state.get("access_token")
    if not token:
        raise HTTPException(status_code=400, detail="Spotify token missing.")
    return token


def _spotify_request(method: str, path: str, params: Optional[Dict[str, Any]] = None, payload: Any = None):
    token = _spotify_get_access_token()
    url = f"{SPOTIFY_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.request(method, url, headers=headers, params=params, json=payload, timeout=8)
    if resp.status_code == 401 and _spotify_state.get("refresh_token"):
        _spotify_refresh_token()
        token = _spotify_state.get("access_token")
        headers["Authorization"] = f"Bearer {token}"
        resp = requests.request(method, url, headers=headers, params=params, json=payload, timeout=8)
    return resp


def _spotify_json_or_empty(resp: requests.Response) -> Dict[str, Any]:
    if resp.status_code == 204:
        return {}
    text = resp.text.strip()
    if not text:
        return {}
    try:
        return resp.json()
    except Exception:
        return {}


def _spotify_parse_context(value: str) -> Dict[str, Any]:
    cleaned = (value or "").strip()
    if not cleaned:
        return {}
    if cleaned.startswith("spotify:"):
        parts = cleaned.split(":")
        if len(parts) >= 3:
            kind = parts[1]
            ident = parts[2]
            if kind in {"track", "episode"}:
                return {"uris": [f"spotify:{kind}:{ident}"]}
            return {"context_uri": f"spotify:{kind}:{ident}"}
        return {}
    match = re.search(
        r"open\\.spotify\\.com\\/(track|album|playlist|artist|episode|show)\\/([A-Za-z0-9]+)",
        cleaned,
    )
    if match:
        kind, ident = match.groups()
        if kind in {"track", "episode"}:
            return {"uris": [f"spotify:{kind}:{ident}"]}
        return {"context_uri": f"spotify:{kind}:{ident}"}
    return {}


def _spotify_html(message: str) -> HTMLResponse:
    html_body = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Spotify Auth</title>
    <style>
      body {{
        margin: 0;
        font-family: "Segoe UI", sans-serif;
        background: #0b1016;
        color: #d9f7ff;
        display: grid;
        place-items: center;
        height: 100vh;
      }}
      .card {{
        padding: 24px 28px;
        border: 1px solid rgba(62, 242, 224, 0.35);
        border-radius: 14px;
        background: rgba(9, 22, 34, 0.85);
        box-shadow: 0 18px 60px rgba(2, 8, 16, 0.7);
        text-align: center;
        max-width: 420px;
      }}
      .title {{
        text-transform: uppercase;
        letter-spacing: 0.2em;
        font-size: 0.85rem;
        margin-bottom: 10px;
      }}
      .hint {{
        color: rgba(217, 247, 255, 0.7);
        font-size: 0.85rem;
      }}
    </style>
  </head>
  <body>
    <div class="card">
      <div class="title">Spotify Connect</div>
      <div class="hint">{message}</div>
    </div>
  </body>
</html>"""
    return HTMLResponse(html_body)


_spotify_state = _spotify_load_state()
_spotify_oauth = _spotify_load_oauth()


class SpotifyConfig(BaseModel):
    token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    scope: Optional[str] = None


@app.post("/spotify/config")
def spotify_config(cfg: SpotifyConfig):
    """Store a bearer token manually (legacy). Prefer /spotify/auth."""
    token = cfg.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="token required")
    expires_in = cfg.expires_in or 3600
    _spotify_set_state(
        {
            "access_token": token,
            "refresh_token": cfg.refresh_token,
            "expires_at": time.time() + int(expires_in),
            "scope": cfg.scope or "",
        }
    )
    return {"ok": True}


@app.get("/spotify/auth")
def spotify_auth():
    client_id = _spotify_client_id()
    redirect_uri = _spotify_redirect_uri()
    if not client_id:
        raise HTTPException(status_code=400, detail="SPOTIFY_CLIENT_ID not set")
    code_verifier = _spotify_base64url(secrets.token_bytes(64))
    challenge = _spotify_base64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
    state = _spotify_base64url(secrets.token_bytes(16))
    _spotify_oauth.update({"state": state, "code_verifier": code_verifier, "created_at": time.time()})
    _spotify_save_oauth(_spotify_oauth)
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "scope": SPOTIFY_SCOPES,
        "state": state,
    }
    return {"url": f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"}


@app.get("/spotify/callback")
def spotify_callback(code: str = "", state: str = "", error: Optional[str] = None):
    if error:
        return _spotify_html(f"Authorization failed: {error}")
    oauth = _spotify_oauth or _spotify_load_oauth()
    if not oauth or state != oauth.get("state"):
        return _spotify_html("Authorization state mismatch.")
    client_id = _spotify_client_id()
    redirect_uri = _spotify_redirect_uri()
    if not client_id:
        return _spotify_html("Missing SPOTIFY_CLIENT_ID.")
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": oauth.get("code_verifier", ""),
    }
    resp = requests.post(SPOTIFY_TOKEN_URL, data=payload, timeout=8)
    if resp.status_code != 200:
        return _spotify_html("Token exchange failed.")
    data = resp.json()
    _spotify_set_state(
        {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "expires_at": time.time() + int(data.get("expires_in", 3600)),
            "scope": data.get("scope", ""),
        }
    )
    _spotify_oauth.clear()
    _spotify_clear_oauth()
    return _spotify_html("Connected. You can return to Bjorgsun-26.")


@app.post("/spotify/disconnect")
def spotify_disconnect():
    _spotify_set_state({})
    return {"ok": True}


@app.get("/spotify/status")
def spotify_status():
    if not _spotify_state or not _spotify_state.get("access_token"):
        return {"authorized": False}
    profile = {}
    player = {}
    try:
        resp = _spotify_request("GET", "/me")
        if resp.status_code == 200:
            profile = _spotify_json_or_empty(resp)
        player_resp = _spotify_request("GET", "/me/player")
        if player_resp.status_code in (200, 204):
            player = _spotify_json_or_empty(player_resp)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"authorized": True, "profile": profile, "player": player}


@app.get("/spotify/now")
def spotify_now():
    """Get current playback info."""
    try:
        resp = _spotify_request("GET", "/me/player")
        if resp.status_code == 204:
            return {"ok": True, "status": "inactive"}
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        data = _spotify_json_or_empty(resp)
        return {"ok": True, "status": "playing", "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/spotify/devices")
def spotify_devices():
    resp = _spotify_request("GET", "/me/player/devices")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return _spotify_json_or_empty(resp)


class SpotifyTransfer(BaseModel):
    device_id: str
    play: Optional[bool] = True


@app.post("/spotify/transfer")
def spotify_transfer(req: SpotifyTransfer):
    payload = {"device_ids": [req.device_id], "play": bool(req.play)}
    resp = _spotify_request("PUT", "/me/player", payload=payload)
    if resp.status_code not in (200, 202, 204):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"ok": True}


class SpotifyPlayRequest(BaseModel):
    context: Optional[str] = None
    position_ms: Optional[int] = None


@app.post("/spotify/play")
def spotify_play(req: SpotifyPlayRequest):
    payload: Dict[str, Any] = {}
    context = _spotify_parse_context(req.context or "")
    if context:
        payload.update(context)
    if req.position_ms is not None:
        payload["position_ms"] = max(0, int(req.position_ms))
    resp = _spotify_request("PUT", "/me/player/play", payload=payload or None)
    if resp.status_code not in (200, 202, 204):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"ok": True}


@app.post("/spotify/pause")
def spotify_pause():
    resp = _spotify_request("PUT", "/me/player/pause")
    if resp.status_code not in (200, 202, 204):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"ok": True}


@app.post("/spotify/next")
def spotify_next():
    resp = _spotify_request("POST", "/me/player/next")
    if resp.status_code not in (200, 202, 204):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"ok": True}


@app.post("/spotify/previous")
def spotify_previous():
    resp = _spotify_request("POST", "/me/player/previous")
    if resp.status_code not in (200, 202, 204):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"ok": True}


class SpotifyVolume(BaseModel):
    volume: int


@app.post("/spotify/volume")
def spotify_volume(req: SpotifyVolume):
    volume = max(0, min(100, int(req.volume)))
    resp = _spotify_request("PUT", "/me/player/volume", params={"volume_percent": volume})
    if resp.status_code not in (200, 202, 204):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"ok": True}


class SpotifyShuffle(BaseModel):
    enabled: bool


@app.post("/spotify/shuffle")
def spotify_shuffle(req: SpotifyShuffle):
    resp = _spotify_request("PUT", "/me/player/shuffle", params={"state": str(bool(req.enabled)).lower()})
    if resp.status_code not in (200, 202, 204):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"ok": True}


class SpotifyRepeat(BaseModel):
    mode: str


@app.post("/spotify/repeat")
def spotify_repeat(req: SpotifyRepeat):
    mode = (req.mode or "off").lower()
    if mode not in SPOTIFY_ALLOWED_REPEAT:
        raise HTTPException(status_code=400, detail="repeat mode must be off, context, or track")
    resp = _spotify_request("PUT", "/me/player/repeat", params={"state": mode})
    if resp.status_code not in (200, 202, 204):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"ok": True}


class SpotifySeek(BaseModel):
    position_ms: int


@app.post("/spotify/seek")
def spotify_seek(req: SpotifySeek):
    pos = max(0, int(req.position_ms))
    resp = _spotify_request("PUT", "/me/player/seek", params={"position_ms": pos})
    if resp.status_code not in (200, 202, 204):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"ok": True}


class SpotifyCommand(BaseModel):
    action: Literal["play", "pause", "next", "prev"]


@app.post("/spotify/control")
def spotify_control(cmd: SpotifyCommand):
    action = cmd.action
    if action == "play":
        return spotify_play(SpotifyPlayRequest())
    if action == "pause":
        return spotify_pause()
    if action == "next":
        return spotify_next()
    if action == "prev":
        return spotify_previous()
    raise HTTPException(status_code=400, detail="Unsupported action")


@app.post("/log/client")
def log_client(body: dict[str, Any]):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        msg = body.get("message") or ""
        detail = body.get("detail") or ""
        with CLIENT_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()}Z {msg} {detail}\n")
        code = body.get("code") or _extract_issue_code(str(msg), str(detail))
        _log_issue(code, str(msg), str(detail), severity="warn", source="client")
    except Exception:
        pass
    return {"ok": True}


@app.post("/log/issue")
def log_issue(body: dict[str, Any]):
    code = str(body.get("code") or "PHX-UNK-000")
    message = str(body.get("message") or "")
    detail = str(body.get("detail") or "")
    severity = str(body.get("severity") or "error")
    source = str(body.get("source") or "client")
    context = body.get("context") if isinstance(body.get("context"), dict) else {}
    _log_issue(code, message, detail, severity=severity, source=source, context=context)
    return {"ok": True}


@app.post("/memory/add")
def add_memory(req: MemoryAddRequest):
    performance_guard()
    role = (req.role or "user").lower()
    if role not in {"user", "assistant", "system"}:
        role = "user"
    item = memory_store.add(req.text, role=role)
    return {"id": item.id, "text": item.text, "timestamp": item.timestamp, "role": item.role}


@app.get("/memory/list")
def list_memories():
    performance_guard()
    items = memory_store.list()
    return [vars(m) for m in items]


@app.get("/memory/export")
def export_memories(label: str | None = None):
    """Export current memory to data/memory_exports and return the path."""
    performance_guard()
    path = memory_store.export_snapshot(label)
    if not path:
        raise HTTPException(status_code=500, detail="Failed to export memory.")
    return {"ok": True, "path": str(path)}


@app.get("/memory/info")
def memory_info():
    """Report the active memory path and counts to verify recall wiring."""
    performance_guard()
    items = memory_store.list()
    return {
        "path": str(memory_store.path),
        "count": len(items),
        "entries": len(items),
        "persist": True,
        "export_dir": str(memory_store.path.parent / "memory_exports"),
    }


@app.post("/memory/reload")
def memory_reload():
    """Reload memory from disk and re-hydrate primer/handoff."""
    performance_guard()
    mem = _refresh_memory("reload")
    return {"ok": True, "count": mem["count"], "path": str(memory_store.path), "hint": mem.get("hint")}


@app.post("/memory/delete")
def delete_memory(req: MemoryDeleteRequest):
    performance_guard()
    deleted = memory_store.delete(req.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory ID not found.")
    return {"status": "ok"}


@app.post("/memory/check")
def memory_check():
    """Validate memory on demand; re-hydrate handoff/primer if needed."""
    performance_guard()
    mem = _refresh_memory("check")
    return {"ok": True, "count": mem.get("count"), "hint": mem.get("hint")}


def _apply_phoenix_update(req: PhoenixUpdateRequest) -> dict[str, Any]:
    state = _load_phoenix_state()
    updated = False
    if req.home_state:
        state["home_state"] = req.home_state
        updated = True
    if req.mood_label:
        mood = state.get("mood") or {}
        mood["label"] = req.mood_label
        state["mood"] = mood
        updated = True
    if req.mood_intensity is not None:
        mood = state.get("mood") or {}
        mood["intensity"] = max(0.0, min(1.0, float(req.mood_intensity)))
        state["mood"] = mood
        updated = True
    if req.notifications_allowed is not None:
        state["notifications_allowed"] = bool(req.notifications_allowed)
        updated = True
    if req.bag_inventory:
        state["bag_inventory"] = {k: bool(v) for k, v in req.bag_inventory.items()}
        updated = True
    state["last_sync"] = datetime.utcnow().isoformat() + "Z"
    _save_phoenix_state(state)
    _apply_phoenix_triggers(req.home_state, req.mood_label)
    state["updated"] = updated
    return state


@app.get("/phoenix/state")
def phoenix_state():
    performance_guard()
    state = _load_phoenix_state()
    return {
        "ok": True,
        "state": state,
        "path": str(PHOENIX_STATE_PATH),
    }


@app.post("/phoenix/state")
def phoenix_state_update(req: PhoenixUpdateRequest):
    performance_guard()
    state = _apply_phoenix_update(req)
    return {"ok": True, "state": state}


@app.post("/phoenix/mood")
def phoenix_mood(label: str, intensity: float | None = None):
    performance_guard()
    state = _apply_phoenix_update(
        PhoenixUpdateRequest(mood_label=label, mood_intensity=intensity)
    )
    return {"ok": True, "state": state}


@app.post("/phoenix/home")
def phoenix_home(state: str):
    performance_guard()
    if state not in {"home", "away", "sleep"}:
        raise HTTPException(status_code=400, detail="Invalid home state")
    updated = _apply_phoenix_update(PhoenixUpdateRequest(home_state=state))
    return {"ok": True, "state": updated}


@app.get("/phoenix/inventory/log")
def phoenix_inventory_log(lines: int = 50):
    performance_guard()
    return {"ok": True, "lines": _tail_file(PHOENIX_INV_LOG_PATH, lines)}


@app.post("/phoenix/inventory/log")
def phoenix_inventory_append(entry: PhoenixLogEntry):
    performance_guard()
    if PHOENIX_REMOTE_BASE:
        try:
            resp = requests.post(
                f"{PHOENIX_REMOTE_BASE}/phoenix/inventory/log",
                headers={"Content-Type": "application/json"},
                json=entry.model_dump(),
                timeout=4,
            )
            data = resp.json()
            return {"ok": True, "record": data.get("record") or entry.model_dump()}
        except Exception:
            pass
    record = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "missing": entry.missing or [],
        "location": entry.location or "unknown",
    }
    try:
        PHOENIX_INV_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PHOENIX_INV_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass
    # update bag inventory in state (mark present unless missing)
    state = _load_phoenix_state()
    bag = state.get("bag_inventory") or {}
    if isinstance(bag, dict):
        missing = set(record["missing"])
        for item in list(bag.keys()):
            bag[item] = item not in missing
        state["bag_inventory"] = bag
        state["last_sync"] = record["ts"]
        _save_phoenix_state(state)
    return {"ok": True, "record": record}


# ---- TF2 coach stubs to avoid missing endpoints ----
@app.get("/tf2/coach/advice")
def tf2_coach_advice():
    return {"telemetry": {}, "coach": {"advice": ["Local AI ready."], "bot_tuning": {}}}


@app.post("/tf2/coach/telemetry")
def tf2_coach_telemetry(body: dict[str, Any] | None = None):
    return {"ok": True}

def _handle_phoenix_command(message: str) -> Optional[dict[str, Any]]:
    msg = (message or "").strip()
    if not msg:
        return None
    if not msg.lower().startswith("/phoenix"):
        return None
    parts = msg.split()
    if len(parts) == 1:
        return {"ok": True, "reply": "Usage: /phoenix INIT", "source": "phoenix"}
    action = parts[1].lower()
    if action in {"init", "initialize"}:
        mem = _refresh_memory("phoenix_init")
        ollama_ok = False
        try:
            resp = requests.get(f"{OLLAMA_ENDPOINT}/api/tags", timeout=2)
            ollama_ok = resp.status_code == 200
        except Exception:
            pass
        if not ollama_ok:
            try:
                ollama_ok = _ensure_ollama_running()
            except Exception:
                pass
        summary = _memory_summary_text(max_lines=12)
        reply_lines = [
            "Phoenix init complete.",
            f"Memory entries: {mem.get('count', 0)}",
            f"Handoff: {'loaded' if HANDOFF_FILE.exists() else 'missing'}",
            f"Ollama: {'online' if ollama_ok else 'offline'}",
        ]
        if mem.get("hint"):
            reply_lines.append("Wake hint injected.")
        if summary:
            reply_lines.append("Summary:\n" + summary)
        reply = "\n".join(reply_lines)
        try:
            memory_store.add(message, role="user")
            memory_store.add(reply, role="assistant")
        except Exception:
            pass
        return {"ok": True, "reply": reply, "source": "phoenix_init"}
    return {"ok": True, "reply": "Usage: /phoenix INIT", "source": "phoenix"}

@app.post("/ai/local")
def ai_local(body: dict[str, Any]):
    """Proxy to a self-hosted Ollama (or compatible) model with persistent memory context."""
    performance_guard()
    message = (body.get("message") or "").strip()
    image_b64 = _strip_data_url(body.get("image_b64") or "")
    image_prompt = (body.get("image_prompt") or "").strip()
    history = body.get("history") or []
    if not message and not image_b64:
        raise HTTPException(status_code=400, detail="Message required")
    if not message:
        message = image_prompt or "Analyze the attached image."
    phoenix_cmd = _handle_phoenix_command(message)
    if phoenix_cmd:
        return phoenix_cmd
    if not memory_store.list():
        _refresh_memory("ai_local")
    if _is_memory_query(message):
        reply = _memory_query_reply(message)
        try:
            memory_store.add(message, role="user")
            memory_store.add(reply, role="assistant")
        except Exception:
            pass
        return {"ok": True, "reply": reply, "source": "memory"}

    ollama_ok = True
    try:
        resp = requests.get(f"{OLLAMA_ENDPOINT}/api/tags", timeout=2)
        ollama_ok = resp.status_code == 200
    except Exception:
        ollama_ok = False
    if not ollama_ok:
        try:
            ollama_ok = _ensure_ollama_running()
        except Exception:
            ollama_ok = False
    use_ollama = bool(ollama_ok)
    if not use_ollama and not (OPENAI_API_KEY and OPENAI_FALLBACK_ENABLED):
        raise HTTPException(
            status_code=503,
            detail="Ollama offline. Start it or set OPENAI_API_KEY for fallback.",
        )
    payload_msgs: list[dict[str, str]] = []
    # primer as a single system message if present
    try:
        primer_text = ""
        if PRIMER_FILE.exists():
            primer_text = PRIMER_FILE.read_text(encoding="utf-8").strip()
        if not primer_text:
            primer_text = DEFAULT_PRIMER.strip()
        payload_msgs.append({"role": "system", "content": primer_text})
    except Exception:
        payload_msgs.append({"role": "system", "content": DEFAULT_PRIMER.strip()})

    # inject handoff memory (identity/mission) as a system block
    try:
        handoff = _handoff_context_text()
        if handoff:
            payload_msgs.append({"role": "system", "content": handoff})
    except Exception:
        pass

    # make memory usage explicit for the model
    payload_msgs.append(
        {
            "role": "system",
            "content": "Persistent memory is provided below. Use it as factual context about the user and system.",
        }
    )

    # inject identity snapshot (personality/tone) if available
    try:
        ident_txt = []
        persona = identity.get_personality()
        tone = identity.get_tone()
        if persona:
            ident_txt.append(f"Personality: {persona}")
        if tone:
            ident_txt.append(f"Tone: {tone}")
        if ident_txt:
            payload_msgs.append({"role": "system", "content": "\n".join(ident_txt)})
    except Exception:
        pass
    # inject owner context to anchor memory about the creator
    try:
        owner_block = owner_profile.get_prompt_block(role="owner")
        if owner_block:
            payload_msgs.append({"role": "system", "content": owner_block})
    except Exception:
        pass

    # allow autonomous edit actions when devmode is enabled
    if _actions_enabled():
        payload_msgs.append(
            {
                "role": "system",
                "content": (
                    "If you need to change settings or files, you may emit an action block. "
                    "Format: [[ACTION]]{json}[[/ACTION]] or [[ACTION]][{...},{...}][[/ACTION]]. "
                    "Allowed types: set_setting, set_settings, set_theme, write_file, append_file, replace_text. "
                    "Paths must be within the project root or F:\\PHOENIX_TRANSFER. "
                    "Do not touch secrets or .env unless explicitly requested."
                ),
            }
        )

    # guardian check on user input
    try:
        guard = guardian.inspect_message(message)
        sev = guard.get("severity")
        if sev and sev != "none":
            note = guard.get("instruction") or "Handle safely and calmly."
            excerpt = guard.get("excerpt") or ""
            payload_msgs.append(
                {
                    "role": "system",
                    "content": f"Safety note ({sev}): {note} Excerpt: {excerpt}",
                }
            )
    except Exception:
        pass

    # record user interaction/profile
    try:
        user_profile.ensure_profile(user="local")
        user_profile.record_interaction(user="local", weight=1, mentioned=True)
        user_profile.learn_from_text(message, user="local")
    except Exception:
        pass
    # persist user message immediately
    try:
        memory_store.add(message, role="user")
    except Exception:
        logging.warning("Failed to persist user message")
    # include a linear, recent timeline to keep memory contextual
    try:
        timeline = _memory_timeline_text(max_turns=12, max_chars=2600)
        if timeline:
            payload_msgs.append({"role": "system", "content": timeline})
    except Exception:
        pass
    # include recent visual memory context if available
    try:
        visual_ctx = _visual_memory_context_text(max_items=2)
        if visual_ctx:
            payload_msgs.append({"role": "system", "content": visual_ctx})
    except Exception:
        pass
    # include explicit vision summary from the UI if provided
    try:
        vision = body.get("vision")
        if isinstance(vision, str) and vision.strip():
            payload_msgs.append(
                {"role": "system", "content": "Latest image insight:\n" + vision.strip()}
            )
    except Exception:
        pass

    # include relevant memory hits for this query
    try:
        hits = cm.search_memories(message, max_hits=8)
        if hits:
            lines = []
            for entry in hits:
                role = entry.get("role") if isinstance(entry, dict) else "system"
                text = entry.get("content") if isinstance(entry, dict) else ""
                lines.append(f"[{role}] {_coerce_mem_text(text)}")
            payload_msgs.append({"role": "system", "content": "Relevant memory:\n" + "\n".join(lines)})
    except Exception:
        pass
    # include recent UI history (last 12)
    if isinstance(history, list) and history:
        for h in history[-12:]:
            if isinstance(h, dict) and "role" in h and "content" in h:
                payload_msgs.append({"role": h["role"], "content": h["content"]})
    if image_b64:
        if not OLLAMA_VISION_MODEL:
            raise HTTPException(status_code=422, detail="vision_model_missing")
        payload_msgs.append(
            {"role": "user", "content": message, "images": [image_b64]}
        )
    else:
        payload_msgs.append({"role": "user", "content": message})

    def _ollama_chat(msgs: list[dict[str, Any]]) -> str:
        model_to_use = OLLAMA_VISION_MODEL if image_b64 else OLLAMA_MODEL
        payload = {
            "model": model_to_use,
            "messages": msgs,
            "stream": False,
        }
        resp = requests.post(
            f"{OLLAMA_ENDPOINT}/api/chat",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if resp.status_code != 200:
            detail = resp.text
            logging.error("Ollama returned %s: %s", resp.status_code, detail)
            raise RuntimeError(detail)
        data = resp.json()
        return data.get("message", {}).get("content") or data.get("response") or ""

    def _openai_fallback(msgs: list[dict[str, Any]]) -> str:
        if not (OPENAI_API_KEY and OPENAI_FALLBACK_ENABLED):
            raise RuntimeError("OpenAI fallback disabled or missing API key.")
        # keep system context + last 20 exchanges to avoid huge payloads
        fallback_msgs: list[dict[str, str]] = []
        for m in msgs:
            if m.get("role") == "system":
                fallback_msgs.append(
                    {"role": "system", "content": m.get("content") or ""}
                )
        tail = [m for m in msgs if m.get("role") != "system"][-20:]
        for m in tail:
            fallback_msgs.append(
                {"role": m.get("role") or "user", "content": m.get("content") or ""}
            )
        payload = {
            "model": OPENAI_FALLBACK_MODEL or OPENAI_SEARCH_MODEL,
            "messages": fallback_msgs,
            "temperature": 0.2,
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(resp.text)
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    source = "ollama"
    if use_ollama:
        try:
            reply = _ollama_chat(payload_msgs)
        except Exception as exc:
            if OPENAI_API_KEY and OPENAI_FALLBACK_ENABLED:
                logging.warning("Ollama failed; falling back to OpenAI: %s", exc)
                reply = _openai_fallback(payload_msgs)
                source = "openai_fallback"
            else:
                logging.exception("Ollama request failed")
                raise HTTPException(status_code=502, detail=f"Ollama request failed: {exc}")
    else:
        logging.warning("Ollama offline; using OpenAI fallback.")
        reply = _openai_fallback(payload_msgs)
        source = "openai_fallback"
    if _denies_memory(reply):
        reply = _memory_summary_text()
        source = f"{source}+memory_guard"

    action_results: List[Dict[str, Any]] = []
    if _actions_enabled():
        cleaned_reply, actions = _parse_action_blocks(reply or "")
        if actions:
            action_results = _execute_actions(actions)
            reply = cleaned_reply or "Done."
            source = f"{source}+actions"

    # persist reply into memory for future turns
    try:
        memory_store.add(f"[assistant] {reply}", role="assistant")
    except Exception:
        logging.warning("Failed to persist assistant reply")
    # reflection log
    try:
        current_mood = state.get("mood", {}).get("label") if "state" in globals() else None
        reflection.log_reflection("ai_local_reply", reply, source=source, mood=current_mood)
    except Exception:
        pass
    return {"ok": True, "reply": reply, "source": source, "actions": action_results}


@app.get("/system/profile")
def get_profile():
    performance_guard()
    cfg = PERFORMANCE_PROFILES[current_profile]
    return {
        "profile": current_profile,
        "label": cfg["label"],
        "max_requests_per_10s": cfg["max_requests_per_10s"],
        "cpu_soft_limit": cfg["cpu_soft_limit"],
        "cooldown_seconds": cfg["cooldown_seconds"],
    }


@app.post("/system/profile")
def set_profile(req: ProfileSetRequest):
    global current_profile
    if req.profile not in PERFORMANCE_PROFILES:
        raise HTTPException(status_code=400, detail="Unknown profile.")
    current_profile = req.profile
    cfg = PERFORMANCE_PROFILES[current_profile]
    return {
        "status": "ok",
        "profile": current_profile,
        "label": cfg["label"],
        "message": f"Freya-13: Switched performance profile to '{current_profile}' - {cfg['label']}.",
    }


# ------------------- Display monitors ------------------- #


def _get_system_monitors() -> List[Dict[str, Any]]:
    if os.name != "nt":
        return []
    try:
        user32 = ctypes.windll.user32
        monitors: List[Dict[str, Any]] = []

        class _RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        class _MONITORINFOEX(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("rcMonitor", _RECT),
                ("rcWork", _RECT),
                ("dwFlags", ctypes.c_ulong),
                ("szDevice", ctypes.c_wchar * 32),
            ]

        MONITORINFOF_PRIMARY = 1

        def _enum_proc(hmonitor, hdc, rect_ptr, lparam):
            info = _MONITORINFOEX()
            info.cbSize = ctypes.sizeof(_MONITORINFOEX)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                rect = info.rcMonitor
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                device = info.szDevice.strip()
                monitors.append(
                    {
                        "id": device or f"monitor-{len(monitors) + 1}",
                        "label": device or f"Display {len(monitors) + 1}",
                        "x": rect.left,
                        "y": rect.top,
                        "width": width,
                        "height": height,
                        "primary": bool(info.dwFlags & MONITORINFOF_PRIMARY),
                        "orientation": "portrait" if height > width else "landscape",
                    }
                )
            return True

        enum_proc = ctypes.WINFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_RECT), ctypes.c_long
        )(_enum_proc)
        user32.EnumDisplayMonitors(0, 0, enum_proc, 0)
        return monitors
    except Exception:
        return []


@app.get("/system/monitors")
def system_monitors():
    performance_guard()
    return {"monitors": _get_system_monitors()}


@app.post("/voice/event")
def voice_event(req: VoiceEvent):
    performance_guard()
    msg = _apply_voice_command(req.text)
    return {
        "status": "ok",
        "message": msg,
        "voice_state": voice_state,
        "profile": current_profile,
    }


@app.get("/voice/state")
def voice_state_get():
    performance_guard()
    return {"voice_state": voice_state, "profile": current_profile}


def _rgb_to_bgr_int(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    return (b << 16) | (g << 8) | r


def _razer_register() -> bool:
    if RAZER_SESSION.get("uri"):
        return True
    try:
        payload = {
            "title": "Bjorgsun-26",
            "description": "Bjorgsun-26 lighting bridge",
            "author": {"name": "Bjorgsun", "contact": "local"},
            "device_supported": ["keyboard", "mouse", "mousepad", "headset", "keypad", "chromalink"],
            "category": "application",
        }
        resp = requests.post("http://localhost:54235/razer/chromasdk", json=payload, timeout=2)
        if resp.status_code != 200:
            logging.error("Razer register failed %s %s", resp.status_code, resp.text)
            return False
        data = resp.json()
        RAZER_SESSION["uri"] = data.get("uri")
        RAZER_SESSION["sessionid"] = data.get("sessionid")
        logging.info("Razer session registered %s", RAZER_SESSION["uri"])
        return True
    except Exception as exc:
        logging.error("Razer register exception: %s", exc)
        return False


def _razer_static_all(color: tuple[int, int, int], devices: list[str] | None = None) -> bool:
    if not _razer_register():
        return False
    uri = RAZER_SESSION.get("uri")
    if not uri:
        return False
    ok = True
    devs = devices or ["keyboard", "mouse", "mousepad", "headset", "chromalink"]
    payload = {"effect": "CHROMA_STATIC", "param": {"color": _rgb_to_bgr_int(color)}}
    for dev in devs:
        try:
            resp = requests.put(f"{uri}/{dev}", json=payload, timeout=2)
            if resp.status_code != 200:
                logging.error("Razer set %s failed %s %s", dev, resp.status_code, resp.text)
                ok = False
        except Exception as exc:
            logging.error("Razer set %s exception %s", dev, exc)
            ok = False
    return ok


@app.post("/razer/lighting")
def razer_lighting(payload: Dict[str, Any]):
    """Simple lighting hook for Synapse Chroma. Modes: dormant|wake|alert|freq."""
    mode = payload.get("mode", "dormant")
    devs = payload.get("devices")
    if mode == "wake":
        color = (0, 255, 120)
    elif mode == "alert":
        color = (255, 40, 40)
    elif mode == "freq":
        hz = float(payload.get("hz") or 440)
        amp = float(payload.get("amp") or 1.0)
        hue = int((hz % 1200) / 1200 * 360)
        r, g, b = [int(x * 255) for x in colorsys.hsv_to_rgb(hue / 360, 1, min(1.0, 0.4 + amp * 0.6))]
        color = (r, g, b)
    else:
        color = (0, 220, 200)
    ok = _razer_static_all(color, devs)
    return {"ok": ok, "color": color}

@app.options("/razer/lighting")
def razer_lighting_options():
    return {"ok": True}

@app.get("/devices/pairing")
def devices_pairing(label_hint: str = "", dev_key: str | None = Header(default=None)):
    _ensure_dev(dev_key)
    performance_guard()
    pending = _start_pairing(label_hint or None)
    host_ip = _guess_local_ip()
    url = f"http://{host_ip}:{SERVER_PORT}/client?token={pending.token}"
    qr = _make_qr_base64(url)
    return {
        "token": pending.token,
        "expires_at": pending.expires_at,
        "host": host_ip,
        "port": SERVER_PORT,
        "url": url,
        "qr_base64": qr,
    }


@app.post("/devices/register")
def devices_register(req: DeviceRegisterRequest):
    performance_guard()
    dev = _register_device(req.token, req.label, req.permissions or ["basic"])
    return {
        "id": dev.id,
        "label": dev.label,
        "permissions": dev.permissions,
        "added_at": dev.added_at,
        "token": dev.token,
    }


@app.get("/devices")
def devices_list(include_tokens: bool = False):
    performance_guard()
    _cleanup_pending()
    devices = []
    for dev in _devices.values():
        entry = {
            "id": dev.id,
            "label": dev.label,
            "permissions": dev.permissions,
            "added_at": dev.added_at,
        }
        if include_tokens:
            entry["token"] = dev.token
        devices.append(entry)
    return sorted(devices, key=lambda d: d["added_at"], reverse=True)


@app.post("/devices/revoke")
def devices_revoke(req: DeviceRevokeRequest, dev_key: str | None = Header(default=None)):
    _ensure_dev(dev_key)
    if req.device_id not in _devices:
        raise HTTPException(status_code=404, detail="Device not found.")
    _devices.pop(req.device_id, None)
    _save_devices()
    return {"status": "ok", "message": "Device revoked."}


@app.get("/client")
def client_page():
    return Response(content=CLIENT_HTML, media_type="text/html")


@app.post("/memory/import")
def memory_import(req: MemoryImportRequest, dev_key: str | None = Header(default=None)):
    _ensure_dev(dev_key)
    performance_guard()
    payload = req.text or ""
    if req.url:
        try:
            resp = requests.get(req.url, timeout=5)
            resp.raise_for_status()
            payload = resp.text
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"URL fetch failed: {e}")
    if req.file:
        payload = _read_file_safe(req.file)
    if not payload:
        raise HTTPException(status_code=400, detail="No content provided.")
    # Append to memory or lore file
    if req.kind == "memory":
        memory_store.add(payload, role="system")
    else:
        lore_file = DATA_DIR / "lore_imports.txt"
        try:
            with lore_file.open("a", encoding="utf-8") as f:
                f.write(payload + "\n\n")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to write lore: {e}")
    return {"status": "ok", "kind": req.kind}


@app.post("/memory/import_chatgpt")
async def memory_import_chatgpt(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Accepts a ChatGPT export zip or conversations.json and ingests messages into memory."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="File required")
    name = file.filename.lower()
    try:
        buf = await file.read()
        data_bytes: bytes
        # allow huge exports (up to ~25GB); still keep a hard cap to avoid runaway memory
        if len(buf) > 25 * 1024 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 25GB)")
        if name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(buf)) as zf:
                inner = [n for n in zf.namelist() if n.lower().endswith("conversations.json")]
                if not inner:
                    # fallback: any .json in the zip, pick the largest
                    jsons = [n for n in zf.namelist() if n.lower().endswith(".json")]
                    if not jsons:
                        raise HTTPException(status_code=400, detail="No conversations.json or *.json found in zip")
                    inner = sorted(jsons, key=lambda n: zf.getinfo(n).file_size, reverse=True)[:1]
                with zf.open(inner[0]) as f:
                    data_bytes = f.read()
        else:
            data_bytes = buf
        log_file = LOG_DIR / "import_chatgpt.log"
        logging.info("import_chatgpt: processing %s bytes from %s", len(data_bytes), file.filename)
        conversations = json.loads(data_bytes.decode("utf-8", errors="ignore"))
        if isinstance(conversations, dict) and "conversations" in conversations:
            conversations = conversations["conversations"]
        if not isinstance(conversations, list):
            detail = "Unsupported export format (expected list)"
            log_file.write_text(f"{datetime.utcnow().isoformat()}Z {detail}\n", encoding="utf-8")
            raise HTTPException(status_code=400, detail=detail)
        imported = 0
        skipped = 0
        batch_entries: list[tuple[str, str]] = []
        for conv in conversations:
            mapping = conv.get("mapping", {}) if isinstance(conv, dict) else {}
            for node in mapping.values():
                msg = (node.get("message") or {}) if isinstance(node, dict) else {}
                role = (msg.get("author") or {}).get("role")
                if role not in {"user", "assistant"}:
                    skipped += 1
                    continue
                raw_parts = ((msg.get("content") or {}).get("parts")) or []
                parts: list[str] = []
                for p in raw_parts:
                    if isinstance(p, str):
                        parts.append(p)
                        continue
                    if isinstance(p, dict):
                        appended = False
                        # try common keys
                        for k in ("text", "value", "content"):
                            if k in p and isinstance(p[k], str):
                                parts.append(p[k])
                                appended = True
                                break
                        if not appended:
                            try:
                                parts.append(json.dumps(p, ensure_ascii=False))
                                appended = True
                            except Exception:
                                appended = False
                        if appended:
                            continue
                    try:
                        parts.append(str(p))
                    except Exception:
                        logging.debug("import_chatgpt: could not coerce part %s", type(p))
                text = "\n".join(parts).strip()
                if not text:
                    skipped += 1
                    continue
                batch_entries.append((f"[chatgpt/{role}] {text}", role or "system"))
                imported += 1
        if batch_entries:
            imported = memory_store.add_bulk(batch_entries)
        log_file.write_text(
            f"{datetime.utcnow().isoformat()}Z ok bytes={len(data_bytes)} imported={imported} skipped={skipped}\n",
            encoding="utf-8",
        )
        return {"ok": True, "imported": imported, "skipped": skipped}
    except HTTPException as exc:
        logging.warning("import_chatgpt HTTP error: %s", exc.detail)
        try:
            log_file = LOG_DIR / "import_chatgpt.log"
            log_file.write_text(f"{datetime.utcnow().isoformat()}Z http_error={exc.detail}\n", encoding="utf-8")
        except Exception:
            pass
        raise
    except Exception as exc:
        logging.exception("import_chatgpt failed")
        try:
            log_file = LOG_DIR / "import_chatgpt.log"
            log_file.write_text(f"{datetime.utcnow().isoformat()}Z exception={exc}\n", encoding="utf-8")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}")


@app.post("/rest/trigger")
def rest_trigger(
    key: str | None = None, dev_key: str | None = Header(default=None)
):  # noqa: ANN001
    _ensure_dev(dev_key)
    if not _authorized_master(key):
        raise HTTPException(status_code=401, detail="Rest key invalid.")
    # Best-effort shutdown
    try:
        _save_devices()
        _save_pending()
    except Exception:
        pass
    os._exit(0)  # noqa: WPS437


@app.get("/rest/check")
def rest_check():
    """Check for sentinel file; if matches any master key, exit gracefully."""
    if not _KEYRING or not RESTSWITCH_FILE:
        return {"status": "disabled"}
    try:
        p = Path(RESTSWITCH_FILE)
        if p.exists():
            content = p.read_text(encoding="utf-8").strip()
            if _authorized_master(content):
                os._exit(0)  # noqa: WPS437
    except Exception:
        pass
    return {"status": "ok"}


@app.get("/rest/status")
def rest_status():
    """Return minimal info about rest configuration without leaking keys."""
    return {
        "keys_loaded": len([v for v in _KEYRING.values() if v]),
        "sentinel_path": RESTSWITCH_FILE if RESTSWITCH_FILE else None,
    }


@app.post("/law/flag")
def flag_content(
    req: MemoryAddRequest, request: Request, dev_key: str | None = Header(default=None)
):
    # content flagging endpoint: no dev key required; bans on abuse
    ip = request.client.host if request.client else "unknown"
    if ip in _banlist:
        raise HTTPException(status_code=403, detail="Access blocked.")
    count = _ban_counts.get(ip, 0) + 1
    _ban_counts[ip] = count
    if count > BAN_THRESHOLD:
        _banlist.add(ip)
        _emit_alert("banlist_add", f"IP {ip} exceeded flag threshold.")
        raise HTTPException(status_code=403, detail="Access blocked.")
    # enqueue pending review
    pending_id = str(uuid.uuid4())
    _pending_requests[pending_id] = {
        "id": pending_id,
        "ip": ip,
        "text": req.text,
        "status": "pending",
        "time": datetime.utcnow().isoformat() + "Z",
        "decision": "no for now",
    }
    _emit_alert("content_flagged", f"Text flagged from {ip}")
    return {
        "status": "pending_review",
        "message": "I cannot answer that. (Pending owner review.)",
    }


class ReviewDecision(BaseModel):
    request_id: str
    action: Literal["allow", "deny", "warn", "ban", "shutdown", "ignore"]
    note: str | None = None


@app.get("/law/review")
def review_queue(dev_key: str | None = Header(default=None)):
    _ensure_dev(dev_key)
    return list(_pending_requests.values())


@app.post("/law/decide")
def review_decide(body: ReviewDecision, dev_key: str | None = Header(default=None)):
    _ensure_dev(dev_key)
    item = _pending_requests.get(body.request_id)
    if not item:
        raise HTTPException(status_code=404, detail="Request not found.")
    item["status"] = body.action
    item["note"] = body.note or ""
    _emit_alert("review_decision", f"{body.action} for {body.request_id}")
    if body.action == "ban" and item.get("ip"):
        _banlist.add(item["ip"])
    if body.action == "shutdown":
        os._exit(0)
    return {"status": "ok", "action": body.action}


@app.get("/law/alerts")
def law_alerts(dev_key: str | None = Header(default=None)):
    _ensure_dev(dev_key)
    return list(_alerts)


@app.post("/alert/raise")
def raise_alert(
    reason: str,
    detail: str | None = None,
    severity: str = "info",
    dev_key: str | None = Header(default=None),
):
    _ensure_dev(dev_key)
    _emit_alert(reason, detail, severity)
    return {"status": "ok", "severity": severity}


# ------------------- OpenAI-backed search endpoint ------------------- #

@app.get("/search")
def search(query: str, dev_key: str | None = Header(default=None)):
    _ensure_dev(dev_key)
    _emit_alert("search_request", query)
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="Search API key not set.")
    if not query:
        raise HTTPException(status_code=400, detail="Empty query.")
    payload = {
        "model": OPENAI_SEARCH_MODEL,
        "messages": [{"role": "user", "content": f"Search the internet and summarize: {query}"}],
        "temperature": 0.2,
    }
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")
    _emit_alert("search", f"Query: {query}")
    return {"query": query, "result": text, "model": OPENAI_SEARCH_MODEL}


# ------------------- Peer heartbeat (coordinator) ------------------- #

@app.post("/peer/register")
def peer_register(request: Request, dev_key: str | None = Header(default=None)):
    # dev key optional; if provided and token mismatch, fail
    if PEER_TOKEN and dev_key != PEER_TOKEN:
        raise HTTPException(status_code=401, detail="Peer token invalid.")
    ip = request.client.host if request.client else "unknown"
    peer_id = request.headers.get("X-Peer-Id") or str(uuid.uuid4())
    _peers[peer_id] = {
        "ip": ip,
        "time": datetime.utcnow().isoformat() + "Z",
    }
    try:
        PEERS_FILE.write_text(json.dumps(_peers, indent=2), encoding="utf-8")
    except Exception:
        pass
    return {"status": "ok", "peer_id": peer_id, "known": len(_peers)}


@app.get("/peer/ping")
def peer_ping():
    return {"status": "ok", "time": datetime.utcnow().isoformat() + "Z"}


# ------------------- Settings persistence ------------------- #


@app.get("/settings/get")
def settings_get():
    performance_guard()
    return settings_store.get()


@app.post("/settings/set")
def settings_set(payload: Dict[str, Any]):
    performance_guard()
    payload = payload or {}
    data = settings_store.set(payload)
    return {"ok": True, "settings": data}


# ------------------- Remote web access ------------------- #


@app.get("/remote/status")
def remote_status():
    enabled = _remote_ui_enabled()
    host = _remote_ui_host()
    links: List[str] = []
    for ip in _get_local_ips():
        links.append(f"http://{ip}:{SERVER_PORT}/")
    if host:
        links.append(f"http://{host}/")
    message = (
        "Remote access enabled. For off-network access, use DNS + port forwarding or a tunnel."
        if enabled
        else "Remote access is off. Enable it in Settings to share a web link."
    )
    return {
        "enabled": enabled,
        "host": host,
        "links": links,
        "message": message,
        "port": SERVER_PORT,
    }


@app.get("/remote/tunnel/status")
def remote_tunnel_status():
    return _remote_tunnel_status()


@app.post("/remote/tunnel/start")
def remote_tunnel_start():
    settings_store.set({"remoteUiEnabled": True, "remoteTunnelEnabled": True})
    status = _start_remote_tunnel()
    return {"ok": True, "status": status}


@app.post("/remote/tunnel/stop")
def remote_tunnel_stop():
    settings_store.set({"remoteTunnelEnabled": False})
    status = _stop_remote_tunnel()
    return {"ok": True, "status": status}


@app.get("/")
def remote_root():
    if not _remote_ui_enabled():
        return {"status": "ok", "message": "Remote UI disabled."}
    if not REMOTE_UI_DIST:
        raise HTTPException(status_code=404, detail="UI build not found")
    return FileResponse(str(REMOTE_UI_DIST / "index.html"))


@app.get("/remote")
def remote_root_alias():
    return remote_root()


@app.get("/remote/{path:path}")
def remote_path_alias(path: str):
    return remote_root()


@app.get("/env-config.js")
def remote_env_config():
    if not _remote_ui_enabled():
        raise HTTPException(status_code=404, detail="Remote UI disabled")
    user = os.getenv("BJORGSUN_USER", "Father")
    pw = os.getenv("BJORGSUN_PASS", "")
    content = (
        "window.__BJ_CFG = "
        + json.dumps({"user": user, "pass": pw, "apiBase": "/"})
        + ";"
    )
    return Response(content=content, media_type="application/javascript")


@app.get("/assets/{path:path}")
def remote_assets(path: str):
    if not _remote_ui_enabled():
        raise HTTPException(status_code=404, detail="Remote UI disabled")
    if not REMOTE_UI_DIST:
        raise HTTPException(status_code=404, detail="UI build not found")
    base = REMOTE_UI_DIST / "assets"
    target = (base / path).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise HTTPException(status_code=404, detail="Invalid asset path")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(str(target))


# ------------------- Titanfall coach (local helper) ------------------- #


@app.post("/tf2/coach")
def tf2_coach(payload: Dict[str, Any]):
    """
    Lightweight tip generator for Titanfall/Northstar telemetry.
    Intended to be called by the bridge that tails [AI_COACH_TELEMETRY] logs.
    """
    performance_guard()
    try:
        elims = int(payload.get("elims", 0))
        deaths = int(payload.get("deaths", 0))
        dur = float(payload.get("duration", 0))
        map_name = payload.get("map", "unknown")
        mode = payload.get("mode", "unknown")
        ratio = elims / max(1, deaths)
        pace = (elims + deaths) / max(1, dur / 60.0)

        suggestions: List[str] = []
        if ratio < 0.8:
            suggestions.append("Play cover and disengage when shields crack; reset often.")
        if pace < 0.6:
            suggestions.append("Increase tempo: third-party fights or rotate faster toward gunfire.")
        if elims < deaths:
            suggestions.append("Prioritize survivability perks and off-angles; avoid direct duels.")
        if not suggestions:
            suggestions.append("Keep current rhythm; maintain off-angles and slide-hop to control sightlines.")

        tip = f"[{map_name} | {mode}] E:{elims} D:{deaths} EDR:{ratio:.2f} Pace:{pace:.2f}/min. " + " ".join(suggestions)
        return {"ok": True, "tip": tip}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ------------------- Ollama readiness helper ------------------- #


def _ensure_ollama():
    if not OLLAMA_ENDPOINT:
        return
    global _ollama_started
    try:
        requests.get(f"{OLLAMA_ENDPOINT}/api/tags", timeout=3)
        return True
    except Exception:
        pass
    try:
        if _ollama_started:
            return False
        ollama_exe = Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if ollama_exe.exists():
            subprocess.Popen(
                [str(ollama_exe), "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            _ollama_started = True
            return True
    except Exception:
        pass
    return False


# Kick off an Ollama readiness check at import time (best-effort, non-fatal)
_ollama_started = False
_ensure_ollama()


# ------------------- Audio frequency analysis ------------------- #


def _get_gpu_load() -> float | None:
    """Return first GPU load percent if available."""
    try:
        try:
            import pynvml  # type: ignore

            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            if count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                return float(util.gpu)
        except Exception:
            import GPUtil  # type: ignore

            gpus = GPUtil.getGPUs()
            if gpus:
                return float(gpus[0].load * 100.0)
    except Exception:
        return None
    return None


def _select_best_profile() -> PerformanceProfileName:
    override = os.getenv("PHOENIX_PERF_PROFILE", "").strip().lower()
    if override in PERFORMANCE_PROFILES:
        return override  # type: ignore[return-value]
    try:
        gpu_load = _get_gpu_load()
    except Exception:
        gpu_load = None
    return "turbo" if gpu_load is not None else "balanced"


try:
    if current_profile == "safe":
        current_profile = _select_best_profile()
        logging.getLogger("bjorgsun").info(
            "Performance profile auto-selected: %s", current_profile
        )
except Exception:
    pass


def _load_freq_emotions() -> List[Dict[str, Any]]:
    try:
        return json.loads(FREQ_EMOTION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _match_emotions(peaks: List[Dict[str, float]], tol_hz: float = 5.0) -> List[Dict[str, Any]]:
    emap = _load_freq_emotions()
    matched: List[Dict[str, Any]] = []
    for peak in peaks:
        hz = peak.get("hz", 0.0)
        amp = peak.get("amplitude", 0.0)
        for entry in emap:
            ehz = entry.get("hz")
            if ehz is None:
                continue
            if abs(hz - float(ehz)) <= tol_hz:
                matched.append(
                    {"hz": hz, "emotion": entry.get("emotion", "unknown"), "amplitude": amp}
                )
    return matched


def _analyze_buffer(buf: bytes, name: str = "audio") -> Dict[str, Any]:
    with sf.SoundFile(io.BytesIO(buf)) as handle:
        sr = handle.samplerate
        channels = handle.channels
        total_frames = len(handle)
        if sr <= 0 or total_frames <= 0:
            raise ValueError("Failed to read audio")
        block = 16384
        window = np.hanning(block)
        mags_accum = None
        blocks = 0
        while True:
            data = handle.read(block, dtype="float32", always_2d=True)
            if data.size == 0:
                break
            if data.ndim > 1:
                data = data.mean(axis=1)
            if data.size < block:
                data = np.pad(data, (0, block - data.size))
            spectrum = np.fft.rfft(data * window)
            mags = np.abs(spectrum)
            if mags_accum is None:
                mags_accum = mags
            else:
                mags_accum += mags
            blocks += 1
        if mags_accum is None or blocks == 0:
            raise ValueError("Empty audio data")
        mags = mags_accum / max(1, blocks)
        freqs = np.fft.rfftfreq(block, d=1.0 / sr)
        duration_sec = total_frames / sr

    bands = [
        (20, 60, "sub"),
        (60, 120, "bass"),
        (120, 180, "low_mid"),
        (180, 300, "mid"),
        (300, 500, "upper_mid"),
        (500, 1000, "presence"),
        (1000, 4000, "brilliance"),
    ]
    band_energy = []
    for lo, hi, label in bands:
        mask = (freqs >= lo) & (freqs < hi)
        energy = float(mags[mask].sum()) if mask.any() else 0.0
        band_energy.append({"label": label, "lo": lo, "hi": hi, "energy": energy})

    top_n = 5
    idx = np.argsort(mags)[::-1][: top_n * 3]  # oversample then filter
    peaks = []
    for i in idx:
        hz = float(freqs[i])
        amp = float(mags[i])
        if hz <= 1.0:
            continue
        peaks.append({"hz": hz, "amplitude": amp})
        if len(peaks) >= top_n:
            break

    centroid = float((freqs * mags).sum() / mags.sum()) if mags.sum() > 0 else 0.0
    rolloff = (
        float(freqs[np.where(np.cumsum(mags) >= 0.85 * mags.sum())[0][0]]) if mags.sum() > 0 else 0.0
    )

    matched = _match_emotions(peaks)
    main_frequency = float(peaks[0]["hz"]) if peaks else 0.0
    max_mag = float(np.max(mags)) if mags.size else 0.0
    threshold = max_mag * 0.02
    significant = freqs[(freqs >= 20.0) & (mags >= threshold)]
    lowest_frequency = float(significant.min()) if significant.size else main_frequency
    highest_frequency = float(significant.max()) if significant.size else main_frequency

    spectrum_bins = []
    if mags.size:
        mag_db = 20.0 * np.log10(np.maximum(mags, 1e-9))
        bins = 64
        step = max(1, len(freqs) // bins)
        for i in range(0, len(freqs), step):
            chunk = mag_db[i : i + step]
            if chunk.size == 0:
                continue
            hz = float(np.mean(freqs[i : i + step]))
            spectrum_bins.append({"hz": hz, "db": float(np.mean(chunk))})

    suggested_emotion = "neutral"
    if matched:
        scores: Dict[str, float] = {}
        for item in matched:
            emotion = item.get("emotion", "unknown")
            scores[emotion] = scores.get(emotion, 0.0) + float(item.get("amplitude", 1.0))
        suggested_emotion = max(scores.items(), key=lambda item: item[1])[0]
    else:
        if centroid < 200:
            suggested_emotion = "calm"
        elif centroid < 600:
            suggested_emotion = "grounded"
        elif centroid < 2000:
            suggested_emotion = "focused"
        elif centroid < 5000:
            suggested_emotion = "energized"
        else:
            suggested_emotion = "airy"

    return {
        "name": name,
        "sr": sr,
        "channels": channels,
        "duration_sec": duration_sec,
        "analysis_blocks": blocks,
        "centroid_hz": centroid,
        "rolloff_hz": rolloff,
        "main_frequency_hz": main_frequency,
        "lowest_frequency_hz": lowest_frequency,
        "highest_frequency_hz": highest_frequency,
        "peaks": peaks,
        "band_energy": band_energy,
        "spectrum": spectrum_bins,
        "matched_emotions": matched,
        "suggested_emotion": suggested_emotion,
    }


@app.post("/orb/image")
def orb_image(payload: Dict[str, Any]) -> JSONResponse:
    if not ORB_IMAGE_LOCK.acquire(blocking=False):
        _log_issue(
            "PHX-ORB-002",
            "orb_image_busy",
            "previous generation still running",
            severity="warn",
            source="server",
        )
        raise HTTPException(status_code=429, detail="orb image busy")
    try:
        if not PROJECTP_DIR.exists():
            _log_issue(
                "PHX-ORB-001",
                "projectp_missing",
                str(PROJECTP_DIR),
                severity="error",
                source="server",
            )
            raise HTTPException(status_code=404, detail="Project-P directory missing")

        thought = str(payload.get("thought") or "").strip()
        emotion = str(payload.get("emotion") or "").strip()
        state_name = str(payload.get("state") or "").strip()
        heartbeat_hz = float(payload.get("heartbeatHz") or 0.0)

        if not _projectp_is_online():
            started, reason = _start_projectp_server()
            if not started:
                _log_issue(
                    "PHX-ORB-003",
                    "projectp_start_failed",
                    reason,
                    severity="error",
                    source="server",
                )
                raise HTTPException(status_code=503, detail="Project-P start failed")
            if not _wait_for_projectp():
                _log_issue(
                    "PHX-ORB-004",
                    "projectp_offline",
                    "Project-P did not respond",
                    severity="error",
                    source="server",
                )
                raise HTTPException(status_code=503, detail="Project-P not responding")

        try:
            _ensure_projectp_default_ref()
        except Exception as exc:
            _log_issue(
                "PHX-ORB-005",
                "projectp_ref_setup_failed",
                str(exc),
                severity="error",
                source="server",
            )
            raise HTTPException(status_code=500, detail="Project-P reference setup failed") from exc

        try:
            data_url, filename = _projectp_generate_orb_image(
                thought=thought,
                emotion=emotion,
                state_name=state_name,
                heartbeat_hz=heartbeat_hz,
            )
        except Exception as exc:
            _log_issue(
                "PHX-ORB-006",
                "projectp_generate_failed",
                str(exc),
                severity="error",
                source="server",
            )
            raise HTTPException(status_code=500, detail="Project-P generation failed") from exc

        return JSONResponse({"dataUrl": data_url, "key": filename})
    finally:
        try:
            ORB_IMAGE_LOCK.release()
        except Exception:
            pass


@app.post("/frequency/analyze")
@app.post("/audio/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    try:
        buf = await file.read()
        res = _analyze_buffer(buf, file.filename)
        outpath = ANALYSIS_DIR / f"{Path(file.filename).stem}.json"
        outpath.write_text(json.dumps(res, indent=2), encoding="utf-8")
        return {"ok": True, "analysis": res}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/vision/analyze")
async def vision_analyze(payload: Dict[str, Any] = Body(...)):
    image_b64 = _strip_data_url(payload.get("image_b64") or "")
    filename = (payload.get("filename") or "image").strip() or "image"
    prompt = (payload.get("prompt") or "").strip()
    if not image_b64:
        raise HTTPException(status_code=400, detail="image_b64 required")
    try:
        raw = base64.b64decode(image_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid image data")

    digest = hashlib.sha256(raw).hexdigest()[:16]
    summary = ""
    meta: dict[str, Any] = {"digest": digest, "filename": filename}

    # Try Ollama vision model first if configured
    model = os.getenv("OLLAMA_VISION_MODEL", "").strip()
    if model:
        try:
            vision_prompt = prompt or "Describe this image briefly and clearly."
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": vision_prompt, "images": [image_b64]}
                ],
                "stream": False,
            }
            resp = requests.post(
                f"{OLLAMA_ENDPOINT}/api/chat",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                summary = (
                    data.get("message", {}).get("content")
                    or data.get("response")
                    or ""
                ).strip()
                if summary:
                    meta["vision_mode"] = "ollama"
                    meta["model"] = model
        except Exception:
            pass
    if not model and not summary and not os.getenv("VISION_ALLOW_METADATA_FALLBACK", "").strip():
        raise HTTPException(status_code=422, detail="vision_model_missing")

    # Fallback: local metadata + colors
    if not summary:
        try:
            img = Image.open(io.BytesIO(raw))
            summary, img_meta = _vision_summary_from_image(img)
            meta.update(img_meta)
            meta["vision_mode"] = "metadata_fallback"
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"image decode failed: {exc}")

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "filename": filename,
        "summary": summary,
        "meta": meta,
        "prompt": prompt,
    }
    _append_visual_memory(entry)
    try:
        memory_store.add(f"[vision] {summary}", role="system")
    except Exception:
        pass
    return {"ok": True, "summary": summary, "memory_saved": True, "meta": meta}


@app.post("/frequency/emotion")
@app.post("/audio/emotion")
async def add_freq_emotion(payload: Dict[str, Any]):
    hz = float(payload.get("hz") or 0)
    emotion = (payload.get("emotion") or "").strip()
    if hz <= 0 or not emotion:
        raise HTTPException(status_code=400, detail="hz and emotion required")
    entries = _load_freq_emotions()
    entries.append({"hz": hz, "emotion": emotion})
    FREQ_EMOTION_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return {"ok": True, "saved": {"hz": hz, "emotion": emotion}, "count": len(entries)}


def _colorize_buffer(
    buf: bytes,
    gain_141: float = 0.1,
    lfo_hz: float = 3.141,
    lfo_depth: float = 0.1,
    partial_gain: float = 0.05,
) -> bytes:
    data, sr = sf.read(io.BytesIO(buf), always_2d=False)
    if data is None or sr <= 0:
        raise ValueError("Failed to read audio")
    if data.ndim > 1:
        data = data.mean(axis=1)
    t = np.arange(len(data)) / sr
    # LFO tremolo
    lfo = 1.0 + lfo_depth * np.sin(2 * np.pi * lfo_hz * t)
    # Beds/partials
    bed_141 = gain_141 * np.sin(2 * np.pi * 141.0 * t)
    partial1 = partial_gain * np.sin(2 * np.pi * 1633.0 * t)
    partial2 = partial_gain * np.sin(2 * np.pi * 941.0 * t)
    colored = data * lfo + bed_141 + partial1 + partial2
    # normalize to prevent clipping
    max_abs = np.max(np.abs(colored)) or 1.0
    colored = colored / max_abs * min(1.0, max_abs)
    out = io.BytesIO()
    sf.write(out, colored.astype(np.float32), sr, format="WAV")
    out.seek(0)
    return out.read()


@app.post("/audio/colorize")
async def colorize_audio(
    file: UploadFile = File(...),
    gain_141: float = 0.1,
    lfo_hz: float = 3.141,
    lfo_depth: float = 0.1,
    partial_gain: float = 0.05,
):
    try:
        buf = await file.read()
        wav = _colorize_buffer(buf, gain_141, lfo_hz, lfo_depth, partial_gain)
        return StreamingResponse(io.BytesIO(wav), media_type="audio/wav", headers={"Content-Disposition": "attachment; filename=colored.wav"})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=SERVER_PORT,
        reload=False,
        access_log=False,
    )
