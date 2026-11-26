import json
from pathlib import Path
import tempfile
import unittest
from fetch_game import fetch_frame, ThrowCharge, throw_point, walk_position
from animation import FETCH_POSES, fetch_asset
from model import PetState
from work_break import WorkBreak, WORK_SECONDS, BREAK_SECONDS


class FetchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata=json.loads((Path(__file__).resolve().parents[1]/'assets/fetch-anchors.json').read_text(encoding='utf-8'))

    def anchors(self,stage=2,outfit='blue'):
        return {pose:self.metadata[fetch_asset(outfit,stage,pose)] for pose in FETCH_POSES}

    def test_distance_changes_ground_and_scale(self):
        near=fetch_frame(.53,.1,174,self.anchors());far=fetch_frame(.53,1.,174,self.anchors())
        self.assertLess(far.scale,near.scale)
        self.assertLess(far.ground,near.ground)
        self.assertLess(far.radius,near.radius)
        self.assertLess(far.scale,.4)

    def test_returns_to_foreground_for_every_age_and_distance(self):
        for power in (0,.13,.39,.71,1.):
            for stage,size in enumerate((122,153,174)):
                start=fetch_frame(0,power,size,self.anchors(stage));end=fetch_frame(1,power,size,self.anchors(stage))
                self.assertEqual(start.x,end.x)
                self.assertEqual(start.ground,end.ground)
                self.assertEqual(end.scale,1)
                self.assertEqual(end.pose,'settle')
                self.assertFalse(end.carrying)
                for i in range(101):
                    frame=fetch_frame(i/100,power,size,self.anchors(stage))
                    self.assertTrue(0<frame.ball_x<420 and 0<frame.ball_y<290)

    def test_throw_lifts_ball_then_lands(self):
        air=fetch_frame(.19,.55,174,self.anchors());land=fetch_frame(.43,.55,174,self.anchors())
        self.assertGreater(air.ball_ground-air.ball_y,50)
        self.assertAlmostEqual(land.ball_ground-land.ball_y,land.radius)

    def test_power_is_continuous_and_preview_matches_landing(self):
        landings=[fetch_frame(.43,i/100,174,self.anchors()) for i in range(101)]
        self.assertEqual(len({frame.ball_x for frame in landings}),101)
        self.assertTrue(all(a.ball_x<b.ball_x and a.ground>b.ground for a,b in zip(landings,landings[1:])))
        for power in (0,.21,.67,1):
            expected=throw_point(1,power);actual=fetch_frame(.43,power,174,self.anchors())
            self.assertAlmostEqual(expected[0],actual.ball_x)
            self.assertAlmostEqual(expected[2],actual.ball_ground)

    def test_fetch_starts_and_returns_at_current_walk_location(self):
        for clock in (0,3,7,11):
            origin=walk_position(clock)
            for power in (0,.5,1):
                start=fetch_frame(0,power,174,self.anchors(),origin)
                end=fetch_frame(1,power,174,self.anchors(),origin)
                self.assertEqual((start.x,start.ground),(origin[0],origin[1]))
                self.assertEqual((end.x,end.ground),(origin[0],origin[1]))
                self.assertEqual(end.origin_flip,origin[2])

    def test_ball_stays_continuous_during_pickup_turn_and_release(self):
        for outfit in ('blue','red','yellow'):
            for stage,size in enumerate((122,153,174)):
                for boundary in (.44,.46,.50,.53,.55,.57,.59,.61,.63,.90,.94,.97):
                    before=fetch_frame(boundary-1e-5,.7,size,self.anchors(stage,outfit))
                    after=fetch_frame(boundary+1e-5,.7,size,self.anchors(stage,outfit))
                    self.assertLess(abs(before.ball_x-after.ball_x)+abs(before.ball_y-after.ball_y),1,(outfit,stage,boundary))
                    self.assertLess(abs(before.x-after.x)+abs(before.ground-after.ground),1,(outfit,stage,boundary))

    def test_turn_passes_through_front_before_direction_reverses(self):
        for origin in (walk_position(0),walk_position(7)):
            frames=[fetch_frame(p,0,174,self.anchors(),origin) for p in (.49,.54,.58,.62)]
            self.assertEqual([f.pose for f in frames],['pickup','turnquarter','turnfront','turnquarter'])
            self.assertEqual(frames[0].flip,frames[1].flip)
            self.assertNotEqual(frames[1].flip,frames[-1].flip)

    def test_ball_waits_for_muzzle_then_lifts_with_head(self):
        from animation import HEAD_FRAMES
        for stage,size in enumerate((122,153,174)):
            for outfit in ('blue','red','yellow'):
                for power in (0.,.6,1.):
                    for clock in (0,8):
                        def sample(p):
                            return fetch_frame(p,power,size,self.anchors(stage,outfit),walk_position(clock))
                        reach,contact,grip,raised=map(sample,(.43,.44,.455,.549))
                        self.assertFalse(reach.carrying)
                        self.assertLess(reach.gait_frame,HEAD_FRAMES)
                        self.assertEqual(contact.gait_frame,HEAD_FRAMES)
                        self.assertTrue(contact.carrying)
                        self.assertAlmostEqual(reach.ball_x,grip.ball_x)
                        self.assertAlmostEqual(reach.ball_y,grip.ball_y)
                        self.assertLess(raised.ball_y,grip.ball_y)

    def test_return_stride_brakes_and_uses_four_drawings(self):
        frames=[fetch_frame(.63+i*.27/200,.8,174,self.anchors()) for i in range(200)]
        self.assertEqual({f.pose for f in frames},{'run0','run1','run2','run3'})
        self.assertTrue(all(a.stride_phase<=b.stride_phase for a,b in zip(frames,frames[1:])))
        motion=[b.stride_phase-a.stride_phase for a,b in zip(frames,frames[1:])]
        self.assertLess(motion[0],max(motion)/5)
        self.assertLess(motion[-1],max(motion)/5)

    def test_charge_cancel_and_single_release(self):
        charge=ThrowCharge()
        self.assertIsNone(charge.release(0))
        self.assertTrue(charge.begin(10))
        self.assertFalse(charge.begin(10.5))
        self.assertAlmostEqual(charge.power(11),.5)
        self.assertAlmostEqual(charge.release(11.2),.6)
        self.assertIsNone(charge.release(11.3))
        charge.begin(12);charge.cancel()
        self.assertIsNone(charge.release(14))

    def test_carried_ball_follows_one_point_between_running_drawings(self):
        for outfit in ('blue','red','yellow'):
            for stage,size in enumerate((122,153,174)):
                anchors = self.anchors(stage,outfit)
                for origin in (walk_position(0),walk_position(7)):
                    for i in range(640,900):
                        frame = fetch_frame(i/1000,.35,size,anchors,origin)
                        if not frame.previous_pose.startswith('run'):
                            continue
                        for pose,offset in ((frame.pose,frame.current_offset),(frame.previous_pose,frame.previous_offset)):
                            dx,dy = anchors[pose]['ball']
                            sign = -1 if frame.flip else 1
                            self.assertAlmostEqual(frame.x+dx*size*frame.scale*sign+offset[0],frame.ball_x)
                            self.assertAlmostEqual(frame.ground-dy*size*frame.scale+offset[1],frame.ball_y)

    def test_long_hold_caps_without_auto_throw(self):
        charge=ThrowCharge();charge.begin(0)
        self.assertEqual(charge.power(100),1.)
        self.assertIsNotNone(charge.started)
        self.assertEqual(charge.release(100),1.)


class BreakTests(unittest.TestCase):
    def work_for(self,timer,seconds,start=0):
        timer.update(start,0)
        for i in range(1,seconds+1):timer.update(start+i,0)

    def test_sixty_minutes_reminds_until_ten_minutes_idle(self):
        timer=WorkBreak();self.work_for(timer,WORK_SECONDS-1)
        self.assertFalse(timer.due)
        timer.update(WORK_SECONDS,0);self.assertTrue(timer.due)
        for idle in range(1,BREAK_SECONDS):timer.update(WORK_SECONDS+idle,idle)
        self.assertTrue(timer.due)
        timer.update(WORK_SECONDS+BREAK_SECONDS,BREAK_SECONDS)
        self.assertFalse(timer.due);self.assertEqual(timer.work,0)

    def test_brief_idle_does_not_reset_and_return_requires_full_break(self):
        timer=WorkBreak();self.work_for(timer,120)
        for idle in range(1,300):timer.update(120+idle,idle)
        self.assertGreaterEqual(timer.work,120)
        previous=timer.work;timer.update(420,0)
        self.assertGreater(timer.work,previous)

    def test_suspend_unknown_input_and_disabled_do_not_count(self):
        timer=WorkBreak();self.work_for(timer,30)
        timer.update(10000,0);self.assertEqual(timer.work,30)
        timer.update(10001,None);self.assertEqual(timer.work,30)
        timer.update(10002,0,False);self.assertEqual(timer.work,0)

    def test_snooze_five_active_minutes(self):
        timer=WorkBreak();self.work_for(timer,WORK_SECONDS)
        timer.snooze();self.assertFalse(timer.due)
        self.work_for(timer,299,WORK_SECONDS);self.assertFalse(timer.due)
        timer.update(WORK_SECONDS+300,0);self.assertTrue(timer.due)

    def test_old_save_defaults_on_and_disabled_persists(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pet.json';state=PetState();state.save(path)
            data=json.loads(path.read_text(encoding='utf-8'));del data['break_reminders']
            path.write_text(json.dumps(data),encoding='utf-8')
            self.assertTrue(PetState.load(path).break_reminders)
            state.break_reminders=False;state.save(path)
            self.assertFalse(PetState.load(path).break_reminders)
