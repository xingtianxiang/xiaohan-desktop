"""Check the real Tk Space bindings and record a played round when requested."""
import ctypes
from ctypes import wintypes as W
import json
from pathlib import Path
import sys
import time
import tkinter as tk

from PIL import Image, ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/XiaohanDesktop'))
from app import DesktopPet
from model import PetState
from tug_game import BEAT_CENTER, GREEN_END, GREEN_START

ctypes.windll.shcore.SetProcessDpiAwareness(1)
out = Path(sys.argv[1])
out.mkdir(parents=True,exist_ok=True)
root = tk.Tk()
root.withdraw()
app = DesktopPet(root,out/'pet.json')
app.keyboard.stop()
app.state = PetState()
root.deiconify()
root.update()
root.focus_force()
results = []


def check(name,condition):
    results.append(dict(name=name,passed=bool(condition)))
    if not condition:
        raise AssertionError(name)


def wait(ms):
    done = tk.BooleanVar(root,value=False)
    root.after(ms,lambda:done.set(True))
    root.wait_variable(done)


def until(condition,timeout=9):
    deadline = time.monotonic()+timeout
    while not condition() and time.monotonic()<deadline:
        wait(24)
    return condition()


def release_space():
    app.desktop.event_generate('<KeyRelease-space>')
    root.update_idletasks()


def tap_space():
    app.desktop.event_generate('<KeyPress-space>')
    release_space()


def click_control(key):
    left,top,right,bottom = app.scene_controls[key]
    x,y = round((left+right)/2),round((top+bottom)/2)
    app.desktop.event_generate('<ButtonPress-1>',x=x,y=y)
    app.desktop.event_generate('<ButtonRelease-1>',x=x,y=y)
    root.update()


def tap_on_beat(phase=BEAT_CENTER):
    game=app.tug
    if game.running and game.last_beat!=game.beat and phase<=game.phase<GREEN_END:
        tap_space()


def capture_box(widget):
    user=ctypes.windll.user32
    user.GetClientRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
    user.ClientToScreen.argtypes=[W.HWND,ctypes.POINTER(W.POINT)]
    handle=widget.winfo_id()
    bounds=W.RECT()
    origin=W.POINT()
    if not user.GetClientRect(handle,ctypes.byref(bounds)) or not user.ClientToScreen(handle,ctypes.byref(origin)):
        raise RuntimeError('无法定位游戏窗口')
    return (origin.x,origin.y,origin.x+bounds.right,origin.y+bounds.bottom)


def record_round(destination):
    app.state.stage=app.state.unlocked_stage=2
    app.state.cooldowns.clear()
    check('preview_opens_adult_tug',app.start_action('toy'))
    previous=app.desktop.cget('bg')
    frames=[]
    timestamps=[]
    poses=[]
    strikes=[]
    finished=None
    try:
        # The opaque test backdrop keeps other apps outside the recording.
        app.desktop.configure(bg='#f5f2ea')
        # Keep the window clear of the Windows notification area during capture.
        root.wm_attributes('-transparentcolor','')
        center=max(0,(root.winfo_screenwidth()-app.width)//2)
        root.geometry(f'{app.width}x{app.height}+{center}+80')
        root.lift()
        root.update()
        app.desktop.focus_force()
        wait(100)
        box=capture_box(app.desktop)
        print(f'Canvas {box}',flush=True)
        sample=ImageGrab.grab(bbox=box,all_screens=True)
        sample.save(out/'preview-start.png')
        check('preview_captures_full_canvas',sample.size==(app.width,app.height)
              and sample.getpixel((4,4))==(245,242,234))
        start=time.monotonic()
        while time.monotonic()-start<13:
            seconds=time.monotonic()-start
            game=app.tug
            if seconds>.45 and not game.started:
                tap_space()
            if game.running:
                target=.22 if game.beat==3 else .64
                old_beat=game.last_beat
                tap_on_beat(target)
                if game.last_beat!=old_beat:
                    strikes.append((round(game.elapsed,2),game.feedback))
            root.update_idletasks()
            frames.append(ImageGrab.grab(bbox=box,all_screens=True))
            timestamps.append(seconds)
            poses.append(game.lean)
            if game.result is not None:
                finished=seconds if finished is None else finished
                if seconds-finished>.8:
                    break
            wait(23)
    finally:
        app.desktop.configure(bg=previous)

    game=app.tug
    print(json.dumps(dict(result=game.result,hits=game.hits,best_combo=game.best_combo,
                          peak_brace=round(max(poses),2),peak_forward=round(-min(poses),2),strikes=strikes),
                     ensure_ascii=False),flush=True)
    check('preview_captures_combo_and_motion_in_both_directions',
          game.result in ('player','tie','dog') and game.best_combo>=3
          and any(rating=='early' for _,rating in strikes) and max(poses)>.72 and min(poses)<-.75)
    width,height=frames[0].size
    palette_source=Image.new('RGB',(width,height*6))
    for i in range(6):
        palette_source.paste(frames[i*(len(frames)-1)//5],(0,height*i))
    palette=palette_source.quantize(colors=256)
    encoded=[frame.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
    intervals=[max(10,10*round(100*(b-a))) for a,b in zip(timestamps,timestamps[1:])]
    intervals.append(60)
    encoded[0].save(destination,save_all=True,append_images=encoded[1:],duration=intervals,
                    loop=0,disposal=2,optimize=False)


def verify_controls():
    position=(root.winfo_x(),root.winfo_y())
    app.show_toolbar()
    root.update()
    app.buttons['toy'].event_generate('<ButtonPress-1>',x=32,y=25)
    root.update()
    check('toy_tile_opens_focused_rhythm_game',app.tug is not None and root.focus_displayof()==app.desktop
          and app.desktop.find_withtag('tug_beat'))
    app.desktop.event_generate('<ButtonPress-1>',x=280,y=209)
    app.desktop.event_generate('<ButtonRelease-1>',x=280,y=209)
    wait(170)
    check('waiting_and_clicking_do_not_start',app.tug.elapsed==0 and not app.tug.started and app.state.completed==0)

    app.desktop.event_generate('<KeyPress-space>')
    check('space_starts_round',app.tug.running and app.tug.hits==0)
    check('first_green_window_is_reachable',until(lambda:GREEN_START<=app.tug.phase<=GREEN_END,2.8))
    app.desktop.event_generate('<KeyPress-space>')
    app.desktop.event_generate('<KeyRelease-space>')
    app.desktop.event_generate('<KeyPress-space>')
    check('holding_and_key_repeat_cannot_score',app.tug.hits==0 and app.tug_space_down)
    release_space()

    check('next_beat_available',until(lambda:app.tug.beat>=1 and app.tug.phase<.35,3))
    tap_space()
    check('early_tap_has_live_feedback',app.tug.feedback=='early' and app.tug.hits==0)
    beat=app.tug.beat
    check('same_beat_reaches_green_after_the_miss',
          until(lambda:app.tug.beat==beat and GREEN_START<=app.tug.phase<=GREEN_END,2))
    tap_space()
    check('mashing_cannot_reuse_the_same_beat',app.tug.hits==0 and app.tug.feedback=='early')

    app.toggle_pause()
    elapsed,advantage=app.tug.elapsed,app.tug.advantage
    wait(200)
    check('pause_keep_beat_and_advantage',app.paused and not app.tug.running
          and (app.tug.elapsed,app.tug.advantage)==(elapsed,advantage))
    app.toggle_pause()
    app.desktop.focus_force()
    tap_space()
    check('space_resumes_without_free_hit',app.tug.running and app.tug.hits==0 and app.tug.elapsed==elapsed)

    deadline=time.monotonic()+9
    greatest_forward=0
    saw_combo=False
    while app.tug.result is None and time.monotonic()<deadline:
        tap_on_beat()
        wait(24)
        greatest_forward=max(greatest_forward,-app.tug.lean)
        saw_combo=saw_combo or app.tug.result is None and bool(app.desktop.find_withtag('tug_combo'))
    check('well_timed_taps_win',app.tug.result=='player' and app.tug.hits>=3)
    check('space_drives_forward_pose_and_visible_combo',greatest_forward>.75 and saw_combo and app.tug.best_combo>=3)
    wait(200)
    check('completed_round_rewards_once',app.state.completed==1 and app.state.values['bond']==12
          and PetState.load(app.data_path).completed==1 and root.grab_current() is None)
    click_control('leave_tug')
    check('exit_restores_original_pet_position',app.tug is None and app.action is None
          and (root.winfo_x(),root.winfo_y())==position and (app.width,app.height)==(280,300))
    check('existing_cooldown_after_play',not app.start_action('toy'))
    app.state.cooldowns.clear()
    app.start_action('toy')
    root.update()
    app.desktop.event_generate('<Escape>')
    root.update()
    check('escape_closes_before_start',app.tug is None and app.state.completed==1)
    check('can_open_another_round',app.start_action('toy'))
    root.update()
    tap_space()
    wait(120)
    app.desktop.event_generate('<Escape>')
    wait(100)
    check('escape_cancels_active_round_without_reward',app.tug is None and app.state.completed==1)


try:
    if '--record-only' not in sys.argv:
        verify_controls()
    if len(sys.argv)>2:
        record_round(Path(sys.argv[2]))
finally:
    (out/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    app.close()

print(json.dumps(dict(passed=len(results),checks=results),ensure_ascii=False))
