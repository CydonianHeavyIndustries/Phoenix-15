"""
OpenAI helper utilities for resilient chat and TTS calls.

Features:
- Single shared client with bounded timeout.
- Jittered retries for transient errors.
- Explicit model selection with sane defaults.
- Optional streaming support for chat.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import os

DEFAULT_CHAT_MODEL = os.getenv("OPENAI_MODEL_CHAT", "gpt-5.1")
DEFAULT_TTS_MODEL = os.getenv("OPENAI_MODEL_TTS", "tts-1")

_client = None
_last_error = ""


def get_client():
    """Return a configured OpenAI client with bounded timeout."""
    global _client, _last_error
    if _client is not None:
        return _client
    try:
        from openai import OpenAI  # type: ignore

        _client = OpenAI(timeout=15.0, max_retries=0)
        return _client
    except Exception as e:
        _last_error = f"OpenAI init failed: {e}"
        return None


def _call_with_retry(fn, attempts: int = 3, base_delay: float = 0.5):
    """Run fn with jittered backoff. Returns (ok, result, error_str)."""
    last_err = ""
    for i in range(max(1, attempts)):
        try:
            return True, fn(), ""
        except Exception as e:
            last_err = str(e)
            delay = base_delay * (1.5 ** i) * (0.6 + 0.8 * random.random())
            time.sleep(min(delay, 5.0))
    return False, None, last_err


def chat_completion(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 500,
    stream: bool = False,
) -> Tuple[bool, Any, str]:
    """Call OpenAI chat with retries. Returns (ok, result, error)."""
    client = get_client()
    if client is None:
        return False, None, _last_error or "OpenAI client unavailable"

    chosen_model = (model or DEFAULT_CHAT_MODEL or "gpt-5.1").strip() or "gpt-5.1"
    kwargs: Dict[str, Any] = {
        "model": chosen_model,
        "messages": messages,
        "max_completion_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }
    # Small tweak for GPT-5 family: keep temperature neutral by default
    if chosen_model.lower().startswith("gpt-5"):
        kwargs["temperature"] = temperature if temperature != 0.7 else 1.0

    def _invoke():
        return client.chat.completions.create(**kwargs)

    return _call_with_retry(_invoke, attempts=3, base_delay=0.6)


def tts_speech(text: str, model: Optional[str] = None, voice: str = "alloy"):
    """Call OpenAI TTS; returns (ok, result, error)."""
    client = get_client()
    if client is None:
        return False, None, _last_error or "OpenAI client unavailable"
    clean = (text or "").strip()
    if not clean:
        return False, None, "Empty text for TTS"
    chosen_model = (model or DEFAULT_TTS_MODEL or "tts-1").strip() or "tts-1"

    def _invoke():
        return client.audio.speech.create(model=chosen_model, voice=voice, input=clean)

    return _call_with_retry(_invoke, attempts=3, base_delay=0.6)


def parse_structured_json(text: str, keys: List[str]) -> Dict[str, Any]:
    """Best-effort JSON parse to extract expected keys."""
    import json

    out: Dict[str, Any] = {k: None for k in keys}
    if not text:
        return out
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for k in keys:
                if k in data:
                    out[k] = data[k]
    except Exception:
        pass
    return out
