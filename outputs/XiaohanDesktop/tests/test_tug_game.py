import unittest
from pathlib import Path

from PIL import Image

from animation import frame_names
from model import OUTFITS
from tug_game import BEAT_CENTER, GREEN_END, TugRound
from tug_view import tug_pose, toy_tip

ASSETS = Path(__file__).resolve().parents[1] / 'assets'


class TugRoundTests(unittest.TestCase):
    def test_waiting_pausing_and_resuming_leave_the_score_in_place(self):
        game = TugRound(7)
        self.assertFalse(game.advance(20))
        self.assertEqual(game.elapsed, 0)
        self.assertTrue(game.strike(21))
        game.advance(21.08)
        elapsed, advantage = game.elapsed, game.advantage
        game.pause()
        self.assertFalse(game.advance(30))
        self.assertEqual((game.elapsed, advantage), (elapsed, game.advantage))
        self.assertTrue(game.strike(40))
        game.advance(40.05)
        self.assertAlmostEqual(game.elapsed, elapsed+.05)
        self.assertEqual(game.hits, 0)

    def test_mashing_does_not_undo_a_missed_beat(self):
        game = TugRound(7)
        game.strike(0)
        game.advance(.08)
        game.strike(.08)
        self.assertEqual(game.feedback, 'early')
        for frame in range(2,10):
            game.advance(frame*.08)
        self.assertEqual(game.beat, 0)
        self.assertFalse(game.strike(.72))
        self.assertEqual(game.hits, 0)

    def test_timed_hits_determine_outcome_and_settle_once(self):
        for allowed, expected in ((set(), 'idle'), ({0}, 'dog'), (set(range(7)), 'player')):
            with self.subTest(outcome=expected):
                game = TugRound(7)
                game.strike(0)
                settlements = 0
                for frame in range(1,330):
                    now = frame/30
                    settlements += game.advance(now)
                    if game.beat in allowed and game.phase>=BEAT_CENTER:
                        game.strike(now)
                self.assertEqual((game.result, settlements), (expected, 1))
                self.assertFalse(game.running)
                self.assertFalse(game.strike(20))

    def test_consecutive_beats_get_a_bonus_and_a_missed_beat_breaks_the_combo(self):
        game = TugRound(7)
        game.strike(0)
        gains = []
        for frame in range(1,340):
            now = frame/50
            game.advance(now)
            if game.beat < 3 and BEAT_CENTER<=game.phase<GREEN_END and game.beat!=game.last_beat:
                before = game.advantage
                game.strike(now)
                gains.append(game.advantage-before)
                self.assertEqual(game.combo,len(gains))
            if game.beat==3 and game.phase>GREEN_END:
                break
        self.assertEqual(len(gains),3)
        self.assertGreater(gains[2],gains[0]+.03)
        self.assertEqual((game.combo,game.best_combo),(0,3))

    def test_early_and_late_taps_break_an_existing_combo(self):
        for phase,feedback in ((.28,'early'),(.92,'late')):
            with self.subTest(phase=phase):
                game=TugRound(7)
                game.strike(0)
                for frame in range(1,140):
                    now=frame/50
                    game.advance(now)
                    if game.beat==0 and game.phase>=BEAT_CENTER and game.last_beat<0:
                        game.strike(now)
                    if game.beat==1 and game.phase>=phase:
                        game.strike(now)
                        break
                self.assertEqual((game.feedback,game.combo,game.best_combo,game.hits),(feedback,0,1,1))

    def test_bracing_and_reaching_keep_contact_pads_and_move_the_toy(self):
        for outfit in OUTFITS:
            for stage in range(3):
                with self.subTest(outfit=outfit,stage=stage), Image.open(
                    ASSETS/(frame_names(outfit,stage,'play')[0]+'.png')
                ) as image:
                    rest=image.convert('RGBA')
                    braced=tug_pose(rest,.95)
                    reached=tug_pose(rest,-1)
                    for pose in (braced,reached):
                        for ground in ((0,208,55,247),(85,232,160,247)):
                            self.assertEqual(rest.getchannel('A').crop(ground).tobytes(),
                                             pose.getchannel('A').crop(ground).tobytes())
                    x,y=toy_tip(rest)
                    bx,by=toy_tip(braced)
                    fx,_=toy_tip(reached)
                    self.assertLess(bx,x-10)
                    self.assertLess(by,y-8)
                    self.assertGreater(fx,x+4)
