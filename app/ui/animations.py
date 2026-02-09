import colorsys
import random
import time
from threading import Thread


class BackgroundAnimator:
    def __init__(self, canvas):
        self.canvas = canvas
        self.running = False
        self.hue = random.random()
        self.speed = 0.002

    def start(self):
        if not self.running:
            self.running = True
            Thread(target=self._animate, daemon=True).start()

    def stop(self):
        self.running = False

    def _animate(self):
        while self.running:
            self.hue = (self.hue + self.speed) % 1.0
            r, g, b = [int(x * 255) for x in colorsys.hsv_to_rgb(self.hue, 0.7, 0.4)]
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.canvas.configure(bg=color)
            time.sleep(0.03)

    def adjust_speed(self, mood_level):
        self.speed = 0.001 + (mood_level * 0.003)
