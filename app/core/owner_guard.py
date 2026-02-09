"""
Owner override guard — protects Father designation.

Any attempt to reassign the "father" relationship must pass this gate.
Only one attempt is allowed; a wrong answer permanently denies the request
until the process restarts (e.g., next run).
"""

from __future__ import annotations

from config import OWNER_LAST_CODE

_override_prompted = False
_override_granted = False


def verify_father_override(reason: str | None = None) -> bool:
    """
    Prompt for the owner's secret code before allowing a father reassignment.
    Returns True when permission is granted.
    """
    global _override_prompted, _override_granted
    if _override_granted:
        return True
    if _override_prompted:
        return False
    _override_prompted = True
    prompt = "Father override requested"
    if reason:
        prompt += f" ({reason})"
    prompt += ". What is my last code? "
    try:
        answer = input(prompt).strip()
    except Exception:
        return False
    if OWNER_LAST_CODE and answer == OWNER_LAST_CODE:
        _override_granted = True
        print("Father override approved.")
        return True
    print("Father override denied - incorrect code.")
    return False
