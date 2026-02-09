"""
ui/theme.py — Centralized HUD theme for Bjorgsun-26

Provides:
- Color palette
- Mood-based accent selection
- Simple drawing helpers (rounded rect)
- Optional custom font loading from skin or env
"""

from __future__ import annotations

import math
import os
import tkinter.font as tkfont  # type: ignore
from typing import Optional

# Base palette (Bjorgsun classic) and selectable presets
COLORS = {
    "bg": "#0a0c10",
    "bg_alt": "#0b0e13",
    "panel": "#111319",
    "text": "#cfe8ff",
    "muted": "#7ba1b7",
    "ok": "#55ff88",
    "warn": "#ffaa00",
    "accent": "#0aa8d4",  # primary teal/cyan
    "accent_glow": "#24c7ff",  # brighter cyan
    "accent2": "#ff3ea5",  # magenta/pink highlight (character accent)
    "peach": "#ffb8a1",
}

# Additional named theme presets that can be selected at runtime.
# These are intentionally small overrides; they map the same keys used in COLORS.
THEMES = {
    "default": COLORS,
    "prime": {
        "bg": "#05070d",
        "bg_alt": "#090d15",
        "panel": "#0d121d",
        "text": "#e8f4ff",
        "muted": "#7fb0c8",
        "ok": "#5fffd0",
        "warn": "#ffb84d",
        "accent": "#34d8ff",  # bright cyan/teal
        "accent_glow": "#6ff1ff",
        "accent2": "#ff8f3d",  # warm highlight
        "peach": "#ffcaa6",
    },
    "tron": {
        "bg": "#02060c",
        "bg_alt": "#08111d",
        "panel": "#0b1624",
        "text": "#c8f6ff",
        "muted": "#71c7e5",
        "ok": "#4cfad7",
        "warn": "#ffb347",
        "accent": "#00d8ff",
        "accent_glow": "#37f0ff",
        "accent2": "#ff9933",
        "peach": "#ffd7b0",
    },
    "femboy": {
        "bg": "#0b0710",
        "bg_alt": "#10061a",
        "panel": "#17121b",
        "text": "#ffeaff",
        "muted": "#c9a7d6",
        "ok": "#b6ffd9",
        "warn": "#ffb86b",
        "accent": "#ff6ec7",  # pink-cyan mix
        "accent_glow": "#ff9bd8",
        "accent2": "#69f0ff",
        "peach": "#ffd7e9",
    },
    "titanfall": {
        "bg": "#081017",
        "bg_alt": "#0b1620",
        "panel": "#0f1720",
        "text": "#cfe8ff",
        "muted": "#9fb8c6",
        "ok": "#7ef59b",
        "warn": "#ffb84d",
        "accent": "#2fb7ff",  # industrial blue
        "accent_glow": "#69d6ff",
        "accent2": "#ff9a3c",  # orange highlight
        "peach": "#ffcfa8",
    },
    "scifi": {
        "bg": "#03010a",
        "bg_alt": "#081023",
        "panel": "#0b1020",
        "text": "#dbe8ff",
        "muted": "#9fb7d6",
        "ok": "#6ef5b0",
        "warn": "#ffd76b",
        "accent": "#b36bff",  # neon purple
        "accent_glow": "#e0b7ff",
        "accent2": "#32f7e6",  # neon teal
        "peach": "#ffdfc6",
    },
}


def set_theme(name: str) -> None:
    """Apply a named theme by updating the `COLORS` dict in-place.

    Callers can use `set_theme('femboy')`, `set_theme('titanfall')`, or
    `set_theme('scifi')`. The selection can also be driven by the
    environment variable `UI_THEME`.
    """
    name = (name or "").lower()
    if not name or name == "default":
        return
    t = THEMES.get(name)
    if not t:
        return
    # Update COLORS in-place to keep existing references valid
    COLORS.clear()
    COLORS.update(t)


def available_themes() -> list[str]:
    """Return a list of available theme names."""
    return sorted(THEMES.keys())


# Apply env-driven default theme at import time if present
_env_theme = os.getenv("UI_THEME", "").strip()
if _env_theme:
    try:
        set_theme(_env_theme)
    except Exception:
        pass


POSITIVE_MOODS = {
    "joy",
    "happiness",
    "fun",
    "glee",
    "amusement",
    "love",
    "adoration",
    "gratitude",
    "admiration",
}
CALM_MOODS = {
    "comfortable",
    "calm",
    "relaxed",
    "acceptance",
    "forgiveness",
    "supportive",
    "empathy",
}
CURIOUS_MOODS = {"wonder", "awe", "curiosity", "surprise"}
CAUTIOUS_MOODS = {
    "cautious",
    "overwhelmed",
    "fear",
    "anger",
    "disgust",
    "envy",
    "sadness",
    "guilt",
    "shame",
    "awkward",
    "embarrassed",
    "disappointed",
}
PLAYFUL_MOODS = {"playful", "fun"}
PROTECTIVE_MOODS = {"protective", "pride"}


def accent_for_mood(mood: str | None) -> tuple[str, str]:
    """Return (primary, glow) accent colors for a mood label."""
    m = (mood or "").lower()
    if any(tag in m for tag in POSITIVE_MOODS | PLAYFUL_MOODS):
        return ("#17cfff", "#7fe7ff")
    if any(tag in m for tag in CAUTIOUS_MOODS):
        return ("#ff9a1f", "#ffd08e")
    if any(tag in m for tag in CALM_MOODS):
        return ("#4fd1c5", "#a9f0eb")
    if any(tag in m for tag in CURIOUS_MOODS):
        return ("#c58bff", "#f0d9ff")
    if any(tag in m for tag in PROTECTIVE_MOODS):
        return ("#ff5ea0", "#ffc3e0")
    return (COLORS["accent"], COLORS["accent_glow"])


def round_rect(canvas, x1, y1, x2, y2, r=8, **kwargs):
    """Draw a rounded rectangle on a Tk canvas.
    Returns the created polygon id.
    """
    r = max(0, int(r))
    points = [
        x1 + r,
        y1,
        x2 - r,
        y1,
        x2,
        y1,
        x2,
        y1 + r,
        x2,
        y2 - r,
        x2,
        y2,
        x2 - r,
        y2,
        x1 + r,
        y2,
        x1,
        y2,
        x1,
        y2 - r,
        x1,
        y1 + r,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def apply_ttk_theme(root) -> None:
    """Lightweight ttk style tuning to better fit the HUD palette.
    Keeps compatibility with existing widgets.
    """
    try:
        import tkinter.ttk as ttk  # noqa

        style = ttk.Style(master=root)
        # Use 'default' theme as base and override colors
        try:
            current = style.theme_use()
        except Exception:
            current = "default"
        # Notebook tabs — increase contrast and legibility
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background="#0f141b",
            foreground="#6fcfff",
            padding=(14, 6),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#18212c"), ("active", "#151d28")],
            foreground=[("selected", "#ffffff"), ("!selected", "#6fcfff")],
        )
        # Scrollbar
        style.configure(
            "Vertical.TScrollbar",
            background=COLORS["panel"],
            troughcolor=COLORS["bg"],
            arrowcolor=COLORS["text"],
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Optional font family support
# ---------------------------------------------------------------------------
_FONT_FAMILY: Optional[str] = None


def get_font_family(default: str = "Consolas") -> str:
    return _FONT_FAMILY or os.getenv("UI_FONT_FAMILY", default)


def _apply_family_to_defaults(root, family: str):
    try:
        for name in (
            "TkDefaultFont",
            "TkTextFont",
            "TkFixedFont",
            "TkMenuFont",
            "TkHeadingFont",
        ):
            try:
                f = tkfont.nametofont(name)
                f.configure(family=family)
            except Exception:
                pass
        # Fallback: set global option for widgets that honor *Font
        try:
            root.option_add("*Font", f"{family} 10")
        except Exception:
            pass
    except Exception:
        pass


def try_apply_custom_font(root) -> None:
    """Attempt to load a custom TTF/OTF from ui/skins/MySkin/Font and apply it.
    Priority: env UI_FONT_FAMILY, then Font/font.txt content, then guess from file name.
    On Windows, the font file is temporarily added to the process via GDI (FR_PRIVATE).
    """
    global _FONT_FAMILY
    try:
        base = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "skins", "MySkin", "Font")
        )
        family = os.getenv("UI_FONT_FAMILY", "").strip()
        guess = ""
        if os.path.isdir(base):
            # Load any .ttf/.otf privately
            try:
                import ctypes

                FR_PRIVATE = 0x10
                for fn in os.listdir(base):
                    if fn.lower().endswith((".ttf", ".otf")):
                        p = os.path.join(base, fn)
                        try:
                            ctypes.windll.gdi32.AddFontResourceExW(
                                ctypes.c_wchar_p(p), FR_PRIVATE, None
                            )
                        except Exception:
                            pass
                        if not guess:
                            guess = os.path.splitext(fn)[0].split("-")[0]
            except Exception:
                pass
            # Read explicit family name if provided
            try:
                famfile = os.path.join(base, "font.txt")
                if os.path.exists(famfile):
                    with open(famfile, "r", encoding="utf-8", errors="ignore") as f:
                        ff = f.read().strip()
                        if ff:
                            family = ff
            except Exception:
                pass
        if not family and guess:
            family = guess
        family = family or _FONT_FAMILY or ""
        if family:
            _FONT_FAMILY = family
            _apply_family_to_defaults(root, family)
    except Exception:
        pass
