"""Isolated UI and timer checks for the potty care loop."""
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
from model import PetState,ACTIONS,TOILET_REMIND_SECONDS,TOILET_URGENT_SECONDS
from animation import frame_names

ctypes.windll.shcore.SetProcessDpiAwareness(1)
out=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'work/desktop-qa/toilet'
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

def capture(name,win):
    root.update();wait(110);x,y=win.winfo_rootx(),win.winfo_rooty()
    ImageGrab.grab(bbox=(x,y,x+win.winfo_width(),y+win.winfo_height())).save(out/(name+'.png'))

try:
    pet.state.toilet_seconds=TOILET_URGENT_SECONDS
    pet.show_toolbar();root.update()
    check('hover_contains_nine_care_icons',len(pet.buttons)==9 and pet.buttons['toilet'].winfo_ismapped())
    check('nine_icons_fit',all(b.winfo_x()+b.winfo_width()<=pet.toolbar.winfo_width() and b.winfo_y()+b.winfo_height()<=pet.toolbar.winfo_height() for b in pet.buttons.values()))
    capture('hover',pet.toolbar)
    pet.buttons['toilet'].event_generate('<ButtonPress-1>',x=32,y=30)
    check('toilet_icon_starts_action',pet.action=='toilet')
    check('no_early_timer_reset',pet.state.toilet_seconds>=TOILET_URGENT_SECONDS)
    pet.action_started=time.monotonic()-3;pet.hide_tools();pet.render(time.monotonic())
    check('privacy_screen_visible',bool(pet.desktop.find_withtag('toilet_screen')))
    check('size_change_blocked_during_toilet',not pet.select_stage(0))
    pet.cancel_action()
    check('cancel_preserves_need_and_reward',pet.state.toilet_seconds>=TOILET_URGENT_SECONDS and pet.state.completed==0)
    pet.popup();root.update()
    pet.more.sections['care'].invoke()
    check('more_contains_toilet_status','很急' in pet.more.bars['toilet'][0].cget('text'))
    check('more_fits_screen',pet.more.height<=root.winfo_screenheight())
    capture('more',pet.more.win)
    pet.more.toilet_button.invoke();check('more_toilet_button_starts_action',pet.action=='toilet')
    pet.close_more();pet.action_started=time.monotonic()-ACTIONS['toilet']['duration']-.1;wait(180)
    check('completion_relaxes_and_resets_timer',pet.action is None and pet.state.toilet_seconds<1 and not pet.state.low_needs())
    check('completion_awarded_once',pet.state.completed==1)
    check('immediate_repeat_not_needed',not pet.start_action('toilet') and pet.state.completed==1)
    pet.save();check('reset_persists',PetState.load(pet.data_path).toilet_seconds<1)
    pet.toggle_pause();before=pet.state.toilet_seconds;wait(220)
    check('pause_stops_toilet_clock',pet.state.toilet_seconds==before)
    pet.toggle_pause();pet.state.toilet_seconds=TOILET_URGENT_SECONDS
    check('urgent_blocks_new_ball',bool(pet.state.check('ball',time.time())))
    pet.set_scene('park',walk=False)
    for outfit in ('blue','red','yellow'):
        for stage in range(3):
            pet.state.stage=pet.state.unlocked_stage=stage;pet.state.outfit=outfit
            now=time.monotonic();pet.keyboard.last_activity=now
            pet.render(now);name,typing=pet.pose(now)
            check(f'{outfit}_{stage}_restless_pose',name in frame_names(outfit,stage,'potty') and not typing)
    pet.state.stage=pet.state.unlocked_stage=2;pet.state.outfit='blue'
    pet.notice_until=0;pet.render(time.monotonic());capture('restless',root)
    pet.start_action('toilet');pet.action_started=time.monotonic()-3;pet.render(time.monotonic())
    check('outdoor_privacy_screen',bool(pet.desktop.find_withtag('toilet_screen')))
    capture('screen',root)
    pet.cancel_action();pet.set_scene(None);pet.show_toolbar();pet.open_wardrobe();root.update()
    check('wardrobe_stays_on_screen',pet.chooser.winfo_x()>=0 and pet.chooser.winfo_x()+pet.chooser.winfo_width()<=root.winfo_screenwidth())
finally:
    (out/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    pet.close()
print(json.dumps({'passed':len(results),'checks':results},ensure_ascii=False))
