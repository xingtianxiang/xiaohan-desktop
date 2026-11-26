from pathlib import Path
import unittest
from PIL import Image
from flame import TypingFlame
from keyboard_activity import KeyboardActivity

ASSETS=Path(__file__).resolve().parents[1]/'assets'


class FlameTests(unittest.TestCase):
    def setUp(self):
        self.flame=TypingFlame({f'fire{i}':Image.open(ASSETS/f'fire{i}.png').convert('RGBA') for i in range(4)})

    def test_idle_never_ignites(self):
        for index in range(60):self.flame.update(index/30,False)
        self.assertEqual(self.flame.level,0)
        self.assertIsNone(self.flame.image(2,168))

    def test_smooth_start_and_decay(self):
        levels=[self.flame.update(i/30,True) for i in range(30)]
        self.assertGreater(levels[0],0);self.assertLess(levels[0],.3)
        self.assertTrue(all(a<b for a,b in zip(levels,levels[1:])))
        start=self.flame.level
        self.flame.update(1,False)
        self.assertGreater(self.flame.level,0);self.assertLess(self.flame.level,start)
        for index in range(31,80):self.flame.update(index/30,False)
        self.assertEqual(self.flame.level,0)

    def test_switch_off_cancels_existing_fire(self):
        self.flame.update(0,True);self.flame.update(.1,True)
        self.flame.update(.2,True,False)
        self.assertIsNone(self.flame.image(.2,240))

    def test_intermediate_frames_are_not_keyframe_jumps(self):
        first=self.flame.blend(0)
        middle=self.flame.blend(6)
        last=self.flame.blend(12)
        self.assertNotEqual(first.tobytes(),middle.tobytes())
        self.assertNotEqual(last.tobytes(),middle.tobytes())
        self.assertEqual(middle.mode,'RGBA')

    def test_all_sizes_stay_inside_desktop(self):
        for i in range(30):self.flame.update(i/30,True)
        for size in (122,153,168,174,211,240):
            image=self.flame.image(1,size)
            self.assertLessEqual(image.width,280);self.assertLessEqual(image.height,275)
            self.assertIsNotNone(image.getbbox())

    def test_desktop_cooldown_survives_color_key_threshold(self):
        self.flame.level=.3
        image=self.flame.image(1,240,fade_alpha=False)
        visible=image.getchannel('A').point(lambda a:255 if a>=128 else 0)
        self.assertIsNotNone(visible.getbbox())
        self.assertLess(image.height,240)

    def test_slow_normal_fast_typing_produce_distinct_sizes(self):
        heights=[]
        for speed in (1.5,5.,12.):
            for index in range(100):self.flame.update(index/30+speed*100,True,speed=speed)
            heights.append(self.flame.image(1,240,fade_alpha=False).height)
        self.assertLess(heights[0]+25,heights[1])
        self.assertLess(heights[1]+20,heights[2])
        self.assertGreater(heights[2],heights[0]*2.5)

    def test_speed_change_is_smoothed_and_extreme_speed_is_bounded(self):
        for index in range(60):self.flame.update(index/30,True,speed=2.)
        before=self.flame.level
        self.flame.update(2,True,speed=1000)
        self.assertLess(self.flame.level-before,.1)
        for index in range(61,120):self.flame.update(index/30,True,speed=1000)
        self.assertLessEqual(self.flame.level,1.)
        self.assertLessEqual(self.flame.image(4,240).width,280)
        high=self.flame.level
        for index in range(120,180):self.flame.update(index/30,True,speed=1.)
        self.assertLess(self.flame.level,high-.4)

    def test_real_activity_estimator_tracks_rate_and_decays(self):
        slow=KeyboardActivity();fast=KeyboardActivity()
        for index in range(6):slow.record_activity(index*.5)
        for index in range(26):fast.record_activity(index*.1)
        self.assertGreater(fast.speed(2.5),slow.speed(2.5)*3)
        self.assertLess(fast.speed(8),.05)
        self.assertEqual(fast.count,26)
        self.assertIsInstance(fast._speed_sample,tuple)


if __name__=='__main__':unittest.main()
