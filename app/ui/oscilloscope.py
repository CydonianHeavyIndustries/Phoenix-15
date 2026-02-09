import math
import time
import tkinter as tk

from ui import theme

NEON_PALETTE = ("#24c7ff", "#ff3ea5", "#f6ff73")
GRID = "#111621"
AFTERGLOW = "#05141b"


class NeonScopeRenderer:
    """Reusable renderer that can be embedded in any canvas."""

    def __init__(self, canvas: tk.Canvas, mode: str = "wave", compact: bool = False):
        self.canvas = canvas
        self.mode = mode
        self.compact = compact
        self._levels: list[float] = [0.0] * 900
        self._tts_wave: list[float] = [0.0] * 240
        self._tts_progress = 0.0
        self._mic_active = False
        self._last_draw = 0.0
        self.canvas.bind("<Configure>", lambda e: self._redraw())

    def set_mode(self, mode: str):
        self.mode = mode
        self._redraw()

    def feed_level(self, level: float, active: bool = False):
        try:
            x = max(0.0, min(1.0, float(level)))
        except Exception:
            x = 0.0
        self._levels.append(x)
        self._levels = self._levels[-900:]
        self._mic_active = bool(active)
        self._redraw_throttled()

    def set_tts_wave(self, samples):
        try:
            pts = [max(0.0, min(1.0, float(v))) for v in (samples or [])]
        except Exception:
            pts = []
        if pts:
            self._tts_wave = pts[-320:]
            self._redraw_throttled()

    def on_tts_event(self, event: str, payload):
        try:
            if event == "tts_wave":
                self.set_tts_wave(payload)
                return
            if event == "progress":
                self._tts_progress = float(payload or 0.0)
            elif event in ("start", "end", "hushed"):
                self._tts_progress = 0.0 if event != "progress" else self._tts_progress
            self._redraw_throttled()
        except Exception:
            pass

    def _redraw_throttled(self):
        now = time.time()
        if now - self._last_draw > 0.02:
            self._last_draw = now
            try:
                self.canvas.after_idle(self._redraw)
            except Exception:
                pass

    def _redraw(self):
        try:
            self.canvas.delete("all")
            w = max(10, int(self.canvas.winfo_width() or 10))
            h = max(10, int(self.canvas.winfo_height() or 10))
        except Exception:
            return
        if not self.compact:
            self._draw_grid(w, h)
        mode = self.mode
        if mode == "xy":
            self._draw_xy(w, h)
        elif mode == "tts":
            self._draw_tts(w, h)
        else:
            self._draw_wave(w, h)

    def _draw_grid(self, w, h):
        for x in range(0, w, 48):
            self.canvas.create_line(x, 0, x, h, fill=GRID)
        for y in range(0, h, 48):
            self.canvas.create_line(0, y, w, y, fill=GRID)
        self.canvas.create_rectangle(0, 0, w, h, outline="#0a1116")

    def _draw_wave(self, w, h):
        mid = h // 2
        data = self._levels[-max(120, w) :]
        if len(data) < 2:
            return
        step = max(1, len(data) // (w - 2))
        pts = []
        samples = data[::step]
        scale = h * 0.45
        for idx, lvl in enumerate(samples):
            x = idx * (w / max(1, len(samples) - 1))
            wobble = math.sin((time.time() * 3.0) + (idx * 0.08)) * (
                3.0 if not self.compact else 1.5
            )
            y = mid - (lvl**0.85) * scale - wobble
            pts.extend((x, y))
        if len(pts) < 4:
            return
        base_color = "#fbff90" if self._mic_active else theme.COLORS["accent"]
        glow = "#ff51c4" if self._mic_active else theme.COLORS["accent_glow"]
        self.canvas.create_line(*pts, fill=AFTERGLOW, width=8, smooth=True)
        self.canvas.create_line(*pts, fill=glow, width=4, smooth=True)
        self.canvas.create_line(*pts, fill=base_color, width=2, smooth=True)
        self.canvas.create_line(0, mid, w, mid, fill="#0f1a21")

    def _draw_tts(self, w, h):
        pad = 16 if self.compact else 24
        base_top = h * 0.35
        base_bottom = h * 0.7
        theme.round_rect(
            self.canvas,
            pad - 4,
            base_top - 16,
            w - pad + 4,
            base_bottom + 12,
            r=14,
            fill="#050a12",
            outline="#0d1820",
        )
        theme.round_rect(
            self.canvas,
            pad,
            base_top,
            w - pad,
            base_bottom,
            r=10,
            fill="#081824",
            outline="#0d202c",
        )
        p = max(0.0, min(1.0, self._tts_progress))
        fill_w = pad + (w - pad * 2) * p
        self.canvas.create_rectangle(
            pad + 3, base_top + 3, fill_w, base_bottom - 3, fill="#19d6ff", outline=""
        )
        self.canvas.create_rectangle(
            fill_w,
            base_top + 3,
            w - pad - 3,
            base_bottom - 3,
            fill="#06101a",
            outline="",
        )
        self.canvas.create_text(
            w // 2,
            base_top - 18,
            text=f"TTS {int(p * 100)}%",
            fill="#c5f2ff",
            font=(theme.get_font_family(), 10, "bold"),
        )
        self.canvas.create_line(pad, base_bottom, w - pad, base_bottom, fill="#0a1823")

    def _draw_xy(self, w, h):
        cx, cy = w // 2, h // 2
        base = min(w, h) * 0.32
        halo = base * 1.25
        for idx, scale in enumerate((1.35, 1.1, 0.85, 0.6)):
            r = base * scale
            tone = ("#04111b", "#06202c", "#08384b", "#0a556c")[idx]
            self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r, outline=tone, width=1
            )
        n = min(len(self._levels), 400)
        if n < 4:
            return
        pts = []
        for i in range(n):
            l = self._levels[-n + i]
            a = i / max(1, n - 1)
            theta = a * math.pi * 2.0
            phi = theta * 1.27 + math.pi / 3
            wobble = math.sin(theta * 2.4 + time.time() * 0.7) * 6.0
            r = base * (0.4 + 0.6 * l) + wobble
            x = cx + math.sin(theta) * r
            y = cy + math.cos(phi) * r
            pts.extend((x, y))
        if len(pts) < 4:
            return
        self.canvas.create_oval(
            cx - halo, cy - halo, cx + halo, cy + halo, outline="#0f2a36", width=2
        )
        self.canvas.create_line(*pts, fill="#031621", width=8, smooth=True)
        self.canvas.create_line(*pts, fill="#10a9d7", width=3, smooth=True)
        self.canvas.create_line(*pts, fill="#83ffe8", width=1, smooth=True)
        step = max(6, len(pts) // 48)
        for idx in range(0, len(pts) - 1, step * 2):
            x = pts[idx]
            y = pts[idx + 1]
            pulse = 3 if self._mic_active else 2
            color = "#ff84d8" if self._mic_active else "#9df7ff"
            self.canvas.create_oval(
                x - pulse, y - pulse, x + pulse, y + pulse, fill=color, outline=""
            )

    @staticmethod
    def _compress(data, bins):
        if not data:
            return [0.0] * max(1, bins // 2)
        size = max(1, len(data) // bins)
        out = []
        for i in range(0, len(data), size):
            seg = data[i : i + size]
            out.append(float(max(seg) if seg else 0.0))
        return out[:bins]


class OscilloscopeWindow(tk.Toplevel):
    """Floating window wrapper around the renderer."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Oscilloscope — Bjorgsun-26")
        self.configure(bg=theme.COLORS["bg"])  # type: ignore
        self.geometry("760x400")
        self.minsize(540, 300)
        self._mode = tk.StringVar(value="wave")

        top = tk.Frame(self, bg=theme.COLORS["bg"])  # type: ignore
        top.pack(fill="x", padx=8, pady=6)
        self.canvas = tk.Canvas(self, bg=theme.COLORS["panel"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.renderer = NeonScopeRenderer(self.canvas, mode="wave")

        for m in ("wave", "xy", "tts"):
            tk.Radiobutton(
                top,
                text=m.upper(),
                value=m,
                variable=self._mode,
                bg=theme.COLORS["bg"],
                fg=theme.COLORS["text"],
                selectcolor=theme.COLORS["panel"],
                indicatoron=False,
                width=8,
                relief="flat",
                command=lambda mod=m: self.renderer.set_mode(mod),
            ).pack(side="left", padx=(0, 6))

    # Proxy methods for compatibility with UI
    def feed_level(self, level: float, active: bool = False):
        self.renderer.feed_level(level, active)

    def set_tts_wave(self, samples):
        self.renderer.set_tts_wave(samples)

    def on_tts_event(self, event: str, payload):
        self.renderer.on_tts_event(event, payload)
