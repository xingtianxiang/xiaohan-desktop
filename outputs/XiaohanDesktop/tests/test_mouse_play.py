import math
from pathlib import Path
import unittest

from PIL import Image, ImageChops

from mouse_play import (ALERT_EARS, ATTENTION_RADIUS, CIRCLE_MAX_PX, CIRCLE_WINDOW, FACE_SETTLE, HAND_EARS, HEAD_RUB_PX, HEADS, PET_EASE_IN,
                        PET_RELEASE, RUB_WINDOW, STROKE_MIN_PX, STROKE_WINDOW, TURN_GAP, TURN_SECONDS, Facing,
                        CircleGesture, HeadRig, PetDetector, Petting, body_centre, body_middle, head_point,
                        heart_positions, hop, pose_frame)

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
CANVAS = (0., 0., 1.)  # Painting drawn at its own size from the screen origin.
ADULT = 2


def feed(detector, points, zone, start=0., step=.1):
    return [detector.feed(x, y, start + index * step, zone) for index, (x, y) in enumerate(points)]


def settle(facing, pointer, start, seconds, **options):
    now = start
    while now <= start + seconds:
        facing.update(now, pointer, ADULT, CANVAS, **options)
        now += .05
    return now


class PetDetectorTests(unittest.TestCase):
    def test_back_and_forth_on_body_triggers_once(self):
        detector = PetDetector()
        xs = [100, 120, 140, 120, 100, 120, 140, 120, 100]
        fired = feed(detector, [(x, 150) for x in xs], 'body')
        self.assertEqual(fired.count(True), 1)
        self.assertFalse(any(feed(detector, [(100, 150), (120, 150)], 'body', start=1)))

    def test_vertical_body_strokes_also_count(self):
        fired = feed(PetDetector(), [(100, y) for y in (150, 180, 150, 180, 150)], 'body')
        self.assertTrue(fired[-1])

    def test_moving_over_her_head_reads_as_petting(self):
        steps = int(HEAD_RUB_PX / 15) + 2
        fired = feed(PetDetector(), [(60 + 15 * i, 80) for i in range(steps)], 'head', step=RUB_WINDOW / steps / 2)
        self.assertTrue(any(fired))
        self.assertGreaterEqual(fired.index(True) * 15, HEAD_RUB_PX)

    def test_resting_hand_jitter_and_slow_moves_do_not_trigger(self):
        jitter = [(80 + (i % 2) * 2, 80) for i in range(int(RUB_WINDOW * 10) * 2)]
        self.assertFalse(any(feed(PetDetector(), jitter, 'head')))
        slow = [(60 + 15 * i, 80) for i in range(12)]
        self.assertFalse(any(feed(PetDetector(), slow, 'head', step=RUB_WINDOW / 3)))
        small = STROKE_MIN_PX // 2
        self.assertFalse(any(feed(PetDetector(), [(100 + small * (i % 2), 150) for i in range(12)], 'body')))
        self.assertFalse(any(feed(PetDetector(), [(100 + 40 * (i % 2), 150) for i in range(6)], 'body',
                                  step=STROKE_WINDOW / 1.5)))

    def test_leaving_her_fur_resets_progress(self):
        detector = PetDetector()
        feed(detector, [(100, 150), (140, 150), (100, 150), (140, 150)], 'body')
        detector.feed(140, 150, .5, None)
        self.assertFalse(any(feed(detector, [(100, 150), (140, 150)], 'body', start=.6)))


class CircleGestureTests(unittest.TestCase):
    MIDDLE = (500, 400)

    def circle(self, gesture, turns, radius=150, seconds=1.5, start=0., direction=1, on_fur=lambda angle: False):
        samples = max(12, int(seconds / .09))
        fired = []
        for index in range(samples + 1):
            angle = direction * math.tau * turns * index / samples
            point = (self.MIDDLE[0] + radius * math.cos(angle), self.MIDDLE[1] + radius * math.sin(angle))
            fired.append(gesture.feed(point, self.MIDDLE, start + seconds * index / samples, on_fur(angle)))
        return fired

    def test_one_full_circle_either_way_starts_a_dance_once(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                fired = self.circle(CircleGesture(), 1.3, direction=direction)
                self.assertEqual(fired.count(True), 1)
                self.assertGreater(fired.index(True), len(fired) * .7)

    def test_partial_slow_far_and_back_and_forth_motion_does_not(self):
        self.assertFalse(any(self.circle(CircleGesture(), .9)))
        self.assertFalse(any(self.circle(CircleGesture(), 1.1, seconds=CIRCLE_WINDOW * 1.4)))
        self.assertFalse(any(self.circle(CircleGesture(), 1.5, radius=CIRCLE_MAX_PX + 20)))
        gesture = CircleGesture()
        for index in range(6):
            self.assertFalse(any(self.circle(gesture, .45, seconds=.5, start=index * .5, direction=1 - 2 * (index % 2))))

    def test_stretches_on_her_fur_do_not_count(self):
        clipped = lambda angle: (angle % math.tau) < math.tau * .3
        fired = self.circle(CircleGesture(), 1.1, on_fur=clipped)
        self.assertFalse(any(fired))
        self.assertTrue(any(self.circle(CircleGesture(), 1.8, seconds=2.4, on_fur=clipped)))

    def test_body_middle_sits_inside_her_body(self):
        canvas = (100, 50, 1.)
        for stage in range(3):
            x, y = body_middle(stage, canvas, True)
            x0, y0, x1, y1 = HEADS[stage]['body']
            self.assertTrue(100 + x0 < x < 100 + x1 and 50 + y0 < y < 50 + y1)


class PettingTests(unittest.TestCase):
    def test_eases_in_holds_and_eases_out(self):
        petting = Petting()
        self.assertEqual(petting.amount(0), 0)
        petting.hold(10, 12)
        self.assertLess(petting.amount(10 + PET_EASE_IN / 3), 1)
        self.assertEqual(petting.amount(11), 1)
        self.assertGreater(petting.amount(12 + PET_RELEASE / 3), 0)
        self.assertFalse(petting.active(12 + PET_RELEASE))
        self.assertEqual(petting.tail(13), 0)

    def test_more_rubbing_extends_without_restarting(self):
        petting = Petting()
        petting.hold(10, 11)
        petting.hold(10.8, 12)
        self.assertEqual(petting.started, 10)
        self.assertEqual(petting.amount(11.5), 1)
        petting.stop()
        self.assertFalse(petting.active(11.5))


class FacingTests(unittest.TestCase):
    def setUp(self):
        self.facing = Facing()
        self.head = head_point(ADULT, CANVAS, True)
        self.centre, self.half = body_centre(ADULT, CANVAS, True)

    def test_turns_for_a_nearby_cursor_only_after_it_settles(self):
        right = (self.centre + self.half + 60, self.head[1])
        now = settle(self.facing, right, 0, FACE_SETTLE * .8)
        self.assertTrue(self.facing.left)
        settle(self.facing, right, now, FACE_SETTLE)
        self.assertFalse(self.facing.left)

    def test_far_cursor_and_cursor_over_her_body_do_not_turn_her(self):
        settle(self.facing, (self.head[0] + ATTENTION_RADIUS + 50, self.head[1]), 0, 2)
        self.assertTrue(self.facing.left)
        settle(self.facing, (self.centre + self.half - 5, self.head[1]), 3, 2)
        self.assertTrue(self.facing.left)

    def test_waits_between_turns_and_ignores_turns_while_petted(self):
        right = (self.centre + self.half + 60, self.head[1])
        left = (self.centre - self.half - 60, self.head[1])
        now = settle(self.facing, right, 0, FACE_SETTLE + .1)
        turned = self.facing.turn_started
        now = settle(self.facing, left, now, FACE_SETTLE + .05)
        self.assertFalse(self.facing.left)
        settle(self.facing, left, now, TURN_GAP)
        self.assertTrue(self.facing.left)
        self.assertGreaterEqual(self.facing.turn_started - turned, TURN_GAP)
        petted = Facing()
        settle(petted, right, 0, 2, petting=1.)
        self.assertTrue(petted.left)

    def test_turn_is_a_hop_that_swaps_sides_at_the_top(self):
        settle(self.facing, (self.centre + self.half + 60, self.head[1]), 0, FACE_SETTLE + .1)
        start = self.facing.turn_started
        early, top, late = (self.facing.view(start + TURN_SECONDS * f) for f in (.1, .5, .9))
        self.assertFalse(early[0])
        self.assertTrue(top[0] and late[0])
        self.assertGreater(top[1], 5)
        self.assertLess(early[3], 1)
        self.assertEqual(self.facing.view(start + TURN_SECONDS + 1e-6), (True, 0., 1., 1.))
        self.assertEqual(hop(0), (0., 1., 1.))

    def test_head_follows_a_hand_resting_on_it_and_ears_relax(self):
        hx, hy = self.head
        settle(self.facing, (hx - 20, hy), 0, 1)
        self.assertLess(self.facing.head[0], -4)
        self.assertAlmostEqual(self.facing.ears, HAND_EARS, places=2)
        settle(self.facing, (hx + 15, hy + 15), 1.1, 1)
        self.assertGreater(self.facing.head[0], 0)
        self.assertGreater(self.facing.head[1], 0)
        self.assertFalse(self.facing.animating(2.15))

    def test_looks_up_at_a_cursor_above_with_pricked_ears(self):
        hx, hy = self.head
        settle(self.facing, (hx, hy - 150), 0, 1)
        self.assertLess(self.facing.head[1], -6)
        self.assertLess(self.facing.ears, ALERT_EARS / 2)
        settle(self.facing, (hx, hy - 1000), 1.1, 1.5)
        self.assertAlmostEqual(self.facing.head[1], 0, places=1)

    def test_petting_flattens_ears_and_pushes_up_even_without_follow(self):
        hx, hy = self.head
        settle(self.facing, (hx + 900, hy + 400), 0, 1, petting=1., follow=False)
        self.assertGreater(self.facing.ears, .95)
        self.assertLess(self.facing.head[1], -2)
        self.assertTrue(self.facing.left)

    def test_follow_off_faces_left_and_keeps_head_still(self):
        settle(self.facing, (self.centre + self.half + 60, self.head[1]), 0, 1)
        self.assertFalse(self.facing.left)
        self.facing.update(2, self.head, ADULT, CANVAS, follow=False)
        settle(self.facing, (self.head[0] - 20, self.head[1]), 2, 1, follow=False)
        self.assertTrue(self.facing.left)
        self.assertEqual(self.facing.view(3)[0], False)
        self.assertAlmostEqual(self.facing.head[0], 0, places=2)


class RigTests(unittest.TestCase):
    def setUp(self):
        self.images = [Image.open(ASSETS / f'blue_{age}.png').convert('RGBA') for age in ('puppy', 'teen', 'adult')]

    def poses(self):
        return (dict(head=(-6, -6)), dict(head=(3, 5)), dict(ears=1), dict(ears=-.3), dict(tail=9),
                dict(head=(-1, -4), ears=1, tail=-9))

    def test_paws_stay_planted_in_every_pose(self):
        for stage, image in enumerate(self.images):
            rig = HeadRig(image, stage)
            paws = (0, 210, 256, 256)
            for pose in self.poses():
                with self.subTest(stage=stage, pose=pose):
                    frame = rig.frame(**pose)
                    self.assertEqual(frame.size, image.size)
                    self.assertIsNone(ImageChops.difference(frame.crop(paws), image.crop(paws)).getbbox())

    def test_neutral_is_the_painting(self):
        rig = HeadRig(self.images[ADULT], ADULT)
        self.assertIs(rig.frame(), self.images[ADULT])

    def top_near(self, frame, x, width=6):
        return frame.getchannel('A').point(lambda a: 255 if a >= 128 else 0).crop((x - width, 0, x + width, 256)).getbbox()[1]

    def test_head_lifts_and_ears_fold_back_and_down(self):
        for stage, image in enumerate(self.images):
            rig = HeadRig(image, stage)
            geometry = HEADS[stage]
            with self.subTest(stage=stage):
                cx = geometry['centre'][0]
                self.assertLess(self.top_near(rig.frame(head=(0, -6)), cx), self.top_near(image, cx))
                for tx, _ in geometry['ears']:
                    self.assertGreater(self.top_near(rig.frame(ears=1), tx), self.top_near(image, tx))

    def test_tail_wags_and_mirror_matches(self):
        image = self.images[ADULT]
        rig = HeadRig(image, ADULT)
        moved = ImageChops.difference(rig.frame(tail=9), image).getbbox()
        self.assertIsNotNone(moved)
        self.assertGreater(moved[0], HEADS[ADULT]['centre'][0])
        mirrored = pose_frame(rig, flip=True, ears=1)
        self.assertIsNone(ImageChops.difference(mirrored, rig.frame(ears=1).transpose(Image.Transpose.FLIP_LEFT_RIGHT)).getbbox())


class HeartTests(unittest.TestCase):
    def test_hearts_rise_and_stop(self):
        first = heart_positions(.2, 100, 50)
        later = heart_positions(.9, 100, 50)
        self.assertLess(later[0][1], first[0][1])
        self.assertEqual(heart_positions(10, 100, 50), [])
        self.assertEqual(len(heart_positions(.6, 100, 50, 1)), 1)
