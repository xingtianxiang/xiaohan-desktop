"""汉堡's stage dance, generated with Jimeng (即梦) and played in the pet window with its soundtrack.

work/build_dance_video.py turns the generated clip into the two assets. The "AI生成" mark the clip
carries in its corner is part of the frames and stays visible.
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw

FPS = 24
STAGE_SIZE = (480, 270)
CORNER = 12
STOP_BUTTON = (STAGE_SIZE[0] - 80, 10, STAGE_SIZE[0] - 10, 40)
# Windows keys out pure magenta (desktop_platform.TRANSPARENT); the stage's pink neon must never hit it.
KEY_SAFE_RED = [min(value, 254) for value in range(256)]


def start_sound(path):
    """Starts the soundtrack without blocking and returns a function that stops it."""
    try:
        if os.name == 'nt':
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            return lambda: winsound.PlaySound(None, 0)
        if sys.platform == 'darwin':
            return subprocess.Popen(['afplay', str(path)]).terminate
    except (RuntimeError, OSError):
        pass  # No audio device or player: she still dances, silently.
    return None


class DanceVideo:
    def __init__(self, frames, sound, *, keyed=False):
        self.frames, self.sound, self.keyed = frames, sound, keyed
        self.clip = None
        self.stop_sound = None
        self.corners = Image.new('L', STAGE_SIZE, 0)
        ImageDraw.Draw(self.corners).rounded_rectangle((0, 0, STAGE_SIZE[0] - 1, STAGE_SIZE[1] - 1), CORNER, fill=255)

    def open(self):
        if self.clip is None:
            self.clip = Image.open(self.frames)
        return self.clip

    def play(self):
        self.stop()
        self.stop_sound = start_sound(self.sound)

    def stop(self):
        if self.stop_sound is not None:
            self.stop_sound()
            self.stop_sound = None

    def frame(self, elapsed):
        clip = self.open()
        # Animated WebP decodes forward from the current frame, so playback only pays for new frames.
        clip.seek(min(clip.n_frames - 1, max(0, int(elapsed * FPS))))
        frame = clip.convert('RGB')
        if self.keyed:
            red, green, blue = frame.split()
            frame = Image.merge('RGB', (red.point(KEY_SAFE_RED), green, blue))
        frame.putalpha(self.corners)
        return frame
