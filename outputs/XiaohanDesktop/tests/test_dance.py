import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

from PIL import Image

import dance
from dance import FPS, STAGE_SIZE, DanceVideo, start_sound
from model import DANCE_SECONDS

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
COLOURS = ((255, 0, 255), (20, 40, 60), (200, 10, 90))


class DanceAssetTests(unittest.TestCase):
    def test_clip_and_soundtrack_match_the_dance_length(self):
        with Image.open(ASSETS / 'dance_stage.webp') as clip:
            self.assertEqual(clip.size, STAGE_SIZE)
            self.assertAlmostEqual(clip.n_frames / FPS, DANCE_SECONDS, delta=1 / FPS + 1e-9)
        with wave.open(str(ASSETS / 'dance_stage.wav')) as sound:
            self.assertEqual(sound.getsampwidth(), 2)
            self.assertAlmostEqual(sound.getnframes() / sound.getframerate(), DANCE_SECONDS, delta=.1)


class DanceVideoTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.clip = Path(self.folder.name) / 'clip.webp'
        frames = [Image.new('RGB', STAGE_SIZE, colour) for colour in COLOURS]
        frames[0].save(self.clip, save_all=True, append_images=frames[1:], duration=1000 / FPS, lossless=True)

    def tearDown(self):
        self.folder.cleanup()

    def video(self, keyed=False):
        video = DanceVideo(self.clip, Path(self.folder.name) / 'sound.wav', keyed=keyed)
        self.addCleanup(lambda: video.clip and video.clip.close())
        return video

    def test_frames_follow_elapsed_time_and_hold_the_last_frame(self):
        video = self.video()
        centre = STAGE_SIZE[0] // 2, STAGE_SIZE[1] // 2
        for elapsed, colour in ((-1, COLOURS[0]), (1.5 / FPS, COLOURS[1]), (100, COLOURS[2]), (0, COLOURS[0])):
            with self.subTest(elapsed=elapsed):
                self.assertEqual(video.frame(elapsed).getpixel(centre), (*colour, 255))

    def test_rounded_corners_are_transparent(self):
        frame = self.video().frame(1 / FPS)
        self.assertEqual(frame.size, STAGE_SIZE)
        self.assertEqual(frame.getpixel((0, 0))[3], 0)
        self.assertEqual(frame.getpixel((STAGE_SIZE[0] - 1, STAGE_SIZE[1] - 1))[3], 0)
        self.assertEqual(frame.getpixel((STAGE_SIZE[0] // 2, 0))[3], 255)

    def test_keyed_frames_never_contain_the_transparent_colour(self):
        self.assertEqual(self.video().frame(0).getpixel((100, 100)), (255, 0, 255, 255))
        self.assertEqual(self.video(keyed=True).frame(0).getpixel((100, 100)), (254, 0, 255, 255))

    def test_play_restarts_and_stop_silences_the_soundtrack(self):
        stops = []
        with mock.patch.object(dance, 'start_sound', side_effect=lambda path: lambda: stops.append(path)) as start:
            video = self.video()
            video.play()
            video.play()
            self.assertEqual((start.call_count, len(stops)), (2, 1))
            video.stop()
            video.stop()
            self.assertEqual(len(stops), 2)

    @unittest.skipUnless(os.name == 'nt', 'winsound is Windows only')
    def test_missing_audio_device_dances_silently(self):
        with mock.patch('winsound.PlaySound', side_effect=RuntimeError('Failed to play sound')):
            self.assertIsNone(start_sound(ASSETS / 'dance_stage.wav'))


if __name__ == '__main__':
    unittest.main()
