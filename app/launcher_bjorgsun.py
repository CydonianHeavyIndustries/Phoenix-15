"""
Simple launcher entrypoint for Bjorgsun-26.

It adjusts sys.path to the project root and delegates to scripts.start_ui.run_ui(),
so run_bjorgsun.bat can start Stable/Dev modes.
"""

import os
import sys
import warnings


def main() -> None:
    # Ensure project root is importable
    root = os.path.abspath(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    # Silence noisy pkg_resources deprecation spam from dependencies
    warnings.filterwarnings(
        "ignore",
        message="pkg_resources is deprecated as an API",
        category=UserWarning,
    )
    try:
        from scripts.start_ui import run_ui
    except Exception as exc:  # pragma: no cover - defensive guard
        print(f"[!] Failed to import UI launcher: {exc}")
        sys.exit(1)
    run_ui()


if __name__ == "__main__":
    main()
