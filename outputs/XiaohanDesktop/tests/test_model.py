import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from model import (ACTIONS, ENERGY_HOURLY, MINI_GAMES, PetState, STAGES, TOILET_REMIND_SECONDS, TOILET_URGENT_SECONDS,
                   TOILET_FULL_SECONDS)


@unittest.skipUnless(os.name=='nt','Windows replace semantics')
class SaveReplaceTests(unittest.TestCase):
    """A folder under WeChat's received files marks pet.json read-only; replace then hit WinError 5."""

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)/'data'/'pet.json'
        PetState().save(self.path)

    def tearDown(self):
        for name in ('pet.json','pet.tmp'):
            target=self.path.parent/name
            if target.exists():target.chmod(stat.S_IREAD|stat.S_IWRITE)
        self.folder.cleanup()

    def test_save_over_read_only_save_file(self):
        self.path.chmod(stat.S_IREAD)
        state=PetState();state.outfit='red';state.save(self.path)
        self.assertEqual(PetState.load(self.path).outfit,'red')
        self.assertFalse(self.path.with_suffix('.tmp').exists())

    def test_save_rewrites_read_only_leftover_temp(self):
        temp=self.path.with_suffix('.tmp');temp.write_text('{}',encoding='utf-8');temp.chmod(stat.S_IREAD)
        state=PetState();state.scene='snow';state.save(self.path)
        self.assertEqual(PetState.load(self.path).scene,'snow')

    def test_save_waits_out_brief_scanner_lock(self):
        handle=self.path.open('rb')
        release=threading.Timer(.02,handle.close);release.start()
        try:
            state=PetState();state.outfit='yellow';state.save(self.path)
        finally:
            release.join()
        self.assertEqual(PetState.load(self.path).outfit,'yellow')

    def test_persistent_lock_still_reports_failure(self):
        with self.path.open('rb'):
            with self.assertRaises(PermissionError):PetState().save(self.path)

class CareTests(unittest.TestCase):
    def test_update_check_setting_defaults_on_for_old_saves(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pet.json';PetState().save(path)
            data=json.loads(path.read_text(encoding='utf-8'));del data['update_checks']
            path.write_text(json.dumps(data),encoding='utf-8')
            self.assertTrue(PetState.load(path).update_checks)
            data['update_checks']='yes';path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):PetState.load(path)

    def test_mouse_follow_defaults_on_for_old_saves(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pet.json';state=PetState();state.mouse_follow=False;state.save(path)
            self.assertFalse(PetState.load(path).mouse_follow)
            data=json.loads(path.read_text(encoding='utf-8'));del data['mouse_follow']
            path.write_text(json.dumps(data),encoding='utf-8')
            self.assertTrue(PetState.load(path).mouse_follow)
            data['mouse_follow']=1;path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):PetState.load(path)

    def test_toilet_time_boundaries_and_completion(self):
        state=PetState()
        self.assertTrue(state.check('toilet',100))
        state.toilet_seconds=TOILET_REMIND_SECONDS-1
        self.assertNotIn('toilet',state.low_needs())
        state.tick(1,False)
        self.assertIn('toilet',state.low_needs())
        self.assertNotIn('toilet',state.urgent_needs())
        self.assertEqual(state.check('ball',100),'')
        state.toilet_seconds=TOILET_URGENT_SECONDS
        self.assertIn('toilet',state.urgent_needs())
        for action in ('walk','ball','toy'):self.assertTrue(state.check(action,100))
        for action in ('feed','water','sleep','toilet'):self.assertEqual(state.check(action,100),'')
        self.assertEqual(state.finish('toilet',100),'')
        self.assertEqual(state.toilet_seconds,0)
        self.assertFalse(state.low_needs())
        self.assertTrue(state.finish('toilet',101))
        self.assertEqual(state.completed,1)
        state.toilet_seconds=TOILET_FULL_SECONDS;state.tick(10,True)
        self.assertEqual(state.toilet_seconds,TOILET_FULL_SECONDS)

    def test_toilet_old_save_defaults_and_no_offline_accumulation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pet.json';state=PetState();state.toilet_seconds=5000;state.save(path)
            self.assertEqual(PetState.load(path).toilet_seconds,5000)
            data=json.loads(path.read_text(encoding='utf-8'));del data['toilet_seconds']
            path.write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(PetState.load(path).toilet_seconds,0)
            data['toilet_seconds']=-1;path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):PetState.load(path)

    def test_low_needs_prioritize_lowest_and_critical_guards(self):
        state=PetState()
        for key in ('food','water','energy'):state.values[key]=25
        self.assertEqual(state.low_needs(),())
        state.values.update(food=24,water=12,energy=20)
        self.assertEqual(state.low_needs(),('water','energy','food'))
        self.assertEqual(state.check('ball',100),'')
        state.values['food']=11
        self.assertEqual(state.low_needs()[0],'food')
        for action in ('walk','ball','toy'):self.assertTrue(state.check(action,100))
        for action in ('feed','water','sleep'):self.assertEqual(state.check(action,100),'')

    def test_care_recovers_only_matching_need(self):
        state=PetState();state.values.update(food=5,water=6,energy=7)
        state.finish('feed',100)
        self.assertEqual(state.low_needs(),('water','energy'))
        state.finish('water',100)
        self.assertEqual(state.low_needs(),('energy',))
        state.finish('sleep',100)
        self.assertEqual(state.low_needs(),())
        self.assertEqual(state.need_text(),'')

    def test_fetch_can_repeat_immediately_even_with_old_cooldown(self):
        state=PetState();state.cooldowns['ball']=1000
        self.assertEqual(state.check('ball',100),'')
        self.assertEqual(state.finish('ball',100),'')
        self.assertEqual(state.check('ball',100),'')
        self.assertEqual(state.finish('ball',101),'')
        self.assertEqual(state.completed,2)

    def test_started_fetch_completes_when_toilet_becomes_urgent_mid_throw(self):
        state=PetState()
        state.toilet_seconds=TOILET_URGENT_SECONDS-4
        self.assertEqual(state.check('ball',100),'')
        state.tick(10,True)
        self.assertEqual(state.finish('ball',110,already_started=True),'')
        self.assertEqual(state.completed,1)
        self.assertEqual(state.values['bond'],12)
        self.assertIn('厕所',state.check('ball',110))
        self.assertTrue(state.finish('ball',111))
        self.assertEqual(state.completed,1)

    def test_completion_and_cooldown(self):
        state=PetState();before=state.values.copy()
        self.assertEqual(state.check('feed',100),'')
        self.assertEqual(state.values,before)
        self.assertEqual(state.finish('feed',100),'')
        self.assertEqual(state.values['food'],90)
        self.assertTrue(state.finish('feed',101))
        self.assertEqual(state.completed,1)

    def test_saturation_and_energy_guards(self):
        state=PetState();state.values['food']=98
        self.assertTrue(state.check('feed',100))
        state.values['energy']=5
        for action in ('walk','ball','toy'):
            self.assertTrue(state.check(action,100))
        self.assertEqual(state.finish('sleep',100),'')
        self.assertEqual(state.values['energy'],30)

    def test_growth_requires_both_conditions_and_never_reverses(self):
        state=PetState();state.companion_seconds=STAGES[2][0]
        state.promote();self.assertEqual(state.unlocked_stage,0)
        state.values['bond']=21;state.promote();self.assertEqual(state.unlocked_stage,1)
        state.values['bond']=55;state.promote();self.assertEqual(state.unlocked_stage,2)
        state.values['bond']=0;state.promote();self.assertEqual(state.unlocked_stage,2)
        self.assertEqual(state.stage,0)

    def test_growth_time_boundaries_and_manual_choice(self):
        state=PetState();state.values['bond']=100
        for stage,hours in ((1,20),(2,40)):
            state.companion_seconds=hours*3600-1;state.promote()
            self.assertEqual(state.unlocked_stage,stage-1)
            self.assertTrue(state.select_stage(stage))
            state.tick(1,True)
            self.assertEqual(state.unlocked_stage,stage)
            self.assertEqual(state.select_stage(stage),'')
            self.assertEqual(state.stage,stage)
        state.select_stage(0);state.tick(1,True)
        self.assertEqual(state.stage,0)
        self.assertEqual(state.unlocked_stage,2)
        for invalid in (-1,3,True,1.5):self.assertTrue(state.select_stage(invalid))

    def test_old_growth_preserved_and_selected_size_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pet.json';state=PetState();state.save(path)
            data=json.loads(path.read_text(encoding='utf-8'));del data['unlocked_stage'];data['stage']=2
            path.write_text(json.dumps(data),encoding='utf-8')
            old=PetState.load(path)
            self.assertEqual((old.stage,old.unlocked_stage),(2,2))
            old.select_stage(0);old.save(path);restored=PetState.load(path)
            self.assertEqual((restored.stage,restored.unlocked_stage),(0,2))
            data=json.loads(path.read_text(encoding='utf-8'));data['stage']=2;data['unlocked_stage']=1
            path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):PetState.load(path)

    def test_idle_and_resume_do_not_award_offline_time(self):
        state=PetState();state.tick(10,False)
        self.assertEqual(state.companion_seconds,0)
        state.tick(999999,True)
        self.assertEqual(state.companion_seconds,10)

    def test_roundtrip_and_corrupt_save_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pet.json'
            state=PetState();state.outfit='red';state.scene='snow';state.window_position=(247,193);state.finish('water',100)
            state.save(path);restored=PetState.load(path)
            self.assertEqual(restored.__dict__,state.__dict__)
            path.write_text('{bad',encoding='utf-8')
            with self.assertRaises(ValueError):PetState.load(path)
            self.assertEqual(path.read_text(),'{bad')

    def test_old_save_without_window_position(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pet.json'
            PetState().save(path)
            data=json.loads(path.read_text(encoding='utf-8'))
            del data['window_position']
            path.write_text(json.dumps(data),encoding='utf-8')
            self.assertIsNone(PetState.load(path).window_position)

    def test_invalid_numbers_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pet.json';PetState().save(path)
            data=json.loads(path.read_text(encoding='utf-8'));data['values']['bond']=float('nan')
            path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):PetState.load(path)



class EnergyAndGameTests(unittest.TestCase):
    def hour(self,state,rest):
        for _ in range(360):state.tick(10,True,rest)

    def test_energy_drains_while_busy_and_recovers_at_rest_and_faster_napping(self):
        changes={}
        for rest in ('busy','rest','nap'):
            state=PetState();state.values['energy']=50
            self.hour(state,rest)
            changes[rest]=state.values['energy']-50
        self.assertAlmostEqual(changes['busy'],ENERGY_HOURLY['busy'])
        self.assertAlmostEqual(changes['rest'],ENERGY_HOURLY['rest'])
        self.assertAlmostEqual(changes['nap'],ENERGY_HOURLY['nap'])
        self.assertTrue(changes['busy']<0<changes['rest']<changes['nap'])
        state=PetState();state.values['energy']=99
        self.hour(state,'nap')
        self.assertEqual(state.values['energy'],100)

    def test_games_are_rewarded_once_per_cooldown_and_blocked_by_urgent_needs(self):
        for game in MINI_GAMES:
            state=PetState()
            self.assertEqual(state.check(game,100),'')
            before=dict(state.values)
            self.assertEqual(state.finish(game,100,already_started=True),'')
            self.assertGreater(state.values['mood'],before['mood'])
            self.assertLess(state.values['energy'],before['energy'])
            self.assertIn('秒后再来',state.check(game,110))
            self.assertEqual(state.check(game,100+ACTIONS[game]['cooldown']),'')
            state.values['energy']=5
            self.assertIn('休息',state.play_block())
            self.assertEqual(state.check(game,1e6),state.play_block())

    def test_best_scores_only_rise_and_survive_a_reload(self):
        state=PetState()
        self.assertTrue(state.record_score('catch',12))
        self.assertFalse(state.record_score('catch',9))
        self.assertFalse(state.record_score('catch',12))
        self.assertTrue(state.record_score('hurdle',40))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pet.json';state.save(path)
            self.assertEqual(PetState.load(path).best_scores,{'catch':12,'hurdle':40})
            data=json.loads(path.read_text(encoding='utf-8'))
            del data['best_scores'];path.write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(PetState.load(path).best_scores,{})
            for bad in ({'chess':3},{'catch':-1},[]):
                data['best_scores']=bad;path.write_text(json.dumps(data),encoding='utf-8')
                with self.assertRaises(ValueError):PetState.load(path)

if __name__=='__main__':unittest.main()
