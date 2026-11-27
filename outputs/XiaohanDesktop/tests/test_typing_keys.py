import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageFilter

from animation import AGES, frame_names
from keyboard_activity import KEY_MEMORY, KeyboardActivity
from model import OUTFITS, PetState
from typing_keys import KEYCAP_SECONDS, ROWS, key_point, key_slot, keycap_motion, vk_label

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
BOARDS = json.loads((ASSETS / 'typing-keyboards.json').read_text(encoding='utf-8'))


class LabelTests(unittest.TestCase):
    def test_virtual_keys_become_keycap_text(self):
        cases = {0x4C: 'L', 0x41: 'A', 0x31: '1', 0x60: '0', 0x20: '空格', 0x0D: '回车', 0x08: '退格',
                 0x70: 'F1', 0x7B: 'F12', 0xBC: ',', 0xA0: 'Shift', 0x25: '←'}
        for vk, label in cases.items():
            self.assertEqual(vk_label(vk), label, hex(vk))
        self.assertIsNone(vk_label(0xFF))
        self.assertIsNone(vk_label(0xE5))

    def test_every_keycap_has_a_key_to_rise_from(self):
        self.assertEqual(key_slot('Q'), (0, 0))
        self.assertEqual(key_slot('L'), (1, 8))
        self.assertEqual(key_slot('M'), (2, 6))
        self.assertEqual(key_slot('5'), (0, 4))
        self.assertEqual(key_slot('回车'), (1, 9))
        for label in ('空格', 'Ctrl', 'Alt', 'Win'):
            self.assertEqual(key_slot(label), (3, 0))
        for vk in [*range(0x30, 0x3A), *range(0x41, 0x5B), *range(0x70, 0x7C), 0x20, 0x0D, 0x08, 0x09, 0x1B, 0xBA, 0xDE]:
            row, col = key_slot(vk_label(vk))
            self.assertTrue(0 <= row <= 3 and 0 <= col <= 9, vk_label(vk))


class KeyboardTests(unittest.TestCase):
    def test_every_outfit_and_age_has_a_measured_keyboard(self):
        self.assertEqual(set(BOARDS), {f'{o}_{a}' for o in OUTFITS for a in AGES})
        for name, board in BOARDS.items():
            self.assertTrue(8 < board['depth'] < 60, (name, board))
            self.assertTrue(0 <= board['left'] < board['right'] <= 256, (name, board))

    def test_keycaps_start_on_the_painted_keyboard_in_every_frame(self):
        # A keycap pops out several pixels wide, so a key within 3px of the keyboard's outline still reads as on it.
        for outfit in OUTFITS:
            for stage, age in enumerate(AGES):
                board = BOARDS[f'{outfit}_{age}']
                points = [key_point(board, row, col) for row in range(3) for col in range(10)] + [key_point(board, 3, 0)]
                for name in frame_names(outfit, stage, 'type'):
                    with self.subTest(name=name), Image.open(ASSETS / f'{name}.png') as source:
                        alpha = source.convert('RGBA').getchannel('A').filter(ImageFilter.MaxFilter(7))
                        missing = [p for p in points if alpha.getpixel((round(p[0]), round(p[1]))) < 200]
                        self.assertEqual(missing, [])

    def test_rows_run_from_back_to_front_and_columns_left_to_right(self):
        board = BOARDS['blue_puppy']
        ys = [key_point(board, row, 4)[1] for row in range(4)]
        self.assertEqual(ys, sorted(ys))
        self.assertLess(key_point(board, 0, 0)[0], key_point(board, 0, 9)[0])
        self.assertEqual(len(ROWS), 3)

    def test_keycaps_pop_out_drift_up_and_shrink_away(self):
        start = (150., 220.)
        positions = [keycap_motion(age, start, 120.) for age in (0., .1, .3, .6, KEYCAP_SECONDS - .01)]
        self.assertLess(positions[0][2], .4)
        self.assertAlmostEqual(positions[2][2], 1., places=1)
        self.assertLess(positions[-1][2], .1)
        ys = [y for _, y, _ in positions]
        self.assertEqual(ys, sorted(ys, reverse=True))
        self.assertGreater(positions[-1][0], start[0])
        self.assertLess(keycap_motion(.5, (90., 220.), 120.)[0], 90.)


class KeyCaptureTests(unittest.TestCase):
    def test_fresh_presses_are_kept_only_while_capturing_and_repeats_are_dropped(self):
        keys = KeyboardActivity()
        keys.key_event(0x4C, True, 1.)
        self.assertEqual((list(keys.keys), keys.count), ([], 1))
        keys.capture_keys = True
        keys.key_event(0x4C, False, 1.1)
        keys.key_event(0x4C, True, 1.2)
        for step in range(1, 6):
            keys.key_event(0x4C, True, 1.2 + .03 * step)
        self.assertEqual(list(keys.keys), [(1.2, 0x4C)])
        self.assertEqual(keys.count, 7)
        keys.key_event(0x4C, False, 1.5)
        keys.key_event(0x4C, True, 1.6)
        self.assertEqual(len(keys.keys), 2)
        for index in range(20):
            keys.key_event(0x41 + index, True, 2 + index)
        self.assertEqual(len(keys.keys), KEY_MEMORY)

    def test_the_setting_defaults_on_and_is_validated(self):
        self.assertTrue(PetState().key_bubbles)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pet.json'
            state = PetState()
            state.key_bubbles = False
            state.save(path)
            self.assertFalse(PetState.load(path).key_bubbles)
            data = json.loads(path.read_text(encoding='utf-8'))
            del data['key_bubbles']
            path.write_text(json.dumps(data), encoding='utf-8')
            self.assertTrue(PetState.load(path).key_bubbles)
            data['key_bubbles'] = 'yes'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(ValueError):
                PetState.load(path)


if __name__ == '__main__':
    unittest.main()
