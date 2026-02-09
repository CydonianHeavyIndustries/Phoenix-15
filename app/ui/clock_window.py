import tkinter as tk
from datetime import datetime
from tkinter import ttk

from ui import theme

try:
    from systems import tasks
except Exception:
    tasks = None  # type: ignore


class ClockWindow(tk.Toplevel):
    """Simple clock with a list of upcoming reminders.

    Uses the shared HUD theme for all visual elements. The clock shows the
    current time and date, and a small Treeview lists the next few tasks.
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("Clock & Alarms — Bjorgsun-26")
        self.configure(bg=theme.COLORS["bg"])
        self.resizable(False, False)

        # Clock time display; accent color for readability
        self.lbl_time = tk.Label(
            self,
            text="--:--:--",
            fg=theme.COLORS["accent_glow"],
            bg=theme.COLORS["bg"],
            font=(theme.get_font_family(), 22, "bold"),
        )
        self.lbl_time.pack(padx=20, pady=(20, 4))
        # Date display below the time
        self.lbl_date = tk.Label(
            self,
            text="---- -- ----",
            fg=theme.COLORS["text"],
            bg=theme.COLORS["bg"],
            font=(theme.get_font_family(), 12),
        )
        self.lbl_date.pack(pady=(0, 20))

        tk.Label(
            self,
            text="Next Reminders",
            fg=theme.COLORS["accent_glow"],
            bg=theme.COLORS["bg"],
            font=(theme.get_font_family(), 12, "bold"),
        ).pack(anchor="w", padx=16)

        # Setup a small Treeview to list upcoming tasks/reminders
        cols = ("when", "message")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=5)
        self.tree.heading("when", text="When")
        self.tree.heading("message", text="Message")
        self.tree.column("when", width=140, anchor="w")
        self.tree.column("message", width=280, anchor="w")
        self.tree.pack(padx=16, pady=10)

        btn = tk.Button(
            self,
            text="Refresh",
            command=self._refresh_tasks,
            bg=theme.COLORS["panel"],
            fg=theme.COLORS["text"],
            relief="flat",
        )
        btn.pack(pady=(0, 12))

        self._update_time()
        self._refresh_tasks()

    def _update_time(self):
        now = datetime.now()
        self.lbl_time.config(text=now.strftime("%H:%M:%S"))
        self.lbl_date.config(text=now.strftime("%A, %B %d %Y"))
        self.after(1000, self._update_time)

    def _refresh_tasks(self):
        for child in self.tree.get_children():
            self.tree.delete(child)
        if tasks is None:
            self.tree.insert(
                "", "end", values=("Unavailable", "systems.tasks not loaded")
            )
            return
        try:
            try:
                tasks.load_tasks()
            except Exception:
                pass
            entries = tasks.get_all_tasks()
        except Exception:
            entries = []
        entries = sorted(entries, key=lambda t: t.get("time") or "")
        for t in entries[:8]:
            when = t.get("time") or "--"
            msg = t.get("message") or t.get("name") or ""
            status = "✅" if t.get("done") else "⏳"
            self.tree.insert("", "end", values=(f"{status} {when}", msg))
