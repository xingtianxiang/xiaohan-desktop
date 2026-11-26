"""Render the ear-check MP4 with an original score on the desktop dance grid."""
from pathlib import Path
import subprocess
import sys
import wave

import numpy as np

APP = Path(__file__).resolve().parents[1] / 'outputs/XiaohanDesktop'
sys.path.insert(0, str(APP))
from dance import ACCENTS, SECONDS_PER_BEAT
from model import DANCE_SECONDS

RATE = 44_100
TAU = 2 * np.pi


def score():
    rng = np.random.default_rng(73)
    samples = np.zeros(RATE * DANCE_SECONDS)

    def time(length):
        return np.arange(round(RATE * length)) / RATE

    def place(beat, sound):
        start = round(beat * SECONDS_PER_BEAT * RATE)
        length = min(len(sound), len(samples) - start)
        samples[start:start+length] += sound[:length]

    kick = time(.25)
    sweep = 48 * kick + 70 * .036 * (1 - np.exp(-kick / .036))
    voice = np.sin(TAU * sweep) * np.exp(-18 * kick)
    for beat in ACCENTS:
        place(beat, .63 * voice)

    clap = time(.14)
    for beat in (1, 3, 5, 7, 9, 11, 13, 15):
        texture = np.diff(rng.uniform(-1, 1, len(clap)+1))
        tap = np.exp(-37 * clap) + .56 * np.exp(-165 * np.abs(clap-.029))
        place(beat, .14 * texture * tap + .08 * np.sin(TAU * 181 * clap) * np.exp(-46 * clap))

    hat = time(.065)
    for tick in range(1, 34):
        sound = np.diff(rng.uniform(-1, 1, len(hat)+1)) * np.exp(-76 * hat)
        place(tick/2, (.052 if tick % 2 else .03) * sound)

    # Four measures of original synth bass, with shortened gaps before the two reaches.
    bassline = (38, 38, 41, 36, 38, 45, 38, 36, 34, 34, 41, 36, 38, 41, 36, 36, 38)
    bass = time(.32)
    for beat, note in enumerate(bassline):
        frequency = 440 * 2**((note - 69) / 12)
        phase = TAU * frequency * bass
        synth = np.sin(phase) + .24 * np.sin(phase*2) + .12 * np.sin(phase*3)
        envelope = np.minimum(1., bass*160) * np.exp(-7*bass)
        place(beat, .22 * synth * envelope)

    pluck = time(.24)
    for beat, note in ((.5, 62), (2.5, 65), (3.5, 69), (6, 74), (7.5, 69),
                       (8, 65), (9.5, 67), (11, 70), (12.5, 65), (14, 74), (16, 62)):
        phase = TAU * 440 * 2**((note - 69) / 12) * pluck
        synth = np.sin(phase) + .33 * np.sin(phase * 2.003)
        place(beat, .115 * synth * np.minimum(1., pluck*180) * np.exp(-14*pluck))

    samples[-RATE//12:] *= np.linspace(1., 0., RATE//12)
    return (np.tanh(samples * 1.12) * 30_000).astype('<i2')


def main(ffmpeg, gif, wav, video):
    with wave.open(wav, 'wb') as audio:
        audio.setparams((1, 2, RATE, 0, 'NONE', 'none'))
        audio.writeframes(score().tobytes())
    subprocess.run([
        ffmpeg, '-v', 'error', '-y', '-ignore_loop', '1', '-i', gif, '-i', wav,
        '-map', '0:v', '-map', '1:a', '-t', str(DANCE_SECONDS),
        '-vf', 'scale=560:600:flags=lanczos', '-c:v', 'libx264', '-crf', '17',
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', video,
    ], check=True)


if __name__ == '__main__':
    main(*sys.argv[1:])
