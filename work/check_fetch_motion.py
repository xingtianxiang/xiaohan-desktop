"""Exercise walking, consecutive throws and cancellation in an isolated Tk app."""
import ctypes
import json
from pathlib import Path
import sys
import time
import tkinter as tk
from PIL import ImageGrab

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/XiaohanDesktop'))
from app import DesktopPet
from model import PetState,ACTIONS,TOILET_URGENT_SECONDS
from fetch_game import walk_position
from animation import fetch_asset

ctypes.windll.shcore.SetProcessDpiAwareness(1)
out=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'work/desktop-qa/fetch-turn-window'
out.mkdir(parents=True,exist_ok=True)
root=tk.Tk();root.withdraw()
app=DesktopPet(root,out/'pet.json');app.keyboard.stop();app.state=PetState()
root.deiconify();root.update()
results=[]

def check(name,value):
    results.append(dict(name=name,passed=bool(value)))
    if not value:raise AssertionError(name)

def wait(milliseconds):
    done=tk.BooleanVar(root,value=False)
    root.after(milliseconds,lambda:done.set(True));root.wait_variable(done)

def release():
    app.desktop.event_generate('<ButtonRelease-1>',x=220,y=245)

try:
    app.set_scene('park');app.walk_clock=2
    started=app.action_started
    check('open_fetch_preserves_walk',app.open_fetch() and app.action=='walk' and app.action_started==started)
    root.update();root.focus_force();wait(100)
    app.desktop.event_generate('<ButtonPress-1>',x=220,y=245)
    check('mouse_press_starts_charge',app.charge.started is not None)
    before=app.walk_clock;wait(280)
    check('walking_advances_while_charging',app.action=='walk' and app.walk_clock>before+.1)
    origin=walk_position(app.walk_clock);release()
    check('release_chases_from_current_position',app.action=='ball' and app.fetch_origin==origin and app.walk_resume is not None)
    paused_walk=app.walk_resume;clock=app.walk_clock;wait(150)
    check('walk_progress_preserved_during_chase',app.walk_clock==clock)
    now=time.monotonic()
    for stage in range(3):
        for outfit in ('blue','red','yellow'):
            app.state.stage=app.state.unlocked_stage=stage;app.state.outfit=outfit
            for progress,pose in ((.48,'pickup'),(.54,'turnquarter'),(.58,'turnfront'),(.62,'turnquarter'),(.7,'run'),(.94,'drop')):
                app.action_started=now-progress*ACTIONS['ball']['duration']
                name,_=app.pose(now)
                check(f'{outfit}_{stage}_{progress}_{pose}_uses_new_art',name.startswith(fetch_asset(outfit,stage,pose)))
                app.render(now)
    app.state.stage=app.state.unlocked_stage=2;app.state.outfit='blue'
    app.action_started=time.monotonic()-7;app.render(time.monotonic());root.update_idletasks()
    x,y=root.winfo_rootx(),root.winfo_rooty()
    ImageGrab.grab(bbox=(x,y,x+app.width,y+app.height)).save(out/'carrying.png')
    app.toggle_pause()
    frozen=app.current_fetch(app.pause_started)[0]
    before=app.state.completed
    wait(260)
    check('pause_keeps_fetch_frame_and_pending_reward',
          app.action=='ball' and app.current_fetch(time.monotonic())[0]==frozen
          and app.state.completed==before and app.resume_button.winfo_ismapped())
    app.resume_button.invoke()
    resumed=app.current_fetch(time.monotonic())[0]
    check('resume_continues_carry_from_same_position',not app.paused and abs(resumed.x-frozen.x)<3)
    app.action_started=time.monotonic()-ACTIONS['ball']['duration']-.1;wait(180)
    check('first_return_awards_once_and_resumes_walk',app.fetch_count==1 and app.state.completed==1 and app.action=='walk')
    check('resume_retains_elapsed_walk',paused_walk<=time.monotonic()-app.action_started<paused_walk+.5)
    app.state.toilet_seconds=TOILET_URGENT_SECONDS-4
    check('second_throw_available_immediately',app.begin_charge())
    release();check('second_release_starts_ball',app.action=='ball')
    app.state.tick(4,False)
    app.action_started=time.monotonic()-ACTIONS['ball']['duration']-.1;wait(180)
    check('second_return_awards_even_with_new_urgency',app.fetch_count==2 and app.state.completed==2 and app.action=='walk')
    check('settlement_visible_and_next_throw_blocked','第 2 球带回来了' in app.notice and not app.begin_charge())
    wait(180)
    check('fetch_reward_cannot_repeat_on_next_tick',app.fetch_count==2 and app.state.completed==2)
    app.state.toilet_seconds=0
    check('third_charge_without_cooldown',app.begin_charge())
    app.escape_fetch();check('cancel_charge_keeps_walk_and_rewards',app.action=='walk' and app.state.completed==2 and app.charge.started is None)
    app.state.values['energy']=5
    check('exhaustion_still_blocks_throw',not app.begin_charge())
    app.state.values['energy']=60
    app.begin_charge();release();app.set_scene(None)
    check('scene_exit_cancels_without_reward',app.action is None and app.walk_resume is None and app.state.completed==2)
finally:
    (out/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    app.close()
print(json.dumps(dict(passed=len(results),checks=results),ensure_ascii=False))
