import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from runtime import coreloop
from systems import tasks
from ui import theme


class TaskWindow(tk.Toplevel):
    """Popup window for viewing and managing scheduled tasks and reminders.

    This window uses the shared theme colors and fonts to blend into the
    overall HUD. It offers a tree view of tasks with three columns:
    scheduled time, status, and description. Users can add new reminders
    using natural language and mark or remove existing tasks with buttons.
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("Tasks & Events — Bjorgsun-26")
        self.configure(bg=theme.COLORS["bg"])

        # Attempt to set a custom window icon if available
        try:
            import os

            _ico = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "assets", "Bjorgsunexeicon.ico")
            )
            if os.path.exists(_ico):
                try:
                    self.iconbitmap(_ico)
                except Exception:
                    pass
        except Exception:
            pass

        # Use a generous initial size and center the window. The
        # calculations account for monitor resolution to avoid windows
        # spanning off-screen on smaller displays.
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = max(680, min(960, sw - 160)), max(480, min(720, sh - 160))
            self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//6}")
        except Exception:
            self.geometry("720x520")
        self.minsize(640, 420)
        self.resizable(True, True)
        self.attributes("-topmost", False)

        # Header area containing a title and refresh button
        header = tk.Frame(self, bg=theme.COLORS["bg"])
        header.pack(fill="x", padx=10, pady=(10, 6))
        tk.Label(
            header,
            text="🗒️ Tasks & Events",
            bg=theme.COLORS["bg"],
            fg=theme.COLORS["accent_glow"],
            font=(theme.get_font_family(), 13, "bold"),
        ).pack(side="left")
        tk.Button(
            header,
            text="Refresh",
            command=self.refresh,
            bg=theme.COLORS["panel"],
            fg=theme.COLORS["text"],
            relief="flat",
        ).pack(side="right")

        # Treeview setup for tasks; explicit column widths help avoid
        # collapsing columns on small windows. Use heading names as keys.
        cols = ("when", "status", "message")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        self.tree.heading("when", text="When")
        self.tree.heading("status", text="Status")
        self.tree.heading("message", text="Message")
        self.tree.column("when", width=140, anchor="w")
        self.tree.column("status", width=80, anchor="center")
        self.tree.column("message", width=320, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # Control row for creating and modifying reminders
        controls = tk.Frame(self, bg=theme.COLORS["bg"])
        controls.pack(fill="x", padx=10, pady=(0, 10))
        # Quick add label
        tk.Label(
            controls,
            text="Add:",
            bg=theme.COLORS["bg"],
            fg=theme.COLORS["text"],
            font=(theme.get_font_family(), 10),
        ).pack(side="left")
        # Task description entry
        self.entry_text = tk.Entry(
            controls,
            width=30,
            bg=theme.COLORS["panel"],
            fg=theme.COLORS["text"],
            insertbackground=theme.COLORS["accent"],
            relief="flat",
        )
        self.entry_text.insert(0, "description…")
        self.entry_text.pack(side="left", padx=(2, 8))
        # Time description entry
        self.entry_time = tk.Entry(
            controls,
            width=28,
            bg=theme.COLORS["panel"],
            fg=theme.COLORS["text"],
            insertbackground=theme.COLORS["accent"],
            relief="flat",
        )
        self.entry_time.insert(0, "time phrase (e.g. 'in 20 minutes')")
        self.entry_time.pack(side="left")

        # Buttons for actions on tasks. Use consistent spacing and the
        # panel color for button backgrounds to match the HUD. Only one
        # "Mark Done" button is needed; remove duplicate "Complete/Finish".
        tk.Button(
            controls,
            text="Add Reminder",
            command=self._add_from_entries,
            bg=theme.COLORS["panel"],
            fg=theme.COLORS["text"],
            relief="flat",
        ).pack(side="left", padx=(8, 0))
        tk.Button(
            controls,
            text="Mark Done",
            command=self._mark_done,
            bg=theme.COLORS["panel"],
            fg=theme.COLORS["text"],
            relief="flat",
        ).pack(side="left", padx=(8, 0))
        tk.Button(
            controls,
            text="Remove",
            command=self._remove,
            bg=theme.COLORS["panel"],
            fg=theme.COLORS["text"],
            relief="flat",
        ).pack(side="left", padx=(8, 0))

        self.refresh()
        # Double-click a row to mark it done quickly
        try:
            self.tree.bind("<Double-1>", lambda e: self._mark_done())
        except Exception:
            pass

    def _add_from_entries(self):
        desc = (self.entry_text.get() or "Your reminder").strip()
        when = (self.entry_time.get() or "in 15 minutes").strip()
        phrase = f"remind me {when} to {desc}"
        try:
            resp = coreloop.process_input(phrase)
            messagebox.showinfo("Reminder", resp)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selection_name(self):
        sel = self.tree.selection()
        if not sel:
            return None
        item = self.tree.item(sel[0])
        # We stored name in iid
        return item.get("iid")

    def _selection_message(self):
        sel = self.tree.selection()
        if not sel:
            return None
        item = self.tree.item(sel[0])
        vals = item.get("values") or []
        # columns: when, status, message
        return vals[2] if len(vals) >= 3 else None

    def _mark_done(self):
        name = self._selection_name()
        if not name:
            # Try fuzzy by message if selection failed
            try:
                msg = self._selection_message()
                if msg:
                    ok, _ = tasks.mark_done_fuzzy(msg)
                else:
                    ok = False
            except Exception:
                ok = False
        else:
            ok = tasks.mark_done(name)
            if not ok:
                # Try multiple fuzzy fallbacks: by message and by name string
                try:
                    msg = self._selection_message() or name
                    ok2, _ = tasks.mark_done_fuzzy(msg)
                    if not ok2:
                        ok3, _ = tasks.mark_done_fuzzy(name)
                        ok = ok2 or ok3
                    else:
                        ok = True
                except Exception:
                    ok = False
        if not ok:
            try:
                messagebox.showwarning(
                    "Tasks", "Could not mark the selected task as done."
                )
            except Exception:
                pass
        self.refresh()

    def _remove(self):
        name = self._selection_name()
        if not name:
            # Try fuzzy by message if selection failed
            try:
                msg = self._selection_message()
                if msg:
                    ok, _ = tasks.remove_task_fuzzy(msg)
                else:
                    ok = False
            except Exception:
                ok = False
        else:
            ok = tasks.remove_task(name)
            if not ok:
                # Try both message and name fuzzy
                try:
                    msg = self._selection_message() or name
                    ok2, _ = tasks.remove_task_fuzzy(msg)
                    if not ok2:
                        ok3, _ = tasks.remove_task_fuzzy(name)
                        ok = ok2 or ok3
                    else:
                        ok = True
                except Exception:
                    ok = False
            if not ok:
                try:
                    messagebox.showwarning(
                        "Tasks", "Could not remove the selected task."
                    )
                except Exception:
                    pass
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            # Reload from disk to reflect reminders created before window opened or after reloads
            tasks.load_tasks()
        except Exception:
            pass
        data = tasks.get_all_tasks()
        for t in data:
            try:
                when = (
                    datetime.fromisoformat(t["time"]).strftime("%Y-%m-%d %H:%M")
                    if t.get("time")
                    else "--"
                )
            except Exception:
                when = t.get("time") or "--"
            status = "✅ done" if t.get("done") else "⏳ pending"
            msg = t.get("message") or t.get("name")
            iid = t.get("name")
            self.tree.insert("", "end", iid=iid, values=(when, status, msg))
