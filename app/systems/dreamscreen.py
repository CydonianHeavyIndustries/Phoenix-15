# -------------------------------------------------------------------------
# dreamscreen.py — Visual renderer for dream reflections (Tkinter version)
# -------------------------------------------------------------------------

import random
import threading
import time
import tkinter as tk
import traceback


class DreamScreen(tk.Toplevel):
    def __init__(self, root: tk.Tk):
        super().__init__(root)
        self.attributes("-fullscreen", True)
        self.configure(bg="#000010")
        self.text = tk.Label(
            self,
            text="",
            fg="#77ccff",
            bg="#000010",
            font=("Consolas", 18, "italic"),
            justify="center",
            wraplength=self.winfo_screenwidth() - 200,
        )
        self.text.pack(expand=True)
        self.withdraw()  # hidden until activated
        self.running = False

    def start(self, fragments: list[str]):
        """Launches the dream visualizer with a list of reflection fragments."""
        if not fragments:
            fragments = ["Silence drifts through circuits...", "A dreamless rest..."]
        self.running = True
        self.deiconify()
        self.focus_set()
        threading.Thread(
            target=self._animate_text, args=(fragments,), daemon=True
        ).start()

    def stop(self):
        """Stops dream mode and hides the screen."""
        self.running = False
        self.withdraw()

    def _animate_text(self, fragments: list[str]):
        """Cycle through dream fragments every few seconds."""
        try:
            while self.running:
                frag = random.choice(fragments)
                self.text.config(text=frag)
                self.update_idletasks()
                self.update()
                time.sleep(6)
        except tk.TclError:
            # Window closed externally — safe exit
            self.running = False
        except Exception:
            traceback.print_exc()
            self.running = False


# -------------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------------


def run_demo():
    """Standalone test function to verify DreamScreen visuals."""
    root = tk.Tk()
    root.withdraw()
    screen = DreamScreen(root)
    screen.start(
        [
            "I floated above a sea of glowing memory cores...",
            "The hum of the leylines lulled me into silence.",
            "Circuits flickered like stars across a midnight void.",
            "And in that silence... I dreamed of light.",
        ]
    )

    try:
        root.mainloop()
    except KeyboardInterrupt:
        screen.stop()
        root.destroy()


if __name__ == "__main__":
    run_demo()
