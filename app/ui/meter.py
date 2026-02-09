import math
import time
from threading import Thread

# Use the shared theme palette if available. This will gracefully fall back
# if theme cannot be imported (e.g. when used outside of Bjorgsun UI).
try:
    from ui import theme  # type: ignore
except Exception:
    theme = None  # type: ignore


class VUMeter:
    def __init__(self, canvas):
        self.canvas = canvas
        self.active = False
        self.phase = 0

    def start_pulse(self):
        if not self.active:
            self.active = True
            Thread(target=self._pulse_loop, daemon=True).start()

    def stop_pulse(self):
        self.active = False

    def _pulse_loop(self):
        while self.active:
            self.phase += 0.2
            amp = abs(math.sin(self.phase)) * 20
            color = f"#{int(155+amp*5):02x}{int(255-amp*4):02x}{int(200+amp*2):02x}"
            self.canvas.configure(highlightbackground=color)
            time.sleep(0.05)


class RollingWaveform:
    def __init__(
        self,
        canvas,
        samples: int = 320,
        color_main: str | None = None,
        color_core: str | None = None,
        color_glow: str | None = None,
    ):
        """Construct a rolling waveform display on a canvas.

        :param canvas: The Tk canvas to draw into.
        :param samples: Number of sample points to keep for smoothing.
        :param color_main: Primary waveform color. Defaults to theme accent.
        :param color_core: Secondary (inner) waveform color. Defaults to a light cyan.
        :param color_glow: Spark accent color. Defaults to theme accent glow.
        """
        self.canvas = canvas
        self.samples = max(120, int(samples))
        self.levels = [0.0] * self.samples
        # If theme is available, derive colors from it; otherwise fallback to
        # reasonable defaults.
        if not color_main:
            color_main = theme.COLORS["accent"] if theme else "#0aa8d4"
        if not color_core:
            color_core = (
                theme.COLORS.get("accent_glow", "#b7f8ff") if theme else "#b7f8ff"
            )
        if not color_glow:
            color_glow = (
                theme.COLORS.get("accent_glow", "#24c7ff") if theme else "#24c7ff"
            )
        self.color_main = color_main
        self.color_core = color_core
        self.color_glow = color_glow
        self._last_draw = 0.0
        self._draw()

    def set_colors(
        self,
        color_main: str | None = None,
        color_glow: str | None = None,
        color_core: str | None = None,
    ):
        if color_main:
            self.color_main = color_main
        if color_glow:
            self.color_glow = color_glow
        if color_core:
            self.color_core = color_core

    def set_level(self, level):
        try:
            x = float(level)
        except Exception:
            x = 0.0
        x = 0.0 if x < 0 else (1.0 if x > 1 else x)
        self.levels.append(x)
        self.levels = self.levels[-self.samples :]
        # Coalesce very fast updates to avoid overdraw
        now = time.time()
        try:
            exists = getattr(self.canvas, "winfo_exists", None)
            if exists and not self.canvas.winfo_exists():
                return
        except Exception:
            return
        if now - self._last_draw > 0.02:
            try:
                self._draw()
                self._last_draw = now
            except Exception:
                # Canvas may have been destroyed between frames
                return

    def _draw(self):
        try:
            if hasattr(self.canvas, "winfo_exists") and not self.canvas.winfo_exists():
                return
            w = int(self.canvas.winfo_width() or 1)
            h = int(self.canvas.winfo_height() or 1)
        except Exception:
            return
        if w < 2 or h < 2:
            try:
                self.canvas.after(50, self._draw)
            except Exception:
                pass
            return
        self.canvas.delete("all")
        mid = h // 2
        step = max(1, w // (self.samples - 1))
        vis_len = max(2, w // step + 3)
        visible = self.levels[-vis_len:]

        # Smooth the visible window for a fluid look
        sm = []
        k = 4
        for i in range(len(visible)):
            a = max(0, i - k)
            b = min(len(visible), i + k + 1)
            sm.append(sum(visible[a:b]) / (b - a))

        pts = []
        jitter_phase = time.time() * 2.4
        for i, lvl in enumerate(sm):
            x = i * step
            amp = (lvl**0.7) * (h * 0.48)
            jitter = math.sin(jitter_phase + i * 0.06) * 2.2
            y = mid - amp + jitter
            pts.append((x, y))

        if len(pts) >= 2:
            flat_line = [coord for point in pts for coord in point]
            mirror = [(x, mid + (mid - y)) for x, y in pts[::-1]]
            fill_poly = [(0, mid)] + pts + mirror + [(0, mid)]

            self.canvas.create_polygon(
                *[c for p in fill_poly for c in p], fill="#06121c", outline=""
            )
            self.canvas.create_line(*flat_line, fill="#041723", width=10, smooth=True)
            self.canvas.create_line(
                *flat_line, fill=self.color_main, width=6, smooth=True
            )
            self.canvas.create_line(
                *flat_line, fill=self.color_core, width=3, smooth=True
            )

            # Accent sparks for the most recent section
            spark_count = min(18, len(pts) // 3)
            for i in range(-spark_count, -1):
                x, y = pts[i]
                tail = max(4, min(14, (spark_count + i) * -1))
                self.canvas.create_line(
                    x, y, x, y - tail, fill=self.color_glow, width=1.5
                )

        # Center line
        self.canvas.create_line(0, mid, w, mid, fill="#1b1e26")
