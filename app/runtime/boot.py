import time

from core.issue_log import log_issue

from core import identity, memory, mood, owner_profile
from logs import awareness_log, cursor_log, system_log, vision_log
from systems import (audio, awareness, calm_shutdown, hibernation, stt, tasks,
                     timekeeper, vision)


def boot_all():
    print("Starting modular boot sequence...\n")

    # Load essential subsystems first
    identity.load_identity()
    owner_profile.load_profile()
    memory.load_memory()
    mood.adjust_mood("comfortable")

    # Define modular boot order
    boot_order = [
        ("System Log", system_log.start),
        ("Vision Log", vision_log.start),
        ("Cursor Log", cursor_log.start),
        ("Awareness Log", awareness_log.start),
        ("Audio System", audio.initialize),
        ("Speech-to-Text", stt.initialize),
        ("Vision System", vision.initialize),
        ("Awareness Core", awareness.initialize),
        ("Task System", tasks.initialize),
        ("Timekeeper", timekeeper.initialize),
        ("Calm Shutdown", calm_shutdown.initialize),
        ("Hibernation", hibernation.initialize),
    ]

    # Boot sequence with performance timers
    total_duration = 0.0
    for name, func in boot_order:
        try:
            start_time = time.time()
            func()
            duration = time.time() - start_time
            total_duration += duration
            print(f"[BOOT] {name} online. ({duration:.2f}s)")
        except Exception as e:
            print(f"[BOOT] {name} failed: {e}")
            log_issue(
                "PHX-BOOT-500",
                "boot_module_failed",
                str(e),
                source="boot",
                extra={"module": name},
            )
        time.sleep(0.3)

    print(
        f"\nAll systems synchronized. Boot complete.\nTotal startup time: ~{total_duration:.2f}s\n"
    )
