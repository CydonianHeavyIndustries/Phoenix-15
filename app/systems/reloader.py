import importlib
import sys


def _safe(func, *a, **k):
    try:
        return func(*a, **k)
    except Exception as e:
        return e


def soft_reload():
    """Reload core config and key subsystems without tearing down the UI.
    Returns a list of (name, status) strings for logging.
    """
    results = []

    # Order matters: config -> identity/mood -> systems
    modules = [
        "config",
        "core.identity",
        "core.mood",
        "systems.audio",
        "systems.stt",
        "systems.vision",
        "systems.awareness",
        "systems.tasks",
        "systems.timekeeper",
        "systems.audio_sense",
        "systems.calm_shutdown",
    ]

    for name in modules:
        try:
            if name in sys.modules:
                importlib.reload(sys.modules[name])
            else:
                importlib.import_module(name)
            results.append((name, "reloaded"))
        except Exception as e:
            results.append((name, f"reload failed: {e}"))

    # Re-initialize subsystems where safe
    try:
        from systems import audio

        _safe(audio.initialize)
        # Apply config-driven cognition/voice defaults
        from config import COGNITION_MODE, VOICE_PITCH, VOICE_RATE

        _safe(audio.set_mode, COGNITION_MODE)
        _safe(audio.set_voice_rate, VOICE_RATE)
        _safe(audio.set_voice_pitch, VOICE_PITCH)
    except Exception:
        pass

    try:
        from systems import stt

        _safe(stt.initialize)
    except Exception:
        pass

    try:
        from systems import vision

        # Do not force-enable; UI controls decide. Just ensure thread exists.
        _safe(vision.initialize)
    except Exception:
        pass
    try:
        from systems import voicemeeter

        _safe(voicemeeter.initialize)
    except Exception:
        pass

    try:
        from systems import awareness

        _safe(awareness.initialize)
    except Exception:
        pass

    try:
        from systems import tasks

        _safe(tasks.initialize)
    except Exception:
        pass

    try:
        from systems import timekeeper

        _safe(timekeeper.initialize)
    except Exception:
        pass

    return results
