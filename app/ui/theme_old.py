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

# Base palette (Bjorgsun classic)
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
