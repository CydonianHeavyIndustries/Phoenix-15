import tkinter as tk

from ui import theme


class TaskDashboard(tk.Frame):
    """Lightweight dashboard for displaying a list of active tasks.

    Uses the shared theme palette for colors and fonts so it blends in with
    the rest of the UI. Tasks are shown in a simple listbox that stretches
    with the window.
    """

    def __init__(self, master):
        # Use panel color rather than hard-coded hex values so the dashboard
        # harmonizes with the rest of the HUD. The parent frame's background
        # is also explicitly set so it inherits the correct color on dark skins.
        super().__init__(master, bg=theme.COLORS["panel"])
        self.pack(side="right", fill="y")

        # Title uses the accent glow for a subtle highlight and the theme's
        # configured font family instead of a hard-coded font name. This
        # automatically adapts to custom skins loaded via ui/theme.py.
        self.title = tk.Label(
            self,
            text="🗒️ Tasks",
            bg=theme.COLORS["panel"],
            fg=theme.COLORS["accent_glow"],
            font=(theme.get_font_family(), 12, "bold"),
        )
        self.title.pack(anchor="n", pady=5)

        # The listbox uses the base background for readability and the
        # theme's text color. A fixed-width font is avoided to let skins
        # pick an appropriate typeface.
        self.listbox = tk.Listbox(
            self,
            bg=theme.COLORS["bg"],
            fg=theme.COLORS["text"],
            font=(theme.get_font_family(), 11),
            highlightthickness=0,
            selectbackground=theme.COLORS["accent"],
            selectforeground=theme.COLORS["bg"],
        )
        self.listbox.pack(fill="both", expand=True, padx=5, pady=5)

    def update_tasks(self, tasks):
        """Replace the current items in the listbox with the given tasks."""
        self.listbox.delete(0, "end")
        for t in tasks:
            # Prefix tasks with a bullet to visually separate them. This
            # character uses the current font so it scales with UI zoom.
            self.listbox.insert("end", f"• {t}")
