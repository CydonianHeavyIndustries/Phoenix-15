"""
systems/stories.py — Story import and "Story Time" helper.

Allows importing narrative material (ChatGPT share links, docx/txt files, manual
text) into a local library and provides a helper to summarize/reflect on one
story at a time.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
import zipfile
from typing import Any, Optional

import requests

from core import memory as _memory

STORIES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "stories")
)
INDEX_FILE = os.path.join(STORIES_DIR, "index.json")

_INDEX_CACHE: list[dict[str, Any]] | None = None


def _ensure_dirs():
    os.makedirs(STORIES_DIR, exist_ok=True)


def _load_index() -> list[dict[str, Any]]:
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE
    _ensure_dirs()
    if not os.path.exists(INDEX_FILE):
        _INDEX_CACHE = []
    else:
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                _INDEX_CACHE = json.load(f)
        except Exception:
            _INDEX_CACHE = []
    return _INDEX_CACHE


def _save_index(data: list[dict[str, Any]]):
    global _INDEX_CACHE
    _INDEX_CACHE = data
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _generate_story_id() -> str:
    return uuid.uuid4().hex


def list_stories() -> list[dict[str, Any]]:
    return sorted(
        _load_index(), key=lambda item: item.get("imported_at", 0), reverse=True
    )


def _write_story_text(story_id: str, text: str) -> str:
    _ensure_dirs()
    path = os.path.join(STORIES_DIR, f"{story_id}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")
    return path


def import_text_story(
    title: str,
    text: str,
    source_type: str = "manual",
    source: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("Story text is empty.")
    story_id = _generate_story_id()
    path = _write_story_text(story_id, text)
    entry = {
        "id": story_id,
        "title": title.strip() or f"Story {story_id[:6]}",
        "source_type": source_type,
        "source": source,
        "metadata": metadata or {},
        "path": path,
        "imported_at": time.time(),
        "last_played": None,
        "summary": None,
        "reaction": None,
    }
    index = _load_index()
    index.append(entry)
    _save_index(index)
    return entry


def import_text_file(file_path: str, title: Optional[str] = None) -> dict[str, Any]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    if ext in {".txt", ".md", ".log"}:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    elif ext == ".docx":
        text = _read_docx(file_path)
    else:
        raise ValueError("Unsupported file type. Use .txt, .md, or .docx.")
    title = title or os.path.splitext(os.path.basename(file_path))[0]
    return import_text_story(title, text, source_type="file", source=file_path)


def import_chatgpt_share(url: str, title: Optional[str] = None) -> dict[str, Any]:
    url = (url or "").strip()
    if not url:
        raise ValueError("Share link is empty.")
    text = _fetch_chatgpt_share(url)
    if not text:
        raise RuntimeError(
            "Unable to read the shared conversation. Download or copy the text manually."
        )
    base_title = title or "ChatGPT Conversation"
    return import_text_story(base_title, text, source_type="chatgpt_share", source=url)


def _fetch_chatgpt_share(url: str) -> str:
    """Best-effort attempt to extract plain text from a ChatGPT shared link."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (StoryTimeBot)"}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return ""
        html = resp.text
        # Remove scripts/styles
        html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
        html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
        # Replace block tags with newlines
        html = re.sub(r"</(p|div|li|br|h[1-6])>", "\n", html, flags=re.I)
        # Strip tags
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"\n{2,}", "\n", text)
        return text.strip()
    except Exception:
        return ""


def _read_docx(path: str) -> str:
    try:
        with zipfile.ZipFile(path) as docx:
            with docx.open("word/document.xml") as xml_file:
                xml = xml_file.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        raise RuntimeError(f"Unable to read DOCX: {exc}") from exc
    # Replace paragraph tags with newlines
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<[^>]+>", " ", xml)
    xml = re.sub(r"\s{2,}", " ", xml)
    return xml.strip()


def story_time_next() -> Optional[dict[str, Any]]:
    index = _load_index()
    if not index:
        return None
    # pick oldest unplayed, otherwise oldest by last_played
    candidates = sorted(
        index, key=lambda item: (item.get("last_played") or 0, item["imported_at"])
    )
    story = candidates[0]
    with open(story["path"], "r", encoding="utf-8") as f:
        text = f.read()
    summary, reaction = _summarize_story(story, text)
    now = time.time()
    story["last_played"] = now
    story["summary"] = summary
    story["reaction"] = reaction
    _save_index(index)
    try:
        _memory.log_story_entry(
            {
                "id": story["id"],
                "title": story["title"],
                "summary": summary,
                "reaction": reaction,
                "timestamp": now,
                "source": story.get("source"),
            }
        )
        _memory.prune_recent_conversation(entries=2)
    except Exception:
        pass
    return {
        "id": story["id"],
        "title": story["title"],
        "summary": summary,
        "reaction": reaction,
        "path": story["path"],
        "source": story.get("source"),
    }


def _summarize_story(story: dict[str, Any], text: str) -> tuple[str, str]:
    from runtime import coreloop

    prompt = (
        "You are reading a story file that the user shared during a cozy 'Story Time' ritual.\n"
        "1. Provide a concise summary (3-4 sentences) capturing the tone, key beats, and any emotional arc.\n"
        "2. Follow with a short personal reflection (2 sentences max) that gently shares how it makes you feel or what it inspires in you.\n"
        "Keep it respectful, warm, and curious. If the text is empty, say so.\n"
        f"Story title: {story.get('title', 'Untitled')}\n"
        f"Story source type: {story.get('source_type', 'unknown')}.\n\n"
        f"Story begins:\n{text.strip()[:6000]}"
    )
    reply = coreloop.process_input(prompt)
    if not reply.strip():
        return "I couldn't read this story.", "But I'm still grateful you shared it."
    parts = reply.strip().split("\n")
    summary = "\n".join(parts[:4]).strip()
    reflection = "\n".join(parts[4:]).strip() or "It leaves me quietly thoughtful."
    return summary, reflection
