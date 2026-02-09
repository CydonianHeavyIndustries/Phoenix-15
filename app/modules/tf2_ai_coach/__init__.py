"""
TF2 AI Coach module
- Exposes a FastAPI router for coach telemetry/advice.
- Reads config paths for Titanfall 2 logs and TF2AI advice JSON.
- On-demand tail of nslog for `[AI_COACH_TELEMETRY]{...}` markers.
"""

from .router import router  # noqa: F401
