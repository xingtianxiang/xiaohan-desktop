"""Explicit macOS bundle checks, using a disposable HOME supplied by the runner."""
import json
from pathlib import Path
import sys
import time
import traceback
from desktop_platform import default_data_path
from mac_activity import key_count,idle_seconds
from model import PetState, ACTIONS, TOILET_URGENT_SECONDS


def schedule(app,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    results=[];initial=app.state.__dict__.copy()
    def check(name,value):
        results.append({'name':name,'passed':bool(value)})
        if not value:raise AssertionError(name)
    def run():
        try:
            check('mac_frozen',sys.platform=='darwin' and getattr(sys,'frozen',False))
            check('external_save_path',app.data_path==default_data_path())
            check('window_visible',app.root.winfo_ismapped())
            check('native_transparent_window',app.root.tk.getboolean(app.root.wm_attributes('-transparent')))
            check('quartz_counter_available',isinstance(key_count(),int) and idle_seconds()>=0)
            check('activity_polling_started',app.keyboard.ready.is_set() and not app.keyboard.error)
            app.show_toolbar();app.root.update()
            check('hover_menu_visible',len(app.buttons)==9 and app.toolbar.winfo_ismapped())
            app.buttons['feed'].event_generate('<ButtonPress-1>',x=32,y=30)
            check('feed_click',app.action=='feed');app.render(time.monotonic());app.cancel_action()
            for action in ('water','sleep','toy'):
                check(action,app.start_action(action));app.render(time.monotonic());app.cancel_action()
            app.popup();app.root.update()
            check('more_panel',app.more.win.winfo_ismapped() and 'toilet' in app.more.bars)
            check('panel_inside_screen',app.more.height<=app.root.winfo_screenheight())
            app.close_more()
            app.open_wardrobe();app.root.update();check('wardrobe',app.chooser.winfo_ismapped())
            app.change_outfit('red');app.hide_tools()
            for scene in ('park','snow'):
                app.set_scene(scene,walk=False);app.render(time.monotonic())
                check(scene,app.scene_photo is not None)
            app.open_fetch();check('throw_ball',app.throw_ball(.7))
            for fraction in (.2,.5,.8,.95):
                app.action_started=time.monotonic()-ACTIONS['ball']['duration']*fraction;app.render(time.monotonic())
            app.cancel_action();app.set_scene(None)
            app.state.toilet_seconds=TOILET_URGENT_SECONDS
            check('toilet',app.start_action('toilet'))
            app.action_started=time.monotonic()-3;app.render(time.monotonic())
            check('privacy_screen',bool(app.desktop.find_withtag('toilet_screen')))
            app.cancel_action();app.state.toilet_seconds=0
            check('save',app.save())
            check('read_back',PetState.load(app.data_path).outfit=='red')
        except Exception:
            results.append({'name':'exception','passed':False,'detail':traceback.format_exc()})
        finally:
            (output/'result.json').write_text(json.dumps({'initial':initial,'checks':results},ensure_ascii=False,indent=2),encoding='utf-8')
            app.close()
    app.root.after(1000,run)
