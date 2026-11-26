"""Continuous typing-only flame motion over the approved painted artwork."""
import math
from functools import lru_cache
from PIL import Image


class TypingFlame:
    def __init__(self, images):
        self.frames = [images[f'fire{i}'].convert('RGBa') for i in range(4)]
        self.level = 0.
        self.previous = None
        self.phase = 0.

    def update(self, now, typing, enabled=True, speed=0.):
        dt = min(.15, max(0, now-self.previous)) if self.previous is not None else 1/30
        self.previous = now
        if not enabled:
            self.level = 0.
        else:
            # Map roughly 1..10 keys/s across the full visual range. Temporal
            # easing below keeps both endpoints smooth without flattening them.
            intensity = min(1.,max(0.,(speed-1)/9))
            target = .10+.90*intensity if typing else 0.
            self.level += (target-self.level)*(1-math.exp(-dt/(.28 if typing else .32)))
            if self.level < .003:
                self.level = 0.
        self.phase = (self.phase+dt*(13+18*self.level))%384
        return self.level

    @lru_cache(maxsize=48)
    def blend(self, phase):
        position = phase/12
        index = int(position)
        # Premultiplied alpha avoids dark fringes during frame interpolation.
        return Image.blend(self.frames[index], self.frames[(index+1)%4], position-index).convert('RGBA')

    def image(self, now, size, fade_alpha=True):
        if not self.level:
            return None
        left = self.blend(int(self.phase)%48)
        right = self.blend(int(self.phase*.875+17)%48)
        fire = left.copy()
        middle = fire.width//2
        fire.paste(right.crop((middle,0,right.width,right.height)),(middle,0))
        strength = .14+.86*self.level
        width = max(1,round(size*(.76+.36*math.sqrt(self.level))))
        height = max(1,round(size*(1.04+.02*math.sin(now*4.1))*strength))
        fire = fire.resize((width,height),Image.Resampling.LANCZOS)
        # A color-key desktop cannot display opacity fades. Let geometry taper
        # there; alpha fading remains available when composed inside a scene.
        if fade_alpha:fire.putalpha(fire.getchannel('A').point(lambda a:round(a*self.level)))
        return fire
