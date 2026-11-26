"""Isolated window checks and actual screenshots for the outing flow."""
import ctypes
import argparse
import json
from pathlib import Path
import sys
import time
import tkinter as tk
from PIL import ImageGrab

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/XiaohanDesktop'))
from app import DesktopPet
from model import ACTIONS, PetState

ctypes.windll.shcore.SetProcessDpiAwareness(1)
parser=argparse.ArgumentParser();parser.add_argument('--out',default='outdoor-page-release');args=parser.parse_args()
out=ROOT/'work/desktop-qa'/args.out
out.mkdir(exist_ok=True)
root=tk.Tk();root.withdraw()
app=DesktopPet(root,out/'pet.json');app.keyboard.stop()
app.state=PetState()
root.deiconify();root.update()
results=[]


def check(name,value):
    results.append(dict(name=name,passed=bool(value)))
    if not value:raise AssertionError(name)


def render():
    app.render(time.monotonic());root.update()

def wait(milliseconds):
    done=tk.BooleanVar(root,value=False)
    root.after(milliseconds,lambda:done.set(True));root.wait_variable(done)


def capture(win,name):
    root.update_idletasks()
    x,y=win.winfo_rootx(),win.winfo_rooty()
    ImageGrab.grab(bbox=(x,y,x+win.winfo_width(),y+win.winfo_height())).save(out/(name+'.png'))


def click_control(key):
    render();box=app.scene_controls[key];x,y=(box[0]+box[2])/2,(box[1]+box[3])/2
    app.desktop.event_generate('<ButtonPress-1>',x=round(x),y=round(y))
    app.desktop.event_generate('<ButtonRelease-1>',x=round(x),y=round(y))
    render()


try:
    app.show_toolbar();root.update()
    check('outdoor_icon_is_mapped',bool(app.buttons['outdoor'].winfo_ismapped()))
    app.buttons['outdoor'].event_generate('<ButtonPress-1>',x=32,y=30)
    check('outdoor_icon_opens_cards',app.trip_picker is not None and app.toolbar is None)
    picker=app.trip_picker;root.update()
    check('two_destination_previews',set(picker.cards)=={'park','snow'} and len(picker.photos)==2)
    check('picker_inside_screen',0<=picker.win.winfo_x()<=root.winfo_screenwidth()-picker.width and 0<=picker.win.winfo_y()<=root.winfo_screenheight()-picker.height)
    capture(picker.win,'destinations')
    picker.cards['park'].event_generate('<ButtonPress-1>',x=70,y=50)
    render()
    check('card_enters_park_and_walks',app.outdoor and app.state.scene=='park' and app.action=='walk' and app.trip_picker is None)
    check('scene_has_direct_controls',set(app.scene_controls)=={'home','walk','ball','care','scene','more'})
    check('scene_has_no_hover_panel',app.toolbar is None)
    capture(root,'park')
    before=app.state.completed;position=(root.winfo_x(),root.winfo_y())
    click_control('walk')
    check('stop_walk_without_reward',app.action is None and app.state.completed==before)
    check('controls_do_not_drag_window',position==(root.winfo_x(),root.winfo_y()))
    click_control('scene')
    check('change_scenery_opens_picker',app.trip_picker is not None)
    app.trip_picker.cards['snow'].event_generate('<ButtonPress-1>',x=70,y=50)
    render();capture(root,'snow')
    check('snow_choice_saved',app.state.scene=='snow' and PetState.load(app.data_path).scene=='snow')
    click_control('ball')
    check('ball_button_keeps_walking_in_same_scene',app.fetch_mode and app.state.scene=='snow' and app.action=='walk')
    app.desktop.event_generate('<ButtonPress-1>',x=220,y=245)
    check('fetch_still_charges',app.charge.started is not None)
    app.charge.started=time.monotonic()-1.24;render();capture(root,'fetch')
    app.desktop.event_generate('<ButtonRelease-1>',x=220,y=245)
    check('fetch_still_releases',app.action=='ball')
    app.set_scene('park',walk=False);render()
    check('switching_cancels_without_reward',app.state.completed==before and app.action is None)
    click_control('more')
    check('more_control_opens_panel',app.more is not None)
    app.close_more();app.toggle_pause();render()
    check('pause_blocks_walk','walk' not in app.scene_controls and not app.start_action('walk') and app.action is None)
    app.toggle_pause();app.state.cooldowns['walk']=time.time();click_control('walk')
    check('walk_cooldown_still_applies',app.action is None)
    app.state.cooldowns.clear();click_control('walk');click_control('home')
    check('home_restores_pet_and_cancels_walk',not app.outdoor and app.action is None and app.state.completed==before and app.width==280)
    app.show_toolbar();root.update();wait(70)
    check('desktop_hover_controls_remain',set(app.buttons)=={'feed','water','toilet','pet','toy','outdoor','wardrobe','sleep','more'})
    status=app.status_strip
    check('hover_directly_shows_three_care_meters',
          status.winfo_ismapped() and set(status.gauges)=={'food','water','energy'})
    old_water=app.state.values['water']
    app.state.values['water']=18
    status.event_generate('<Enter>')
    wait(320)
    _,_,number,bar=status.gauges['water']
    check('visible_meter_updates_with_the_actual_need',
          status.itemcget(number,'text')=='18' and 8<status.coords(bar)[2]-status.coords(bar)[0]<10)
    root.geometry(f'+{root.winfo_screenwidth()//2}+80')
    root.update_idletasks()
    app.place_toolbar()
    capture(app.toolbar,'hover-status')
    status.event_generate('<ButtonRelease-1>',x=101,y=18)
    root.update_idletasks()
    check('status_strip_opens_care_details_in_one_click',
          app.more is not None and app.more.page=='care' and app.more.bars['water'][0].winfo_ismapped())
    app.close_more()
    app.state.values['water']=old_water
    app.scene_menu();app.escape_fetch()
    check('escape_closes_picker',app.trip_picker is None and not app.outdoor)
    app.start_action('water');app.scene_menu();root.update();app.trip_picker.cards['park'].event_generate('<ButtonPress-1>',x=70,y=50)
    check('care_action_not_interrupted_by_travel',app.action=='water' and not app.outdoor and app.trip_picker is not None)
    app.cancel_action();app.close_trip_picker()
    app.set_scene('park',walk=False);app.escape_fetch()
    check('escape_returns_from_outdoor',not app.outdoor)
    app.set_scene('snow')
    app.walk_clock=3
    app.state.values.update(food=18,water=7,energy=46)
    render()
    check('only_most_urgent_care_shortcut', 'water' in app.scene_controls and 'feed' not in app.scene_controls)
    capture(root,'care-shortcut')
    clock=app.walk_clock
    click_control('water')
    check('water_starts_in_snow_and_holds_walk',app.action=='water' and app.state.scene=='snow'
          and app.walk_resume is not None and abs(app.walk_clock-clock)<.2)
    app.action_started=time.monotonic()-ACTIONS['water']['duration'];wait(200)
    check('water_rewards_and_resumes_same_walk',app.state.values['water']>36 and app.state.completed==before+1
          and app.action=='walk' and clock<=app.walk_clock<clock+.5)
    click_control('care')
    check('care_picker_shows_all_three_actions',app.more.page=='care'
          and all(button.winfo_ismapped() for button in app.more.care_actions.values()))
    capture(app.more.win,'care-menu')
    app.more.care_actions['feed'].invoke()
    check('meal_starts_in_snow',app.action=='feed' and app.outdoor and app.state.scene=='snow')
    app.action_started=time.monotonic()-ACTIONS['feed']['duration'];wait(200)
    check('meal_rewards_and_resumes',app.state.values['food']>42 and app.state.completed==before+2 and app.action=='walk')
    click_control('ball')
    click_control('care')
    app.more.care_actions['sleep'].invoke()
    check('rest_is_available_even_in_fetch_mode',app.action=='sleep' and app.fetch_mode and app.state.scene=='snow')
    check('care_blocks_new_throw_until_complete',not app.begin_charge())
    app.action_started=time.monotonic()-ACTIONS['sleep']['duration'];wait(200)
    check('rest_rewards_and_keeps_fetch_mode',app.state.values['energy']>70 and app.state.completed==before+3
          and app.fetch_mode and app.action=='walk')
    clock=app.walk_clock
    check('aborted_throw_starts',app.throw_ball(.3))
    click_control('leave_fetch')
    check('header_returns_to_snow_without_unfinished_reward',app.outdoor and not app.fetch_mode and app.state.scene=='snow'
          and app.state.completed==before+3 and app.action=='walk' and clock<=app.walk_clock<clock+.5)
    click_control('ball')
    check('begins_charge_for_escape',app.begin_charge())
    app.escape_fetch()
    check('first_escape_cancels_only_charge',app.fetch_mode and app.charge.started is None)
    app.escape_fetch()
    check('second_escape_returns_to_snow_walk',app.outdoor and not app.fetch_mode and app.state.scene=='snow' and app.action=='walk')
    click_control('home')
    app.open_fetch();app.escape_fetch()
    check('fetch_started_on_desktop_returns_to_desktop',not app.outdoor and not app.fetch_mode)

    press_x,press_y=root.winfo_x()+100,root.winfo_y()+100
    app.desktop.event_generate('<ButtonPress-1>',x=100,y=100,rootx=press_x,rooty=press_y)
    app.desktop.event_generate('<B1-Motion>',x=100,y=100,rootx=247+100,rooty=193+100)
    app.desktop.event_generate('<ButtonRelease-1>',x=100,y=100,rootx=247+100,rooty=193+100)
    root.update()
    check('dragged_position_is_saved',PetState.load(app.data_path).window_position==(247,193))
    app.popup();root.update()
    app.more.hide.invoke();root.update()
    check('hide_folds_pet_and_panel_into_recall_button',app.hidden and not app.desktop.winfo_ismapped()
          and app.more is None and app.recall_button.winfo_ismapped() and root.winfo_width()<app.width)
    capture(root,'recall')
    app.recall_button.invoke();render()
    check('recall_returns_to_dragged_position',not app.hidden and app.desktop.winfo_ismapped()
          and (root.winfo_x(),root.winfo_y())==(247,193) and root.winfo_width()==app.width)

    reopened_root=tk.Toplevel(root)
    reopened=DesktopPet(reopened_root,app.data_path)
    reopened.keyboard.stop()
    try:
        root.update()
        check('reopen_remembers_saved_position',(reopened_root.winfo_x(),reopened_root.winfo_y())==(247,193))
    finally:
        reopened.close()
finally:
    (out/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    app.close()
print(json.dumps(results,ensure_ascii=False))
