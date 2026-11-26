"""Actual Tk checks with isolated data and a simulated active-input clock."""
import ctypes
import json
from pathlib import Path
import sys
import time
import tkinter as tk
from PIL import ImageGrab

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/XiaohanDesktop'))
import app as application
from model import PetState,STAGES

application.user_idle_seconds=lambda:0
ctypes.windll.shcore.SetProcessDpiAwareness(1)
out=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'work/desktop-qa/growth-progress'
out.mkdir(parents=True,exist_ok=True)
root=tk.Tk();root.withdraw()
pet=application.DesktopPet(root,out/'pet.json');pet.keyboard.stop();pet.state=PetState()
root.deiconify();root.update();results=[]

def check(name,value):
    results.append(dict(name=name,passed=bool(value)))
    if not value:raise AssertionError(name)

def refresh():
    pet.more.refresh();root.update_idletasks()

def wait(milliseconds):
    done=tk.BooleanVar(root,value=False)
    root.after(milliseconds,lambda:done.set(True));root.wait_variable(done)

def capture(name,compact=False):
    root.update();win=pet.more.win;x,y=win.winfo_rootx(),win.winfo_rooty()
    height=panel.growth.winfo_rooty()+panel.growth.winfo_height()-y+8 if compact else win.winfo_height()
    ImageGrab.grab(bbox=(x,y,x+win.winfo_width(),y+height)).save(out/(name+'.png'))

try:
    pet.popup();panel=pet.more;panel.sections['growth'].invoke();root.update()
    check('initial_small_selected',pet.state.stage==0 and '使用中' in panel.stage_buttons[0].cget('text'))
    check('locked_stages_disabled',all(panel.stage_buttons[i].cget('state')=='disabled' for i in (1,2)))
    panel.stage_buttons[2].invoke();check('locked_click_keeps_small',pet.state.stage==0)
    check('progress_shows_remaining', '少年还差' in panel.growth.cget('text'))
    check('panel_fits_screen',panel.height<=root.winfo_screenheight() and panel.win.winfo_y()>=0)
    capture('locked')
    pet.state.companion_seconds=0;refresh()
    check('empty_progress_starts_at_zero',pet.state.growth_fraction()==0 and not panel.growth_bar.find_withtag('progress'))
    pet.state.companion_seconds=12.5*3600;pet.state.values['bond']=20;refresh()
    coords=panel.growth_bar.coords('progress')
    check('fill_matches_elapsed_time',abs((coords[2]-coords[0])/(panel.growth_bar.winfo_width()-10)-.625)<.001)
    check('remaining_time_shown','7小时30分' in panel.growth.cget('text'))
    capture('progress',compact=True)
    pet.state.companion_seconds=STAGES[1][0]-.1;refresh()
    check('not_prematurely_shown_as_full','99%' in panel.growth_percent.cget('text') and '0小时01分' in panel.growth.cget('text'))
    pet.state.companion_seconds=STAGES[1][0];pet.state.values['bond']=10;refresh()
    check('time_full_but_bond_still_required',pet.state.growth_fraction()==1 and '亲密 10' in panel.growth.cget('text') and panel.stage_buttons[1].cget('state')=='disabled')
    pet.state.unlocked_stage=1;pet.state.stage=0;pet.state.companion_seconds=30*3600;refresh()
    check('progress_tracks_unlock_not_selected_size',pet.state.growth_fraction()==.5 and '成年' in panel.growth_title.cget('text'))
    pet.state=PetState()
    pet.state.companion_seconds=STAGES[1][0]-.05;pet.state.values['bond']=STAGES[1][1]
    wait(240);refresh()
    check('time_tick_unlocks_without_action',pet.state.unlocked_stage==1 and pet.state.stage==0)
    check('unlock_notice_visible','解锁少年' in pet.notice)
    check('unlock_saved',PetState.load(pet.data_path).unlocked_stage==1)
    panel.stage_buttons[1].invoke();refresh()
    check('select_medium_changes_render',pet.state.stage==1 and pet.pose(time.monotonic())[0]=='blue_teen')
    check('choice_saved',PetState.load(pet.data_path).stage==1)
    pet.state.companion_seconds=STAGES[2][0];pet.state.values['bond']=STAGES[2][1]-1
    pet.state.promote();refresh()
    check('adult_bond_gate_remains',pet.state.unlocked_stage==1 and panel.stage_buttons[2].cget('state')=='disabled')
    pet.state.finish('pet',time.time());refresh()
    check('bond_completion_unlocks_adult',pet.state.unlocked_stage==2)
    panel.stage_buttons[2].invoke();refresh()
    check('select_large_changes_render',pet.pose(time.monotonic())[0]=='blue_adult')
    pet.start_action('water');refresh();before=pet.state.stage
    panel.stage_buttons[0].invoke()
    check('busy_switch_is_disabled',panel.stage_buttons[0].cget('state')=='disabled' and pet.state.stage==before)
    pet.cancel_action();refresh();panel.stage_buttons[0].invoke();wait(130);refresh()
    check('small_choice_survives_ticks',pet.state.stage==0 and pet.state.unlocked_stage==2)
    check('reload_keeps_choice_and_unlocks',(PetState.load(pet.data_path).stage,PetState.load(pet.data_path).unlocked_stage)==(0,2))
    check('all_sizes_selectable',all(b.cget('state')=='normal' for b in panel.stage_buttons.values()))
    check('all_unlocked_shows_complete',pet.state.growth_fraction()==1 and panel.growth_percent.cget('text')=='已完成')
    capture('unlocked')
    pet.close_more();pet.set_scene('park',walk=False);pet.popup();panel=pet.more
    panel.sections['growth'].invoke()
    panel.stage_buttons[1].invoke()
    check('choice_applies_outdoors',pet.state.stage==1 and pet.outdoor)
finally:
    (out/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    pet.close()
print(json.dumps({'passed':len(results),'checks':results},ensure_ascii=False))
