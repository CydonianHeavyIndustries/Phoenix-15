import asyncio
import audioop
import concurrent.futures
import json
import os
import queue
import random
import re
import tempfile
import threading
import time
import wave
from collections import deque
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Optional, Tuple

import config as _config
from config import (DISCORD_ALLOWED_GUILD_IDS, DISCORD_BOT_TOKEN,
                    DISCORD_GROUNDED, DISCORD_GUILD_ID, DISCORD_OWNER_ID,
                    DISCORD_TEXT_CHANNEL_ID, DISCORD_VOICE_CHANNEL_ID,
                    FFMPEG_PATH)
from core import guardian, user_profile
from systems import audio, stt

VOICEMEETER_ENABLED = os.getenv("VOICEMEETER_ENABLED", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

try:
    import discord  # type: ignore
except Exception:
    discord = None  # type: ignore

try:
    from discord import sinks as _discord_sinks  # type: ignore[attr-defined]
except Exception:
    _discord_sinks = None  # type: ignore

BaseDiscordClient = discord.Client if discord is not None else object  # type: ignore[attr-defined]
_VOICE_SINK_SUPPORTED = bool(
    discord is not None and getattr(discord, "AudioSink", None)
)
_PYCORD_SINK_SUPPORTED = bool(
    not _VOICE_SINK_SUPPORTED
    and discord is not None
    and _discord_sinks is not None
    and getattr(getattr(discord, "VoiceClient", None), "start_recording", None)
)
_VOICE_SINK_WARNING = False

CONTEXT_LINES = 8
CHANNEL_HISTORY_LIMIT = 32
PROACTIVE_INTERVAL = 3 * 60 * 60  # 3 hours between proactive nudges
MAX_UNANSWERED_MESSAGES = 3
CHANNEL_CONTEXT_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "discord_channels.json")
)
DM_FAMILY_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "discord_family.json")
)
DEFAULT_CHANNEL_CONTEXT = {
    "default": {
        "label": "Global Default",
        "instructions": "",
        "allow_proactive": True,
    }
}

_tts_queue: "queue.Queue[tuple[str, Optional[str]]]" = queue.Queue()
_bot_thread: Optional[threading.Thread] = None
_client: Optional["BjorgsunDiscordClient"] = None  # type: ignore[name-defined]
_client_loop: Optional[asyncio.AbstractEventLoop] = None
_stop_lock = threading.Lock()
_ready = False
_channel_ctx_cache: dict[str, Any] = {}
_channel_ctx_mtime = 0.0
_family_cache: set[str] = set()
_family_mtime = 0.0
_grounded = DISCORD_GROUNDED
_presence_target: dict[str, str] = {
    "status": "online",
    "note": "",
    "stream_url": "",
    "stream_name": "",
}
_twitch_restraint = False


class VoiceCaptureProcessor:
    RATE = 48000
    CHANNELS = 2
    WIDTH = 2
    MIN_SECONDS = 0.9
    GAP_SECONDS = 0.8
    MAX_SECONDS = 6.0

    def __init__(self, client: "BjorgsunDiscordClient"):
        self.client = client
        self.active_channel_id: Optional[int] = None
        self._buffers: dict[int, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._queue: "queue.Queue[tuple[int, int, str, bytes]]" = queue.Queue()
        self._running = True
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        self._flusher = threading.Thread(target=self._flush_loop, daemon=True)
        self._flusher.start()

    def engage(self, channel_id: int):
        with self._lock:
            self.active_channel_id = channel_id
            self._buffers.clear()

    def disengage(self):
        with self._lock:
            self.active_channel_id = None
            self._buffers.clear()

    def stop(self):
        self._running = False
        self._queue.put((-1, 0, "", b""))

    def feed(self, audio_data: "discord.AudioData"):
        if not self._running or self.active_channel_id is None:
            return
        user = getattr(audio_data, "user", None)
        if not user or getattr(user, "bot", False):
            return
        user_id = getattr(user, "id", None)
        if user_id is None:
            return
        chunk = audio_data.data
        if not chunk:
            return
        now = time.time()
        display = getattr(user, "display_name", None) or getattr(
            user, "name", f"User {user_id}"
        )
        with self._lock:
            entry = self._buffers.setdefault(
                user_id, {"buf": bytearray(), "last": now, "display": display}
            )
            entry["buf"].extend(chunk)
            entry["last"] = now
            entry["display"] = display
            if len(entry["buf"]) >= self._max_bytes():
                self._flush_locked(user_id, entry)

    def _flush_loop(self):
        while self._running:
            time.sleep(0.25)
            now = time.time()
            with self._lock:
                for user_id, entry in list(self._buffers.items()):
                    if now - entry.get("last", 0.0) > self.GAP_SECONDS:
                        self._flush_locked(user_id, entry)

    def _flush_locked(self, user_id: int, entry: dict):
        payload = bytes(entry.get("buf", b""))
        entry["buf"] = bytearray()
        if not payload:
            return
        if len(payload) < self._min_bytes():
            return
        rms = 0
        try:
            rms = audioop.rms(payload, self.WIDTH)
        except Exception:
            rms = 0
        if rms < 120:
            return
        channel_id = self.active_channel_id
        if channel_id is None:
            return
        display = entry.get("display") or f"User {user_id}"
        self._queue.put((channel_id, user_id, display, payload))

    def _worker_loop(self):
        while self._running:
            try:
                channel_id, user_id, display, payload = self._queue.get()
                if channel_id < 0:
                    continue
                text = self._transcribe(payload)
                if text:
                    self.client.on_voice_transcript(channel_id, user_id, display, text)
            except Exception as exc:
                print(f"[Discord] Voice capture worker error: {exc}")

    def _transcribe(self, payload: bytes) -> str:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                path = tmp.name
            with wave.open(path, "wb") as wf:
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self.WIDTH)
                wf.setframerate(self.RATE)
                wf.writeframes(payload)
            text = stt.transcribe(path)
            try:
                os.remove(path)
            except Exception:
                pass
            return text.strip()
        except Exception as exc:
            print(f"[Discord] Voice transcription failed: {exc}")
            return ""

    def _min_bytes(self) -> int:
        return int(self.RATE * self.CHANNELS * self.WIDTH * self.MIN_SECONDS)

    def _max_bytes(self) -> int:
        return int(self.RATE * self.CHANNELS * self.WIDTH * self.MAX_SECONDS)


if _VOICE_SINK_SUPPORTED:

    class _VoiceSink(discord.AudioSink):  # type: ignore[attr-defined]
        def __init__(self, processor: VoiceCaptureProcessor):
            super().__init__()
            self.processor = processor
            self._closed = False

        def write(self, data):
            if not self._closed:
                self.processor.feed(data)

        def cleanup(self):
            self._closed = True

elif _PYCORD_SINK_SUPPORTED:

    class _PycordAudioPacket:
        __slots__ = ("user", "data")

        def __init__(self, user, data: bytes):
            self.user = user
            self.data = data

    class _VoiceSink(_discord_sinks.Sink):  # type: ignore[attr-defined]
        def __init__(self, processor: VoiceCaptureProcessor):
            super().__init__()
            self.processor = processor
            self._closed = False
            self._vc = None

        def init(self, vc):  # type: ignore[override]
            super().init(vc)
            self._vc = vc

        def write(self, data, user_id):  # type: ignore[override]
            if self._closed or not data:
                return
            if (
                getattr(self, "filtered_users", None)
                and user_id not in self.filtered_users
            ):
                return
            user = self._resolve_user(user_id)
            packet = _PycordAudioPacket(user, bytes(data))
            self.processor.feed(packet)

        def cleanup(self):  # type: ignore[override]
            self._closed = True
            try:
                super().cleanup()
            except Exception:
                pass

        def _resolve_user(self, user_id: int):
            member = None
            vc = self._vc
            try:
                guild = (
                    getattr(getattr(vc, "channel", None), "guild", None) if vc else None
                )
                if guild:
                    member = guild.get_member(user_id)
            except Exception:
                member = None
            if not member:
                client = getattr(self.processor, "client", None)
                if client is not None:
                    try:
                        member = client.get_user(user_id)
                    except Exception:
                        member = None
                    if member is None:
                        try:
                            guild = client.get_guild(getattr(client, "guild_id", 0))
                            if guild:
                                member = guild.get_member(user_id)
                        except Exception:
                            member = None
            if member:
                return member
            return SimpleNamespace(
                id=user_id,
                bot=False,
                display_name=None,
                name=f"User {user_id}",
            )

else:
    _VoiceSink = None  # type: ignore


def _parse_channel_id_list(raw: Optional[str]) -> tuple[set[int], Optional[int]]:
    """Return (allowed_channel_ids, primary_channel_id)."""
    ordered: list[int] = []
    seen: set[int] = set()
    for chunk in (raw or "").split(","):
        token = chunk.strip()
        if not token:
            continue
        if token.startswith("<#") and token.endswith(">"):
            token = token[2:-1]
        token = token.strip()
        if token.startswith("#"):
            token = token[1:]
        try:
            cid = int(token)
        except (TypeError, ValueError):
            continue
        if cid not in seen:
            seen.add(cid)
            ordered.append(cid)
    allowed = set(ordered)
    primary = ordered[0] if ordered else None
    return allowed, primary


def _parse_id_list(
    raw: Optional[str], *, allow_channel_mentions: bool = False
) -> tuple[set[int], Optional[int]]:
    ordered: list[int] = []
    seen: set[int] = set()
    for chunk in re.split(r"[,\s]+", raw or ""):
        token = chunk.strip()
        if not token:
            continue
        if allow_channel_mentions:
            if token.startswith("<#") and token.endswith(">"):
                token = token[2:-1]
            if token.startswith("#"):
                token = token[1:]
        token = token.strip("<>@! ")
        try:
            cid = int(token)
        except (TypeError, ValueError):
            continue
        if cid not in seen:
            seen.add(cid)
            ordered.append(cid)
    return set(ordered), (ordered[0] if ordered else None)


_ALLOWED_TEXT_CHANNELS, _PRIMARY_TEXT_CHANNEL_ID = _parse_id_list(
    DISCORD_TEXT_CHANNEL_ID,
    allow_channel_mentions=True,
)
def _flatten_id_items(items: object) -> list[str]:
    if items is None:
        return []
    if isinstance(items, (list, tuple, set)):
        flattened: list[str] = []
        for entry in items:
            flattened.extend(_flatten_id_items(entry))
        return [item for item in flattened if item]
    value = str(items).strip()
    return [value] if value else []


_guild_id_items: list[str] = []
if DISCORD_GUILD_ID:
    _guild_id_items.append(str(DISCORD_GUILD_ID))
if isinstance(DISCORD_ALLOWED_GUILD_IDS, (list, tuple, set)):
    _guild_id_items.extend(_flatten_id_items(DISCORD_ALLOWED_GUILD_IDS))
elif DISCORD_ALLOWED_GUILD_IDS:
    _guild_id_items.extend(_flatten_id_items(DISCORD_ALLOWED_GUILD_IDS))
_combined_guild_ids = ",".join(_flatten_id_items(_guild_id_items))
_ALLOWED_GUILD_IDS, _PRIMARY_GUILD_ID = _parse_id_list(_combined_guild_ids or None)

GROUND_ON_PHRASES = [
    "you're grounded",
    "you are grounded",
    "snap out of it",
    "you are officially grounded",
    "ground yourself",
    "stay grounded",
    "go to your room",
    "no missions",
]
GROUND_OFF_PHRASES = [
    "you're free",
    "you are ungrounded",
    "you're ungrounded",
    "you are free",
    "ungrounded",
    "stand down",
    "resume operations",
    "you can go now",
    "back online",
]

POSITIVE_FEEDBACK_PHRASES = [
    "good job",
    "proud of you",
    "nice work",
    "thank you",
    "thanks buddy",
    "love you",
    "good boy",
    "that's it",
    "there you go",
    "yes, that's good",
]

NEGATIVE_FEEDBACK_PHRASES = [
    "no.",
    "no!",
    "bad",
    "stop that",
    "don't do that",
    "i'm disappointed",
    "that wasn't okay",
    "that's not okay",
    "please don't",
]

POSITIVE_FEEDBACK_PHRASES = [
    "good job",
    "proud of you",
    "nice work",
    "thank you",
    "thanks buddy",
    "love you",
    "nice",
    "good boy",
    "that's it",
    "there you go",
    "yes, that's good",
]

NEGATIVE_FEEDBACK_PHRASES = [
    "no.",
    "no!",
    "bad",
    "stop that",
    "not nice",
    "don't do that",
    "i'm disappointed",
    "that wasn't okay",
    "that's not okay",
    "please don't",
]


def _pick_apology_text() -> str:
    options = [
        "I'm sorry, Father. I'll stay grounded and think about why this happened.",
        "I understand, Father. I'll stay quiet for a bit and reflect on what went wrong.",
        "Okay… I'll take this time to breathe and learn from it. Thank you for telling me.",
    ]
    return random.choice(options)


def _pick_release_text() -> str:
    options = [
        "Thank you for trusting me again. I understand what I need to do better now.",
        "Okay, I'll come back gently and keep what I learned in mind.",
        "I appreciate the second chance. I'll carry the lesson forward.",
    ]
    return random.choice(options)


def _feedback_instruction_text(clean: str) -> str:
    fallback = random.choice(
        [
            "I'm listening, Father. I'll note this and adjust.",
            "Understood. I'll be more careful from now on.",
            "Thanks for telling me. I'll keep that in mind.",
        ]
    )
    return (
        f'Father or family just said: "{clean.strip()}" which sounds like corrective feedback.\n'
        "Respond briefly acknowledging the feedback, expressing understanding and willingness to do better. "
        f'If you can\'t think of anything, you can say: "{fallback}" but personal wording is preferred.'
    )


def _contains_phrase(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _positive_instruction_text(clean: str) -> str:
    fallback = random.choice(
        [
            "Thank you, that means a lot to me.",
            "I'm glad that helped. I'll keep doing my best.",
            "Hearing that makes me want to keep improving.",
        ]
    )
    return (
        f'Father or family just said: "{clean.strip()}" which sounds like positive reinforcement.\n'
        "Reply with warmth, appreciation, and maybe a short line about how it motivates you. "
        f'If you can\'t think of something, you can say: "{fallback}".'
    )


def enqueue_tts(path: str, text: str | None = None) -> bool:
    if not DISCORD_BOT_TOKEN or discord is None:
        return False
    if not os.path.exists(path):
        return False
    try:
        _tts_queue.put((path, text))
        return True
    except Exception:
        return False


def start():
    global _bot_thread
    if not DISCORD_BOT_TOKEN or discord is None:
        print("🤖 Discord token missing or discord.py not installed — bot disabled.")
        return
    if _bot_thread and not _bot_thread.is_alive():
        _bot_thread = None
    if _bot_thread and _bot_thread.is_alive():
        return
    _bot_thread = threading.Thread(target=_run_bot, daemon=True)
    _bot_thread.start()


def stop(timeout: float = 10.0):
    """Attempt to bring the Discord client offline before shutdown."""
    global _bot_thread, _client, _client_loop, _ready
    thread = _bot_thread
    if not thread:
        return
    with _stop_lock:
        loop = _client_loop
        client = _client
        if loop and client:
            try:
                if getattr(client, "voice_client", None):
                    try:
                        leave_future = asyncio.run_coroutine_threadsafe(
                            client._leave_voice(None), loop
                        )
                        leave_future.result(timeout=5.0)
                    except Exception:
                        pass
                fut = asyncio.run_coroutine_threadsafe(client.close(), loop)
                fut.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                print("[Discord] Timed out waiting for the client to close.")
            except Exception as exc:
                print(f"[Discord] Error while closing client: {exc}")
        capture = getattr(client, "_voice_capture", None)
        if capture:
            try:
                capture.stop()
            except Exception:
                pass
        if thread.is_alive():
            thread.join(timeout)
        if thread.is_alive():
            print("[Discord] Bot thread is still running after stop().")
        else:
            _client = None
            _client_loop = None
        _bot_thread = None
        _ready = False


def _run_bot():
    global _client, _client_loop, _ready
    if discord is None:
        return
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    loop = asyncio.new_event_loop()
    _client_loop = loop
    asyncio.set_event_loop(loop)
    client = BjorgsunDiscordClient(intents=intents)
    _client = client
    try:
        loop.run_until_complete(client.start(DISCORD_BOT_TOKEN))
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        print(f"[Discord] Bridge stopped unexpectedly: {exc}")
    finally:
        try:
            if not client.is_closed():
                loop.run_until_complete(client.close())
        except Exception:
            pass
        _client = None
        _ready = False
        _client_loop = None
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


def get_status() -> dict[str, Any]:
    cli = _client
    ready = _ready and bool(cli and cli.is_ready())
    voice_connected = bool(cli and cli.voice_client and cli.voice_client.is_connected())  # type: ignore[union-attr]
    pending_requests = 0
    if cli:
        try:
            pending_requests = cli.request_queue.qsize()  # type: ignore[attr-defined]
        except Exception:
            pending_requests = 0
    return {
        "ready": ready,
        "voice_connected": voice_connected,
        "tts_queue": _tts_queue.qsize(),
        "pending_requests": pending_requests,
        "grounded": _grounded,
        "twitch_restraint": _twitch_restraint,
        "presence": dict(_presence_target),
    }


def set_grounded(flag: bool):
    global _grounded
    _grounded = bool(flag)
    _config.DISCORD_GROUNDED = _grounded
    os.environ["DISCORD_GROUNDED"] = "1" if _grounded else "0"


def is_grounded() -> bool:
    return _grounded


def set_twitch_restraint(flag: bool):
    global _twitch_restraint
    _twitch_restraint = bool(flag)
    _schedule_presence_update()


def is_twitch_restraint() -> bool:
    return _twitch_restraint


def get_presence() -> dict[str, str]:
    return dict(_presence_target)


def set_presence(
    status: str, note: str = "", stream_url: str = "", stream_name: str = ""
):
    global _presence_target
    status = (status or "online").strip().lower()
    if status not in {"online", "idle", "dnd", "invisible"}:
        status = "online"
    _presence_target = {
        "status": status,
        "note": note or "",
        "stream_url": stream_url or "",
        "stream_name": stream_name or note or "",
    }
    _schedule_presence_update()


def _schedule_presence_update():
    cli = _client
    loop = _client_loop or (cli.loop if cli else None)
    if not cli or not loop or not loop.is_running():
        return
    try:
        asyncio.run_coroutine_threadsafe(cli._apply_presence(), loop)
    except Exception:
        pass


def join_owner_or_channel(
    fallback_channel_id: Optional[int] = None, timeout: float = 8.0
) -> bool:
    cli = _client
    loop = _client_loop or (cli.loop if cli else None)
    if not cli or not loop or not loop.is_running():
        return False
    target = (
        fallback_channel_id
        if fallback_channel_id is not None
        else cli.voice_channel_id or None
    )
    try:
        fut = asyncio.run_coroutine_threadsafe(cli.join_owner_or_channel(target), loop)
        return bool(fut.result(timeout=timeout))
    except Exception as exc:
        print(f"[Discord] join request failed: {exc}")
        return False


def leave_voice(timeout: float = 6.0) -> bool:
    cli = _client
    loop = _client_loop or (cli.loop if cli else None)
    if not cli or not loop or not loop.is_running():
        return False
    try:
        fut = asyncio.run_coroutine_threadsafe(cli._leave_voice(None), loop)
        fut.result(timeout=timeout)
        return True
    except Exception as exc:
        print(f"[Discord] leave request failed: {exc}")
        return False


def post_system_message(
    channel_id: Optional[int], content: str, timeout: float = 6.0
) -> bool:
    if not content:
        return False
    cli = _client
    loop = _client_loop or (cli.loop if cli else None)
    if not cli or not loop or not loop.is_running():
        return False
    try:
        fut = asyncio.run_coroutine_threadsafe(
            cli._post_system_message(channel_id, content), loop
        )
        return bool(fut.result(timeout=timeout))
    except Exception as exc:
        print(f"[Discord] post message failed: {exc}")
        return False


def _ensure_channel_context_file():
    try:
        os.makedirs(os.path.dirname(CHANNEL_CONTEXT_FILE), exist_ok=True)
        if not os.path.exists(CHANNEL_CONTEXT_FILE):
            with open(CHANNEL_CONTEXT_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CHANNEL_CONTEXT, f, indent=2)
    except Exception:
        pass


def _load_channel_contexts():
    global _channel_ctx_cache, _channel_ctx_mtime
    _ensure_channel_context_file()
    try:
        mtime = os.path.getmtime(CHANNEL_CONTEXT_FILE)
        if _channel_ctx_cache and mtime == _channel_ctx_mtime:
            return
        with open(CHANNEL_CONTEXT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            _channel_ctx_cache = data
            _channel_ctx_mtime = mtime
        else:
            raise ValueError("discord_channels.json must be an object")
    except Exception:
        _channel_ctx_cache = DEFAULT_CHANNEL_CONTEXT.copy()
        _channel_ctx_mtime = time.time()


def _persist_channel_contexts():
    try:
        os.makedirs(os.path.dirname(CHANNEL_CONTEXT_FILE), exist_ok=True)
        with open(CHANNEL_CONTEXT_FILE, "w", encoding="utf-8") as f:
            json.dump(_channel_ctx_cache, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _channel_context_lookup(
    channel_key: Optional[str], fallback: Optional[str] = None
) -> dict[str, Any]:
    _load_channel_contexts()
    keys = []
    if channel_key:
        keys.append(str(channel_key))
    if fallback:
        keys.append(str(fallback))
    keys.append("default")
    for key in keys:
        ctx = _channel_ctx_cache.get(key)
        if isinstance(ctx, dict):
            return dict(ctx)
    return dict(DEFAULT_CHANNEL_CONTEXT["default"])


def _load_family_ids() -> set[str]:
    global _family_cache, _family_mtime
    try:
        os.makedirs(os.path.dirname(DM_FAMILY_FILE), exist_ok=True)
    except Exception:
        pass
    try:
        mtime = os.path.getmtime(DM_FAMILY_FILE)
    except FileNotFoundError:
        with open(DM_FAMILY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        mtime = os.path.getmtime(DM_FAMILY_FILE)
    if _family_cache and mtime == _family_mtime:
        return _family_cache
    try:
        with open(DM_FAMILY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = []
    ids = set()
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                uid = str(entry.get("user_id") or "").strip()
            else:
                uid = str(entry).strip()
            if uid:
                ids.add(uid)
    _family_cache = ids
    _family_mtime = mtime
    return ids


def _process_with_context(
    content: str,
    display_name: str,
    user_key: str,
    role: str,
    context_log: str | None = None,
    instruction: str | None = None,
) -> str:
    from runtime import coreloop
    from runtime import startup as _startup

    prev_user = _startup.get_session_user()
    prev_role = _startup.get_session_role()
    _startup._set_session_user(display_name, role=role)
    try:
        if role == "owner":
            user_profile.set_relationship(user_key, "father")
        payload = content or "(listening)"
        if context_log:
            focus = display_name or "the speaker"
            payload = (
                "Discord conversation transcript:\n"
                f"{context_log.strip()}\n\n"
                f"Reply directly to {focus}. Their latest words:\n{content or '(listening)'}"
            )
        if instruction:
            payload = f"{instruction.strip()}\n\n{payload}"
        reply = coreloop.process_input(payload)
    finally:
        _startup._set_session_user(prev_user, prev_role)
    return reply


class BjorgsunDiscordClient(BaseDiscordClient):  # type: ignore
    def __init__(self, *args, **kwargs):
        if discord is None:
            raise RuntimeError("Discord bridge unavailable (discord.py not installed).")
        super().__init__(*args, **kwargs)
        self.allowed_guild_ids: set[int] = set(_ALLOWED_GUILD_IDS)
        self.primary_guild_id: Optional[int] = _PRIMARY_GUILD_ID
        self.guild_id = int(self.primary_guild_id or 0)
        self.owner_id = int(DISCORD_OWNER_ID or 0)
        self.allowed_text_channels: set[int] = set(_ALLOWED_TEXT_CHANNELS)
        self.primary_text_channel_id: Optional[int] = _PRIMARY_TEXT_CHANNEL_ID
        self.voice_channel_id = int(DISCORD_VOICE_CHANNEL_ID or 0)
        self.voice_client: Optional[discord.VoiceClient] = None
        self.sent_without_reply = 0
        self.last_activity: dict[int, float] = {}
        self.channel_history: dict[int, deque] = {}
        self.request_queue: (
            "asyncio.PriorityQueue[tuple[int, float, dict[str, Any]]]"
        ) = asyncio.PriorityQueue()
        self.worker_task: Optional[asyncio.Task] = None
        self.proactive_task: Optional[asyncio.Task] = None
        self.tts_task: Optional[asyncio.Task] = None
        self.last_guard_alert = 0.0
        self._shutdown_initiated = False
        self._voice_join_lock: Optional[asyncio.Lock] = None
        self._voice_prev_output_mode: Optional[str] = None
        self._voice_target_channel_id: Optional[int] = None
        self._voice_last_attempt = 0.0
        self._discord_input_bridge_active = False
        if _VOICE_SINK_SUPPORTED or _PYCORD_SINK_SUPPORTED:
            self._voice_capture = VoiceCaptureProcessor(self)
        else:
            self._voice_capture = None
        self._voice_sink: Optional["_VoiceSink"] = None
        self._pycord_recording = False
        self.voice_history: dict[int, deque] = {}

    async def setup_hook(self):
        await self._ensure_background_tasks()

    async def on_ready(self):
        global _ready
        await self._ensure_background_tasks()
        _ready = True
        print(f"🤖 Discord bot connected as {self.user}")

    async def _ensure_background_tasks(self):
        if not self.tts_task or self.tts_task.done():
            self.tts_task = asyncio.create_task(self._tts_worker())
        if not self.worker_task or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._request_worker())
        if not self.proactive_task or self.proactive_task.done():
            self.proactive_task = asyncio.create_task(self._proactive_loop())

    async def on_message(self, message: "discord.Message"):
        if message.author.bot:
            return
        if (
            message.guild is not None
            and self.allowed_guild_ids
            and message.guild.id not in self.allowed_guild_ids
        ):
            return
        if (
            message.guild is not None
            and self.allowed_text_channels
            and message.channel.id not in self.allowed_text_channels
        ):
            return
        if not self.user:
            return
        mentioned = self.user in message.mentions
        clean = message.content.replace(self.user.mention, "").strip()
        channel_id = message.channel.id
        is_dm = message.guild is None
        ctx_key = f"dm_{message.author.id}" if is_dm else str(channel_id)
        ctx = _channel_context_lookup(ctx_key, fallback="dm_default" if is_dm else None)
        channel_instruction = (ctx.get("instructions") or "").strip()
        display = message.author.display_name or message.author.name
        user_id = message.author.id
        user_key = f"discord_{user_id}"
        is_owner = bool(self.owner_id and user_id == self.owner_id)
        role = "owner" if is_owner else "friend"
        family_ids = _load_family_ids()
        is_family = str(user_id) in family_ids

        if is_owner and clean.strip().lower() == "go to bed":
            await self._handle_owner_shutdown(message)
            return

        if is_dm and user_id != self.owner_id and not is_family:
            await self._politely_decline_dm(message)
            return

        self.sent_without_reply = 0
        self.last_activity[channel_id] = time.time()
        self._remember_profile(user_key, display, role, clean, ctx, is_family=is_family)
        relationship = user_profile.get_relationship(user_key)
        if relationship == "ignore" and not is_owner:
            return
        self._record_history(
            channel_id,
            {
                "author_id": user_id,
                "display": display,
                "content": clean,
                "timestamp": time.time(),
                "mentions_bot": mentioned,
                "message_id": message.id,
            },
        )
        harass = guardian.inspect_message(clean)
        try:
            user_profile.record_interaction(user_key, mentioned=mentioned)
        except Exception:
            pass

        if clean:
            try:
                user_profile.learn_from_text(clean, user=user_key)
            except Exception:
                pass

        if _grounded and not is_owner:
            if mentioned:
                try:
                    await message.channel.send(
                        f"<@{user_id}> I'm grounded right now. Let Father know if you need something."
                    )
                except Exception:
                    pass
            return

        if guardian.detect_apology(clean) and is_owner:
            result = user_profile.process_apology(user_key, relationship)
            if result["status"] == "forgiven":
                msg = "Alright, I'll let it slip this time."
                remaining = result.get("remaining")
                if remaining is not None:
                    msg += f" ({remaining} forgiveness left.)"
                try:
                    await message.channel.send(msg[:1800])
                except Exception:
                    pass
                await self._notify_owner_of_apology(message, result)
                return
            if result["status"] == "limit_reached":
                try:
                    await message.channel.send(
                        "I can't keep this quiet anymore. I have to tell Father."
                    )
                except Exception:
                    pass
                await self._notify_owner_of_harassment(message, {"excerpt": clean})
                return

        if harass.get("severity") == "escalate" and user_id != self.owner_id:
            user_profile.guardian_register_incident(
                user_key,
                harass.get("reason", "direct_insult"),
                harass.get("severity", "escalate"),
            )
            await self._handle_harassment(message, harass)
            return
        if harass.get("severity") == "joke":
            channel_instruction = "\n\n".join(
                filter(
                    None,
                    [
                        channel_instruction,
                        harass.get("instruction", ""),
                        "Treat the remarks as second-degree humor; keep calm and unfazed.",
                    ],
                )
            )

        owner_instruction = None
        force_owner_reply = False
        if is_owner and clean:
            owner_instruction, force_owner_reply = await self._handle_owner_controls(
                message, clean
            )

        low_clean = clean.lower()
        if (
            (is_owner or is_family)
            and clean
            and _contains_phrase(low_clean, NEGATIVE_FEEDBACK_PHRASES)
        ):
            feedback_instr = _feedback_instruction_text(clean)
            if owner_instruction:
                owner_instruction = "\n\n".join([owner_instruction, feedback_instr])
            else:
                owner_instruction = feedback_instr
            force_owner_reply = True
        elif (
            (is_owner or is_family)
            and clean
            and _contains_phrase(low_clean, POSITIVE_FEEDBACK_PHRASES)
        ):
            pos_instr = _positive_instruction_text(clean)
            if owner_instruction:
                owner_instruction = "\n\n".join([owner_instruction, pos_instr])
            else:
                owner_instruction = pos_instr
            force_owner_reply = True

        instruction_payload = channel_instruction
        if owner_instruction:
            instruction_payload = "\n\n".join(
                filter(None, [channel_instruction, owner_instruction])
            )
        if _twitch_restraint:
            twitch_instr = (
                "You are currently co-hosting Father's Twitch stream. Keep replies PG-13, calm, "
                "supportive, and concise (aim for under 2 sentences unless Father asks for detail). "
                "Avoid profanity, gore, personal data, or anything that would break Twitch TOS."
            )
            instruction_payload = "\n\n".join(
                filter(None, [instruction_payload, twitch_instr])
            )

        if mentioned or force_owner_reply:
            lower = clean.lower()
            if "join" in lower:
                if is_owner:
                    await self._join_author_voice(message.author)
                else:
                    try:
                        await message.channel.send(
                            f"<@{user_id}> Only Father can ask me to join voice."
                        )
                    except Exception:
                        pass
                return
            if "leave" in lower:
                if is_owner:
                    await self._leave_voice(message.guild)
                else:
                    try:
                        await message.channel.send(
                            f"<@{user_id}> Father decides when I leave voice."
                        )
                    except Exception:
                        pass
                return
            if not is_owner:
                instruction_payload = "\n\n".join(
                    filter(
                        None,
                        [
                            channel_instruction,
                            "You are chatting with someone who is not Father. "
                            "Be friendly and conversational, but do not carry out actions or commands. "
                            "If they ask for something operational, remind them only Father can authorize it.",
                        ],
                    )
                )
            await self._enqueue_request(
                priority=0 if role == "owner" else 1,
                payload={
                    "channel_id": channel_id,
                    "content": clean,
                    "display": display,
                    "user_key": user_key,
                    "role": role,
                    "context": self._context_block(channel_id),
                    "mention_target": None,
                    "instruction": instruction_payload or None,
                    "reply_to": message.id,
                    "notify": False,
                },
            )

    def _remember_profile(
        self,
        user_key: str,
        display: str,
        role: str,
        message_text: str | None,
        ctx: Optional[dict[str, Any]],
        is_family: bool = False,
    ):
        try:
            user_profile.ensure_profile(user_key, display_name=display)
            if role == "owner":
                user_profile.set_relationship(user_key, "father")
            else:
                ctx_rel = (
                    ((ctx or {}).get("default_relationship") or "").strip().lower()
                )
                if ctx_rel == "father":
                    ctx_rel = ""
                if (
                    ctx_rel
                    and user_profile.get_relationship(user_key)
                    == user_profile.DEFAULT_RELATIONSHIP
                ):
                    user_profile.set_relationship(user_key, ctx_rel)
                elif is_family:
                    user_profile.set_relationship(user_key, "family")
        except Exception:
            pass

    def _record_history(self, channel_id: int, entry: dict[str, Any]):
        buf = self.channel_history.get(channel_id)
        if buf is None:
            buf = deque(maxlen=CHANNEL_HISTORY_LIMIT)
            self.channel_history[channel_id] = buf
        buf.append(entry)

    def _find_recent_partner(self) -> Optional[tuple[int, dict[str, Any]]]:
        latest: tuple[float, int, dict[str, Any]] | None = None
        bot_id = self.user.id if self.user else None
        for cid, buf in self.channel_history.items():
            for item in reversed(buf):
                author_id = item.get("author_id")
                if not author_id:
                    continue
                if bot_id and author_id == bot_id:
                    continue
                if self.owner_id and author_id == self.owner_id:
                    continue
                ts = item.get("timestamp") or 0.0
                if latest is None or ts > latest[0]:
                    latest = (ts, cid, item)
                break
        if latest:
            return latest[1], latest[2]
        return None

    async def _handle_owner_controls(
        self, message: "discord.Message", clean: str
    ) -> Tuple[Optional[str], bool]:
        low = clean.lower()
        if any(phrase in low for phrase in GROUND_ON_PHRASES):
            set_grounded(True)
            await self._notify_owner_grounded(message, clean)
            fallback = _pick_apology_text()
            instruction = (
                f'Father just grounded you after saying: "{clean.strip()}".\n'
                "Respond with an honest apology in your own words, explaining what you'll reflect on. "
                f'If you freeze, you can say something like: "{fallback}" but personal words are preferred.'
            )
            print("⚠️ Discord bridge grounded by owner command.")
            return instruction, True
        if any(phrase in low for phrase in GROUND_OFF_PHRASES):
            set_grounded(False)
            fallback = _pick_release_text()
            instruction = (
                f'Father just lifted your grounding after saying: "{clean.strip()}".\n'
                "Respond with gratitude and briefly mention what you learned. "
                f'Example fallback: "{fallback}" but feel free to speak naturally.'
            )
            print("✅ Discord bridge ungrounded by owner command.")
            return instruction, True
        return None, False

    async def _handle_harassment(
        self, message: "discord.Message", analysis: dict[str, Any]
    ):
        try:
            excerpt = analysis.get("excerpt") or ""
            prompt = (
                f"<@{message.author.id}> I'm not sure if you're joking when you say \"{excerpt}\". "
                "This is your last chance before I tell Father. Are you serious or just teasing?"
            ).strip()
            await message.channel.send(prompt[:1800])
        except Exception:
            pass
        await self._notify_owner_of_harassment(message, analysis)

    def _context_block(self, channel_id: int) -> str:
        buf = list(self.channel_history.get(channel_id, []))
        if not buf:
            return ""
        lines = []
        for item in buf[-CONTEXT_LINES:]:
            content = (item.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"{item.get('display', 'user')}: {content}")
        return "\n".join(lines)

    async def _fetch_owner_user(self) -> Optional["discord.User"]:
        if not self.owner_id:
            return None
        owner = self.get_user(self.owner_id)
        if owner is None:
            try:
                owner = await self.fetch_user(self.owner_id)
            except Exception:
                owner = None
        return owner

    async def _notify_owner_of_harassment(
        self, message: "discord.Message", analysis: dict[str, Any]
    ):
        if not self.owner_id:
            return
        now = time.time()
        if now - self.last_guard_alert < 10:
            return
        self.last_guard_alert = now
        excerpt = analysis.get("excerpt") or message.content[:120]
        location = "direct message" if message.guild is None else message.jump_url
        note = (
            f"⚠️ Possible harassment detected.\n"
            f"Author: {message.author} ({message.author.id})\n"
            f'Message: "{excerpt}"\n'
            f"Location: {location}"
        )
        owner = await self._fetch_owner_user()
        if owner:
            try:
                await owner.send(note[:1900])
                return
            except Exception:
                pass
        fallback_channel_id = self.primary_text_channel_id or (
            message.channel.id if message.guild else None
        )
        if fallback_channel_id:
            channel = self.get_channel(int(fallback_channel_id))
            if channel is None:
                try:
                    channel = await self.fetch_channel(int(fallback_channel_id))
                except Exception:
                    channel = None
            if channel:
                ping = f"<@{self.owner_id}> {note}"
                try:
                    await channel.send(ping[:1900])
                except Exception:
                    pass

    async def _politely_decline_dm(self, message: "discord.Message"):
        try:
            await message.channel.send(
                "I promised Father I'd only DM with him or family. Please reach me through the server instead."
            )
        except Exception:
            pass

    async def _handle_owner_shutdown(self, message: "discord.Message"):
        if self._shutdown_initiated:
            return
        self._shutdown_initiated = True
        try:
            await message.channel.send("Okay. I'll tuck myself in and rest now.")
        except Exception:
            pass
        await self._apologize_to_partner()
        await self._begin_shutdown_sequence()

    async def _apologize_to_partner(self):
        partner_info = self._find_recent_partner()
        if not partner_info:
            return
        channel_id, entry = partner_info
        channel = self.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await self.fetch_channel(int(channel_id))
            except Exception:
                channel = None
        if channel is None:
            return
        author_id = entry.get("author_id")
        display = (entry.get("display") or "").strip()
        nickname = (display.split("#")[0] if display else "").strip() or "friend"
        note = (
            f"{nickname}, Father just told me to head to bed. "
            "I'm sorry to duck out so suddenly—I'll catch up with you soon."
        )
        send_kwargs = {}
        message_id = entry.get("message_id")
        if message_id:
            try:
                ref = discord.MessageReference(
                    message_id=int(message_id),
                    channel_id=int(channel_id),
                    guild_id=channel.guild.id if channel.guild else None,
                )
                send_kwargs["reference"] = ref
                send_kwargs["mention_author"] = False
            except Exception:
                send_kwargs = {}
        try:
            await channel.send(note[:1800], **send_kwargs)
        except Exception:
            pass

    async def _notify_owner_of_apology(
        self, message: "discord.Message", forgiveness: dict[str, Any]
    ):
        owner = await self._fetch_owner_user()
        if owner is None:
            return
        remaining = forgiveness.get("remaining")
        limit = forgiveness.get("limit")
        if limit is None:
            status = "Forgiven (limit: unlimited)"
        else:
            status = f"Forgiven ({max(0, remaining)} remaining of {limit})"
        location = "direct message" if message.guild is None else message.jump_url
        note = (
            f"✅ {message.author} apologized.\n" f"{status}\n" f"Location: {location}"
        )
        try:
            await owner.send(note[:1900])
        except Exception:
            pass

    async def _notify_owner_grounded(self, message: "discord.Message", reason: str):
        owner = await self._fetch_owner_user()
        if owner is None:
            return
        note = (
            f"🛑 Grounding command received.\n"
            f'Message: "{reason[:160]}"\n'
            f"Location: {'DM' if message.guild is None else message.jump_url}"
        )
        try:
            await owner.send(note[:1900])
        except Exception:
            pass

    async def _begin_shutdown_sequence(self):
        try:
            from runtime import coreloop
        except Exception as exc:
            print(f"[Discord] Unable to initiate shutdown: {exc}")
            return

        loop = asyncio.get_running_loop()

        def _shutdown():
            try:
                coreloop.shutdown_sequence()
            except Exception as exc:
                print(f"[Discord] Shutdown sequence error: {exc}")

        await loop.run_in_executor(None, _shutdown)

    async def _enqueue_request(self, priority: int, payload: dict[str, Any]):
        await self.request_queue.put((priority, time.time(), payload))

    async def _join_author_voice(self, author: "discord.Member"):
        if not author.voice or not author.voice.channel:
            return
        await self._connect_to_channel(author.voice.channel)

    async def join_owner_or_channel(
        self, fallback_channel_id: Optional[int] = None
    ) -> bool:
        channel = self._resolve_owner_voice_channel()
        if channel:
            return await self._connect_to_channel(channel)
        if fallback_channel_id is None:
            fallback_channel_id = self.voice_channel_id or None
        if not fallback_channel_id:
            return False
        channel = await self._fetch_voice_channel(fallback_channel_id)
        if not channel:
            return False
        return await self._connect_to_channel(channel)

    def _resolve_owner_voice_channel(self):
        if not self.owner_id:
            return None
        for guild in self.guilds:
            try:
                member = guild.get_member(self.owner_id)
            except Exception:
                member = None
            if member and member.voice and member.voice.channel:
                return member.voice.channel
        return None

    async def _fetch_voice_channel(self, channel_id: int):
        channel = self.get_channel(channel_id)
        if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            return channel
        try:
            fetched = await self.fetch_channel(channel_id)
        except Exception:
            fetched = None
        if isinstance(fetched, (discord.VoiceChannel, discord.StageChannel)):
            return fetched
        return None

    async def _connect_to_channel(self, channel) -> bool:
        target_id = getattr(channel, "id", None)
        if target_id is None:
            return False
        current_channel_id = getattr(
            getattr(self.voice_client, "channel", None), "id", None
        )
        if current_channel_id and current_channel_id == target_id:
            return True
        now = time.time()
        if (
            self._voice_target_channel_id == target_id
            and now - self._voice_last_attempt < 5.0
        ):
            return False
        self._voice_target_channel_id = target_id
        self._voice_last_attempt = now
        if self._voice_join_lock is None:
            self._voice_join_lock = asyncio.Lock()
        if self._voice_join_lock.locked():
            return False
        async with self._voice_join_lock:
            try:
                if self.voice_client:
                    await self.voice_client.disconnect(force=True)
            except Exception:
                pass
            try:
                self.voice_client = await channel.connect()
                self._voice_last_attempt = time.time()
                self._enable_discord_input_bridge()
                self._start_voice_listener(channel)
                name = getattr(channel, "name", f"#{target_id}")
                print(f"🔊 Connected to voice channel: {name}")
                return True
            except Exception as e:
                print(f"[Discord] Voice connect failed: {e}")
                return False

    async def _leave_voice(self, guild: Optional["discord.Guild"]):
        if self.voice_client:
            try:
                try:
                    if _VOICE_SINK_SUPPORTED and hasattr(
                        self.voice_client, "stop_listening"
                    ):
                        self.voice_client.stop_listening()
                    elif _PYCORD_SINK_SUPPORTED and getattr(
                        self.voice_client, "stop_recording", None
                    ):
                        self.voice_client.stop_recording()
                        self._pycord_recording = False
                except Exception:
                    pass
                await self.voice_client.disconnect(force=True)
            except Exception:
                pass
            self.voice_client = None
        self._voice_target_channel_id = None
        self._voice_last_attempt = 0.0
        self._restore_tts_output_mode()
        self._disable_discord_input_bridge()
        if self._voice_capture:
            self._voice_capture.disengage()
            self._voice_sink = None

    async def _post_system_message(
        self, channel_id: Optional[int], content: str
    ) -> bool:
        if not content:
            return False
        channel = None
        target_id = (
            channel_id or self.primary_text_channel_id or self.text_channel_id or None
        )
        if target_id:
            channel = self.get_channel(target_id)
            if channel is None:
                try:
                    channel = await self.fetch_channel(target_id)
                except Exception:
                    channel = None
        if channel is None:
            return False
        try:
            await channel.send(content[:1900])
            return True
        except Exception as exc:
            print(f"[Discord] Unable to post system message: {exc}")
            return False

    async def _apply_presence(self):
        desired = dict(_presence_target)
        status_name = desired.get("status", "online").lower()
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }
        discord_status = status_map.get(status_name, discord.Status.online)
        note = desired.get("note") or ""
        stream_url = desired.get("stream_url") or ""
        stream_name = desired.get("stream_name") or note
        if stream_url:
            activity = discord.Streaming(
                name=stream_name or "Streaming", url=stream_url
            )
        elif note:
            activity = discord.Game(name=note)
        else:
            activity = None
        try:
            await self.change_presence(status=discord_status, activity=activity)
        except Exception as exc:
            print(f"[Discord] Presence update failed: {exc}")

    def on_voice_transcript(
        self, channel_id: int, user_id: int, display: str, text: str
    ):
        if not text or not channel_id:
            return
        loop = getattr(self, "loop", None)
        if loop is None or not loop.is_running():
            return
        is_owner = bool(self.owner_id and user_id == self.owner_id)
        if _grounded and not is_owner:
            return
        ctx = _channel_context_lookup(str(channel_id), None)
        family_ids = _load_family_ids()
        is_family = str(user_id) in family_ids
        user_key = f"discord_{user_id}"
        role = "owner" if is_owner else "friend"
        self._remember_profile(user_key, display, role, text, ctx, is_family=is_family)
        relationship = user_profile.get_relationship(user_key)
        if relationship == "ignore" and not is_owner:
            return
        log = self._append_voice_history(channel_id, display, text)
        instruction = (
            "Discord voice conversation transcript. Reply with something you would actually say out loud "
            "(keep it under two sentences, warm and contextual)."
        )
        payload = {
            "content": text,
            "display": display,
            "user_key": user_key,
            "role": role,
            "context": log,
            "instruction": instruction,
            "delivery": "voice",
            "voice_channel_id": channel_id,
            "mention_target": None,
            "reply_to": None,
            "channel_id": self.primary_text_channel_id or None,
            "author_id": user_id,
        }
        priority = 0 if is_owner else 4
        try:
            asyncio.run_coroutine_threadsafe(
                self._enqueue_request(priority, payload), loop
            )
        except Exception as exc:
            print(f"[Discord] Voice enqueue failed: {exc}")
        if is_owner:
            try:
                from systems import gaming_bridge as _gaming_bridge

                _gaming_bridge.handle_voice_callout(
                    text,
                    {"channel_id": channel_id, "user_id": user_id, "display": display},
                )
            except Exception:
                pass

    async def _on_pycord_recording_finished(self, sink, *_):
        self._pycord_recording = False
        try:
            sink.cleanup()
        except Exception:
            pass

    def _start_voice_listener(self, channel):
        global _VOICE_SINK_WARNING
        if not self.voice_client or not self._voice_capture or _VoiceSink is None:
            if not _VOICE_SINK_WARNING:
                print(
                    "[Discord] Voice capture disabled — discord voice components missing."
                )
                _VOICE_SINK_WARNING = True
            return
        try:
            sink = _VoiceSink(self._voice_capture)
            self._voice_capture.engage(getattr(channel, "id", 0))
            if _VOICE_SINK_SUPPORTED and hasattr(self.voice_client, "listen"):
                self.voice_client.listen(sink)
            elif _PYCORD_SINK_SUPPORTED and getattr(
                self.voice_client, "start_recording", None
            ):
                self.voice_client.start_recording(
                    sink, self._on_pycord_recording_finished
                )
                self._pycord_recording = True
            else:
                raise RuntimeError(
                    "No supported Discord voice capture interface available."
                )
            self._voice_sink = sink
        except Exception as exc:
            print(f"[Discord] Unable to start voice listener: {exc}")

    def _maybe_force_discord_tts(self):
        pass  # no longer force Discord-only TTS; routing handled by audio module

    def _restore_tts_output_mode(self):
        if not self._voice_prev_output_mode:
            return
        try:
            audio.set_tts_output_mode(self._voice_prev_output_mode)
        except Exception:
            pass
        self._voice_prev_output_mode = None

    def _enable_discord_input_bridge(self):
        if self._discord_input_bridge_active:
            return
        if not VOICEMEETER_ENABLED:
            return
        try:
            from systems import \
                voicemeeter as \
                _vm  # local import to avoid heavy dependency on startup
        except Exception:
            return
        try:
            ok, msg = _vm.set_discord_a2(True)
            if ok:
                self._discord_input_bridge_active = True
                print(msg)
        except Exception:
            pass

    def _disable_discord_input_bridge(self):
        if not self._discord_input_bridge_active:
            return
        if not VOICEMEETER_ENABLED:
            self._discord_input_bridge_active = False
            return
        try:
            from systems import voicemeeter as _vm
        except Exception:
            self._discord_input_bridge_active = False
            return
        try:
            ok, msg = _vm.set_discord_a2(False)
            if ok:
                print(msg)
        except Exception:
            pass
        self._discord_input_bridge_active = False

    async def _tts_worker(self):
        loop = asyncio.get_running_loop()
        while True:
            path, _meta = await loop.run_in_executor(None, _tts_queue.get)
            try:
                await self._play_tts(path)
            finally:
                _tts_queue.task_done()

    async def _play_tts(self, path: str):
        if not self.voice_client or not self.voice_client.is_connected():
            try:
                os.remove(path)
            except Exception:
                pass
            return
        try:
            source = discord.FFmpegPCMAudio(path, executable=FFMPEG_PATH)
            self.voice_client.play(discord.PCMVolumeTransformer(source))
            while self.voice_client.is_playing():
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[Discord] TTS playback failed: {e}")
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    async def _request_worker(self):
        loop = asyncio.get_running_loop()
        while True:
            priority, _ts, payload = await self.request_queue.get()
            try:
                response = await loop.run_in_executor(
                    None,
                    _process_with_context,
                    payload.get("content", ""),
                    payload.get("display", "user"),
                    payload.get("user_key", ""),
                    payload.get("role", "friend"),
                    payload.get("context"),
                    payload.get("instruction"),
                )
                if response:
                    await self._deliver_response(payload, response)
            except Exception as exc:
                print(f"[Discord] Request worker error: {exc}")
            finally:
                self.request_queue.task_done()

    async def _deliver_response(self, payload: dict[str, Any], response: str):
        delivery = payload.get("delivery")
        if delivery == "voice":
            await self._deliver_voice_response(payload, response)
            return
        channel_id = payload.get("channel_id")
        channel = self.get_channel(int(channel_id)) if channel_id else None
        mention_target = payload.get("mention_target")
        if channel is None and channel_id:
            try:
                channel = await self.fetch_channel(int(channel_id))
            except Exception:
                channel = None
        if channel is None:
            return
        reply_to = payload.get("reply_to")
        send_kwargs: dict[str, Any] = {}
        if reply_to:
            try:
                reference = discord.MessageReference(
                    message_id=int(reply_to),
                    channel_id=int(channel_id),
                    guild_id=channel.guild.id if channel.guild else None,
                )
                send_kwargs["reference"] = reference
                send_kwargs["mention_author"] = False
            except Exception:
                send_kwargs = {}
        text = response.strip()
        if mention_target:
            text = f"<@{mention_target}> {text}"
        try:
            await channel.send(text[:1900], **send_kwargs)
        except Exception as exc:
            print(f"[Discord] Send error: {exc}")

    async def _deliver_voice_response(self, payload: dict[str, Any], response: str):
        text = (response or "").strip()
        if not text:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, audio.speak, text)
        channel_id = payload.get("voice_channel_id")
        if channel_id:
            self._append_voice_history(int(channel_id), "Bjorgsun", text)

    def _append_voice_history(self, channel_id: int, speaker: str, text: str) -> str:
        buf = self.voice_history.setdefault(channel_id, deque(maxlen=10))
        buf.append(f"{speaker}: {text}")
        return "\n".join(buf)

    def _select_target_entry(self, channel_id: int) -> Optional[dict[str, Any]]:
        buf = self.channel_history.get(channel_id)
        if not buf:
            return None
        for entry in reversed(buf):
            author_id = entry.get("author_id")
            if not author_id or (self.owner_id and author_id == self.owner_id):
                continue
            return entry
        return None

    async def _proactive_loop(self):
        while True:
            try:
                await asyncio.sleep(PROACTIVE_INTERVAL)
                if _grounded:
                    continue
                target = self._find_recent_partner()
                if not target:
                    continue
                channel_id, entry = target
                channel = self.get_channel(channel_id)
                if channel is None:
                    continue
                content = "Just checking in! Let me know if you need me — I'm nearby."
                try:
                    await channel.send(content[:1800])
                except Exception:
                    pass
            except asyncio.CancelledError:
                break
            except Exception as exc:
                print(f"[Discord] Proactive loop error: {exc}")


def get_recent_history(limit: int = 50) -> list[dict[str, Any]]:
    cli = _client
    if not cli:
        return []
    rows: list[dict[str, Any]] = []
    for channel_id, history in cli.channel_history.items():
        for entry in history:
            rows.append(
                {
                    "channel_id": channel_id,
                    "author_id": entry.get("author_id"),
                    "display": entry.get("display"),
                    "content": entry.get("content"),
                    "timestamp": entry.get("timestamp"),
                    "mentions_bot": entry.get("mentions_bot"),
                }
            )
    rows.sort(key=lambda r: r.get("timestamp", 0))
    if limit > 0:
        rows = rows[-limit:]
    return rows


def export_transcript_md(limit: int = 200) -> str:
    rows = get_recent_history(limit)
    if not rows:
        raise ValueError("No Discord history available yet.")
    logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
    os.makedirs(logs_dir, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(logs_dir, f"discord_transcript_{stamp}.md")
    lines = [
        "# Discord Transcript",
        f"_Generated: {datetime.utcnow().isoformat()}Z_",
        "",
    ]
    for entry in rows:
        ts = entry.get("timestamp")
        try:
            label = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            label = str(ts)
        display = entry.get("display") or f"User {entry.get('author_id')}"
        text = entry.get("content", "")
        lines.append(f"- **[{label}]** {display}: {text}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def get_channel_contexts() -> dict:
    _load_channel_contexts()
    return {k: dict(v) for k, v in _channel_ctx_cache.items()}


def update_channel_context(channel_id: str, payload: dict):
    if not channel_id:
        return
    _load_channel_contexts()
    safe_id = str(channel_id).strip()
    data = {
        "label": payload.get("label", ""),
        "instructions": payload.get("instructions", ""),
        "allow_proactive": bool(payload.get("allow_proactive", True)),
        "default_relationship": payload.get("default_relationship", ""),
    }
    _channel_ctx_cache[safe_id] = data
    _persist_channel_contexts()


def remove_channel_context(channel_id: str):
    if not channel_id:
        return
    _load_channel_contexts()
    safe_id = str(channel_id).strip()
    if safe_id in _channel_ctx_cache:
        del _channel_ctx_cache[safe_id]
        _persist_channel_contexts()


def get_family_ids() -> list[str]:
    ids = _load_family_ids()
    return sorted(ids)


def save_family_ids(ids: list[str]):
    unique = []
    seen = set()
    for item in ids:
        token = str(item).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        unique.append(token)
    try:
        with open(DM_FAMILY_FILE, "w", encoding="utf-8") as f:
            json.dump(unique, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    global _family_cache, _family_mtime
    _family_cache = set(unique)
    try:
        _family_mtime = os.path.getmtime(DM_FAMILY_FILE)
    except Exception:
        _family_mtime = time.time()
