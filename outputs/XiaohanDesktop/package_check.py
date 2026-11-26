"""Opt-in checks run against an extracted disposable release, never a live save."""
import json
from pathlib import Path
import sys
import time
import traceback
from PIL import ImageGrab
from animation import FRAME_COUNTS, frame_names, required_assets
from model import PetState, OUTFITS, ACTIONS, TOILET_URGENT_SECONDS


def schedule(app, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    results=[]
    initial=app.state.__dict__.copy()

    def check(name, condition):
        results.append({'name':name,'passed':bool(condition)})
        if not condition:raise AssertionError(name)

    def capture(name, window):
        app.root.update_idletasks()
        x,y=window.winfo_rootx(),window.winfo_rooty()
        ImageGrab.grab(bbox=(x,y,x+window.winfo_width(),y+window.winfo_height())).save(output/(name+'.png'))

    def run():
        try:
            check('frozen_executable',getattr(sys,'frozen',False))
            check('portable_save_location',app.data_path==Path(sys.executable).resolve().parent/'data/pet.json')
            check('keyboard_listener_registered',app.keyboard.ready.is_set() and not app.keyboard.error and bool(app.keyboard.hwnd))
            check('all_pet_assets_loaded',all(n in app.images for n in required_assets(OUTFITS)))
            check('desktop_visible',app.root.winfo_ismapped() and app.desktop.winfo_ismapped())
            capture('desktop',app.root)
            app.show_toolbar();app.root.update()
            check('nine_care_buttons',len(app.buttons)==9 and all(b.winfo_ismapped() for b in app.buttons.values()))
            capture('menu',app.toolbar)
            app.buttons['feed'].event_generate('<ButtonPress-1>',x=32,y=30)
            check('feeding_from_icon',app.action=='feed')
            app.render(time.monotonic());app.cancel_action()
            for action in ('water','sleep','toy'):
                check(action+'_starts',app.start_action(action))
                app.render(time.monotonic());app.cancel_action()
            for outfit in OUTFITS:
                for stage in range(3):
                    for motion in FRAME_COUNTS:
                        for name in frame_names(outfit,stage,motion):
                            app.photo(name,(160,160))
            check('all_age_outfit_frames_decode',True)
            app.popup();app.root.update()
            check('more_and_growth_panel',app.more is not None and 'toilet' in app.more.bars)
            capture('more',app.more.win);app.close_more()
            for scene in ('park','snow'):
                app.set_scene(scene,walk=False);app.render(time.monotonic());app.root.update()
                check(scene+'_rendered',app.scene_photo is not None)
            capture('outdoor',app.root)
            check('fetch_opens',app.open_fetch())
            app.throw_ball(.65);check('fetch_throw_starts',app.action=='ball')
            for progress in (.2,.5,.7,.9):
                app.action_started=time.monotonic()-progress*ACTIONS['ball']['duration']
                app.render(time.monotonic())
            check('fetch_return_frames_render',True)
            app.cancel_action();app.set_scene(None)
            app.state.toilet_seconds=TOILET_URGENT_SECONDS
            check('toilet_starts',app.start_action('toilet'))
            app.action_started=time.monotonic()-3;app.render(time.monotonic())
            check('toilet_privacy_screen',bool(app.desktop.find_withtag('toilet_screen')))
            app.cancel_action();app.state.toilet_seconds=0
            app.state.outfit='red';app.state.scene='snow'
            check('portable_save_written',app.save() and app.data_path.is_file())
            saved=PetState.load(app.data_path)
            check('portable_save_read_back',saved.outfit=='red' and saved.scene=='snow')
        except Exception:
            results.append({'name':'exception','passed':False,'detail':traceback.format_exc()})
        finally:
            (output/'result.json').write_text(json.dumps({'initial':initial,'checks':results},ensure_ascii=False,indent=2),encoding='utf-8')
            app.close()
    app.root.after(1000,run)
