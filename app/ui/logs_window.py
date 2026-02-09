import os
import tkinter as tk
from tkinter import ttk

from ui import theme


class LogsWindow(tk.Toplevel):
    """Popup window for viewing log files.

    Displays a list of text and log files from the logs directory on the left
    and the tail of the selected file on the right. The filter at the top
    allows narrowing the list by file contents. All colors and fonts are
    derived from the shared theme so the window blends into the HUD.
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("Logs — Bjorgsun-26")
        self.configure(bg=theme.COLORS["bg"])

        # Attempt to set a custom window icon
        try:
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

        self.geometry("920x560")
        self.resizable(True, True)

        # Top bar: filter entry and action buttons
        top = tk.Frame(self, bg=theme.COLORS["bg"])
        top.pack(fill="x", padx=8, pady=6)
        tk.Label(
            top,
            text="Filter:",
            bg=theme.COLORS["bg"],
            fg=theme.COLORS["text"],
            font=(theme.get_font_family(), 10),
        ).pack(side="left")
        self.var_filter = tk.StringVar(value="")
        ent = tk.Entry(
            top,
            textvariable=self.var_filter,
            bg=theme.COLORS["panel"],
            fg=theme.COLORS["text"],
            insertbackground=theme.COLORS["accent"],
            width=30,
            relief="flat",
        )
        ent.pack(side="left", padx=(6, 8))
        tk.Button(
            top,
            text="Refresh",
            command=self.refresh,
            bg=theme.COLORS["panel"],
            fg=theme.COLORS["text"],
            relief="flat",
        ).pack(side="left")
        tk.Button(
            top,
            text="Clear Selected",
            command=self.clear_selected,
            bg=theme.COLORS["panel"],
            fg=theme.COLORS["text"],
            relief="flat",
        ).pack(side="left", padx=(6, 0))

        # Split: left tree of files, right text preview
        body = tk.PanedWindow(
            self,
            orient="horizontal",
            sashrelief="flat",
            bg=theme.COLORS["bg"],
        )
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        left = tk.Frame(body, bg=theme.COLORS["bg"])
        right = tk.Frame(body, bg=theme.COLORS["bg"])
        body.add(left, minsize=220)
        body.add(right)

        self.tree = ttk.Treeview(
            left, columns=("file",), show="headings", selectmode="browse"
        )
        self.tree.heading("file", text="File")
        self.tree.column("file", width=220, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._show_tail())

        # Right-side preview text area; make it read-only until text is inserted
        self.text = tk.Text(
            right,
            wrap="word",
            fg=theme.COLORS["text"],
            bg=theme.COLORS["panel"],
            font=(theme.get_font_family(), 10),
            relief="flat",
        )
        self.text.pack(fill="both", expand=True)

        self.refresh()

    def _log_dir(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        base = self._log_dir()
        try:
            files = []
            if os.path.isdir(base):
                for fn in os.listdir(base):
                    if fn.lower().endswith((".txt", ".log")):
                        files.append(fn)
            filt = (self.var_filter.get() or "").lower().strip()
            for fn in sorted(files):
                try:
                    # apply filter by content if provided
                    if filt:
                        path = os.path.join(base, fn)
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            if filt not in (f.read().lower()):
                                continue
                    self.tree.insert("", "end", values=(fn,))
                except Exception:
                    continue
        except Exception:
            pass
        # Auto-select first item
        try:
            first = self.tree.get_children()
            if first:
                self.tree.selection_set(first[0])
                self._show_tail()
        except Exception:
            pass

    def _show_tail(self):
        sel = self.tree.selection()
        if not sel:
            return
        fn = self.tree.item(sel[0]).get("values", [""])[0]
        if not fn:
            return
        base = self._log_dir()
        path = os.path.join(base, fn)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-150:]
            text = "".join(lines)
        except Exception:
            text = "(unable to read)"
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", text)
        self.text.configure(state="disabled")

    def clear_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        items = [self.tree.item(s)["values"][0] for s in sel]
        base = self._log_dir()
        for fn in items:
            try:
                with open(os.path.join(base, fn), "w", encoding="utf-8") as f:
                    f.write("")
            except Exception:
                pass
        self.refresh()
