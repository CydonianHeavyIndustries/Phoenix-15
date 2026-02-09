def run():
    results = []
    # Cognition backends
    try:
        from systems import audio

        mode = getattr(audio, "get_mode", lambda: "auto")()
        results.append((True, f"Cognition mode: {mode}"))
        ok, msg = audio.test_openai()
        results.append((ok, msg))
    except Exception as e:
        results.append((False, f"OpenAI check error: {e}"))
    # Tesseract
    try:
        from systems import vision

        label, text = vision.capture_once()
        results.append((label != "Unavailable", f"Vision: {label}"))
    except Exception as e:
        results.append((False, f"Vision check error: {e}"))
    # Audio devices
    try:
        import sounddevice as sd

        devs = sd.query_devices()
        results.append((bool(devs), f"Audio devices: {len(devs)} found"))
    except Exception as e:
        results.append((False, f"Audio device check error: {e}"))
    # Logs folder writable
    try:
        import os
        import time

        p = os.path.join(os.path.dirname(__file__), "..", "logs", "selfcheck.txt")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"selfcheck {time.time()}\n")
        results.append((True, "Logs writable"))
    except Exception as e:
        results.append((False, f"Logs write failed: {e}"))
    return results
