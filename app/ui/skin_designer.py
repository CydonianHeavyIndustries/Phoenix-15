import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from PIL import Image, ImageTk  # type: ignore
except Exception:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore


class SkinDesigner(tk.Toplevel):
    """Interactive designer to place UI regions on top of a background.

    Usage:
      win = SkinDesigner(root, skin_dir="ui/skins/MySkin")
      win.grab_set()
    """

    REGION_ORDER = [
        ("top_bar", "#ffb86c"),
        ("hud_orb", "#ff79c6"),
        ("console", "#8be9fd"),
        ("right_panel", "#6272a4"),
        ("waveform", "#50fa7b"),
        ("input_bar", "#f1fa8c"),
    ]

    def __init__(self, master, skin_dir: str = None):
        super().__init__(master)
        self.title("Skin Designer — Bjorgsun-26")
        self.configure(bg="#0a0c10")
        self.geometry("1100x720")
        self.minsize(920, 560)

        self.skin_dir = skin_dir or os.path.join(
            os.path.dirname(__file__), "skins", "MySkin"
        )
        os.makedirs(self.skin_dir, exist_ok=True)
        self.bg_path = os.path.join(self.skin_dir, "bg.png")
        self.bg_img = None
        self.bg_w = 0
        self.bg_h = 0
        self.crop = (0, 0, 0, 0)  # x,y,w,h in image pixels; (0,0,0,0) means full

        # Normalized regions in crop coordinates (0..1)
        self.regions = {
            "top_bar": [0.02, 0.02, 0.96, 0.08],
            "hud_orb": [0.42, 0.12, 0.16, 0.14],
            "console": [0.02, 0.28, 0.72, 0.58],
            "right_panel": [0.76, 0.14, 0.22, 0.78],
            "waveform": [0.02, 0.88, 0.72, 0.04],
            "input_bar": [0.02, 0.93, 0.72, 0.05],
        }

        self._sel = None
        self._drag_off = (0, 0)
        self._scale = 1.0
        self._pad = (0, 0)  # x,y letterbox inside canvas

        # Layout
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)

        self.canvas = tk.Canvas(self, bg="#0a0c10", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.status = tk.Label(
            self, text="", bg="#0a0c10", fg="#77ccff", font=("Consolas", 10)
        )
        self.status.grid(row=1, column=0, sticky="ew")

        # Toolbar
        bar = tk.Frame(self, bg="#0a0c10")
        bar.grid(row=2, column=0, sticky="ew")

        def _btn(txt, cmd):
            b = tk.Button(
                bar, text=txt, command=cmd, bg="#1a1c22", fg="#cccccc", relief="flat"
            )
            b.pack(side="left", padx=6, pady=6)
            return b

        _btn("Open BG…", self._open_bg)
        _btn("Load JSON", self._load_json)
        _btn("Export JSON", self._save_json)
        _btn("Save Crop → bg_cropped.png", self._save_crop_png)
        _btn("Defaults", self._reset_defaults)
        _btn("Help", self._show_help)

        # Events
        self.canvas.bind("<Configure>", lambda e: self._draw())
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", lambda e: self._update_status())
        self.bind("<Delete>", self._clear_selection)
        self.bind("<Escape>", self._clear_selection)

        # Try to load background
        self._load_bg_default()
        self._draw()

    # ---------- File ops ----------
    def _load_bg_default(self):
        if os.path.exists(self.bg_path):
            self._set_bg(self.bg_path)
        else:
            self._log("No bg.png in skin dir — use Open BG…")

    def _open_bg(self):
        p = filedialog.askopenfilename(
            title="Open background PNG",
            filetypes=[["PNG", "*.png"], ["All", "*.*"]],
            initialdir=self.skin_dir,
        )
        if p:
            self._set_bg(p)

    def _set_bg(self, path: str):
        try:
            if Image is None or ImageTk is None:
                raise RuntimeError(
                    "Pillow not available; install pillow to use designer"
                )
            im = Image.open(path)
            self.bg_w, self.bg_h = im.size
            self.bg_img_full = im.copy()
            self.bg_img = ImageTk.PhotoImage(im)
            self.bg_path = path
            # reset crop to full
            self.crop = (0, 0, 0, 0)
            self._log(
                f"Background loaded: {os.path.basename(path)} ({self.bg_w}×{self.bg_h})"
            )
            self._draw()
        except Exception as e:
            messagebox.showerror("Open", str(e), parent=self)

    def _load_json(self):
        p = filedialog.askopenfilename(
            title="Load skin.json",
            filetypes=[["JSON", "*.json"], ["All", "*.*"]],
            initialdir=self.skin_dir,
        )
        if not p:
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if Image is not None and ImageTk is not None:
                # If JSON points to a different background, try to open it
                bg = data.get("background") or "bg.png"
                bg_abs = os.path.join(os.path.dirname(p), bg)
                if os.path.exists(bg_abs):
                    self._set_bg(bg_abs)
            bs = data.get("base_size") or [self.bg_w, self.bg_h]
            self.bg_w, self.bg_h = int(bs[0]), int(bs[1])
            cr = data.get("crop") or [0, 0, 0, 0]
            self.crop = tuple(int(v) for v in cr)
            reg = data.get("regions") or {}
            for k in self.regions.keys():
                if k in reg and isinstance(reg[k], (list, tuple)) and len(reg[k]) == 4:
                    self.regions[k] = [
                        float(reg[k][0]),
                        float(reg[k][1]),
                        float(reg[k][2]),
                        float(reg[k][3]),
                    ]
            self._log("skin.json loaded")
            self._draw()
        except Exception as e:
            messagebox.showerror("Load JSON", str(e), parent=self)

    def _save_json(self):
        try:
            out = {
                "base_size": [self.bg_w, self.bg_h],
                "background": (
                    os.path.basename(self.bg_path) if self.bg_path else "bg.png"
                ),
                "crop": list(self.crop),
                "regions": self.regions,
            }
            p = os.path.join(self.skin_dir, "skin.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
            self._log(f"Exported {p}")
        except Exception as e:
            messagebox.showerror("Export", str(e), parent=self)

    def _save_crop_png(self):
        if Image is None:
            messagebox.showwarning(
                "Crop", "Pillow not available; cannot save crop.", parent=self
            )
            return
        try:
            if not hasattr(self, "bg_img_full"):
                messagebox.showwarning("Crop", "Open a background first.", parent=self)
                return
            x, y, w, h = self._crop_box_abs()
            if w <= 0 or h <= 0:
                messagebox.showwarning("Crop", "Invalid crop area.", parent=self)
                return
            box = (x, y, x + w, y + h)
            im = self.bg_img_full.crop(box)
            out = os.path.join(self.skin_dir, "bg_cropped.png")
            im.save(out)
            self._log(f"Saved crop → {out}")
        except Exception as e:
            messagebox.showerror("Crop", str(e), parent=self)

    # ---------- Drawing ----------
    def _letterbox(self, cw: int, ch: int):
        if self.bg_w <= 0 or self.bg_h <= 0:
            return 1.0, 0, 0, cw, ch
        sx = cw / self.bg_w
        sy = ch / self.bg_h
        s = min(sx, sy)
        vw = int(self.bg_w * s)
        vh = int(self.bg_h * s)
        px = (cw - vw) // 2
        py = (ch - vh) // 2
        return s, px, py, vw, vh

    def _draw(self):
        self.canvas.delete("all")
        cw = int(self.canvas.winfo_width() or 1)
        ch = int(self.canvas.winfo_height() or 1)
        self._scale, px, py, vw, vh = self._letterbox(cw, ch)
        self._pad = (px, py)
        # Background
        try:
            if self.bg_img is not None:
                if (
                    ImageTk
                    and isinstance(self.bg_img, ImageTk.PhotoImage)
                    and self._scale not in (0, 1)
                ):
                    # Generate a scaled display image for quality
                    try:
                        im = self.bg_img_full.resize((vw, vh))
                        self._bg_scaled = ImageTk.PhotoImage(im)
                        self.canvas.create_image(
                            px, py, image=self._bg_scaled, anchor="nw"
                        )
                    except Exception:
                        self.canvas.create_image(px, py, image=self.bg_img, anchor="nw")
                else:
                    self.canvas.create_image(px, py, image=self.bg_img, anchor="nw")
        except Exception:
            pass

        # Crop rectangle (optional)
        x, y, w, h = self._crop_box_abs()
        cx0, cy0 = self._abs_to_canvas(x, y)
        cx1, cy1 = self._abs_to_canvas(x + w, y + h)
        self.canvas.create_rectangle(
            cx0, cy0, cx1, cy1, outline="#ffaa00", width=2, dash=(6, 4)
        )
        self.canvas.create_text(
            cx0 + 8,
            cy0 + 12,
            text="crop",
            anchor="w",
            fill="#ffaa00",
            font=("Consolas", 10, "bold"),
        )

        # Regions
        for name, color in self.REGION_ORDER:
            rx, ry, rw, rh = self.regions.get(name, [0, 0, 0, 0])
            # Convert normalized (crop space) → image abs → canvas
            ax = x + int(rx * (w or 1))
            ay = y + int(ry * (h or 1))
            aw = int(rw * (w or 1))
            ah = int(rh * (h or 1))
            c0x, c0y = self._abs_to_canvas(ax, ay)
            c1x, c1y = self._abs_to_canvas(ax + aw, ay + ah)
            tag = f"region:{name}"
            self.canvas.create_rectangle(
                c0x, c0y, c1x, c1y, outline=color, width=2, tags=(tag,)
            )
            self.canvas.create_text(
                c0x + 8,
                c0y + 12,
                text=name,
                anchor="w",
                fill=color,
                font=("Consolas", 10, "bold"),
            )

        self._update_status()

    # ---------- Events ----------
    def _on_click(self, e):
        # hit-test regions (topmost)
        hit = None
        for name, _ in reversed(self.REGION_ORDER):
            if self._point_in_region_canvas(name, e.x, e.y):
                hit = name
                break
        if hit is None:
            # click near crop border toggles crop drag
            self._sel = ("crop", (e.x, e.y))
            self._drag_off = (e.x, e.y)
        else:
            self._sel = ("region", hit)
            self._drag_off = (e.x, e.y)

    def _on_drag(self, e):
        if not self._sel:
            return
        kind, val = self._sel
        dx = e.x - self._drag_off[0]
        dy = e.y - self._drag_off[1]
        self._drag_off = (e.x, e.y)
        if kind == "region":
            name = val
            self._nudge_region(name, dx, dy)
        else:
            self._nudge_crop(dx, dy)
        self._draw()

    def _clear_selection(self, *_):
        self._sel = None
        self._update_status()

    # ---------- Geometry helpers ----------
    def _abs_to_canvas(self, ax: int, ay: int):
        px, py = self._pad
        return int(px + ax * self._scale), int(py + ay * self._scale)

    def _canvas_to_abs(self, cx: int, cy: int):
        px, py = self._pad
        ax = int((cx - px) / (self._scale or 1.0))
        ay = int((cy - py) / (self._scale or 1.0))
        # clamp to image
        ax = max(0, min(self.bg_w, ax))
        ay = max(0, min(self.bg_h, ay))
        return ax, ay

    def _crop_box_abs(self):
        if self.crop == (0, 0, 0, 0):
            return 0, 0, self.bg_w, self.bg_h
        x, y, w, h = self.crop
        if w <= 0 or h <= 0:
            return 0, 0, self.bg_w, self.bg_h
        return x, y, w, h

    def _point_in_region_canvas(self, name: str, cx: int, cy: int) -> bool:
        x, y, w, h = self._crop_box_abs()
        rx, ry, rw, rh = self.regions.get(name, [0, 0, 0, 0])
        ax0 = x + int(rx * (w or 1))
        ay0 = y + int(ry * (h or 1))
        ax1 = ax0 + int(rw * (w or 1))
        ay1 = ay0 + int(rh * (h or 1))
        c0x, c0y = self._abs_to_canvas(ax0, ay0)
        c1x, c1y = self._abs_to_canvas(ax1, ay1)
        return (c0x <= cx <= c1x) and (c0y <= cy <= c1y)

    def _nudge_region(self, name: str, dx_canvas: int, dy_canvas: int):
        # convert canvas delta to normalized crop-space delta
        x, y, w, h = self._crop_box_abs()
        if w <= 0 or h <= 0:
            return
        dx = (dx_canvas / (self._scale or 1.0)) / float(w)
        dy = (dy_canvas / (self._scale or 1.0)) / float(h)
        rx, ry, rw, rh = self.regions.get(name, [0, 0, 0, 0])
        rx = max(0.0, min(1.0 - rw, rx + dx))
        ry = max(0.0, min(1.0 - rh, ry + dy))
        self.regions[name] = [rx, ry, rw, rh]

    def _nudge_crop(self, dx_canvas: int, dy_canvas: int):
        ax, ay = self._canvas_to_abs(*self._drag_off)
        # simple pan for crop box
        x, y, w, h = self._crop_box_abs()
        if w <= 0 or h <= 0:
            return
        dx = int(dx_canvas / (self._scale or 1.0))
        dy = int(dy_canvas / (self._scale or 1.0))
        nx = max(0, min(self.bg_w - w, x + dx))
        ny = max(0, min(self.bg_h - h, y + dy))
        self.crop = (nx, ny, w, h)

    # ---------- UI helpers ----------
    def _reset_defaults(self):
        self.regions.update(
            {
                "top_bar": [0.02, 0.02, 0.96, 0.08],
                "hud_orb": [0.42, 0.12, 0.16, 0.14],
                "console": [0.02, 0.28, 0.72, 0.58],
                "right_panel": [0.76, 0.14, 0.22, 0.78],
                "waveform": [0.02, 0.88, 0.72, 0.04],
                "input_bar": [0.02, 0.93, 0.72, 0.05],
            }
        )
        # set crop to centered square within image by default if image exists
        if self.bg_w and self.bg_h:
            size = min(self.bg_w, self.bg_h)
            x = (self.bg_w - size) // 2
            y = (self.bg_h - size) // 2
            self.crop = (x, y, size, size)
        self._draw()

    def _update_status(self):
        try:
            x, y, w, h = self._crop_box_abs()
            sel = (
                "none"
                if not self._sel
                else (
                    self._sel[0]
                    if isinstance(self._sel, (tuple, list))
                    else str(self._sel)
                )
            )
            self.status.config(
                text=f"bg:{self.bg_w}×{self.bg_h}  crop:{x},{y} {w}×{h}  selection:{sel}"
            )
        except Exception:
            pass

    def _log(self, s: str):
        try:
            self.status.config(text=s)
        except Exception:
            pass

    def _show_help(self):
        txt = (
            "Left‑click + drag a region to move it.\n"
            "Click empty area to drag the crop (yellow).\n"
            "Export JSON writes ui/skins/MySkin/skin.json by default.\n"
            "Save Crop writes ui/skins/MySkin/bg_cropped.png.\n"
        )
        messagebox.showinfo("Skin Designer", txt, parent=self)
