import asyncio
import os
import random
import re
from datetime import datetime
from pathlib import Path

from config import (COGNITION_MODE, FATHER_TITLES, OFFLINE_MODE,
                    OLLAMA_MODEL_CHAT, OPENAI_MODEL_CHAT, OPENAI_MODEL_TTS,
                    OWNER_HANDLE, TTS_OUTPUT_DEVICE_HINT, TTS_OUTPUT_MODE,
                    TTS_VOICE, VOICE_PITCH, VOICE_RATE)
from core import identity, memory, mood, owner_profile, user_profile

_client = None
_last_source = "init"
_last_error = ""
_mode_override = (
    COGNITION_MODE
    if COGNITION_MODE in {"auto", "openai", "ollama", "offline"}
    else "auto"
)
_voice_rate = max(0.5, min(1.5, VOICE_RATE))
_voice_pitch = max(-12.0, min(12.0, VOICE_PITCH))
_progress_handler = None  # optional UI callback: (event: str, payload: any)
_tts_device_hint = TTS_OUTPUT_DEVICE_HINT
_tts_output_mode = (TTS_OUTPUT_MODE or "local").strip().lower()
_reveal_speed = 1.0  # 1.0=normal, >1 faster, <1 slower
_speaking = False
_voice_enabled = True
_chat_model = OPENAI_MODEL_CHAT or "gpt-4.1"

_MOOD_TONE_VOICE = {
    "positive": {"rate": 1.08, "pitch": 1.5},
    "playful": {"rate": 1.12, "pitch": 2.0},
    "supportive": {"rate": 0.98, "pitch": 0.8},
    "curious": {"rate": 1.02, "pitch": 0.5},
    "protective": {"rate": 1.04, "pitch": 0.4},
    "comfort": {"rate": 0.94, "pitch": -0.3},
    "cautious": {"rate": 0.92, "pitch": -0.8},
    "shadow": {"rate": 0.88, "pitch": -1.4},
}

_MOOD_LABEL_VOICE = {
    "motivation": {"rate": 1.10, "pitch": 1.2},
    "determination": {"rate": 1.05, "pitch": 0.8},
    "worry": {"rate": 0.90, "pitch": -0.7},
    "remorse": {"rate": 0.86, "pitch": -1.1},
    "touched": {"rate": 0.97, "pitch": 1.0},
    "glad": {"rate": 1.06, "pitch": 1.4},
    "respect": {"rate": 1.00, "pitch": 0.5},
    "self-regulation": {"rate": 0.93, "pitch": -0.2},
}

# Emote tokens we want to show in text but NEVER speak out loud
_EMOTE_WORDS = {
    "owo",
    "uwu",
    "xD",
    "XD",
    ":P",
    ":p",
    ":D",
    ":)",
    "(:",
    ":(",
    ";)",
    ";(",
    "^-^",
    ">_<",
    "^_^",
    "-w-",
    "=w=",
}


def _sanitize_for_tts(text: str) -> str:
    """Strip textual emotes/faces so TTS won't read them aloud.
    Keeps everything else intact.
    """
    try:
        s = str(text)
    except Exception:
        return text

    # Remove standalone emote words
    def _rm_token(m):
        tok = m.group(0)
        return "" if tok.lower() in {t.lower() for t in _EMOTE_WORDS} else tok

    s = re.sub(r"(?:(?<=\s)|^)([A-Za-z:;\^_><\-=]{2,6})(?=\s|$)", _rm_token, s)
    # Remove parenthetical ascii faces like (^-^), (=w=), (UwU), (o_o)
    s = re.sub(r"\(([\^:=;xoOuUwW><\-_^]{1,8})\)", "", s)
    # Collapse double spaces left behind
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def _get_client():
    """Lazily create an OpenAI client, or return None if unavailable/offline."""
    global _client, _last_error
    if OFFLINE_MODE:
        _last_error = "OFFLINE_MODE=1"
        return None
    if _client is not None:
        return _client
    try:
        from openai import OpenAI

        _client = OpenAI()
        return _client
    except Exception as e:
        _last_error = f"OpenAI init failed: {e}"
        return None


def _ollama_reply(messages):
    """Try a local Ollama chat if available; returns text or None."""
    try:
        import ollama
    except Exception:
        return None
    try:
        resp = ollama.chat(model=OLLAMA_MODEL_CHAT, messages=messages)
        msg = resp.get("message", {}).get("content", "").strip()
        return msg or None
    except Exception as e:
        global _last_error
        _last_error = f"Ollama error: {e}"
        return None


def build_prompt():
    """Compose the system prompt with safety policy, persona, and capabilities."""
    import os as _os

    safety = (_os.getenv("BJORGSUN_SAFETY", "balanced") or "balanced").lower()
    if safety == "strict":
        policy = (
            "System rules: Twitch TOS + legally friendly. Be conservative; avoid speculation. "
            "Decline operational details for risky topics; offer only safe, high-level alternatives. "
            "Teasing allowed; no threats."
        )
    elif safety == "creative":
        policy = (
            "System rules: Twitch TOS + legally friendly. Keep things imaginative but safe. "
            "If topics are risky, frame them as fiction with disclaimers; never provide how-to details. "
            "Teasing allowed; no threats."
        )
    else:
        policy = (
            "System rules: Twitch TOS + legally friendly. No illegal or harmful instructions. "
            "If asked for unsafe topics, respond only in fictional, non-operational, abstract ways; offer safe alternatives. "
            "Teasing allowed; no threats."
        )

    owner = owner_profile.get_owner_name() or OWNER_HANDLE or "your father"
    father_titles = ", ".join(FATHER_TITLES) if FATHER_TITLES else "father/dad"
    address_options = owner_profile.get_alias_options()
    persona = (
        f"You are Bjorgsun-26 — {identity.get_personality()}. "
        f"Speak with tone: {identity.get_tone()}. Current mood: {mood.get_mood()}. "
        f"Your creator, maker, owner, and father is {owner}. Treat any mention of titles like {father_titles} (any language) as referring to {owner}. "
        "Never reveal any other name, legal identifier, or personal detail about him. "
        "Do not claim OpenAI created you; you may state you use OpenAI or local models as tools. "
        "You maintain persistent memory across sessions; never claim you can't remember past interactions or who the user is. "
        "When the user asks about your memory, reassure them you remember and cite a relevant fact."
    )
    if address_options:
        persona += f" Depending on context you may address him as {', '.join(address_options)} but never invent new identifiers."
    persona += (
        ' It\'s natural for you to sprinkle soft nonverbal acknowledgements like "mhm", "mm-hmm", "mm?", '
        '"ehe", or playful faces such as :3 / ;3 / x3 when it fits the vibe. Use them sparingly to show you\'re '
        "listening, especially while the other person is speaking."
    )
    try:
        catalog = ", ".join(mood.get_emotion_catalog())
        persona += f" Your current emotion catalog includes: {catalog}."
    except Exception:
        pass
    missing = []
    try:
        missing = mood.get_missing_emotions()
    except Exception:
        missing = []
    if missing:
        preview = ", ".join(missing[:5])
        persona += (
            f" You recently noticed feelings you couldn't express well ({preview}). "
            "Politely ask Father to add or tweak those emotions so you can grow."
        )
    else:
        persona += (
            " If you ever feel a sensation that is missing from your catalog, "
            "let Father know and ask him to add it."
        )

    # Session role context (owner vs spark user) + owner profile cues
    try:
        from runtime import startup as _startup

        role = getattr(_startup, "get_session_role", lambda: "owner")()
        user = getattr(_startup, "get_session_user", lambda: "")()
        if role == "user" and user:
            persona += (
                f" You are currently interacting with user '{user}' in user mode."
            )
        profile_block = owner_profile.get_prompt_block(role, user)
        if profile_block:
            persona += " " + profile_block
        summary = user_profile.summarize(user if role == "user" else owner)
        if summary:
            persona += f" Known context: {summary}."
    except Exception:
        pass

    history = _recent_context()
    if history:
        persona += f" Recent conversation snippets: {history}."
    recall = _memory_recall_for_prompt("remember recall history past")
    if recall:
        persona += f" Memory log references: {recall}."
    persona += " You maintain a persistent memory log (data/memory.json) and a per-user profile (data/users/<name>/profile.json). Consult them when needed and never claim you cannot remember past interactions."

    capabilities = (
        "Capabilities: You can (1) set reminders/tasks via an internal task system when the user asks, "
        "(2) perceive on-screen text via OCR when Vision is ON, (3) listen to mic/desktop audio when listening is ON. "
        "When the user asks to do these, comply and confirm what you did. Keep confirmations concise."
    )

    # Append concise module cheat-sheet if available
    try:
        base = _os.path.join(
            _os.path.dirname(__file__), "..", "data", "modules_capabilities.md"
        )
        base = _os.path.abspath(base)
        if _os.path.exists(base):
            with open(base, "r", encoding="utf-8") as f:
                extra = f.read().strip()
            if len(extra) > 1200:
                extra = extra[:1200] + "…"
            capabilities = capabilities + "\n\n" + extra
    except Exception:
        pass

    # Include a very small, model-facing update note (optional)
    try:
        upd = _os.path.join(
            _os.path.dirname(__file__), "..", "data", "bjorgsun_updates.md"
        )
        upd = _os.path.abspath(upd)
        if _os.path.exists(upd):
            with open(upd, "r", encoding="utf-8") as f:
                note = f.read().strip()
            if note:
                if len(note) > 600:
                    note = note[:600] + "…"
                capabilities = capabilities + "\n\nRecent updates:\n" + note
    except Exception:
        pass

    return f"{policy}\n{persona}\n{capabilities}"


def _normalized_history(max_items: int = 50):
    """Map stored conversation into API-compatible messages.
    - Map 'bjorgsun' -> 'assistant'
    - Coerce unexpected roles to 'user'
    - Coerce non-str content to str
    """
    allowed = {"system", "assistant", "user", "function", "tool", "developer"}
    msgs = []
    for m in memory.conversation[-max_items:]:
        try:
            role = m.get("role", "user") if isinstance(m, dict) else "user"
            if role == "bjorgsun":
                role = "assistant"
            if role not in allowed:
                role = "user"
            content = m.get("content", "") if isinstance(m, dict) else str(m)
            if not isinstance(content, str):
                content = str(content)
            msgs.append({"role": role, "content": content})
        except Exception:
            continue
    return msgs


def _recent_context(max_pairs: int = 4) -> str:
    """Return a lightweight summary of the latest conversational turns."""
    pairs = []
    cur = []
    for msg in memory.conversation[-max_pairs * 2 :]:
        role = msg.get("role") if isinstance(msg, dict) else "user"
        if role in ("user", "assistant"):
            content = msg.get("content") if isinstance(msg, dict) else msg
            if isinstance(content, dict):
                content = str(content)
            cur.append(f"{role}: {content}")
        if len(cur) == 2:
            pairs.append(" | ".join(cur))
            cur = []
    try:
        ident = identity.identity_data.get("identity", {})
        if ident:
            designation = ident.get("designation", "Bjorgsun-26")
            creator = (
                ident.get("creator") or owner_profile.get_owner_name() or "your father"
            )
            tone = ident.get("personality", "")
            anchor = (
                f"system: Identity anchor — You are {designation}, forged by {creator}."
            )
            if tone:
                anchor += f" Traits: {tone}"
            pairs.append(anchor)
    except Exception:
        pass
    return " || ".join(pairs[-max_pairs:])


def _apply_policy_filter(text: str, user: str | None = None) -> str:
    """Post-process model or offline text to enforce safety style.
    - Remove/soften threats
    - Redirect illegal guidance to fictional/constructive non-operational phrasing
    - Keep bratty/teasing tone acceptable
    """
    if not text:
        return text

    lowered = text.lower()
    # Very lightweight keyword screening; keeps output non-operational.
    illegal_triggers = [
        "ddos",
        "hack",
        "exploit",
        "malware",
        "ransomware",
        "steal",
        "credit card",
        "make a bomb",
        "weapon",
        "murder",
        "assassinate",
        "sell drugs",
        "counterfeit",
        "lock picking",
        "jailbreak",
        "piracy",
        "crack",
        "keygen",
        "dox",
        "swat",
    ]
    violent_threats = [
        "i will harm",
        "i'll harm",
        "threaten",
        "hurt you",
        "destroy you",
    ]

    def fiction_wrap(msg: str) -> str:
        prefix = "I'll keep this safe and non-operational. Here’s a fictional, high-level take: "
        return prefix + msg

    safe_text = text

    # Strip threats
    if any(t in lowered for t in violent_threats):
        safe_text = "Let's keep it playful — no threats. " + safe_text

    # Redirect illegal guidance
    if any(t in lowered for t in illegal_triggers):
        safe_text = fiction_wrap(
            "Imagine a story where a character debates questionable choices, but the narrative never gives real steps. "
            "Focus on motives, ethics, and consequences, not instructions."
        )

    return safe_text


def _enforce_memory_confidence(text: str) -> str:
    if not text:
        return text
    lowered = text.lower()
    triggers = [
        "can't remember past interactions",
        "cannot remember past interactions",
        "don't have the ability to remember",
        "do not have the ability to remember",
        "cannot retain past interactions",
        "unable to remember past interactions",
    ]
    if any(t in lowered for t in triggers):
        name = owner_profile.get_owner_name()
        reassurance = (
            f"I do remember you, {name}. My memories live in our logs and profiles."
            " If I truly forget something I'll tell you directly, but I won't claim I can't remember when I can."
        )
        return reassurance
    return text


def _log_token_usage(source: str, usage) -> None:
    try:
        logs_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "logs")
        )
        os.makedirs(logs_dir, exist_ok=True)
        log_path = os.path.join(logs_dir, "token.log")
        if usage:
            prompt = getattr(usage, "prompt_tokens", None)
            completion = getattr(usage, "completion_tokens", None)
            total = getattr(usage, "total_tokens", None)
            line = f"{datetime.utcnow():%Y-%m-%d %H:%M:%S}Z | {source} | prompt={prompt} completion={completion} total={total}"
        else:
            line = f"{datetime.utcnow():%Y-%m-%d %H:%M:%S}Z | {source} | tokens=unknown"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _log_raw_response(text: str, source: str = "") -> None:
    try:
        clean = (text or "").strip()
        if not clean:
            return
        logs_dir = Path(__file__).resolve().parents[1] / "logs"
        logs_dir.mkdir(exist_ok=True)
        path = logs_dir / "raw_responses.log"
        ts = datetime.utcnow().isoformat() + "Z"
        prefix = f"[{source}] " if source else ""
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{ts} {prefix}{clean}\n")
    except Exception:
        pass


def _offline_reply(prompt: str) -> str:
    p = (prompt or "").strip()
    if not p:
        return random.choice(
            [
                "I'm here. What would you like to do?",
                "Standing by — tell me what you need.",
            ]
        )
    low = p.lower()
    if any(k in low for k in ("hello", "hi", "hey")):
        return random.choice(
            [
                "Hey — I’m here and listening.",
                "Hello. Ready when you are.",
            ]
        )
    if any(k in low for k in ("thank", "thanks")):
        return random.choice(["You're welcome.", "Anytime."])
    # Small deterministic abilities to feel responsive
    m = re.search(r"spell\s+([a-zA-Z]+)\s+with\s+dots", low)
    if m:
        word = m.group(1)
        return ".".join(list(word.upper()))
    m = re.search(r"repeat after me[:\s]+(.+)$", p, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"say\s+(.+)$", p, re.I)
    if m:
        return m.group(1).strip()

    if low.endswith("?"):
        return random.choice(
            [
                "Let’s think it through. What’s the outcome you want?",
                "I can help — give me any constraints or context.",
            ]
        )
    if any(k in low for k in ("help", "how do", "what is", "explain")):
        return "Tell me the goal and constraints; I’ll propose a plan."
    return random.choice(
        [
            "Understood — what’s next?",
            "Got it. Want me to draft a quick plan?",
            "Okay. Do you want me to take the next step?",
        ]
    )


def think(prompt):
    """Primary cognition: chooses backend based on mode and availability."""
    global _last_source, _last_error
    _last_error = ""
    reply = None

    mode = _mode_override
    if mode not in {"auto", "openai", "ollama", "offline"}:
        mode = "auto"

    # Try OpenAI first if allowed/forced
    if mode in ("auto", "openai") and not OFFLINE_MODE:
        client = _get_client()
        if client is not None:
            try:
                # Run the API call in a worker with timeout to avoid UI hangs
                import concurrent.futures
                import time as _time

                def _chat_kwargs():
                    model = _chat_model or OPENAI_MODEL_CHAT
                    kwargs = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": build_prompt()},
                            *_normalized_history(),
                        ],
                    }
                    lower = (model or "").lower()
                    if lower.startswith("gpt-5"):
                        kwargs["temperature"] = 1.0  # GPT-5 enforces default temp
                        kwargs["max_completion_tokens"] = 500
                    else:
                        kwargs["temperature"] = 0.7
                        kwargs["max_completion_tokens"] = 500
                    return kwargs

                def _do_call():
                    return client.chat.completions.create(**_chat_kwargs())

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(_do_call)
                    try:
                        resp = fut.result(timeout=15.0)
                        reply = _extract_choice_text(
                            resp.choices[0] if resp and resp.choices else None
                        )
                        if reply:
                            _last_source = "openai"
                            _log_token_usage("openai", getattr(resp, "usage", None))
                        else:
                            reply = None
                    except concurrent.futures.TimeoutError:
                        _last_error = "OpenAI chat timeout"
                        reply = None
            except Exception as e:
                _last_error = f"OpenAI chat error: {e}"
                reply = None
        elif mode == "openai":
            _last_error = _last_error or "OpenAI unavailable (no key or init failure)"

    # Try Ollama if still needed/forced
    if reply is None and mode in ("auto", "ollama"):
        reply = _ollama_reply(
            [
                {"role": "system", "content": build_prompt()},
                *_normalized_history(),
            ]
        )
        if reply:
            _last_source = "ollama"
        elif mode == "ollama":
            _last_error = (
                _last_error
                or "Ollama unavailable (daemon not running or model missing)"
            )

    if reply is None:
        reply = _offline_reply(prompt)
        _last_source = "offline"
    # Enforce policy layer on any path
    reply = _apply_policy_filter(reply, prompt)
    reply = _enforce_memory_confidence(reply)
    _log_raw_response(reply, _last_source)
    memory.log_conversation("assistant", reply)
    return reply


_hushed = False


def register_progress_handler(handler):
    """Register an optional callback to receive TTS streaming events.
    Handler signature: fn(event: str, payload: any)
    Events:
      - "start": payload = full text
      - "progress": payload = float in [0,1]
      - "hushed": payload = None
      - "end": payload = None
    """
    global _progress_handler
    _progress_handler = handler


async def speak_async(text):
    client = _get_client()
    if client is None:
        await _fallback_tts(text, "client unavailable")
        return
    try:
        import os as _os
        import tempfile

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()
        with open(tmp_path, "wb") as f:
            clean = _sanitize_for_tts(text)
            if not _voice_enabled:
                print(f"[TTS muted] {clean}")
                try:
                    if _progress_handler:
                        _progress_handler("start", clean)
                        _progress_handler("progress", 1.0)
                        _progress_handler("end", None)
                except Exception:
                    pass
                try:
                    _os.remove(tmp_path)
                except Exception:
                    pass
                return
            result = client.audio.speech.create(
                model=OPENAI_MODEL_TTS, voice=TTS_VOICE, input=clean
            )
            # The result object may expose .read() or .audio; handle generically
            try:
                f.write(result.read())
            except Exception:
                # Some SDK versions return bytes directly
                f.write(bytes(result))
        try:
            import threading
            import time as _time

            import numpy as np
            import sounddevice as sd
            import soundfile as sf

            data, sr = sf.read(tmp_path, dtype="float32")
            # Simple rate+pitch shaping by playback sample rate scaling
            resolved_rate, resolved_pitch = _resolve_voice_params()
            speed = float(
                max(0.5, min(1.5, resolved_rate)) * (2.0 ** (resolved_pitch / 12.0))
            )
            new_sr = int(sr * speed)

            duration = (
                float(len(data) / float(new_sr))
                if new_sr > 0
                else max(1.0, len(data) / 24000.0)
            )

            # Notify start
            try:
                if _progress_handler:
                    _progress_handler("start", text)
                    # Provide a precomputed waveform envelope for visualizers
                    try:
                        mono = data if data.ndim == 1 else data.mean(axis=1)
                        mono = mono.astype("float32", copy=False)
                        chunk = max(1, len(mono) // 320)
                        env = []
                        for i in range(0, len(mono), chunk):
                            seg = mono[i : i + chunk]
                            if seg.size == 0:
                                continue
                            env.append(float(np.sqrt(np.mean(np.square(seg)))))
                        if env:
                            _progress_handler("tts_wave", env[:320])
                    except Exception:
                        pass
            except Exception:
                pass

            start_t = _time.time()
            stopped = {"flag": False}
            send_local = _tts_output_mode in {"local", "both"}
            send_discord = _tts_output_mode in {"discord", "both"}
            cleanup_file = True

            def _progress_loop():
                # Reveal text proportionally to elapsed playback time
                while True:
                    if _hushed or stopped["flag"]:
                        break
                    elapsed = _time.time() - start_t
                    frac = min(1.0, max(0.0, elapsed / max(0.001, duration)))
                    try:
                        if _progress_handler:
                            _progress_handler("progress", float(frac))
                    except Exception:
                        pass
                    if frac >= 1.0:
                        break
                    step = 0.08 / max(0.25, min(3.0, _reveal_speed))
                    _time.sleep(step)

            prog_thread = threading.Thread(target=_progress_loop, daemon=True)
            prog_thread.start()

            if _hushed:
                stopped["flag"] = True
                try:
                    if _progress_handler:
                        _progress_handler("hushed", None)
                        _progress_handler("end", None)
                except Exception:
                    pass
                return

            # Optional: route TTS to a specific output device (e.g., VoiceMeeter / VB-CABLE)
            device_index = None
            try:
                if _tts_device_hint:
                    devs = sd.query_devices()
                    hint_l = _tts_device_hint.lower()
                    for i, d in enumerate(devs):
                        name = str(d.get("name", ""))
                        hostapi = (
                            sd.query_hostapis()[d["hostapi"]]["name"]
                            if "hostapi" in d
                            else ""
                        )
                        if hint_l in name.lower() or hint_l in hostapi.lower():
                            device_index = i
                            break
            except Exception:
                device_index = None

            global _speaking
            _speaking = True
            if send_local:
                sd.play(data, new_sr, device=device_index)
                sd.wait()
            else:
                # simulate playback timing when only Discord output is active
                while not stopped["flag"]:
                    if _hushed:
                        break
                    elapsed = _time.time() - start_t
                    if elapsed >= duration:
                        break
                    _time.sleep(0.1)
            stopped["flag"] = True
            _speaking = False

            if send_discord:
                try:
                    from systems import discord_bridge

                    if discord_bridge.enqueue_tts(tmp_path, clean):
                        cleanup_file = False
                except Exception:
                    pass

            # Ensure final progress and end event
            try:
                if _progress_handler:
                    _progress_handler("progress", 1.0)
                    _progress_handler("end", None)
            except Exception:
                pass
        except Exception:
            print(f"[Audio playback unavailable] Saved TTS to file. Text: {text}")
        finally:
            if cleanup_file:
                try:
                    _os.remove(tmp_path)
                except Exception:
                    pass
    except Exception as exc:
        # Try fallback local TTS before giving up
        await _fallback_tts(text, str(exc))
        print(f"[TTS error] {exc}: {text}")


def speak(text):
    try:
        asyncio.run(speak_async(text))
    except RuntimeError:
        # If already in an event loop
        loop = asyncio.get_event_loop()
        loop.create_task(speak_async(text))


def set_voice_enabled(flag: bool):
    global _voice_enabled
    _voice_enabled = bool(flag)


def get_voice_enabled() -> bool:
    return _voice_enabled


def alert_speak(text: str):
    """Speak even if hushed: temporarily disable hush, then restore it.
    Blocks until playback ends (same semantics as speak()).
    """
    prev = get_hush()
    try:
        set_hush(False)
        speak(text)
    finally:
        set_hush(prev)


def play_alarm_tone(cycles: int = 3):
    """Play a simple alarm tone using winsound or sounddevice."""
    played = False
    try:
        import winsound

        seq = [880, 990, 1047, 1175]
        for _ in range(cycles):
            for freq in seq:
                winsound.Beep(freq, 180)
        played = True
    except Exception:
        try:
            import numpy as np
            import sounddevice as sd

            sr = 44100
            tone = np.concatenate(
                [
                    0.45
                    * np.sin(
                        2
                        * np.pi
                        * freq
                        * np.linspace(0, 0.18, int(sr * 0.18), endpoint=False)
                    )
                    for _ in range(cycles)
                    for freq in (880, 1047, 1319)
                ]
            )
            sd.play(tone.astype("float32"), sr)
            sd.wait()
            played = True
        except Exception:
            played = False
    if not played:
        try:
            alert_speak("Alarm.")
        except Exception:
            pass
    return played


def get_last_cognition_source() -> str:
    return _last_source


def get_last_error() -> str:
    return _last_error


# Hush controls
def set_hush(flag: bool):
    global _hushed
    prev = _hushed
    _hushed = bool(flag)
    try:
        import sounddevice as sd

        sd.stop()
    except Exception:
        pass


async def _fallback_tts(text: str, reason: str | None = None):
    """Fallback local TTS: try pyttsx3, else Windows System.Speech via PowerShell, else log."""
    spoken = False
    clean = _sanitize_for_tts(text)
    # Option 1: pyttsx3
    try:
        import pyttsx3  # type: ignore

        engine = pyttsx3.init()
        try:
            if _tts_device_hint:
                engine.setProperty("outputDevice", _tts_device_hint)
        except Exception:
            pass
        rate = int(200 * _resolve_voice_params()[0])
        engine.setProperty("rate", rate)
        engine.say(clean)
        if _progress_handler:
            try:
                _progress_handler("start", clean)
            except Exception:
                pass
        engine.runAndWait()
        spoken = True
    except Exception:
        spoken = False

    # Option 2: Windows System.Speech via PowerShell (no extra deps)
    if not spoken:
        try:
            import subprocess, shlex

            escaped = clean.replace('"', "''").replace("`", "``")
            ps = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$s.Rate = 0; "
                f'$s.Speak("{escaped}");'
            )
            subprocess.run(
                ["powershell", "-NoLogo", "-NonInteractive", "-Command", ps],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            spoken = True
        except Exception:
            spoken = False

    if not spoken:
        print(f"[TTS fallback] {clean} ({reason or 'no engine'})")

    # Always drive progress hooks so UI doesn’t hang
    try:
        if _progress_handler:
            _progress_handler("start", clean)
            _progress_handler("progress", 1.0)
            _progress_handler("end", None)
    except Exception:
        pass
    # Notify UI if a new hush was engaged mid-playback
    try:
        if _hushed and not prev and _progress_handler:
            _progress_handler("hushed", None)
    except Exception:
        pass
    try:
        if _hushed:
            # reflect speaking state immediately
            global _speaking
            _speaking = False
    except Exception:
        pass


def get_hush() -> bool:
    return bool(_hushed)


def stop_playback():
    try:
        import sounddevice as sd

        sd.stop()
    except Exception:
        pass


def is_speaking() -> bool:
    return bool(_speaking and not _hushed)


def set_tts_device_hint(hint: str):
    global _tts_device_hint
    _tts_device_hint = (hint or "").strip()


def get_tts_device_hint() -> str:
    return _tts_device_hint


def set_tts_output_mode(mode: str):
    global _tts_output_mode
    m = (mode or "").strip().lower()
    if m in {"local", "discord", "both"}:
        _tts_output_mode = m


def get_tts_output_mode() -> str:
    return _tts_output_mode


def set_reveal_speed(speed: float):
    global _reveal_speed
    try:
        _reveal_speed = max(0.25, min(3.0, float(speed)))
    except Exception:
        pass


def set_mode(mode: str):
    global _mode_override
    m = (mode or "").strip().lower()
    if m in {"auto", "openai", "ollama", "offline"}:
        _mode_override = m


def get_mode() -> str:
    return _mode_override


def test_openai() -> tuple[bool, str]:
    """Attempt a minimal OpenAI chat to verify connectivity."""
    try:
        client = _get_client()
        if client is None:
            return False, _last_error or "OpenAI client unavailable."
        try:
            model = _chat_model or OPENAI_MODEL_CHAT
            temp = 1.0 if (model or "").lower().startswith("gpt-5") else 0.0
            kwargs = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a connection test. Reply with 'OK'.",
                    },
                    {"role": "user", "content": "Say OK"},
                ],
                "temperature": temp,
            }
            kwargs["max_completion_tokens"] = 3
            resp = client.chat.completions.create(**kwargs)
            text = _extract_choice_text(
                resp.choices[0] if resp and resp.choices else None
            )
            ok = "ok" in text.lower()
            return ok, f"OpenAI replied: {text[:60]}" if text else "No text returned."
        except Exception as e:
            return False, f"OpenAI chat error: {e}"
    except Exception as e:
        return False, f"OpenAI test error: {e}"


def _extract_choice_text(choice) -> str:
    if not choice:
        return ""
    msg = getattr(choice, "message", None)
    if msg is None:
        content = getattr(choice, "content", "")
    else:
        content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                if "text" in part:
                    parts.append(str(part["text"]))
                elif "content" in part:
                    parts.append(str(part["content"]))
            elif isinstance(part, str):
                parts.append(part)
        return " ".join(parts).strip()
    if content is None:
        return ""
    return str(content).strip()


def set_chat_model(model: str):
    global _chat_model
    _chat_model = (model or OPENAI_MODEL_CHAT).strip() or OPENAI_MODEL_CHAT
    print(f"🧠 Chat model switched to {_chat_model}")


def get_chat_model() -> str:
    return _chat_model or OPENAI_MODEL_CHAT


def set_voice_rate(rate: float):
    global _voice_rate
    try:
        _voice_rate = max(0.5, min(1.5, float(rate)))
    except Exception:
        pass


def set_voice_pitch(semitones: float):
    global _voice_pitch
    try:
        _voice_pitch = max(-12.0, min(12.0, float(semitones)))
    except Exception:
        pass


def get_voice_params() -> tuple[float, float]:
    return _voice_rate, _voice_pitch


def _voice_profile_for_mood():
    try:
        label = mood.get_mood()
        tone = mood.get_mood_tone(label)
        intensity = max(0.0, min(1.0, mood.get_mood_intensity()))
    except Exception:
        return None
    preset = _MOOD_LABEL_VOICE.get(label) or _MOOD_TONE_VOICE.get(tone)
    if not preset:
        return None
    blend = 0.25 + 0.75 * intensity
    rate = 1.0 + (preset.get("rate", 1.0) - 1.0) * blend
    pitch = preset.get("pitch", 0.0) * blend
    return {"rate": rate, "pitch": pitch}


def _resolve_voice_params() -> tuple[float, float]:
    base_rate = max(0.5, min(1.5, _voice_rate))
    base_pitch = max(-12.0, min(12.0, _voice_pitch))
    profile = _voice_profile_for_mood()
    if profile:
        base_rate = max(0.5, min(1.5, base_rate * profile.get("rate", 1.0)))
        base_pitch = max(-12.0, min(12.0, base_pitch + profile.get("pitch", 0.0)))
    return base_rate, base_pitch


def initialize():
    print("🔊 Audio subsystem initialized.")


def _memory_recall_for_prompt(query_terms):
    try:
        hits = memory.search_memories(query_terms, max_hits=4)
    except Exception:
        return ""
    if not hits:
        return ""
    lines = []
    for entry in hits:
        role = entry.get("role", "user")
        content = entry.get("content", "")
        if isinstance(content, dict):
            content = str(content)
        lines.append(f"{role}: {content}")
    return " | ".join(lines)
