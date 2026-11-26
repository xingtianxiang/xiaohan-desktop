import ctypes
import json
import time
import traceback
import tkinter as tk
from PIL import ImageGrab
from model import PetState, ACTIONS, STAGES
from animation import frame_names

def schedule(app,out):
    out.mkdir(parents=True,exist_ok=True)
    results=[]
    backdrop=tk.Toplevel(app.root);backdrop.title('小汉验证');backdrop.geometry('820x560+40+40');backdrop.configure(bg='#ece9e2');backdrop.attributes('-topmost',True)
    tk.Label(backdrop,text='桌面宠物 · 悬停互动',bg='#ece9e2',fg='#708078',font=('Microsoft YaHei UI',14)).pack(anchor='nw',padx=24,pady=20)
    backdrop.update_idletasks()
    app.root.geometry('+410+130');app.root.lift()
    def record(name,passed,detail=''):results.append(dict(name=name,passed=bool(passed),detail=detail))
    def focus_window(win):
        win.lift()
        win.focus_force();deadline=time.monotonic()+1
        while time.monotonic()<deadline:
            app.root.update()
            focused=app.root.focus_displayof()
            if focused is not None and focused.winfo_toplevel()==win:
                app.root.update();return True
            time.sleep(.02)
        return False
    def screenshot(name):
        backdrop.lift();app.root.lift()
        if app.toolbar:app.toolbar.lift()
        if app.chooser:app.chooser.lift()
        if app.more:app.more.win.lift()
        app.render(time.monotonic());app.root.update();time.sleep(.08)
        ImageGrab.grab(bbox=(40,70,860,600)).save(out/(name+'.png'))
    def finish():
        app.keyboard.stop()
        record('listener_stopped',not app.keyboard.thread.is_alive() and not app.keyboard.error,app.keyboard.error)
        (out/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(results,ensure_ascii=False),flush=True)
        app.close()
    def begin():
        record('no_client_window',not hasattr(app,'panel'))
        record('display_name',app.root.title()=='小汉 · 桌面宠物')
        record('raw_input_registered',app.keyboard.ready.is_set() and not app.keyboard.error,app.keyboard.error)
        app.desktop.event_generate('<Enter>')
    def click_feed():
        record('hover_opens_icons',bool(app.toolbar and len(app.buttons)==9))
        screenshot('hover-icons')
        app.state.values['food']=40
        tile=app.buttons['feed']
        tile.event_generate('<ButtonPress-1>',x=32,y=25)
        tile.event_generate('<ButtonRelease-1>',x=32,y=25)
        record('feed_started_from_icon',app.action=='feed')
        record('overlap_rejected',not app.start_action('water'))
    def eating():screenshot('feeding')
    def after_feed():
        if app.action=='feed':return False
        record('feed_completed',app.state.values['food']>64)
        record('feed_cooldown',not app.start_action('feed'))
        app.state.values['water']=40;app.start_action('water')
    def after_water():
        if app.action=='water':return False
        record('water_completed',app.state.values['water']>69)
        app.show_toolbar();app.open_wardrobe();app.change_outfit('red')
        record('wardrobe_saved',PetState.load(app.data_path).outfit=='red')
        screenshot('wardrobe')
        app.buttons['toy'].event_generate('<ButtonPress-1>',x=32,y=25)
        record('toy_icon_opens_interactive_round',app.tug is not None and not app.tug.started)
        record('costume_in_action',app.pose(time.monotonic())[0].startswith('red_puppy_play'))
        app.cancel_action();record('cancel_no_reward',app.state.completed==2)
        app.set_scene('park');record('walking_pose','_walk' in app.pose(time.monotonic())[0])
    def outdoors():
        screenshot('outdoor')
        record('outdoor_composed_in_one_image',len(app.desktop.find_withtag('outdoor_scene'))==1 and app.scene_photo.width()==420)
    def keyboard():
        app.cancel_action();app.set_scene(None);app.hide_tools()
        record('outdoor_returns_to_desktop',not app.outdoor and (app.width,app.height)==(280,300))
        app.root.focus_force();app.root.update_idletasks();app._test_count=app.keyboard.count
        from ctypes import wintypes as W
        class KI(ctypes.Structure):_fields_=[('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]
        class MI(ctypes.Structure):_fields_=[('x',W.LONG),('y',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]
        class U(ctypes.Union):_fields_=[('ki',KI),('mi',MI)]
        class INPUT(ctypes.Structure):_fields_=[('type',W.DWORD),('data',U)]
        inputs=(INPUT*2)()
        # F24 exercises Raw Input without leaving a letter in the user's IME.
        for i,flags in enumerate((0,2)):inputs[i].type=1;inputs[i].data.ki=KI(0x87,0,flags,0,0)
        user=ctypes.WinDLL('user32',use_last_error=True);user.SendInput.argtypes=[W.UINT,ctypes.POINTER(INPUT),ctypes.c_int]
        n=user.SendInput(2,inputs,ctypes.sizeof(INPUT));record('native_input_injected',n==2,str(n))
    def check_keyboard():
        record('native_synthetic_key_received',app.keyboard.count>app._test_count)
        record('native_typing_rate_received',app.keyboard.speed(time.monotonic())>0)
        record('typing_pose_activated',app.pose(time.monotonic())[1]);screenshot('typing')
        app.state.keyboard_enabled=False;record('typing_toggle_off',not app.pose(time.monotonic())[1]);app.state.keyboard_enabled=True
    def stopped():
        record('typing_returns_idle',not app.pose(time.monotonic())[1])
        app.toggle_pause();record('pause_blocks_action',not app.start_action('pet'));app.toggle_pause()
        app.state.companion_seconds=STAGES[1][0];app.state.values['bond']=STAGES[1][1];app.state.promote();app.state.select_stage(1);app.save()
        record('growth_and_reload',PetState.load(app.data_path).stage==1)
        app.change_outfit('yellow');app.start_action('snack');record('yellow_snack_uses_standing_art',app.pose(time.monotonic())[0]=='yellow_teen')
        app.cancel_action();app.show_toolbar();ctypes.windll.user32.SetCursorPos(70,85);app.defer_hide()
    def hidden():
        record('hover_leave_hides_icons',app.toolbar is None)
        screenshot('pet-only')
    def more_panel():
        app.cancel_action();app.keyboard.last_activity=-100;app.flame.update(time.monotonic(),False,False)
        app.show_toolbar();app.root.update()
        record('more_button_mapped',bool(app.buttons['more'].winfo_ismapped()))
        app.buttons['more'].event_generate('<ButtonPress-1>',x=25,y=25)
        app.root.update()
        record('more_opens_compact_panel',app.more is not None and app.toolbar is None)
        panel=app.more
        record('more_inside_screen',0<=panel.win.winfo_x()<=app.root.winfo_screenwidth()-panel.width and 0<=panel.win.winfo_y()<=app.root.winfo_screenheight()-panel.height)
        record('more_shows_actions_first',panel.actions['snack'].winfo_ismapped() and not panel.growth_bar.winfo_ismapped()
               and not panel.bars['food'][1].winfo_ismapped() and not panel.switches['flames'].winfo_ismapped())
        panel.sections['growth'].invoke();app.root.update_idletasks()
        record('growth_is_reachable',panel.growth_bar.winfo_ismapped() and panel.stage_buttons[0].winfo_ismapped())
        panel.back.invoke()
        panel.sections['care'].invoke();app.root.update_idletasks()
        record('care_is_reachable',panel.bars['toilet'][1].winfo_ismapped() and panel.toilet_button.winfo_ismapped())
        panel.back.invoke()
        panel.sections['settings'].invoke()
        panel.switches['flames'].invoke()
        record('more_fire_setting_saved',not PetState.load(app.data_path).flames)
        panel.switches['flames'].invoke()
        panel.switches['keyboard_enabled'].invoke()
        record('more_keyboard_setting_saved',not PetState.load(app.data_path).keyboard_enabled)
        panel.switches['keyboard_enabled'].invoke()
        panel.back.invoke()
        panel.pause.invoke();panel.refresh()
        record('more_pause_disables_actions',app.paused and str(panel.actions['ball']['state'])=='disabled')
        app.root.update_idletasks()
        name,typing=app.pose(time.monotonic())
        record('pause_has_rest_pose_and_resume_control','_sleep' in name and not typing and app.resume_button.winfo_ismapped())
        screenshot('paused')
        app.resume_button.invoke();panel.refresh()
        record('resume_unpauses_pet',not app.paused and not app.resume_button.winfo_manager())
        panel.actions['snack'].invoke();panel.refresh()
        record('more_action_and_end',app.action=='snack' and str(panel.end['state'])=='normal')
        app.action_started=time.monotonic()-.90
        app.render(time.monotonic())
        record('snack_renders_own_sprite',str(app.care_photo)==app.desktop.itemcget('pet_sprite','image'))
        screenshot('snack')
        app.action_started=time.monotonic()-2.85
        before=app.state.completed
        panel.pause.invoke()
        elapsed=app.pause_started-app.action_started
        state_before=(app.state.companion_seconds,app.state.toilet_seconds,app.state.values.copy())
        deadline=time.monotonic()+.30
        while time.monotonic()<deadline:
            app.root.update()
            time.sleep(.02)
        record('pause_freezes_action_and_needs',app.action=='snack' and app.state.completed==before
               and state_before==(app.state.companion_seconds,app.state.toilet_seconds,app.state.values))
        app.resume_button.invoke()
        record('resume_preserves_elapsed_action',app.action=='snack' and abs(time.monotonic()-app.action_started-elapsed)<.1)
        panel.end.invoke();panel.refresh()
        record('more_cancel_action',app.action is None)
        screenshot('more-panel')
        x,y=panel.win.winfo_rootx(),panel.win.winfo_rooty()
        ImageGrab.grab(bbox=(x,y,x+panel.width,y+panel.height)).save(out/'more-panel-detail.png')
        record('close_button_visible',panel.close_button.winfo_ismapped() and '关闭' in panel.close_button.cget('text'))
        panel.close_button.invoke();record('close_button_closes_more',app.more is None)
        app.popup();app.more.sections['settings'].invoke()
        if not focus_window(app.more.win):raise RuntimeError('更多面板未获得焦点')
        app.more.close_button.event_generate('<Escape>')
        record('escape_closes_more_from_settings',app.more is None)
        app.popup();app.popup();record('more_toggle_closes_panel',app.more is None)
        app.desktop.event_generate('<ButtonPress-1>',x=140,y=200)
        app.desktop.event_generate('<ButtonRelease-1>',x=140,y=200)
        app.render(time.monotonic())
        record('mouse_does_not_ignite',app.flame.level==0 and not app.desktop.find_withtag('typing_flame'))
        app.hide_tools()
        app.set_scene(None)
    def speed_flame():
        from keyboard_activity import KeyboardActivity
        from flame import TypingFlame
        from copy import deepcopy
        saved_keyboard,saved_flame,saved_state=app.keyboard,app.flame,app.state
        heights={}
        try:
            app.state=deepcopy(app.state);app.state.stage=app.state.unlocked_stage=2;app.state.outfit='blue';app.action=None
            for label,rate in (('slow',2),('fast',10)):
                app.keyboard=KeyboardActivity();app.flame=TypingFlame(app.images)
                start=time.monotonic()-3
                for index in range(91):
                    now=start+index/30
                    if index%(30//rate)==0:app.keyboard.record_activity(now)
                    app.render(now)
                heights[label]=app.fire_photo.height()
                screenshot('speed-'+label)
            record('typing_speed_changes_visible_fire_size',heights['fast']>heights['slow']*2,str(heights))
        finally:
            app.keyboard,app.flame,app.state=saved_keyboard,saved_flame,saved_state
    def age_rendering():
        from copy import deepcopy
        saved=deepcopy(app.state)
        count=0
        try:
            for stage in range(3):
                for outfit in ('blue','red','yellow'):
                    app.state=PetState();app.state.stage=app.state.unlocked_stage=stage;app.state.outfit=outfit
                    for action,motion in [('feed','eat'),('water','drink'),('sleep','sleep'),('walk','walk'),('toy','play'),(None,'type')]:
                        now=time.monotonic()
                        if action=='toy':
                            app.action=None;app.start_action('toy')
                        else:app.action=action;app.action_started=now-.2
                        app.keyboard.last_activity=now if action is None else -100
                        app.render(now)
                        name,typing=app.pose(now)
                        if name not in frame_names(outfit,stage,motion) or typing!=(action is None):
                            raise AssertionError((stage,outfit,action,name))
                        if not app.desktop.find_all():raise AssertionError('Empty canvas')
                        count+=1
                        if action=='toy':app.cancel_action()
                    if outfit=='blue':screenshot(f'age-{stage}-typing')
                app.action=None;app.set_scene('park')
                screenshot(f'age-{stage}-outdoor');app.cancel_action();app.set_scene(None)
            record('age_outfit_actions_rendered',count==54,str(count))
        finally:
            app.state=saved;app.action=None;app.keyboard.last_activity=-100
            app.save()
    def fetch_break():
        from work_break import WORK_SECONDS, BREAK_SECONDS
        app.state.cooldowns.pop('ball',None)
        before=app.state.completed
        app.popup();app.more.actions['ball'].invoke();app.root.update()
        record('fetch_opens_ready_without_throw',app.fetch_mode and app.outdoor and app.width==420 and app.action is None and app.more is None)
        start_position=(app.root.winfo_x(),app.root.winfo_y())
        app.desktop.event_generate('<ButtonPress-1>',x=220,y=245)
        record('mouse_press_starts_charge',app.charge.started is not None and app.action is None)
        app.charge.started=time.monotonic()-1.25
        app.render(time.monotonic());app.root.update_idletasks()
        record('charge_shows_vertical_bar_and_trajectory',bool(app.desktop.find_withtag('power_fill')) and bool(app.desktop.find_withtag('throw_trajectory')))
        x,y=app.root.winfo_rootx(),app.root.winfo_rooty()
        ImageGrab.grab(bbox=(x,y,x+app.width,y+app.height)).save(out/'charged-throw.png')
        app.desktop.event_generate('<B1-Motion>',x=240,y=250)
        app.desktop.event_generate('<ButtonRelease-1>',x=240,y=250)
        record('release_throws_at_measured_power',app.action=='ball' and .60<app.fetch_power<.9 and app.charge.started is None)
        record('charge_does_not_drag_window',start_position==(app.root.winfo_x(),app.root.winfo_y()))
        frozen=app.fetch_power
        app.desktop.event_generate('<ButtonPress-1>',x=220,y=245)
        app.desktop.event_generate('<ButtonRelease-1>',x=220,y=245)
        record('busy_click_does_not_rethrow',app.action=='ball' and app.fetch_power==frozen and app.charge.started is None)
        for phase in (.05,.3,.53,.78,.85):
            app.action_started=time.monotonic()-phase*ACTIONS['ball']['duration']
            app.render(time.monotonic());app.root.update_idletasks()
            screenshot('fetch-'+str(phase))
        record('discrete_distance_buttons_removed',not any(app.desktop.find_withtag('throw_'+d) for d in ('near','middle','far')))
        record('fetch_still_running_before_cancel',app.action=='ball')
        app.set_scene(None)
        record('closing_fetch_cancels_without_reward',app.action is None and app.state.completed==before)
        app.open_fetch();app.begin_charge();app.escape_fetch()
        record('escape_cancels_charge_without_throw',app.fetch_mode and app.charge.started is None and app.action is None and app.root.grab_current() is None)
        app.begin_charge();app.desktop.event_generate('<ButtonRelease-1>',x=-10,y=245)
        record('outside_release_cancels_charge',app.charge.started is None and app.action is None)
        focus_target=app.floating(150,62)
        focus_target.geometry('+80+95')
        try:
            app.root.update()
            if not focus_window(app.root): raise RuntimeError('测试窗口未获得焦点')
            record('charge_started_before_focus_change',app.begin_charge())
            if not focus_window(focus_target): raise RuntimeError('焦点未切换至单独的测试窗口')
            record('focus_loss_cancels_charge',app.charge.started is None and app.root.grab_current() is None)
        finally:
            focus_target.destroy()
        if not focus_window(app.root): raise RuntimeError('测试窗口未重新获得焦点')
        app.desktop.event_generate('<ButtonRelease-1>',x=220,y=245)
        record('release_after_focus_loss_does_not_throw',app.action is None)
        app.begin_charge();app.popup()
        record('opening_more_cancels_charge',app.charge.started is None and app.more is not None)
        app.close_more()
        app.begin_charge();app.toggle_pause()
        record('pause_cancels_charge',app.charge.started is None and not app.begin_charge())
        app.toggle_pause();app.begin_charge();app.set_scene(None)
        record('closing_page_cancels_charge',not app.fetch_mode and app.charge.started is None and app.root.grab_current() is None)
        app.work_break.work=WORK_SECONDS;app.render(time.monotonic())
        record('rest_reminder_visible',any('休息 10 分钟' in app.desktop.itemcget(i,'text') for i in app.desktop.find_all() if app.desktop.type(i)=='text'))
        app.popup();app.more.refresh();app.root.update()
        record('rest_snooze_enabled',str(app.more.snooze['state'])=='normal')
        app.more.snooze.invoke();app.more.refresh()
        record('rest_snooze_defers',not app.work_break.due and str(app.more.snooze['state'])=='disabled')
        app.more.sections['settings'].invoke()
        app.more.switches['break_reminders'].invoke()
        record('rest_switch_saved',not PetState.load(app.data_path).break_reminders)
        app.more.switches['break_reminders'].invoke()
        app.work_break.work=WORK_SECONDS
        app.work_break.update(time.monotonic(),BREAK_SECONDS)
        record('full_break_resets_work',app.work_break.work==0)
        app.more.refresh();app.root.update_idletasks()
        panel=app.more;x,y=panel.win.winfo_rootx(),panel.win.winfo_rooty()
        ImageGrab.grab(bbox=(x,y,x+panel.width,y+panel.height)).save(out/'rest-panel.png')
        record('updated_panel_inside_screen',panel.height<=app.root.winfo_screenheight() and panel.width<400)
        app.close_more()
        app.open_fetch();app.throw_ball(.2);app.action_started=time.monotonic()-ACTIONS['ball']['duration']
        app._fetch_completed_before=app.state.completed
        app._fetch_count_before=app.fetch_count
    def fetch_finished():
        record('fetch_completion_awards_once',app.action is None and app.state.completed==app._fetch_completed_before+1 and app.fetch_count==app._fetch_count_before+1)
        record('fetch_can_repeat_immediately',app.begin_charge())
        app.cancel_charge()
        app.set_scene(None)
    steps=iter([(900,begin),(500,click_feed),(1200,eating),(4400,after_feed),(4700,after_water),(1000,outdoors),(600,keyboard),(150,check_keyboard),(1300,stopped),(800,hidden),(200,more_panel),(200,speed_flame),(200,age_rendering),(200,fetch_break),(300,fetch_finished),(200,finish)])
    def next_step():
        try:delay,fn=next(steps)
        except StopIteration:return
        deadline=time.monotonic()+delay/1000+10
        def execute():
            try:
                done=fn()
                if done is False:
                    if time.monotonic()>deadline:raise TimeoutError(fn.__name__)
                    app.root.after(100,execute)
                elif not app.closing:next_step()
            except Exception:
                record(fn.__name__,False,traceback.format_exc());finish()
        app.root.after(delay,execute)
    next_step()
