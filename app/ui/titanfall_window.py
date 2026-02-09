import time
import tkinter as tk
from tkinter import ttk
from typing import Any, List

from systems import gaming_bridge
from ui import theme


class TitanfallWindow:
    """Pop-out control panel for Titanfall telemetry and autopilot orders."""

    def __init__(self, app):
        self.app = app
        self.root = tk.Toplevel(app.root)
        self.root.title("Titanfall Control Console")
        try:
            # Start at a compact-but-roomy size; auto-scale if screen is small
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            base_w = 1220
            base_h = 820
            scale = min(1.0, max(0.85, min(sw / 1440.0, sh / 900.0)))
            w = int(base_w * scale)
            h = int(base_h * scale)
            self.root.geometry(f"{w}x{h}+120+120")
            self.root.minsize(int(960 * scale), int(640 * scale))
        except Exception:
            pass
        self.root.configure(bg=theme.COLORS["bg"])
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.close)
        except Exception:
            pass

        self.status_var = tk.StringVar(value="Titanfall link idle.")
        self.detail_var = tk.StringVar(value="Waiting for telemetry…")
        self.mission_var = tk.StringVar(value="Mission: offline")
        self.autopilot_var = tk.BooleanVar(value=True)

        self._build_layout()
        self.refresh()

    # ------------------------------------------------------------------
    def _build_layout(self):
        top = tk.Frame(self.root, bg=theme.COLORS["bg"])
        top.pack(fill="x", padx=10, pady=(10, 6))
        tk.Label(
            top,
            textvariable=self.status_var,
            bg=theme.COLORS["bg"],
            fg="#ffae6b",
            font=(theme.get_font_family(), 12, "bold"),
            anchor="w",
        ).pack(fill="x")
        self.detail_label = tk.Label(
            top,
            textvariable=self.detail_var,
            bg=theme.COLORS["bg"],
            fg=theme.COLORS["text"],
            font=(theme.get_font_family(), 10),
            anchor="w",
            wraplength=700,
            justify="left",
        )
        self.detail_label.pack(fill="x", pady=(2, 4))
        tk.Label(
            top,
            textvariable=self.mission_var,
            bg=theme.COLORS["bg"],
            fg="#ffdcb3",
            font=(theme.get_font_family(), 10, "bold"),
            anchor="w",
        ).pack(fill="x")

        body = tk.Frame(self.root, bg=theme.COLORS["bg"])
        body.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        body.columnconfigure(0, weight=3, minsize=640)
        body.columnconfigure(1, weight=2, minsize=400)
        body.rowconfigure(0, weight=1)

        # Orders + status list
        orders_card = tk.LabelFrame(
            body,
            text="Active Orders",
            bg=theme.COLORS["bg"],
            fg="#77ccff",
            font=(theme.get_font_family(), 10, "bold"),
        )
        orders_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        orders_card.rowconfigure(1, weight=1)
        orders_card.columnconfigure(0, weight=1)
        self.orders_hint = tk.Label(
            orders_card,
            text="Autopilot should remember these until you overwrite them.",
            bg=theme.COLORS["bg"],
            fg=theme.COLORS["muted"],
            font=(theme.get_font_family(), 9),
            anchor="w",
            wraplength=520,
        )
        self.orders_hint.grid(row=0, column=0, sticky="ew", padx=8, pady=(4, 2))
        self.orders_box = tk.Text(
            orders_card,
            height=14,
            wrap="word",
            bg="#0f131a",
            fg="#cde6ff",
            relief="flat",
            state="disabled",
        )
        self.orders_box.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 4))

        # Controls
        controls = tk.LabelFrame(
            body,
            text="Directives",
            bg=theme.COLORS["bg"],
            fg="#ffae6b",
            font=(theme.get_font_family(), 10, "bold"),
        )
        controls.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))
        controls.columnconfigure(0, weight=1)
        controls.rowconfigure(7, weight=1)

        autop_row = tk.Frame(controls, bg=theme.COLORS["bg"])
        autop_row.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 4))
        tk.Checkbutton(
            autop_row,
            text="Enable Titan autopilot control",
            variable=self.autopilot_var,
            command=self._toggle_autopilot,
            bg=theme.COLORS["bg"],
            fg="#ffdcb3",
            selectcolor=theme.COLORS["panel"],
            activebackground=theme.COLORS["bg"],
            font=(theme.get_font_family(), 10, "bold"),
            anchor="w",
            wraplength=260,
        ).pack(side="left", fill="x", expand=True)
        self._make_button(autop_row, "Reissue", self._reissue_orders).pack(
            side="right", padx=(4, 0)
        )
        self._make_button(
            autop_row, "Stop Game Mode", self._stop_game_mode
        ).pack(side="right", padx=(4, 0))

        tk.Label(
            controls,
            text="New order:",
            bg=theme.COLORS["bg"],
            fg=theme.COLORS["text"],
            font=(theme.get_font_family(), 10, "bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=6)
        self.order_entry = tk.Entry(
            controls, bg="#10141c", fg="#cde6ff", insertbackground="#cde6ff"
        )
        self.order_entry.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 4))
        options = tk.Frame(controls, bg=theme.COLORS["bg"])
        options.grid(row=3, column=0, sticky="ew", padx=6, pady=(0, 4))
        options.columnconfigure(0, weight=1)
        tk.Label(
            options,
            text="Tag:",
            bg=theme.COLORS["bg"],
            fg=theme.COLORS["muted"],
            font=(theme.get_font_family(), 9),
        ).grid(row=0, column=0, sticky="w")
        self.tag_var = tk.StringVar(value="")
        tag_menu = ttk.Combobox(
            options,
            textvariable=self.tag_var,
            values=[
                "",
                "follow",
                "guard",
                "hold",
                "patrol",
                "aggressive_push",
                "defensive_block",
            ],
            width=16,
        )
        tag_menu.grid(row=0, column=1, sticky="w", padx=(6, 0))
        tk.Label(
            options,
            text="Priority (1-9):",
            bg=theme.COLORS["bg"],
            fg=theme.COLORS["muted"],
            font=(theme.get_font_family(), 9),
        ).grid(row=0, column=2, sticky="e", padx=(8, 2))
        self.pri_var = tk.StringVar(value="5")
        tk.Spinbox(options, from_=1, to=9, textvariable=self.pri_var, width=4).grid(
            row=0, column=3, sticky="e"
        )

        btns = tk.Frame(controls, bg=theme.COLORS["bg"])
        btns.grid(row=4, column=0, sticky="ew", padx=6, pady=(4, 2))
        self._make_button(btns, "Queue", lambda: self._submit_order(False)).pack(
            side="left", expand=True, fill="x", padx=(0, 4)
        )
        self._make_button(btns, "Overwrite", lambda: self._submit_order(True)).pack(
            side="left", expand=True, fill="x"
        )

        quick = tk.Frame(controls, bg=theme.COLORS["bg"])
        quick.grid(row=5, column=0, sticky="ew", padx=6, pady=(6, 2))
        quick.columnconfigure((0, 1), weight=1)
        self._make_button(
            quick, "Guard pilot", lambda: self._quick_order("guard")
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._make_button(
            quick, "Hold position", lambda: self._quick_order("hold")
        ).grid(row=0, column=1, sticky="ew")
        self._make_button(
            quick, "Aggressive push", lambda: self._quick_order("aggressive_push", 8)
        ).grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(4, 0))
        self._make_button(
            quick, "Defensive fallback", lambda: self._quick_order("defensive_block", 7)
        ).grid(row=1, column=1, sticky="ew", pady=(4, 0))

        radio_frame = tk.LabelFrame(
            controls,
            text="In-game comms",
            bg=theme.COLORS["bg"],
            fg="#9fe8ff",
            font=(theme.get_font_family(), 10, "bold"),
        )
        radio_frame.grid(row=6, column=0, sticky="ew", padx=4, pady=(8, 6))
        self.radio_entry = tk.Entry(
            radio_frame, bg="#10141c", fg="#cde6ff", insertbackground="#cde6ff"
        )
        self.radio_entry.pack(fill="x", padx=6, pady=(4, 2))
        self._make_button(
            radio_frame,
            "Send radio (with context)",
            lambda: self._send_radio(True),
        ).pack(fill="x", padx=6, pady=(0, 4))
        self._make_button(
            radio_frame,
            "Send radio (text only)",
            lambda: self._send_radio(False),
        ).pack(fill="x", padx=6, pady=(0, 8))

        def _on_resize(evt):
            try:
                wrap = max(420, int(evt.width * 0.45))
                self.orders_hint.configure(wraplength=wrap)
                self.detail_label.configure(
                    wraplength=max(520, int(evt.width * 0.55))
                )
            except Exception:
                pass

        body.bind("<Configure>", _on_resize)

    # ------------------------------------------------------------------
    def _make_button(self, parent, text: str, cmd):
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=theme.COLORS["panel"],
            fg="#e8f4ff",
            activebackground="#1c2735",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            font=(theme.get_font_family(), 10, "bold"),
            cursor="hand2",
        )

    def _quick_order(self, tag: str, priority: int = 6):
        label = {
            "guard": "Guard the pilot and stay close.",
            "hold": "Hold current position and cover the area.",
            "patrol": "Patrol this sector and report contacts.",
            "aggressive_push": "Push forward aggressively and clear hostiles.",
            "defensive_block": "Fall back to cover and hold the line.",
        }.get(tag, f"Execute {tag}.")
        self.order_entry.delete(0, "end")
        self.order_entry.insert(0, label)
        self.tag_var.set(tag)
        self.pri_var.set(str(priority))
        self._submit_order(False)

    def _submit_order(self, overwrite: bool):
        text = (self.order_entry.get() or "").strip()
        tag = (self.tag_var.get() or "").strip().lower() or None
        try:
            priority = int(self.pri_var.get() or "5")
        except Exception:
            priority = 5
        if not text and tag:
            text = f"{tag.replace('_', ' ').title()} order"
        if not text:
            return
        gaming_bridge.add_titanfall_order(
            text, tag=tag, priority=priority, overwrite=overwrite
        )
        self.order_entry.delete(0, "end")

    def _send_radio(self, contextual: bool):
        text = (self.radio_entry.get() or "").strip()
        if not text:
            return
        gaming_bridge.send_titanfall_radio(text, contextual=contextual)
        self.radio_entry.delete(0, "end")

    def _toggle_autopilot(self):
        flag = bool(self.autopilot_var.get())
        gaming_bridge.set_titanfall_autopilot(flag)

    def _reissue_orders(self):
        if gaming_bridge.reissue_titanfall_orders():
            if self.app:
                try:
                    self.app.safe_log("Titanfall orders resent.", "#ffae6b")
                except Exception:
                    pass

    def _stop_game_mode(self):
        try:
            gaming_bridge.configure_titanfall(enabled=False)
            try:
                if self.app:
                    self.app.safe_log("Titanfall monitor disabled.", "#ffae6b")
            except Exception:
                pass
        except Exception as exc:
            try:
                if self.app:
                    self.app.safe_log(f"Stop game mode failed: {exc}", "#ff5555")
            except Exception:
                pass

    # ------------------------------------------------------------------
    def refresh(self):
        try:
            status = gaming_bridge.get_titanfall_status()
        except Exception:
            status = {}
        try:
            orders_state = gaming_bridge.get_titanfall_orders()
        except Exception:
            orders_state = {}

        titan = status.get("titan") or {}
        match_info = status.get("match") or {}
        callsign = (status.get("callsign") or "Bjorgsun-26").strip()
        titan_status = titan.get("status") or ("ready" if titan.get("ready") else "")
        self.status_var.set(
            f"{callsign} • {(titan.get('chassis') or 'Titan')}: {titan_status.title() or 'offline'}"
        )
        detail_parts: List[str] = []
        if titan.get("health"):
            detail_parts.append(f"HP {int(titan.get('health') or 0)}")
        if titan.get("shield"):
            detail_parts.append(f"Shield {int(titan.get('shield') or 0)}")
        if titan.get("battery"):
            detail_parts.append(f"Battery ×{int(titan.get('battery') or 0)}")
        if titan.get("core_ready"):
            detail_parts.append("Core ready")
        elif titan.get("cooldown"):
            detail_parts.append(f"Build {int(titan.get('cooldown') or 0)}%")
        map_name = match_info.get("map")
        mode = match_info.get("mode")
        if map_name:
            detail_parts.append(f"{map_name} ({mode or 'Unknown'})")
        score = match_info.get("score") or {}
        if score:
            detail_parts.append(
                f"Score {int(score.get('friend') or 0)} - {int(score.get('foe') or 0)}"
            )
        time_rem = match_info.get("time_remaining")
        if time_rem:
            detail_parts.append(f"{time_rem} remaining")
        detail_text = " • ".join(detail_parts) if detail_parts else "Awaiting data…"
        self.detail_var.set(detail_text)

        mission_raw = (
            status.get("mission_state")
            or ("in_mission" if status.get("in_mission") else "offline")
        )
        self.mission_var.set(f"Mission: {str(mission_raw).replace('_', ' ').title()}")

        autopilot = bool(orders_state.get("autopilot_enabled", True))
        self.autopilot_var.set(autopilot)
        orders = orders_state.get("orders") or []
        lines: List[str] = []
        for item in orders:
            try:
                issued = time.strftime(
                    "%H:%M:%S", time.localtime(item.get("issued_at", time.time()))
                )
            except Exception:
                issued = "--:--"
            tag = (item.get("tag") or "").replace("_", " ").title()
            text = item.get("text") or ""
            prio = item.get("priority") or 5
            label = f"[{issued}] P{prio} {tag}: {text}" if tag else f"[{issued}] P{prio}: {text}"
            lines.append(label.strip())
        if not lines:
            lines = ["No standing orders. Add one to steer the autopilot."]
        orders_text = "\n".join(lines)
        try:
            self.orders_box.configure(state="normal")
            self.orders_box.delete("1.0", "end")
            self.orders_box.insert(
                "end", orders_text + ("\n" if not orders_text.endswith("\n") else "")
            )
            self.orders_box.configure(state="disabled")
        except Exception:
            pass

        try:
            self.root.after(2200, self.refresh)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass
