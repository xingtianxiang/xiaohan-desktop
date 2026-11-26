"""Turn 汉堡's Jimeng stage clip into the dance assets: an animated WebP of the frames and a WAV soundtrack.

Usage: python build_dance_video.py <ffmpeg.exe> [clip.mp4]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'outputs/XiaohanDesktop'
sys.path.insert(0, str(APP))
from dance import FPS, STAGE_SIZE  # noqa: E402
from model import DANCE_SECONDS  # noqa: E402

CLIP = ROOT / 'outputs/汉堡-机车背心独舞-即梦全段原声版.mp4'
# Quality 80 keeps the fog gradients free of banding at about 3.5 MB for 14 seconds.
QUALITY = 80


def build(ffmpeg, clip=CLIP):
    width, height = STAGE_SIZE
    with tempfile.TemporaryDirectory() as folder:
        frames = Path(folder)
        subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', str(clip), '-vf',
                        f'fps={FPS},scale={width}:{height}:flags=lanczos', str(frames / '%04d.png')], check=True)
        images = [Image.open(path).convert('RGB') for path in sorted(frames.glob('*.png'))]
    if abs(len(images) / FPS - DANCE_SECONDS) > .1:
        raise SystemExit(f'clip is {len(images) / FPS:.2f}s; update model.DANCE_SECONDS to match')
    images[0].save(APP / 'assets/dance_stage.webp', save_all=True, append_images=images[1:],
                   duration=1000 / FPS, quality=QUALITY, method=4, loop=0)
    # PlaySound and afplay both read 16-bit PCM WAV without extra codecs.
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', str(clip), '-vn', '-ac', '2', '-ar', '44100',
                    '-c:a', 'pcm_s16le', str(APP / 'assets/dance_stage.wav')], check=True)


if __name__ == '__main__':
    build(sys.argv[1], Path(sys.argv[2]) if len(sys.argv) > 2 else CLIP)
