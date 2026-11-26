"""Verify needs, care recovery and both render surfaces using isolated data."""
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
from model import PetState,ACTIONS
from animation import frame_names

ctypes.windll.shcore.SetProcessDpiAwareness(1)
out=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'work/desktop-qa/need-states'
out.mkdir(parents=True,exist_ok=True)
root=tk.Tk();root.withdraw()
pet=DesktopPet(root,out/'pet.json');pet.keyboard.stop();pet.state=PetState()
root.deiconify();root.update();results=[]

def check(name,value):
    results.append(dict(name=name,passed=bool(value)))
    if not value:raise AssertionError(name)

def wait(ms):
    done=tk.BooleanVar(root,value=False)
    root.after(ms,lambda:done.set(True));root.wait_variable(done)

def render():
    pet.notice_until=0;pet.render(time.monotonic());root.update_idletasks()

def capture(name,win=root):
    root.update();wait(100);x,y=win.winfo_rootx(),win.winfo_rooty()
    ImageGrab.grab(bbox=(x,y,x+win.winfo_width(),y+win.winfo_height())).save(out/(name+'.png'))

try:
    pet.set_scene('park',walk=False)
    for outfit in ('blue','red','yellow'):
        for stage in range(3):
            for key,motion in (('food','hungry'),('water','thirsty'),('energy','tired')):
                pet.state=PetState();pet.state.stage=pet.state.unlocked_stage=stage;pet.state.outfit=outfit;pet.state.scene='park'
                pet.state.values[key]=8;pet.keyboard.last_activity=time.monotonic()
                render();name,typing=pet.pose(time.monotonic())
                check(f'{outfit}_{stage}_{key}_pose',name in frame_names(outfit,stage,motion) and not typing)
                if outfit=='blue' and stage==2:capture(motion)
    pet.set_scene(None);pet.state=PetState();pet.state.values.update(food=8,water=9,energy=10)
    render()
    check('desktop_weak_hint_visible',bool(pet.desktop.find_withtag('status_notice')) and '吃饭' in pet.state.need_text())
    pet.show_toolbar();root.update()
    check('care_controls_remain_available',all(pet.buttons[key].winfo_ismapped() for key in ('feed','water','sleep')))
    pet.hide_tools();pet.popup();pet.more.refresh();capture('needs-panel',pet.more.win)
    pet.more.sections['care'].invoke()
    check('panel_marks_all_low_needs',all('偏低' in pet.more.bars[key][0].cget('text') for key in ('food','water','energy')))
    pet.close_more()
    for key in ('walk','toy'):check(key+'_blocked_when_weak',not pet.start_action(key))
    pet.open_fetch();check('ball_charge_blocked_when_weak',not pet.begin_charge())
    clock=pet.walk_clock;wait(180)
    check('weak_pet_rests_in_fetch_waiting',pet.walk_clock==clock and not pet.pose(time.monotonic())[1])
    pet.set_scene(None)
    for action,remaining in (('feed',('water','energy')),('water',('energy',)),('sleep',())):
        check(action+'_can_start',pet.start_action(action))
        now=time.monotonic();check(action+'_animation_has_priority',pet.pose(now)[0] in frame_names(pet.state.outfit,pet.state.stage,ACTIONS[action]['pose']))
        pet.action_started=now-ACTIONS[action]['duration']-.1;wait(180)
        check(action+'_clears_matching_need',pet.state.low_needs()==remaining)
    check('all_recovered_and_rewarded_once',pet.state.completed==3 and pet.state.need_text()=='')
    pet.keyboard.last_activity=time.monotonic();check('typing_resumes_after_recovery',pet.pose(time.monotonic())[1])
    pet.save();check('needs_persist_from_saved_values',not PetState.load(pet.data_path).low_needs())
    pet.state.values['food']=20;pet.state.cooldowns.clear()
    check('mild_hunger_allows_play',pet.start_action('toy'));pet.cancel_action()
finally:
    (out/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    pet.close()
print(json.dumps({'passed':len(results),'checks':results},ensure_ascii=False))
