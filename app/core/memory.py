import json
import os
import re
from pathlib import Path
import datetime
import time
import uuid

from core.issue_log import log_issue

from config import PRIVATE_MODE

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEGACY_MEMORY_PATH = DATA_DIR.parent / "server" / "data" / "memory.json"
ENV_MEMORY_PATH = os.getenv("MEMORY_PATH", "").strip()
if ENV_MEMORY_PATH:
    MEMORY_PATH = Path(ENV_MEMORY_PATH).expanduser().resolve()
else:
    MEMORY_PATH = DATA_DIR / "memory.json"
# Export folder follows the chosen memory path
CACHE_DIR = MEMORY_PATH.parent / "memory_exports"
CACHE_HISTORY = 26000  # entries kept in RAM + disk to maintain prompt history

memory_data: dict = {}
conversation: list = []
# Persistence is on by default so he always remembers, regardless of PRIVATE_MODE,
# but the UI toggle can still disable it for privacy.
persist_enabled = True
if PRIVATE_MODE:
    print(
        " PRIVATE_MODE env detected, but persistence defaults to ON. Use the UI toggle to disable if needed."
    )


def _empty_memory() -> dict:
    return {"version": 2, "conversation": [], "storytime": [], "migrations": {}}


def _quarantine_memory_file(path: Path, raw_text: str, reason: str):
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    quarantine_path = path.with_suffix(f".corrupt.{ts}.json")
    try:
        path.replace(quarantine_path)
    except Exception as exc:
        log_issue(
            "PHX-MEM-013",
            "memory_quarantine_failed",
            str(exc),
            source="memory",
            extra={"path": str(path)},
        )
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = CACHE_DIR / f"memory_corrupt_{ts}.json"
        backup_path.write_text(raw_text, encoding="utf-8")
    except Exception as exc:
        log_issue(
            "PHX-MEM-014",
            "memory_backup_failed",
            str(exc),
            source="memory",
            extra={"path": str(path)},
        )
    log_issue(
        "PHX-MEM-012",
        "memory_corrupt",
        reason,
        source="memory",
        extra={"path": str(path), "quarantine": str(quarantine_path)},
    )


def _read_memory_raw(path: Path):
    try:
        raw_text = path.read_text(encoding="utf-8")
    except Exception as exc:
        log_issue(
            "PHX-MEM-010",
            "memory_read_failed",
            str(exc),
            source="memory",
            extra={"path": str(path)},
        )
        return None
    if not raw_text.strip():
        log_issue(
            "PHX-MEM-011",
            "memory_empty",
            "memory.json is empty",
            source="memory",
            extra={"path": str(path)},
        )
        return None
    try:
        return json.loads(raw_text)
    except Exception as exc:
        _quarantine_memory_file(path, raw_text, str(exc))
        return None


def _normalize_entry(entry) -> dict | None:
    if isinstance(entry, dict):
        content = entry.get("content")
        if content is None:
            content = entry.get("text")
        if isinstance(content, str):
            content = content.strip()
        if not content:
            return None
        role = entry.get("role") if isinstance(entry.get("role"), str) else "system"
        ts = entry.get("timestamp") or entry.get("time") or entry.get("created_at")
        if not isinstance(ts, str) or not ts:
            ts = datetime.datetime.utcnow().isoformat() + "Z"
        return {"role": role, "content": content, "timestamp": ts}
    if isinstance(entry, str) and entry.strip():
        return {
            "role": "system",
            "content": entry.strip(),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }
    return None


def _normalize_conversation(raw_list: list) -> list[dict]:
    normalized: list[dict] = []
    for entry in raw_list:
        norm = _normalize_entry(entry)
        if norm:
            normalized.append(norm)
    return normalized


def _merge_legacy_memory():
    if not LEGACY_MEMORY_PATH.exists():
        return
    migrations = memory_data.setdefault("migrations", {})
    if migrations.get("legacy_merge_done"):
        return
    try:
        raw = json.loads(LEGACY_MEMORY_PATH.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return
    if isinstance(raw, dict):
        legacy_raw = raw.get("conversation", [])
    elif isinstance(raw, list):
        legacy_raw = raw
    else:
        legacy_raw = []
    legacy_conv = _normalize_conversation(legacy_raw)
    if not legacy_conv:
        migrations["legacy_merge_done"] = datetime.datetime.utcnow().isoformat() + "Z"
        return
    existing = {(e.get("role"), e.get("content")) for e in memory_data.get("conversation", []) if isinstance(e, dict)}
    merged = memory_data.get("conversation", [])
    added = 0
    for entry in legacy_conv:
        key = (entry.get("role"), entry.get("content"))
        if key in existing:
            continue
        merged.append(entry)
        existing.add(key)
        added += 1
    memory_data["conversation"] = merged
    migrations["legacy_merge_done"] = datetime.datetime.utcnow().isoformat() + "Z"
    if added:
        _persist_memory_file()


def load_memory():
    global conversation, memory_data
    if os.path.exists(MEMORY_PATH):
        raw = _read_memory_raw(MEMORY_PATH)
        if raw is None:
            memory_data = _empty_memory()
        elif isinstance(raw, list):
            memory_data = _empty_memory()
            memory_data["conversation"] = raw
        elif isinstance(raw, dict):
            memory_data = raw
        else:
            memory_data = _empty_memory()
    else:
        memory_data = _empty_memory()
        print(
            f" No prior memory log found (state: {'persistent' if persist_enabled else 'private'})."
        )
    if "conversation" not in memory_data or not isinstance(memory_data["conversation"], list):
        memory_data["conversation"] = []
    memory_data["conversation"] = _normalize_conversation(memory_data["conversation"])
    if "storytime" not in memory_data or not isinstance(memory_data["storytime"], list):
        memory_data["storytime"] = []
    memory_data.setdefault("version", 2)
    memory_data.setdefault("migrations", {})
    _merge_legacy_memory()
    conversation = memory_data["conversation"]
    state = "persistent" if persist_enabled else "private / volatile"
    print(f" Memory loaded ({len(conversation)} convo entries, {state}).")
    _persist_memory_file()
    return conversation


def _persist_memory_file():
    """Atomic-ish save to avoid WinError 5; fallback to direct write on failure."""
    os.makedirs(MEMORY_PATH.parent, exist_ok=True)
    payload = json.dumps(memory_data, indent=2, ensure_ascii=False)
    last_err = None
    for attempt in range(3):
        tmp = MEMORY_PATH.with_suffix(f".tmp.{uuid.uuid4().hex}")
        try:
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, MEMORY_PATH)
            return
        except Exception as exc:
            last_err = exc
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
            time.sleep(0.2 * (attempt + 1))
    try:
        MEMORY_PATH.write_text(payload, encoding="utf-8")
    except Exception:
        if last_err:
            log_issue(
                "PHX-MEM-015",
                "memory_save_failed",
                str(last_err),
                source="memory",
                extra={"path": str(MEMORY_PATH)},
            )


def save_memory():
    if not persist_enabled:
        return
    memory_data["conversation"] = conversation[-CACHE_HISTORY:]
    _persist_memory_file()


def _append(role: str, content):
    if not content:
        return
    if not isinstance(content, str):
        try:
            content = json.dumps(content, ensure_ascii=False)
        except Exception:
            content = str(content)
    if not content:
        return
    entry = {"role": role, "content": content}
    if (
        conversation
        and conversation[-1].get("role") == role
        and conversation[-1].get("content") == content
    ):
        return
    conversation.append(entry)
    if len(conversation) > CACHE_HISTORY * 3:
        del conversation[: -CACHE_HISTORY * 3]


def log_conversation(role: str, content: str):
    """Append a conversation turn and persist a rolling window."""
    _append(role, content)
    save_memory()


def save_memory_entry(entry: dict):
    """Store an arbitrary memory entry in the conversation log."""
    if not isinstance(entry, dict):
        return
    _append("system", entry)
    save_memory()


def log_story_entry(entry: dict):
    """Archive Story Time summaries separately from conversational memory."""
    if not isinstance(entry, dict):
        return
    bucket = memory_data.setdefault("storytime", [])
    bucket.append(entry)
    if len(bucket) > 200:
        del bucket[:-200]
    if persist_enabled:
        _persist_memory_file()


def export_snapshot(label: str | None = None) -> Path | None:
    """Export current memory to data/memory_exports for inspection/backups."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        name = f"memory_export_{ts}"
        if label:
            safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", label)
            if safe:
                name += f"_{safe}"
        path = CACHE_DIR / f"{name}.json"
        payload = json.dumps(memory_data, indent=2, ensure_ascii=False)
        path.write_text(payload, encoding="utf-8")
        return path
    except Exception:
        return None


def set_persist_enabled(flag: bool):
    global persist_enabled
    persist_enabled = bool(flag)
    print(
        f" Memory persistence {'enabled' if persist_enabled else 'disabled (private mode)'}"
    )


def get_persist_enabled() -> bool:
    return bool(persist_enabled)


def prune_recent_conversation(entries: int = 1):
    """Drop the most recent N conversation turns (used for synthetic prompts)."""
    if entries <= 0:
        return
    removed = False
    for _ in range(min(entries, len(conversation))):
        conversation.pop()
        removed = True
    if removed:
        save_memory()


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower()
    lowered = re.sub(r"[^\w']+", " ", lowered)
    return lowered.strip()


def search_memories(query: str, max_hits: int = 5) -> list[dict]:
    """Return conversation entries containing all terms in query."""
    if not query:
        return []
    q_terms = []
    for token in query.split():
        cleaned = re.sub(r"[^\w']+", "", token.lower())
        if cleaned:
            q_terms.append(cleaned)
    prioritized: list[dict] = []
    others: list[dict] = []
    norm_query = _normalize_text(query)
    recent_skipped = False
    for idx in range(len(conversation) - 1, -1, -1):
        entry = conversation[idx]
        text = entry.get("content", "")
        norm = _normalize_text(text)
        role = entry.get("role", "user")
        if not recent_skipped and role == "user" and norm and norm == norm_query:
            recent_skipped = True
            continue
        if all(term in norm for term in q_terms):
            target = prioritized if role in {"assistant", "system"} else others
            target.append(entry)
            if len(prioritized) + len(others) >= max_hits:
                break
    ordered = prioritized + others
    ordered = ordered[:max_hits]
    return list(reversed(ordered))
