from pathlib import Path
from types import SimpleNamespace
import hashlib
import unittest
from PIL import Image, ImageChops
from app import DesktopPet
from animation import AGES, FRAME_COUNTS, frame_names, required_assets
from care_motion import bowl_frame, snack_frame, sleep_frame
from farewell import farewell_pose
from model import PetState, OUTFITS, STAGES
from dance import ANKLES, DancePose, FORELEGS, footwork

ASSETS = Path(__file__).resolve().parents[1] / 'assets'


class AgeAnimationTests(unittest.TestCase):
    def setUp(self):
        self.app = DesktopPet.__new__(DesktopPet)
        self.app.state = PetState()
        self.app.action_started = 100
        self.app.paused = False
        self.app.keyboard = SimpleNamespace(error=None, last_activity=-100)
        self.app.action = None
        self.app.fetch_mode = False
        self.app.outdoor = False
        self.app.walk_clock = 0.

    def test_all_age_outfit_frames_exist_and_fit(self):
        for name in required_assets(OUTFITS):
            with self.subTest(name=name), Image.open(ASSETS / (name + '.png')) as image:
                self.assertEqual(image.size, (256, 256))
                alpha = image.getchannel('A').point(lambda a: 255 if a >= 128 else 0)
                left, top, right, bottom = alpha.getbbox()
                self.assertGreater(left, 0)
                self.assertGreater(top, 0)
                self.assertLess(right, 256)
                self.assertLess(bottom, 256)

    def test_low_needs_override_typing_but_not_care(self):
        for key,motion in (('food','hungry'),('water','thirsty'),('energy','tired')):
            for outfit in OUTFITS:
                for stage in range(3):
                    self.app.state=PetState();self.app.state.stage=stage;self.app.state.outfit=outfit
                    self.app.state.values[key]=10;self.app.keyboard.last_activity=100;self.app.action=None
                    name,typing=self.app.pose(100.1)
                    self.assertIn(name,frame_names(outfit,stage,motion));self.assertFalse(typing)
                    self.app.action='water'
                    self.assertIn(self.app.pose(100.1)[0],frame_names(outfit,stage,'drink'))

    def test_actions_route_to_distinct_age_art_not_scaled_adult(self):
        actions = {'feed':'eat', 'water':'drink', 'sleep':'sleep', 'walk':'walk', 'ball':'walk', 'toy':'play'}
        for outfit in OUTFITS:
            self.app.state.outfit = outfit
            for action, motion in actions.items():
                paths = []
                pixels = []
                for stage in range(3):
                    self.app.state.stage = stage
                    self.app.action = action
                    name, typing = self.app.pose(100)
                    self.assertFalse(typing)
                    self.assertIn(name, frame_names(outfit, stage, motion))
                    paths.append(name)
                    with Image.open(ASSETS / (name + '.png')) as image:
                        pixels.append(hashlib.sha256(image.tobytes()).hexdigest())
                self.assertEqual(len(set(paths)), 3, (outfit, action))
                self.assertEqual(len(set(pixels)), 3, (outfit, action))

    def test_snack_biscuit_appears_and_disappears_without_a_bowl(self):
        self.app.action = 'snack'
        for outfit in OUTFITS:
            for stage, age in enumerate(AGES):
                self.app.state.outfit, self.app.state.stage = outfit, stage
                name, typing = self.app.pose(100)
                self.assertEqual(name, f'{outfit}_{age}')
                self.assertFalse(typing)
                with Image.open(ASSETS / (name + '.png')) as source:
                    start = snack_frame(source, stage, 0)
                    bite = snack_frame(source, stage, .88)
                    done = snack_frame(source, stage, 2.8)
                self.assertTrue(ImageChops.difference(start, bite).getbbox(alpha_only=False))
                self.assertEqual(start.tobytes(), done.tobytes())
                self.assertEqual(start.crop((0, 222, 256, 256)).tobytes(),
                                 bite.crop((0, 222, 256, 256)).tobytes())

    def test_sleep_and_bowls_move_without_shifting_contact_pixels(self):
        for outfit in OUTFITS:
            for stage in range(3):
                for pose in ('eat', 'drink', 'sleep'):
                    with self.subTest(outfit=outfit, stage=stage, pose=pose), Image.open(
                        ASSETS / (frame_names(outfit, stage, pose)[0] + '.png')
                    ) as source:
                        moving = sleep_frame(source, 1.3) if pose == 'sleep' else bowl_frame(source, pose, stage, .26)
                        original = sleep_frame(source, 0) if pose == 'sleep' else bowl_frame(source, pose, stage, 0)
                        self.assertTrue(ImageChops.difference(original, moving).getbbox(alpha_only=False))
                        self.assertEqual(original.crop((0, 227, 256, 256)).tobytes(),
                                         moving.crop((0, 227, 256, 256)).tobytes())

    def test_farewell_changes_the_pose_and_keeps_the_paws_planted(self):
        for outfit in OUTFITS:
            for age in AGES:
                with self.subTest(outfit=outfit,age=age), Image.open(
                    ASSETS / f'{outfit}_{age}.png'
                ) as image:
                    standing=image.convert('RGBA')
                    alpha=standing.getchannel('A')
                    bounds=alpha.point(lambda a:255 if a>=128 else 0).getbbox()
                    _,top,_,bottom=bounds
                    ground=(0,round(top+.84*(bottom-top)),256,256)
                    moving=farewell_pose(standing,bounds,.48).getchannel('A')
                    self.assertTrue(ImageChops.difference(alpha,moving).getbbox())
                    self.assertEqual(alpha.crop(ground).tobytes(),moving.crop(ground).tobytes())

    def test_dance_lifts_a_front_paw_with_the_support_paws_planted(self):
        for outfit in OUTFITS:
            for stage,age in enumerate(AGES):
                with self.subTest(outfit=outfit,age=age), Image.open(
                    ASSETS/f'{outfit}_{age}.png'
                ) as image:
                    standing=image.convert('RGBA')
                    raised=DancePose(standing,FORELEGS[stage],ANKLES[stage]).pose(14,-8,65)
                    original_alpha=standing.getchannel('A')
                    raised_alpha=raised.getchannel('A')
                    left_sole=(0,229,79,245)
                    support=(108,234,256,256)
                    self.assertTrue(ImageChops.difference(original_alpha.crop(left_sole),
                                                           raised_alpha.crop(left_sole)).getbbox())
                    self.assertEqual(original_alpha.crop(support).tobytes(),raised_alpha.crop(support).tobytes())

    def test_dance_rolls_onto_the_other_diagonal_before_stepping(self):
        transfer=((1,3,-20,18,True),)
        for beat,planted in ((1.4,(0,3)), (2.5,(1,2))):
            with self.subTest(beat=beat):
                root,feet=footwork(beat,0,transfer)
                for i in planted:
                    self.assertAlmostEqual(root+feet[i][0],0 if beat<2 else -20)
                    self.assertAlmostEqual(feet[i][1],0)
                self.assertTrue(any(lift>8 for _,lift in feet))

    def test_typing_all_stages_then_stopping_and_action_priority(self):
        for outfit in OUTFITS:
            for stage, age in enumerate(AGES):
                self.app.state.outfit, self.app.state.stage = outfit, stage
                self.app.keyboard.last_activity = 100
                self.app.action = None
                name, typing = self.app.pose(100.1)
                self.assertTrue(typing)
                self.assertIn(name, frame_names(outfit, stage, 'type'))
                self.assertEqual(self.app.pose(101), (f'{outfit}_{age}', False))
                self.app.action = 'water'
                name, typing = self.app.pose(100.2)
                self.assertFalse(typing)
                self.assertIn(name, frame_names(outfit, stage, 'drink'))

    def test_cycles_contain_different_drawings(self):
        for outfit in OUTFITS:
            for stage in range(3):
                for motion in FRAME_COUNTS:
                    hashes = set()
                    for name in frame_names(outfit, stage, motion):
                        hashes.add(hashlib.sha256((ASSETS / (name + '.png')).read_bytes()).hexdigest())
                    self.assertGreater(len(hashes), 1, (outfit, stage, motion))

    def test_promoting_and_changing_outfit_during_action(self):
        self.app.action = 'sleep'
        self.app.state.companion_seconds = STAGES[1][0]
        self.app.state.values['bond'] = 20
        self.app.state.promote()
        self.app.state.select_stage(1)
        self.assertTrue(self.app.pose(100)[0].startswith('blue_teen_sleep'))
        self.app.state.outfit = 'yellow'
        self.assertTrue(self.app.pose(100)[0].startswith('yellow_teen_sleep'))
        self.app.state.companion_seconds = STAGES[2][0]
        self.app.state.values['bond'] = 55
        self.app.state.promote()
        self.app.state.select_stage(2)
        self.assertTrue(self.app.pose(100)[0].startswith('yellow_sleep'))


if __name__ == '__main__':
    unittest.main()
