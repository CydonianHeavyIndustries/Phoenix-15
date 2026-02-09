"""
Lightweight developer console window with a Tron-inspired palette.

Displays live logs, recent gaming events, and Titanfall status in a vertical,
scroll-friendly layout. Intended to be launched alongside the main UI when
dev mode is enabled.
"""

from __future__ import annotations

import os
import subprocess
import time
import tkinter as tk
from datetime import datetime
from typing import Any, Optional

try:
    from runtime import startup
except Exception:
    startup = None  # type: ignore
try:
    from module_manager import (
        import_folder,
        import_zip,
        export_module,
        MODULES_DIR,
        list_approved,
        mark_approved,
        is_approved,
    )
except Exception:
    import_folder = import_zip = export_module = MODULES_DIR = None  # type: ignore
    list_approved = mark_approved = is_approved = None  # type: ignore

try:
    import psutil  # type: ignore
except Exception:
    psutil = None

try:
    from systems import gaming_bridge
except Exception:  # pragma: no cover - defensive import
    gaming_bridge = None  # type: ignore


# Tron-like palette (kept local so it won't perturb the main theme)
TRON = {
    "bg": "#03060c",
    "panel": "#07111e",
    "panel_alt": "#0b1b2b",
    "text": "#c9f4ff",
    "muted": "#6bc0da",
    "accent": "#00d8ff",
    "accent2": "#ff9b2f",
    "glow": "#3cf0ff",
}


class DevPanel:
    """Standalone dev console stacked vertically for narrow/portrait displays."""

    def __init__(self, ui_instance):
        self.ui = ui_instance
        self.root: Optional[tk.Toplevel] = None
        self.log_box: Optional[tk.Text] = None
        self.events_box: Optional[tk.Text] = None
        self.status_box: Optional[tk.Text] = None
        self._build()
        self._schedule_refresh()
        self._wire_controls()
        self._dev_authorized = self._authorize_dev()

    # UI construction -----------------------------------------------------
    def _build(self):
        self.root = tk.Toplevel(self.ui.root)
        self.root.title("Bjorgsun Dev Console // Tron")
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass
        self.root.configure(bg=TRON["bg"])
        try:
            self.root.geometry("440x960+40+40")
        except Exception:
            pass

        title = tk.Label(
            self.root,
            text="DEV CONSOLE — TRON",
            fg=TRON["accent"],
            bg=TRON["bg"],
            font=("Segoe UI Semibold", 12),
            pady=6,
        )
        title.pack(fill="x")

        self.status_box = self._make_section(
            "System / Titanfall / Discord",
            height=10,
        )
        self.events_box = self._make_section("Recent Events", height=12)
        self.log_box = self._make_section("Live Logs", height=18)

        self.controls_frame = tk.Frame(self.root, bg=TRON["panel"], bd=0)
        self.controls_frame.pack(fill="x", padx=10, pady=(0, 10))
        tk.Label(
            self.controls_frame,
            text="Quick Actions",
            fg=TRON["text"],
            bg=TRON["panel"],
            anchor="w",
            font=("Segoe UI Semibold", 10),
        ).pack(fill="x", pady=(6, 4))
        self.btn_row = tk.Frame(self.controls_frame, bg=TRON["panel"])
        self.btn_row.pack(fill="x", pady=(0, 4))
        self._make_token_controls()

    def _make_section(self, title: str, height: int = 10) -> tk.Text:
        frame = tk.Frame(self.root, bg=TRON["panel"], bd=0, highlightthickness=1)
        frame.configure(highlightbackground=TRON["accent"])
        frame.pack(fill="both", expand=False, padx=10, pady=6)

        lbl = tk.Label(
            frame,
            text=title,
            anchor="w",
            fg=TRON["text"],
            bg=TRON["panel"],
            font=("Segoe UI Semibold", 10),
            pady=3,
        )
        lbl.pack(fill="x")

        txt = tk.Text(
            frame,
            height=height,
            wrap="word",
            bg=TRON["panel_alt"],
            fg=TRON["text"],
            padx=8,
            pady=6,
            relief="flat",
            insertbackground=TRON["glow"],
        )
        txt.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        txt.configure(state="disabled")
        return txt

    def _wire_controls(self):
        """Attach quick-action buttons to existing UI hooks if present."""
        def make_btn(label, cmd):
            btn = tk.Button(
                self.btn_row,
                text=label,
                command=cmd,
                bg=TRON["panel_alt"],
                fg=TRON["text"],
                activebackground=TRON["panel"],
                activeforeground=TRON["accent"],
                relief="flat",
                padx=8,
                pady=4,
            )
            btn.pack(side="left", padx=4, pady=2)

        make_btn("Wake", lambda: self._call_ui("_do_wake", True))
        make_btn("Sleep", lambda: self._call_ui("_sleep_toggle"))
        make_btn("Discord", lambda: self._call_ui("_refresh_discord_status"))
        make_btn("Reload Layout", lambda: self._call_ui("_load_layout_prefs"))

    # Logging -------------------------------------------------------------
    def add_log(self, line: str, level: str = "info"):
        if not self.log_box:
            return
        try:
            self.log_box.configure(state="normal")
            stamp = datetime.now().strftime("%H:%M:%S")
            tag = f"lvl_{level}"
            self.log_box.insert("end", f"[{stamp}] {line}\n", (tag,))
            self.log_box.tag_configure(tag, foreground=self._color_for_level(level))
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        except Exception:
            pass

    @staticmethod
    def _color_for_level(level: str) -> str:
        lv = (level or "").lower()
        if lv in {"error", "err", "danger", "fatal"}:
            return "#ff6b6b"
        if lv in {"warn", "warning"}:
            return "#ffb347"
        if lv in {"event", "action"}:
            return TRON["accent2"]
        return TRON["text"]

    # Refresh / data ------------------------------------------------------
    def _schedule_refresh(self):
        try:
            if self.root:
                self.root.after(1200, self._refresh)
        except Exception:
            pass

    def _refresh(self):
        self._update_status()
        self._update_events()
        self._update_tokens()
        self._schedule_refresh()

    def _authorize_dev(self) -> bool:
        """Gate dev tools behind a password if configured."""
        pwd_required = os.getenv("DEV_MODE_PASSWORD", "").strip()
        if not pwd_required:
            return True
        try:
            import tkinter.simpledialog as _sd
            pre_top = None
            try:
                pre_top = self.root.attributes("-topmost")
                self.root.attributes("-topmost", True)
                self.root.lift()
                self.root.focus_force()
            except Exception:
                pass
            val = _sd.askstring(
                "Dev Authorization",
                "Enter dev mode password to enable tools:",
                show="•",
                parent=self.root,
            )
            ok = bool(val and val.strip() == pwd_required)
            try:
                if pre_top is not None:
                    self.root.attributes("-topmost", pre_top)
            except Exception:
                pass
            return ok
        except Exception:
            return False

    def _update_status(self):
        if not self.status_box:
            return
        lines: list[str] = []
        # System stats
        if psutil:
            try:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
                lines.append(f"CPU {cpu:.0f}%   MEM {mem:.0f}%")
            except Exception:
                pass
        # Titanfall state
        status: dict[str, Any] = {}
        if gaming_bridge:
            try:
                status = gaming_bridge.get_titanfall_status() or {}
            except Exception:
                status = {}
        titan = status.get("titan") or {}
        match = status.get("match") or {}
        mission = status.get("mission") or status.get("mission_state") or ""
        connected = status.get("connected") or status.get("log_connected") or False
        if status:
            lines.append(
                f"Link: {'ON' if connected else 'idle'} | Mission: {mission or 'n/a'}"
            )
            if match:
                map_name = match.get("map") or "?"
                mode = match.get("mode") or "?"
                lines.append(f"Match: {mode} @ {map_name}")
            if titan:
                state = titan.get("status") or "offline"
                hp = titan.get("health") or 0
                shield = titan.get("shield") or 0
                ready = "READY" if titan.get("ready") else "charging"
                lines.append(f"Titan: {state} | HP {hp} | SH {shield} | {ready}")
        else:
            lines.append("Titanfall: no link (dev mode passive).")

        # Discord bridge quick info
        info = {}
        try:
            if hasattr(self.ui, "_refresh_discord_status"):
                info = getattr(
                    __import__("systems.discord_bridge", fromlist=["discord_bridge"]),
                    "discord_bridge",
                ).get_status()
        except Exception:
            info = {}
        if info:
            ready = info.get("ready")
            voice = "voice" if info.get("voice_connected") else "text-only"
            queue = info.get("pending_requests", 0)
            lines.append(
                f"Discord: {'online' if ready else 'offline'} | {voice} | queue {queue}"
            )

        content = "\n".join(lines) or "No data yet."
        try:
            self.status_box.configure(state="normal")
            self.status_box.delete("1.0", "end")
            self.status_box.insert("end", content)
            self.status_box.configure(state="disabled")
        except Exception:
            pass

    def _update_events(self):
        if not self.events_box:
            return
        events: list[dict[str, Any]] = []
        if gaming_bridge:
            try:
                events = gaming_bridge.get_recent_events(20)
            except Exception:
                events = []
        lines = []
        for evt in events[-20:]:
            ts = evt.get("time") or time.time()
            try:
                stamp = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            except Exception:
                stamp = "--:--"
            txt = evt.get("text") or ""
            level = evt.get("level") or ""
            lines.append(f"[{stamp}] {txt}" + (f" ({level})" if level else ""))
        content = "\n".join(lines) if lines else "No events yet."
        try:
            self.events_box.configure(state="normal")
            self.events_box.delete("1.0", "end")
            self.events_box.insert("end", content)
            self.events_box.configure(state="disabled")
        except Exception:
            pass

    # Token usage --------------------------------------------------------
    def _make_token_controls(self):
        self.token_frame = tk.Frame(self.controls_frame, bg=TRON["panel"], bd=0)
        self.token_frame.pack(fill="x", padx=2, pady=(6, 4))
        tk.Label(
            self.token_frame,
            text="Token Budget",
            fg=TRON["text"],
            bg=TRON["panel"],
            anchor="w",
            font=("Segoe UI Semibold", 10),
        ).pack(fill="x", pady=(2, 2))
        self.token_vals = tk.Label(
            self.token_frame,
            text="total: 0 | used: 0 | remaining: 0",
            fg=TRON["muted"],
            bg=TRON["panel"],
            anchor="w",
            font=("Consolas", 9),
        )
        self.token_vals.pack(fill="x")
        self.token_bar = tk.Canvas(
            self.token_frame,
            height=14,
            bg=TRON["panel_alt"],
            highlightthickness=0,
        )
        self.token_bar.pack(fill="x", pady=(2, 4))
        btns = tk.Frame(self.token_frame, bg=TRON["panel"])
        btns.pack(fill="x", pady=(0, 4))

        def _set_budget():
            try:
                import tkinter.simpledialog as _sd

                val = _sd.askinteger(
                    "Set Token Budget", "Enter starting tokens:", parent=self.root
                )
                if val is None:
                    return
                if startup:
                    startup.set_token_budget(val)
            except Exception:
                pass

        def _add_usage():
            try:
                import tkinter.simpledialog as _sd

                amt = _sd.askinteger(
                    "Add Token Usage", "Tokens consumed:", parent=self.root
                )
                if amt is None:
                    return
                src = _sd.askstring(
                    "Usage Source",
                    "What used these tokens? (e.g., gpt, search, titanfall)",
                    parent=self.root,
                )
                if startup:
                    startup.add_token_usage(amt, source=src or "manual")
            except Exception:
                pass

        tk.Button(
            btns,
            text="Set Budget",
            command=_set_budget,
            bg=TRON["panel_alt"],
            fg=TRON["text"],
            relief="flat",
            padx=6,
            pady=2,
        ).pack(side="left", padx=3)
        tk.Button(
            btns,
            text="Add Usage",
            command=_add_usage,
            bg=TRON["panel_alt"],
            fg=TRON["text"],
            relief="flat",
            padx=6,
            pady=2,
        ).pack(side="left", padx=3)

        self.token_breakdown = tk.Text(
            self.token_frame,
            height=4,
            wrap="word",
            bg=TRON["panel_alt"],
            fg=TRON["muted"],
            padx=6,
            pady=4,
            relief="flat",
            font=("Consolas", 9),
        )
        self.token_breakdown.configure(state="disabled")
        self.token_breakdown.pack(fill="x", pady=(2, 2))

    def _update_tokens(self):
        if not startup:
            return
        try:
            stats = startup.get_token_stats()
        except Exception:
            return
        total = stats.get("total", 0) or 0
        used = stats.get("used", 0) or 0
        remain = stats.get("remaining", 0) or 0
        pct = stats.get("percent", 0.0) or 0.0
        self.token_vals.config(
            text=f"total: {total} | used: {used} | remaining: {remain} | {pct:.1f}%"
        )
        # Draw bar
        try:
            self.token_bar.delete("all")
            w = self.token_bar.winfo_width() or 360
            if w < 10:
                w = 360
            used_w = 0
            if total > 0:
                used_w = min(w, int(w * (used / total)))
            self.token_bar.create_rectangle(
                0, 0, w, 14, fill=TRON["panel_alt"], outline=TRON["panel"]
            )
            self.token_bar.create_rectangle(
                0, 0, used_w, 14, fill=TRON["accent2"], outline=TRON["panel"]
            )
        except Exception:
            pass
        # Breakdown
        try:
            self.token_breakdown.configure(state="normal")
            self.token_breakdown.delete("1.0", "end")
            breakdown = stats.get("breakdown") or []
            if not breakdown:
                self.token_breakdown.insert("end", "No usage recorded.\n")
            else:
                for src, amt in breakdown[:5]:
                    self.token_breakdown.insert("end", f"{src}: {amt}\n")
            self.token_breakdown.configure(state="disabled")
        except Exception:
            pass

        # Dev tools + module import/export (dev-only)
        if import_zip and import_folder:
            mod_frame = tk.Frame(self.token_frame, bg=TRON["panel"])
            mod_frame.pack(fill="x", pady=(6, 4))
            tk.Label(
                mod_frame,
                text="Modules / Dev Tools",
                fg=TRON["text"],
                bg=TRON["panel"],
                anchor="w",
                font=("Segoe UI Semibold", 10),
            ).pack(fill="x", pady=(2, 2))
            btns = tk.Frame(mod_frame, bg=TRON["panel"])
            btns.pack(fill="x", pady=(0, 4))

            def _import_zip():
                if not self._dev_authorized:
                    self.add_log("Dev tools locked (password).", "warn")
                    return
                try:
                    from tkinter import filedialog as _fd

                    path = _fd.askopenfilename(
                        title="Select module zip",
                        filetypes=[("Zip", "*.zip"), ("All files", "*.*")],
                    )
                    if not path:
                        return
                    target = import_zip(path)
                    mod_name = os.path.basename(target)
                    approved = " (approved)" if is_approved and is_approved(mod_name) else " (unapproved)"
                    self.add_log(f"Module imported: {target}{approved}", "event")
                except Exception as e:
                    self.add_log(f"Module import failed: {e}", "error")

            def _import_folder():
                if not self._dev_authorized:
                    self.add_log("Dev tools locked (password).", "warn")
                    return
                try:
                    from tkinter import filedialog as _fd

                    path = _fd.askdirectory(title="Select module folder")
                    if not path:
                        return
                    target = import_folder(path)
                    mod_name = os.path.basename(target)
                    approved = " (approved)" if is_approved and is_approved(mod_name) else " (unapproved)"
                    self.add_log(f"Module imported: {target}{approved}", "event")
                except Exception as e:
                    self.add_log(f"Module import failed: {e}", "error")

            def _export_module():
                if not MODULES_DIR:
                    return
                if not self._dev_authorized:
                    self.add_log("Dev tools locked (password).", "warn")
                    return
                try:
                    from tkinter import simpledialog as _sd, filedialog as _fd
                    name = _sd.askstring("Module name", "Module folder name:", parent=self.root)
                    if not name:
                        return
                    out = _fd.asksaveasfilename(
                        title="Save module zip",
                        defaultextension=".zip",
                        filetypes=[("Zip", "*.zip")],
                        initialfile=f"{name}.zip",
                    )
                    if not out:
                        return
                    res = export_module(name, out)
                    self.add_log(f"Module exported: {res}", "event")
                except Exception as e:
                    self.add_log(f"Module export failed: {e}", "error")

            def _open_vscode():
                if not self._dev_authorized:
                    self.add_log("Dev tools locked (password).", "warn")
                    return
                try:
                    # Attempt to launch VS Code in repo root
                    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                    subprocess.Popen(["code", repo_root])
                    self.add_log("VS Code launch requested.", "event")
                except Exception as e:
                    self.add_log(f"VS Code launch failed: {e}", "error")

            tk.Button(
                btns,
                text="Import Zip",
                command=_import_zip,
                bg=TRON["panel_alt"],
                fg=TRON["text"],
                relief="flat",
                padx=6,
                pady=2,
            ).pack(side="left", padx=3)
            tk.Button(
                btns,
                text="Import Folder",
                command=_import_folder,
                bg=TRON["panel_alt"],
                fg=TRON["text"],
                relief="flat",
                padx=6,
                pady=2,
            ).pack(side="left", padx=3)
            tk.Button(
                btns,
                text="Export Module",
                command=_export_module,
                bg=TRON["panel_alt"],
                fg=TRON["text"],
                relief="flat",
                padx=6,
                pady=2,
            ).pack(side="left", padx=3)
            tk.Button(
                btns,
                text="Open VS Code",
                command=_open_vscode,
                bg=TRON["panel_alt"],
                fg=TRON["text"],
                relief="flat",
                padx=6,
                pady=2,
            ).pack(side="left", padx=3)
            if mark_approved and list_approved:
                def _approve():
                    try:
                        from tkinter import simpledialog as _sd
                        name = _sd.askstring("Approve Module", "Module folder name to approve:", parent=self.root)
                        if not name:
                            return
                        mark_approved(name)
                        self.add_log(f"Module approved: {name}", "event")
                    except Exception as e:
                        self.add_log(f"Approve failed: {e}", "error")

                def _show_approved():
                    try:
                        items = list_approved()
                        msg = "Approved modules:\n" + ("\n".join(items) if items else "None")
                        self.add_log(msg, "info")
                    except Exception as e:
                        self.add_log(f"List failed: {e}", "error")

                tk.Button(
                    btns,
                    text="Approve Module",
                    command=_approve,
                    bg=TRON["panel_alt"],
                    fg=TRON["text"],
                    relief="flat",
                    padx=6,
                    pady=2,
                ).pack(side="left", padx=3)
                tk.Button(
                    btns,
                    text="List Approved",
                    command=_show_approved,
                    bg=TRON["panel_alt"],
                    fg=TRON["text"],
                    relief="flat",
                    padx=6,
                    pady=2,
                ).pack(side="left", padx=3)
    # Helpers -------------------------------------------------------------
    def _call_ui(self, method: str, *args):
        """Invoke a method on the main UI if it exists (defensive)."""
        try:
            fn = getattr(self.ui, method, None)
            if callable(fn):
                return fn(*args)
        except Exception:
            return None
