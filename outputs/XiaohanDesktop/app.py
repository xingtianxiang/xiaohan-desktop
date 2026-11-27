import argparse
import ctypes
import json
import math
import os
import sys
from pathlib import Path
import time
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageOps
from model import PetState, ACTIONS, STAGES, OUTFITS, NEEDS, NEED_ACTIONS, MINI_GAMES, NAP_AFTER_SECONDS
from keyboard_activity import KeyboardActivity, user_idle_seconds
from animation import AGES, FETCH_POSES, fetch_asset, motion_frame, required_assets
from typing_keys import KEYCAP_SECONDS, draw_typing_keys, vk_label
from care_motion import bowl_frame, snack_frame, sleep_frame
from outdoor import OutdoorRenderer
from flame import TypingFlame
from more_panel import CareStatusStrip, MorePanel
from fetch_game import fetch_frame, walk_position, ThrowCharge
from throw_controls import draw_throw_controls
from work_break import WorkBreak
from trip_view import TripPicker, draw_scene_button, draw_scene_controls, draw_scene_notice
from tug_game import TugRound
from tug_view import POSE_STEPS, TUG_SIZE, TUG_EXIT, TUG_RETRY, draw_tug, toy_tip, tug_pose
from desktop_platform import IS_MAC, UI_FONT, TRANSPARENT, default_data_path, screen_bounds, MacInstanceLock
from farewell import FarewellAnimation
from dance import STOP_BUTTON, STAGE_SIZE, DanceVideo
from minigames import GAME_SIZE, CatchGame, HurdleGame, MemoryGame, ShellGame
from game_view import GameArt, catch_geometry, draw_game, hurdle_half_width
import updater
from version import VERSION
from mouse_play import (ART, HEADS, PET_HOLD, PET_RELEASE, CircleGesture, Facing, HeadRig, PetDetector, Petting,
                        body_middle, head_point, heart_positions, pose_frame)

BASE=Path(__file__).resolve().parent
KEY=TRANSPARENT
PAPER='#fffaf2'
INK='#30504c'
TEAL='#368b7d'
TOOLBAR_COLUMNS=3
TOOLBAR_WIDTH=208
TOOLBAR_HEIGHT=256
RECALL_WIDTH=108
RECALL_HEIGHT=36
UPDATE_FIRST_CHECK_MS=15_000
UPDATE_INTERVAL_MS=6*3600*1000
SAVE_HINT=('小汉会继续陪你，但进度暂时存不下来。请退出后把整个“小汉”文件夹移到桌面或 D 盘等普通文件夹再打开，'
           '不要放在微信、QQ 的接收文件夹或 Program Files 里。')

class DesktopPet:
    def __init__(self,root,data_path,smoke=None,update_manifest=None):
        self.root,self.data_path,self.smoke=root,Path(data_path),smoke
        self.state=PetState.load(data_path)
        self.images={p.stem:Image.open(p).convert('RGBA') for p in (BASE/'assets').glob('*.png')
                     if not p.stem.endswith('_gait')}
        for name in required_assets(OUTFITS):
            if name not in self.images: raise RuntimeError('缺少素材：'+name)
        for name in ('dance_stage.webp','dance_stage.wav'):
            if not (BASE/'assets'/name).is_file(): raise RuntimeError('缺少素材：'+name)
        self.typing_boards=json.loads((BASE/'assets/typing-keyboards.json').read_text(encoding='utf-8'))
        for outfit in OUTFITS:
            for age in AGES:
                if outfit+'_'+age not in self.typing_boards:raise RuntimeError('缺少键盘位置：'+outfit+'_'+age)
        self.fetch_anchors=json.loads((BASE/'assets/fetch-anchors.json').read_text(encoding='utf-8'))
        for outfit in OUTFITS:
            for stage in range(3):
                for pose in FETCH_POSES:
                    if fetch_asset(outfit,stage,pose) not in self.fetch_anchors:raise RuntimeError('缺少捡球动作定位数据')
        self.outdoor_renderer=OutdoorRenderer(self.images); self.scene_photo=None
        self.flame=TypingFlame(self.images); self.fire_photo=None; self.more=None; self.last_panel_refresh=0.
        self.work_break=WorkBreak(); self.fetch_power=.55; self.fetch_count=0
        self.fetch_mode=False; self.fetch_from_outdoor=False; self.charge=ThrowCharge()
        self.tug=None; self.tug_frames={}
        self.dance=DanceVideo(BASE/'assets/dance_stage.webp',BASE/'assets/dance_stage.wav',keyed=os.name=='nt')
        self.stage_return=None
        self.game=self.game_key=self.game_result=self.game_art=None
        self.napping=False; self.nap_energy=0.; self.rest_state='rest'
        self.tug_space_down=False; self.tug_key_reset=None
        self.tug_origin=None
        self.walk_clock=0.;self.walk_resume=None;self.fetch_origin=walk_position(0.)
        self.keyboard=KeyboardActivity(); self.keyboard.start()
        self.keycaps=[]; self.key_seen=0.; self.sync_key_capture()
        self.tk_images={}; self.action=None; self.action_started=0.; self.paused=False; self.closing=False
        self.pause_started=0.; self.hidden=False
        self.notice='鼠标移到我身上试试'; self.notice_until=time.monotonic()+6
        self.last_tick=time.monotonic(); self.last_save=self.last_tick; self.keyboard_error_shown=False
        self.save_error_shown=False
        self.drag=None; self.toolbar=None; self.status_strip=None; self.chooser=None; self.hide_job=None; self.outdoor=False
        self.buttons={}; self.width,self.height=280,300; self.hit=None
        self.trip_picker=None;self.scene_controls={};self.pressed_control=None
        root.title('小汉 · 桌面宠物'); root.overrideredirect(True); root.attributes('-topmost',True); root.configure(bg=KEY)
        if os.name=='nt': root.wm_attributes('-transparentcolor',KEY)
        elif IS_MAC: root.wm_attributes('-transparent',True)
        position=self.state.window_position or (root.winfo_screenwidth()-330,root.winfo_screenheight()-380)
        self.place_pet_window(*position)
        self.desktop=tk.Canvas(root,width=280,height=300,bg=KEY,highlightthickness=0); self.desktop.pack()
        self.recall_button=tk.Button(root,text='叫回小汉',command=self.show_pet,
                                     bg='#e3eee3',fg=INK,activebackground='#d1e4d6',
                                     font=(UI_FONT,10,'bold'),relief='flat',borderwidth=0,
                                     highlightthickness=1,highlightbackground=TEAL,cursor='hand2')
        self.resume_button=tk.Button(self.desktop,text='▶  继续陪伴',command=self.toggle_pause,
                                     bg='#e3eee3',fg=INK,activebackground='#d1e4d6',
                                     font=(UI_FONT,10,'bold'),relief='flat',borderwidth=0,
                                     highlightthickness=1,highlightbackground='#e3eee3',highlightcolor=TEAL,
                                     padx=14,pady=4,cursor='hand2')
        self.desktop.bind('<Enter>',lambda e:self.show_toolbar()); self.desktop.bind('<Leave>',lambda e:self.defer_hide())
        # Tk reports the cursor position on request; no system-wide mouse hook is installed.
        self.stroke=PetDetector(); self.facing=Facing(); self.petting=Petting(); self.circle=CircleGesture()
        self.pointer=root.winfo_pointerxy
        self.rigs={}; self.pose_key=self.pose_photo=None
        self.desktop.bind('<Motion>',self.pointer_motion)
        self.desktop.bind('<ButtonPress-1>',self.press); self.desktop.bind('<B1-Motion>',self.move)
        self.desktop.bind('<ButtonRelease-1>',self.release); self.desktop.bind('<Button-3>',self.popup)
        self.desktop.bind('<KeyPress-space>',self.tug_key_down)
        self.desktop.bind('<KeyRelease-space>',self.tug_key_up)
        if IS_MAC:
            self.desktop.bind('<Button-2>',self.popup)
            self.desktop.bind('<Control-Button-1>',self.popup)
            root.bind('<Command-q>',lambda event:self.request_exit())
            root.createcommand('::tk::mac::Quit',self.request_exit)
        root.bind('<Escape>',self.escape_fetch)
        root.bind('<FocusOut>',lambda e:root.after_idle(self.cancel_unfocused_gesture))
        root.protocol('WM_DELETE_WINDOW',self.request_exit); root.after(80,self.tick)
        # Only the portable Windows build replaces its own files; source runs and Mac builds never update.
        self.updates_supported=os.name=='nt' and getattr(sys,'frozen',False)
        self.install_dir=Path(sys.executable).resolve().parent
        self.update_source=update_manifest or updater.MANIFEST_URL
        self.update_allow_file=update_manifest is not None
        self.update_offer=self.update_check_job=self.update_install_job=None
        self.update_status='还没有检查'
        if self.updates_supported:
            updater.cleanup(self.install_dir)
            root.after(UPDATE_FIRST_CHECK_MS,self.schedule_update_checks)

    def photo(self,name,size,flip=False):
        key=(name,size,flip)
        if key not in self.tk_images:
            im=ImageOps.fit(self.images[name],size,Image.Resampling.LANCZOS) if name.startswith('scene_') else self.images[name].resize(size,Image.Resampling.LANCZOS)
            if flip: im=ImageOps.mirror(im)
            # Windows color-key transparency cannot blend partial alpha at sprite edges.
            if os.name=='nt' and not name.startswith('scene_'):im.putalpha(im.getchannel('A').point(lambda value:255 if value>=128 else 0))
            self.tk_images[key]=ImageTk.PhotoImage(im,master=self.root)
        return self.tk_images[key]

    def say(self,text,seconds=4): self.notice,self.notice_until=text,time.monotonic()+seconds

    def write_save(self):
        try: self.state.save(self.data_path)
        except OSError as exc: return str(exc)
        self.save_error_shown=False
        return ''

    def save(self):
        error=self.write_save()
        if not error: return True
        # Autosave runs every 30 seconds; a modal box each time would make the pet unusable.
        if self.save_error_shown: self.say('存档失败，进度暂时没有保存',6)
        else:
            self.save_error_shown=True
            messagebox.showerror('存档失败',error+'\n\n'+SAVE_HINT,parent=self.root)
        return False

    def press(self,e):
        for key,(left,top,right,bottom) in self.scene_controls.items():
            if left<=e.x<=right and top<=e.y<=bottom:
                self.pressed_control=key;self.drag=None;return
        if self.game is not None:
            self.desktop.focus_force()
            if not self.paused:self.game.press(e.x,e.y)
            return
        if self.tug is not None or self.action=='dance':
            # Focus lets Esc reach the window; neither scene can be dragged.
            self.desktop.focus_force()
            return
        if self.fetch_mode and 37<=e.y<self.height-26:
            self.begin_charge(); return
        self.drag=(e.x_root,e.y_root,self.root.winfo_x(),self.root.winfo_y())

    def move(self,e):
        if self.tug is not None:
            return
        if self.drag:
            sx,sy,x,y=self.drag
            self.state.window_position=self.place_pet_window(x+e.x_root-sx,y+e.y_root-sy)
            self.place_toolbar()

    def release(self,e):
        if self.pressed_control is not None:
            key=self.pressed_control;self.pressed_control=None
            box=self.scene_controls.get(key)
            if box and box[0]<=e.x<=box[2] and box[1]<=e.y<=box[3]:self.outdoor_action(key)
            return
        if self.game is not None:
            self.game.release()
            return
        if self.tug is not None:
            return
        if self.charge.started is not None:
            power=self.charge.release(time.monotonic())
            self.cancel_charge()
            if self.fetch_mode and 0<=e.x<self.width and 37<=e.y<self.height-26:
                self.throw_ball(power)
            else: self.say('这球先不扔，重新蓄力吧')
            return
        if self.drag:
            if abs(e.x_root-self.drag[0])+abs(e.y_root-self.drag[1])<8:self.show_toolbar()
            else:self.save()
        self.drag=None

    def floating(self,width,height):
        win=tk.Toplevel(self.root); win.overrideredirect(True); win.attributes('-topmost',True)
        win.configure(bg=PAPER); win.geometry(f'{width}x{height}')
        win.bind('<Enter>',lambda e:self.cancel_hide()); win.bind('<Leave>',lambda e:self.defer_hide())
        return win

    def show_toolbar(self):
        self.cancel_hide()
        if (self.hidden or self.paused or self.more or self.outdoor or self.trip_picker or self.tug is not None
                or self.action=='dance' or self.game is not None): return
        if self.toolbar and self.toolbar.winfo_exists(): return
        self.toolbar=self.floating(TOOLBAR_WIDTH,TOOLBAR_HEIGHT); self.buttons={}
        actions=[('feed','喂食'),('water','喝水'),('toilet','上厕所'),('pet','摸摸'),('toy','小游戏'),('outdoor','出游'),('wardrobe','换装'),('sleep','睡觉'),('more','更多')]
        for i,(key,title) in enumerate(actions):
            tile=tk.Canvas(self.toolbar,width=64,height=66,bg=PAPER,highlightthickness=0,cursor='hand2')
            tile.grid(row=i//TOOLBAR_COLUMNS,column=i%TOOLBAR_COLUMNS,padx=2,pady=2); self.draw_icon(tile,key)
            tile.create_text(32,56,text=title,fill=INK,font=(UI_FONT,9))
            tile.bind('<Enter>',lambda e,t=tile:(self.cancel_hide(),t.configure(bg='#e5f0e8')))
            tile.bind('<Leave>',lambda e,t=tile:(t.configure(bg=PAPER),self.defer_hide()))
            tile.bind('<Button-1>',lambda e,k=key:self.toolbar_action(k,e)); self.buttons[key]=tile
        self.status_strip=CareStatusStrip(self.toolbar,lambda:self.popup(page='care'))
        self.status_strip.grid(row=3,column=0,columnspan=TOOLBAR_COLUMNS,padx=4,pady=(3,5))
        self.status_strip.bind('<Enter>',lambda event:self.cancel_hide())
        self.status_strip.bind('<Leave>',lambda event:self.defer_hide())
        self.status_strip.refresh(self.state)
        self.place_toolbar()

    def draw_icon(self,c,key):
        if key=='feed':
            for x,y in [(23,22),(31,19),(39,22)]: c.create_oval(x-4,y-4,x+4,y+4,fill='#d7a064',outline='')
            c.create_polygon(13,25,51,25,46,40,18,40,fill='#85beb4',outline=TEAL,width=2); c.create_line(12,25,52,25,fill=TEAL,width=3)
        elif key=='water':
            c.create_polygon(32,9,18,29,19,37,25,42,39,42,45,37,46,29,fill='#86bed5',outline='#4f8da9',width=2,smooth=True)
            c.create_line(25,29,24,33,28,37,fill='white',width=2,smooth=True)
        elif key=='pet': c.create_polygon(32,40,14,25,15,16,23,12,32,20,41,12,49,16,50,25,fill='#e8a3a1',outline='#c77f7c',width=2,smooth=True)
        elif key=='toy':
            c.create_line(21,32,32,26,44,19,fill='#b6544b',width=7,smooth=True,capstyle='round')
            c.create_line(24,30,38,22,fill='#efb093',width=2,capstyle='round')
            c.create_oval(12,27,25,40,fill=PAPER,outline='#b6544b',width=4)
            c.create_oval(40,12,53,25,fill=PAPER,outline='#b6544b',width=4)
        elif key=='outdoor':
            c.create_rectangle(29,29,35,43,fill='#bc9467',outline='')
            c.create_polygon(32,8,15,29,24,29,18,36,46,36,40,29,49,29,fill='#89b78b',outline='#638e68',width=2)
        elif key=='wardrobe': c.create_polygon(23,13,16,17,10,27,19,31,22,25,22,42,43,42,43,25,46,31,55,27,49,17,41,13,36,19,28,19,fill='#e9c976',outline='#b49d56',width=2)
        elif key=='sleep':
            c.create_oval(18,10,46,40,fill='#e8ca79',outline=''); c.create_oval(29,6,51,30,fill=PAPER,outline='')
        elif key=='toilet':
            c.create_polygon(17,15,45,15,52,39,12,39,fill='#dcebe2',outline=TEAL,width=2)
            c.create_line(21,20,41,20,46,34,18,34,21,20,fill='#8ebba8',width=2)
            c.create_oval(27,26,37,33,fill=TEAL,outline='')
            for px,py in ((24,23),(30,21),(36,21),(41,24)):c.create_oval(px-2,py-2,px+2,py+2,fill=TEAL,outline='')
        else:
            for x in (19,32,45): c.create_oval(x-3,24,x+3,30,fill=TEAL,outline='')

    def place_toolbar(self):
        if self.more: self.more.place()
        if self.trip_picker:self.trip_picker.place()
        if not self.toolbar: return
        x,y=self.root.winfo_x(),self.root.winfo_y()
        left,top,right,bottom=screen_bounds(self.root,x+self.width/2,y+self.height/2)
        tx=x-TOOLBAR_WIDTH-4 if x-left>=TOOLBAR_WIDTH+4 else x+self.width+4; ty=y+60
        tx=max(left,min(right-TOOLBAR_WIDTH,tx)); ty=max(top,min(bottom-TOOLBAR_HEIGHT,ty))
        self.toolbar.geometry(f'+{tx}+{ty}')
        if self.chooser:
            cy=ty+TOOLBAR_HEIGHT+4
            if cy+160>bottom: cy=ty-164
            cx=max(left,min(right-276,tx))
            self.chooser.geometry(f'+{cx}+{max(top,cy)}')

    def cancel_hide(self):
        if self.hide_job: self.root.after_cancel(self.hide_job); self.hide_job=None

    def defer_hide(self): self.cancel_hide(); self.hide_job=self.root.after(450,self.maybe_hide)

    def maybe_hide(self):
        self.hide_job=None; px,py=self.root.winfo_pointerxy()
        if self.more or self.trip_picker: return
        for win in (self.toolbar,self.chooser):
            if win and win.winfo_exists():
                x,y=win.winfo_rootx(),win.winfo_rooty()
                if x<=px<x+win.winfo_width() and y<=py<y+win.winfo_height(): return
        rx,ry=px-self.root.winfo_rootx(),py-self.root.winfo_rooty()
        if self.outdoor and 0<=rx<self.width and 0<=ry<290:return
        if self.pet_at(rx,ry):return
        self.hide_tools()

    def pet_at(self,rx,ry):
        """Whether a point in the pet window lands on her fur rather than a transparent margin."""
        if not self.hit:return False
        left,top,size,name,flip=self.hit
        if not (left<=rx<left+size and top<=ry<top+size):return False
        im=self.images[name]; ix=min(im.width-1,int((rx-left)*im.width/size)); iy=min(im.height-1,int((ry-top)*im.height/size))
        if flip:ix=im.width-1-ix
        return im.getpixel((ix,iy))[3]>40

    def pet_zone(self,rx,ry):
        """None off her fur, 'head' on her head, otherwise 'body'."""
        if not self.pet_at(rx,ry):return None
        left,top,size,_,flip=self.hit
        hx,hy=head_point(self.state.stage,(left,top,size/ART),not flip)
        return 'head' if math.hypot(rx-hx,ry-hy)<=HEADS[self.state.stage]['radius']*size/ART*1.1 else 'body'

    def pointer_motion(self,e):
        if self.outdoor or self.hidden or self.paused or self.action or self.fetch_mode or self.tug is not None:
            self.stroke.reset();return
        if self.stroke.feed(e.x,e.y,time.monotonic(),self.pet_zone(e.x,e.y)):self.stroke_pet()

    def stroke_pet(self):
        now=time.monotonic()
        # She leans into every rub; the 摸摸 reward and its message only come when it is off cooldown,
        # and while it cools down she just enjoys it instead of nagging.
        self.petting.hold(now,now+PET_HOLD)
        if self.state.check('pet',time.time()):return False
        if not self.start_action('pet'):return False
        self.say('好舒服～再摸摸',3)
        return True

    def facing_applies(self,typing):
        return not typing and self.action in (None,'pet') and not self.paused and not self.fetch_mode and not self.outdoor

    def follow_pointer(self,now):
        if self.hidden or self.paused:
            self.circle.reset();return
        if self.outdoor or self.fetch_mode or self.tug is not None or self.action not in (None,'pet'):
            # Other actions and scenes have their own left-facing poses; pick up from there afterwards.
            self.facing.rest();self.petting.stop();self.circle.reset();return
        if self.action=='pet':self.petting.hold(now,self.action_started+ACTIONS['pet']['duration']-PET_RELEASE)
        # Idle paintings are drawn 240px square, bottom-centred at (width/2, 275) in the pet window.
        rx,ry=self.root.winfo_rootx(),self.root.winfo_rooty()
        canvas=(rx+self.width/2-120,ry+275-240,240/ART)
        pointer=self.pointer()
        self.facing.update(now,pointer,self.state.stage,canvas,petting=self.petting.amount(now),follow=self.state.mouse_follow)
        if self.action or self.petting.active(now):self.circle.reset()
        elif self.circle.feed(pointer,body_middle(self.state.stage,canvas,self.facing.left),now,
                              self.pet_at(pointer[0]-rx,pointer[1]-ry)):
            self.start_action('dance')

    def posed_sprite(self,name,flip,size,x_scale,y_scale,tail):
        """Her painting with head, ears and tail bent and squashed for a hop; rebuilt only when it changes."""
        idle=name==self.state.outfit+'_'+AGES[self.state.stage]
        head=tuple(round(v*4)/4 for v in self.facing.head) if idle else (0.,0.)
        ears=round(self.facing.ears*50)/50 if idle else 0.
        tail=round(tail*4)/4 if idle else 0.
        dims=(round(size*x_scale),round(size*y_scale))
        if head==(0.,0.) and not ears and not tail:return self.photo(name,dims,flip)
        key=(name,flip,dims,head,ears,tail)
        if key!=self.pose_key:
            if name not in self.rigs:self.rigs[name]=HeadRig(self.images[name],self.state.stage)
            frame=pose_frame(self.rigs[name],flip=flip,head=head,ears=ears,tail=tail).resize(dims,Image.Resampling.LANCZOS)
            if os.name=='nt':frame.putalpha(frame.getchannel('A').point(lambda a:255 if a>=128 else 0))
            self.pose_key,self.pose_photo=key,ImageTk.PhotoImage(frame,master=self.root)
        return self.pose_photo

    def hide_tools(self):
        self.close_trip_picker()
        self.cancel_hide()
        for win in (self.chooser,self.toolbar):
            if win: win.destroy()
        self.chooser=self.toolbar=self.status_strip=None; self.buttons={}

    def toolbar_action(self,key,event=None):
        if key=='wardrobe': self.open_wardrobe()
        elif key=='outdoor': self.scene_menu(event)
        elif key=='more': self.popup(event)
        elif key=='toy': self.popup(event,page='games')
        else: self.start_action(key)

    def open_wardrobe(self):
        if self.chooser: self.chooser.destroy()
        self.chooser=self.floating(276,160)
        for i,(key,title) in enumerate(OUTFITS.items()):
            tile=tk.Canvas(self.chooser,width=90,height=156,bg=PAPER,highlightthickness=0,cursor='hand2'); tile.grid(row=0,column=i)
            tile.create_image(45,100,image=self.photo(key+'_'+AGES[self.state.stage],(90,100)),anchor='s')
            tile.create_text(45,118,text=title,fill=INK,font=(UI_FONT,9))
            tile.create_text(45,140,text='✓ 已穿上' if key==self.state.outfit else '穿这套',fill=TEAL,font=(UI_FONT,9))
            tile.bind('<Button-1>',lambda e,k=key:self.change_outfit(k)); tile.bind('<Enter>',lambda e:self.cancel_hide()); tile.bind('<Leave>',lambda e:self.defer_hide())
        self.place_toolbar()

    def change_outfit(self,key):
        self.state.outfit=key; self.save(); self.say('换上'+OUTFITS[key]+'啦')
        if self.chooser: self.open_wardrobe()

    def scene_menu(self,event=None):
        if self.trip_picker:self.trip_picker.win.lift();return
        self.cancel_charge();self.hide_tools();self.close_more()
        self.trip_picker=TripPicker(self)

    def close_trip_picker(self):
        if self.trip_picker:
            self.trip_picker.win.destroy();self.trip_picker=None

    def outdoor_action(self,key):
        if key=='home':self.set_scene(None)
        elif key=='scene':self.scene_menu()
        elif key=='more':self.popup()
        elif key=='care':self.popup(page='care')
        elif key=='leave_fetch':self.close_fetch()
        elif key=='leave_tug':self.close_tug()
        elif key=='retry_tug':self.tug=TugRound(ACTIONS['toy']['duration'])
        elif key=='stop_dance':self.cancel_action()
        elif key=='leave_game':self.close_game()
        elif key=='start_game':self.game.start()
        elif key=='retry_game':self.retry_game()
        elif key in NEED_ACTIONS.values():self.start_action(key)
        elif key=='walk':
            if self.action=='walk':self.cancel_action()
            else:self.start_action('walk')
        elif key=='ball':
            self.open_fetch()

    def set_scene(self,scene,walk=True):
        if scene and self.action not in (None,'walk','ball'):
            self.say('等这次互动结束，再一起出门吧');return False
        if self.tug is not None:
            self.close_tug()
        self.hide_tools();self.scene_controls={};self.pressed_control=None
        self.cancel_charge(); self.fetch_mode=False; self.fetch_from_outdoor=False
        self.walk_resume=None
        if self.action in ('walk','ball'): self.cancel_action()
        self.walk_clock=0.
        self.outdoor=scene is not None
        if scene: self.state.scene=scene
        self.width,self.height=(420,330) if self.outdoor else (280,300)
        self.resize_window()
        self.place_toolbar(); self.save(); self.say('一起去走走吧' if scene else '回到你身边啦')
        if scene and walk: self.start_action('walk')

    def place_pet_window(self,x,y):
        left,top,right,bottom=screen_bounds(self.root,x+self.width/2,y+self.height/2)
        x=max(left,min(right-self.width,x))
        y=max(top,min(bottom-self.height,y))
        self.root.geometry(f'{self.width}x{self.height}+{x}+{y}')
        return x,y

    def resize_window(self,position=None):
        if position is None:
            position=self.state.window_position or (self.root.winfo_x(),self.root.winfo_y())
        self.place_pet_window(*position)
        self.desktop.configure(width=self.width,height=self.height)

    def hide_pet(self):
        if self.hidden:return
        self.end_dance()
        if self.game is not None:self.close_game()
        x,y=self.root.winfo_x(),self.root.winfo_y()
        if self.state.window_position is None:
            self.state.window_position=(x,y)
        self.stop_gesture()
        self.close_more()
        self.hide_tools()
        self.drag=self.pressed_control=None
        self.hidden=True
        self.flame.update(time.monotonic(),False,False)
        self.desktop.pack_forget()
        self.recall_button.pack(fill='both',expand=True)
        left,top,right,bottom=screen_bounds(self.root,x+self.width/2,y+self.height/2)
        edge_x=left+6 if x+self.width/2<(left+right)/2 else right-RECALL_WIDTH-6
        edge_y=max(top,min(bottom-RECALL_HEIGHT,y+(self.height-RECALL_HEIGHT)//2))
        self.root.geometry(f'{RECALL_WIDTH}x{RECALL_HEIGHT}+{edge_x}+{edge_y}')
        self.save()

    def show_pet(self):
        if not self.hidden:return
        self.hidden=False
        self.recall_button.pack_forget()
        self.resize_window()
        self.desktop.pack()
        self.render(time.monotonic())

    def popup(self,event=None,*,page='home'):
        self.stop_gesture()
        if self.more:
            if self.more.page==page:self.close_more()
            else:self.more.show(page)
            return
        self.hide_tools();self.more=MorePanel(self)
        if page!='home':self.more.show(page)

    def close_more(self):
        if self.more:
            self.more.win.destroy();self.more=None

    def sync_key_capture(self):
        """Which keys go down is read only while keycaps are on and she follows typing."""
        capture=self.state.key_bubbles and self.state.keyboard_enabled
        self.keyboard.capture_keys=capture
        if not capture:
            self.keyboard.keys.clear();self.keycaps=[]

    def take_keys(self,now):
        for at,vk in list(self.keyboard.keys):
            if at>self.key_seen:
                self.key_seen=at
                label=vk_label(vk)
                if label:self.keycaps.append((at,label))
        self.keycaps=[keycap for keycap in self.keycaps if now-keycap[0]<KEYCAP_SECONDS]

    def set_option(self,key,value):
        setattr(self.state,key,value)
        if key in ('key_bubbles','keyboard_enabled'):self.sync_key_capture()
        if key=='break_reminders': self.work_break=WorkBreak()
        if key=='update_checks' and value: self.request_update_check()
        self.save(); self.say('已开启' if value else '已关闭')

    def schedule_update_checks(self):
        self.request_update_check()
        self.root.after(UPDATE_INTERVAL_MS,self.schedule_update_checks)

    def request_update_check(self):
        if not self.updates_supported or not self.state.update_checks or self.update_check_job or self.update_install_job:
            return False
        source,allow_file=self.update_source,self.update_allow_file
        self.update_check_job=updater.Job(lambda job:updater.fetch_manifest(source,allow_file))
        self.update_status='正在检查更新…'
        return True

    def start_update(self):
        offer,install_dir=self.update_offer,self.install_dir
        if offer is None or self.update_install_job: return False
        def work(job):
            return updater.prepare(install_dir,offer,lambda fraction:setattr(job,'progress',fraction))
        self.update_install_job=updater.Job(work)
        self.update_status=f'正在下载 {offer["version"]}…'
        return True

    def update_text(self):
        if self.update_install_job: return f'正在下载新版本 {round(self.update_install_job.progress*100)}%'
        if self.update_offer: return f'新版本 {self.update_offer["version"]} 可以更新'
        return ''

    def poll_updates(self):
        job=self.update_check_job
        if job and job.done:
            self.update_check_job=None
            if job.error: self.update_status='检查更新失败：'+job.error
            elif updater.is_newer(job.result['version']):
                version=job.result['version']
                if self.update_offer is None or self.update_offer['version']!=version:
                    self.say(f'小汉有新版本 {version}，在“更多”里点更新',10)
                self.update_offer=job.result;self.update_status=f'发现新版本 {version}'
            else: self.update_status='已是最新版本'
        job=self.update_install_job
        if job and job.done:
            self.update_install_job=None
            if job.error:
                self.update_status='更新失败：'+job.error;self.say(self.update_status,10)
            else: self.finish_update(job.result)

    def finish_update(self,staged):
        if not self.begin_close():
            self.update_status='已取消更新';return
        try: updater.launch_installer(staged,self.install_dir,os.getpid())
        except OSError as exc:
            self.closing=False  # finish_update runs inside tick, which keeps scheduling itself.
            self.update_status=f'没能启动新版本：{exc}';self.say(self.update_status,10);return
        self.finish_close()

    def select_stage(self,stage):
        if self.action:
            self.say('等这次互动结束，再换个模样吧');return False
        error=self.state.select_stage(stage)
        if error:self.say(error);return False
        self.cancel_charge()
        self.save();self.say('现在是'+STAGES[stage][2]+'小汉啦')
        self.render(time.monotonic())
        if self.more:self.more.refresh()
        return True

    def snooze_break(self):
        self.work_break.snooze(); self.say('好，5 分钟后再叫你')

    def open_fetch(self):
        if self.paused:
            self.say('已暂停，请先继续陪伴');return False
        if self.action not in (None,'walk'):
            self.say('先结束当前互动，再来扔球吧'); return False
        self.close_more(); self.hide_tools()
        from_outdoor=self.outdoor
        if not self.outdoor:
            walking_started=self.action_started if self.action=='walk' else None
            self.set_scene('park',walk=False)
            if walking_started is not None:self.action,self.action_started='walk',walking_started
        self.fetch_mode=True; self.fetch_from_outdoor=from_outdoor
        self.resize_window(); self.notice_until=0
        return True

    def close_fetch(self):
        if not self.fetch_from_outdoor:
            self.set_scene(None)
            return
        self.cancel_charge()
        self.fetch_mode=False
        self.fetch_from_outdoor=False
        if self.action=='ball':
            self.cancel_action()
        if self.action in (None,'walk'):
            self.say('接着散步吧' if self.action=='walk' else '在这里歇一会儿吧')

    def begin_charge(self):
        self.drag=None
        if not self.fetch_mode or self.paused or self.action not in (None,'walk'): return False
        error=self.state.check('ball',time.time())
        if error: self.say(error); return False
        if not self.charge.begin(time.monotonic()): return False
        self.desktop.focus_set(); self.desktop.grab_set()
        return True

    def cancel_charge(self):
        self.charge.cancel()
        if self.root.grab_current()==self.desktop: self.desktop.grab_release()

    def stop_gesture(self):
        if self.tug is not None:
            self.tug.pause()
            if self.tug_key_reset is not None:
                self.root.after_cancel(self.tug_key_reset)
            self.clear_tug_key()
        if self.game is not None:
            self.clear_tug_key()
        self.cancel_charge()

    def cancel_unfocused_gesture(self):
        if self.closing: return
        focused=self.root.focus_displayof()
        if focused is None or focused.winfo_toplevel()!=self.root: self.stop_gesture()

    def escape_fetch(self,event=None):
        if self.hidden or self.closing:return 'break'
        if self.more:self.close_more()
        elif self.trip_picker:self.close_trip_picker()
        elif self.tug is not None:self.close_tug()
        elif self.game is not None:self.close_game()
        elif self.action=='dance':self.cancel_action()
        elif self.charge.started is not None:
            self.cancel_charge(); self.say('已取消蓄力')
        elif self.fetch_mode: self.close_fetch()
        elif self.outdoor: self.set_scene(None)
        return 'break'

    def throw_ball(self,power):
        if not self.fetch_mode or self.paused or self.action not in (None,'walk'): return False
        error=self.state.check('ball',time.time())
        if error: self.say(error); return False
        now=time.monotonic()
        self.walk_resume=now-self.action_started if self.action=='walk' else None
        self.fetch_origin=walk_position(self.walk_clock)
        self.fetch_power=min(1.,max(0.,power))
        self.action,self.action_started='ball',now
        self.say(f'看球！力度 {round(self.fetch_power*100)}%')
        return True

    def toggle_pause(self):
        now=time.monotonic()
        if self.paused:
            if self.action:
                self.action_started+=now-self.pause_started
            self.paused=False
            self.resume_button.place_forget()
            self.say('继续陪你啦',2)
        else:
            self.end_dance()
            self.stop_gesture()
            self.hide_tools()
            self.paused=True
            self.pause_started=now
            self.work_break.update(now,None,False)
            self.resume_button.place(relx=.5,rely=1,y=-3,anchor='s')
        self.last_tick=now
        if not self.hidden:
            self.render(now)
        if self.more:
            self.more.refresh()

    def start_action(self,key):
        if key=='ball': return self.open_fetch()
        if key in MINI_GAMES: return self.open_game(key)
        if self.paused: self.say('已暂停，请先继续陪伴'); return False
        care_while_walking=self.outdoor and self.action=='walk' and key in NEED_ACTIONS.values()
        if self.action and not care_while_walking:
            self.say('等这次互动结束再来吧'); return False
        error=self.state.check(key,time.time())
        if error: self.say(error); return False
        self.cancel_charge()
        now=time.monotonic()
        if key=='toy':
            self.open_tug(now)
            return True
        if care_while_walking:self.walk_resume=now-self.action_started
        self.action,self.action_started=key,now
        if key=='dance':
            self.close_more()
            self.hide_tools()
            self.open_stage(STAGE_SIZE)
            self.dance.play()
        if self.outdoor and key in NEED_ACTIONS.values():self.close_more()
        self.say(ACTIONS[key]['label']+'中…',ACTIONS[key]['duration']+1)
        return True

    def cancel_action(self):
        if self.tug is not None:
            self.close_tug()
            return
        if self.game is not None:
            self.close_game()
            return
        self.cancel_charge()
        if self.action=='dance':self.stop_dance()
        self.action=None
        self.resume_walk(self.pause_started if self.paused else time.monotonic())
        self.say('好啦，继续陪着你')

    def open_stage(self,size):
        """The window grows into a scene of this size, bottom-centred where she stood."""
        x,y=self.root.winfo_x(),self.root.winfo_y()
        self.stage_return=(x,y,self.width,self.height)
        self.width,self.height=size
        self.resize_window((x+(self.stage_return[2]-self.width)//2,y+self.stage_return[3]-self.height))

    def close_stage(self):
        x,y,self.width,self.height=self.stage_return
        self.stage_return=None
        self.resize_window((x,y))

    def stop_dance(self):
        self.dance.stop()
        self.close_stage()

    def end_dance(self):
        """Pausing, hiding or quitting cuts a dance short without a message."""
        if self.action=='dance':
            self.stop_dance()
            self.action=None

    def open_game(self,key):
        if self.paused: self.say('已暂停，请先继续陪伴'); return False
        if self.action or self.tug is not None: self.say('等这次互动结束再来吧'); return False
        if self.outdoor or self.fetch_mode: self.say('回到桌面再玩小游戏吧'); return False
        error=self.state.play_block()
        if error: self.say(error); return False
        self.close_more()
        self.hide_tools()
        self.drag=self.pressed_control=None
        if self.game_art is None:
            self.game_art=GameArt(self.root,self.images,self.outdoor_renderer)
        now=time.monotonic()
        self.game_key,self.game,self.game_result=key,self.new_game(key),None
        self.action,self.action_started=key,now
        self.open_stage(GAME_SIZE)
        self.render(now)
        self.desktop.focus_force()
        return True

    def new_game(self,key):
        stage=self.state.stage
        if key=='catch':return CatchGame(*catch_geometry(stage))
        if key=='hurdle':return HurdleGame(hurdle_half_width(stage))
        return ShellGame() if key=='shell' else MemoryGame()

    def retry_game(self):
        error=self.state.play_block()
        if error:
            self.close_game();self.say(error);return
        self.game,self.game_result=self.new_game(self.game_key),None

    def score_game(self):
        key,score=self.game_key,self.game.score
        record=score>0 and self.state.record_score(key,score)
        reward='这局没有得分，再试一次吧'
        if score>0:
            error=self.state.check(key,time.time())
            if error:
                reward='这局不加奖励：'+error
            else:
                self.state.finish(key,time.time(),already_started=True)
                names={'mood':'心情','bond':'亲密','energy':'体力','food':'饱腹','water':'水分'}
                reward=' · '.join(f'{names[k]} {v:+g}' for k,v in ACTIONS[key]['effects'].items())
        self.game_result=dict(score=score,record=record,reward=reward)
        self.save()

    def close_game(self):
        self.clear_tug_key()
        self.game=self.game_key=self.game_result=None
        self.action=None
        self.scene_controls={}
        self.pressed_control=None
        self.close_stage()
        self.say('下次再一起玩')

    def resume_walk(self,now):
        if self.walk_resume is not None:
            self.action='walk'
            self.action_started=now-self.walk_resume
            self.walk_resume=None

    def open_tug(self,now):
        self.hide_tools()
        self.close_more()
        self.drag=self.pressed_control=None
        self.tug_origin=(self.root.winfo_x(),self.root.winfo_y())
        self.tug=TugRound(ACTIONS['toy']['duration'])
        self.action,self.action_started='toy',now
        self.width,self.height=TUG_SIZE
        self.resize_window(self.tug_origin)
        self.render(now)
        self.desktop.focus_force()

    def tug_key_down(self,event=None):
        if self.tug is None and self.game is None:
            return
        if self.tug_key_reset is not None:
            # Some platforms emit an immediate release/press pair for repeat.
            self.root.after_cancel(self.tug_key_reset)
            self.tug_key_reset=None
            return 'break'
        if not self.paused and not self.tug_space_down:
            self.tug_space_down=True
            if self.game is not None:
                if self.game.over:self.retry_game()
                else:self.game.press()
            elif self.tug.started or not self.state.check('toy',time.time()):
                self.tug.strike(time.monotonic())
        return 'break'

    def tug_key_up(self,event=None):
        if self.tug is None and self.game is None:
            return
        if self.tug_space_down and self.tug_key_reset is None:
            self.tug_key_reset=self.root.after_idle(self.clear_tug_key)
        return 'break'

    def clear_tug_key(self):
        self.tug_space_down=False
        self.tug_key_reset=None
        if self.game is not None:self.game.release()

    def close_tug(self):
        completed=self.tug.result in ('player','dog','tie')
        self.stop_gesture()
        self.tug=None
        self.action=None
        self.scene_controls={}
        self.pressed_control=None
        self.width,self.height=(420,330) if self.outdoor else (280,300)
        self.resize_window(self.tug_origin)
        self.tug_origin=None
        self.say('小汉玩得很开心' if completed else '小汉把玩具收好啦')

    def current_fetch(self,now):
        if self.paused:
            now=self.pause_started
        elapsed=now-self.action_started
        anchors={pose:self.fetch_anchors[fetch_asset(self.state.outfit,self.state.stage,pose)] for pose in FETCH_POSES}
        size=round(174*(.70,.88,1.)[self.state.stage])
        sample=fetch_frame(elapsed/ACTIONS['ball']['duration'],self.fetch_power,size,anchors,self.fetch_origin)
        return sample,size

    def pose(self,now):
        outfit,stage=self.state.outfit,self.state.stage
        if self.paused:
            if self.action is None:
                return motion_frame(outfit,stage,'sleep',0),False
            now=self.pause_started
        if self.action:
            if self.action=='toilet':
                elapsed=now-self.action_started
                return (motion_frame(outfit,stage,'walk',elapsed) if elapsed<1.5 or elapsed>6.5 else outfit+'_'+AGES[stage]),False
            if self.action=='ball':
                progress=(now-self.action_started)/ACTIONS['ball']['duration']
                if .44<=progress<.97:return fetch_asset(outfit,stage,self.current_fetch(now)[0].pose),False
                return motion_frame(outfit,stage,'walk',self.walk_clock+max(0,now-self.action_started)*1.4),False
            if self.action=='walk': return motion_frame(outfit,stage,'walk',self.walk_clock if self.outdoor else now-self.action_started),False
            if self.action=='toy': return motion_frame(outfit,stage,'play',0),False
            name=ACTIONS[self.action]['pose']
            if name in ('eat','drink','play','sleep'): return motion_frame(outfit,stage,name,now-self.action_started),False
            if name=='shy': return outfit+'_shy',False
        elif self.petting.active(now):
            return outfit+'_'+AGES[stage],False
        elif self.napping:
            return motion_frame(outfit,stage,'sleep',now),False
        elif self.state.low_needs():
            need=self.state.low_needs()[0]
            return motion_frame(outfit,stage,NEEDS[need][0],0 if self.paused else now),False
        elif self.fetch_mode:
            return motion_frame(outfit,stage,'walk',self.walk_clock),False
        elif not self.paused and self.state.keyboard_enabled and not self.keyboard.error and now-self.keyboard.last_activity<.8:
            return motion_frame(outfit,stage,'type',now),True
        return outfit+'_'+AGES[stage],False

    def render(self,now):
        if self.paused:
            now=self.pause_started
        c=self.desktop; c.delete('all')
        self.scene_controls={}
        if self.tug is not None:
            self.render_tug()
            return
        if self.game is not None:
            self.scene_controls=draw_game(self.desktop,self.game_art,self.game_key,self.game,outfit=self.state.outfit,
                                          stage=self.state.stage,paused=self.paused,
                                          best=self.state.best_scores.get(self.game_key,0),result=self.game_result)
            self.hit=None
            return
        if self.action=='dance':
            self.render_dance(now-self.action_started)
            return
        name,typing=self.pose(now)
        x,y=self.width/2,275; elapsed=now-self.action_started; flip=False
        if self.outdoor and (self.action=='walk' or self.walk_clock>0 or self.fetch_mode and self.action is None and not self.paused):
            x,y,flip=walk_position(self.walk_clock)
        elif self.action=='walk':
            progress=min(1,elapsed/ACTIONS[self.action]['duration']); x=self.width*.28+self.width*.44*math.sin(progress*math.pi); flip=progress>.5
        base_size=174 if self.outdoor else 240
        size=base_size if name.endswith(('puppy','teen','adult')) else round(base_size*(.70,.88,1.)[self.state.stage])
        care=None
        if self.action in ('snack','sleep','feed','water'):
            outfit,stage=self.state.outfit,self.state.stage
            care_pose=ACTIONS[self.action]['pose']
            care_name=f'{outfit}_{AGES[stage]}' if self.action=='snack' else motion_frame(outfit,stage,care_pose,0)
            source=self.outdoor_renderer.lit_artwork(self.state.scene,care_name) if self.outdoor else self.images[care_name]
            if self.action=='snack':
                care=snack_frame(source,stage,elapsed)
            elif self.action=='sleep':
                care=sleep_frame(source,elapsed)
            else:
                care=bowl_frame(source,care_pose,stage,elapsed)
            care=care.resize((size,size),Image.Resampling.LANCZOS)
        fetch=None
        if self.action=='ball':
            fetch,body_size=self.current_fetch(now)
            x,y,flip=fetch.x,fetch.ground,fetch.flip
            size=round(size*fetch.scale)
        self.flame.update(now,typing,self.state.flames and self.state.keyboard_enabled and not self.paused and not self.action and not self.fetch_mode,speed=self.keyboard.speed(now))
        # Keep the fade at the typing body's scale when its pose returns to idle.
        fire_size=round(base_size*(.70,.88,1.)[self.state.stage])
        fire=self.flame.image(now,fire_size,fade_alpha=self.outdoor or IS_MAC)
        if self.outdoor:
            if fetch is None: y=246
            if fetch is not None:
                origin_name=motion_frame(self.state.outfit,self.state.stage,'walk',self.walk_clock)
                frame=self.outdoor_renderer.compose_fetch(self.state.scene,self.state.outfit,self.state.stage,body_size,fetch,origin_name)
            else:frame=self.outdoor_renderer.compose(self.state.scene,name,size,x,y,flip,fire,pet=care)
            self.scene_photo=ImageTk.PhotoImage(frame,master=self.root)
            c.create_image(0,0,anchor='nw',image=self.scene_photo,tags='outdoor_scene')
            self.hit=None
            if self.fetch_mode:
                charging=self.charge.started is not None
                power=self.charge.power(now) if charging else self.fetch_power if self.action else 0.
                error='陪伴已暂停' if self.paused else self.state.check('ball',time.time())
                draw_throw_controls(c,power,charging,self.action not in (None,'walk'),error,self.fetch_count)
                back_label=('‹  回雪地' if self.state.scene=='snow' else '‹  回公园') if self.fetch_from_outdoor else '‹  回桌面'
                self.scene_controls['leave_fetch']=(328,3,412,35)
                draw_scene_button(c,self.scene_controls['leave_fetch'],back_label,'close_scene')
                if not self.paused and self.action in (None,'walk'):
                    self.scene_controls['care']=(264,3,322,35)
                    draw_scene_button(c,self.scene_controls['care'],'照顾','trip_care')
            else:
                self.scene_controls=draw_scene_controls(c,self.state.scene,self.action=='walk',self.paused)
        else:
            if fire is not None:
                if os.name=='nt':fire.putalpha(fire.getchannel('A').point(lambda value:255 if value>=128 else 0))
                self.fire_photo=ImageTk.PhotoImage(fire,master=self.root)
                c.create_image(x,y,image=self.fire_photo,anchor='s',tags='typing_flame')
            bob=math.sin(now*(1 if self.state.low_needs() else 2))*(.5 if self.state.low_needs() else 1.5) if not self.paused and not self.action else 0
            lift=0.
            if self.facing_applies(typing):
                flip,lift,x_scale,y_scale=self.facing.view(now)
                sprite=self.posed_sprite(name,flip,size,x_scale,y_scale,self.petting.tail(now))
            else:sprite=self.photo(name,(size,size),flip)
            if care is not None:
                if os.name=='nt':
                    care.putalpha(care.getchannel('A').point(lambda a:255 if a>=128 else 0))
                self.care_photo=ImageTk.PhotoImage(care,master=self.root)
                sprite=self.care_photo
            c.create_image(x,y+bob-lift,image=sprite,anchor='s',tags='pet_sprite')
            self.hit=(x-size/2,y+bob-lift-size,size,name,flip)
            if typing and self.keycaps:
                board=self.typing_boards[self.state.outfit+'_'+AGES[self.state.stage]]
                draw_typing_keys(c,self.keycaps,now,x-size/2,y+bob-lift-size,size,board,UI_FONT,INK)
        if self.action=='toilet' and 1.2<elapsed<6.8:
            screen_size=round(base_size*(.70,.88,1.)[self.state.stage])
            self.draw_toilet_screen(c,x,y,screen_size,elapsed)
        if self.action=='pet' or self.petting.active(now):
            if self.outdoor:heart_x,heart_top,since=x,y-size+40,elapsed
            else:
                heart_x,head_y=head_point(self.state.stage,(x-size/2,y-size,size/ART),not flip)
                heart_top,since=head_y-HEADS[self.state.stage]['radius']*size/ART,now-self.petting.started
            for hx,hy,font_size in heart_positions(since,heart_x,heart_top,5 if self.action=='pet' else 2):
                c.create_text(hx,hy,text='♥',fill='#d58988',font=('Segoe UI',font_size),tags='pet_heart')
        if self.action=='ball' and elapsed/ACTIONS['ball']['duration']>.92:
            c.create_text(x,y-size-10,text='✦  好棒！  ✦',fill=TEAL,font=(UI_FONT,11,'bold'))
        reminder=self.state.break_reminders and self.work_break.due and not self.paused
        need_text=self.state.need_text() if self.action in (None,'walk') else ''
        care_action=None
        if self.outdoor and need_text and not (self.paused or reminder or self.charge.started is not None):
            care_action=NEED_ACTIONS[self.state.low_needs()[0]]
            if not self.state.check(care_action,time.time()):
                self.scene_controls[care_action]=draw_scene_notice(c,need_text,care_action)
            else:
                care_action=None
        if not self.paused and (now<self.notice_until or self.fetch_mode or reminder or need_text):
            text=self.work_break.text() if reminder else fetch.message if self.action=='ball' else self.notice if now<self.notice_until else need_text or '她正等着你的下一球'
            if self.fetch_mode and self.action in (None,'walk') and not reminder:
                if charging:text='松手抛出 · 移出场景松手或 Esc 取消'
                elif now>=self.notice_until:text=error or '按住左键蓄力 · 松手抛出 · Esc 返回'
            if self.outdoor and not self.fetch_mode:
                if care_action is None:draw_scene_notice(c,text)
            else:
                c.create_rectangle(4,self.height-26,self.width-4,self.height-2,fill=PAPER,outline='')
                c.create_text(self.width/2,self.height-14,text=text,width=self.width-16,fill=INK,font=(UI_FONT,9),tags='status_notice')

    def draw_toilet_screen(self,c,x,ground,size,elapsed):
        top=ground-size*.94;left=x-size*.48;panel=size*.32
        for index,color in enumerate(('#b9d1bc','#d9e5ce','#afc9b0')):
            x0=left+index*panel;offset=size*.035 if index%2 else 0
            c.create_polygon(x0,top+offset,x0+panel,top+(0 if offset else size*.035),x0+panel,ground-4,x0,ground-4,
                             fill=color,outline='#6f977e',width=2,tags='toilet_screen')
            for u in (.18,.5,.82):
                c.create_line(x0+panel*u,top+size*.12,x0+panel*u,ground-10,fill='#9cb79d',tags='toilet_screen')
        c.create_text(x,top+size*.47,text='稍等一下'+'.'*(int(elapsed)%3+1),fill=INK,font=(UI_FONT,9),tags='toilet_screen')

    def render_tug(self):
        outfit,stage=self.state.outfit,self.state.stage
        name=motion_frame(outfit,stage,'play',0)
        size=round(218*(.70,.88,1.)[stage])
        level=round(self.tug.lean*POSE_STEPS)
        for step in (0,level):
            if (name,step) not in self.tug_frames:
                art=tug_pose(self.images[name],step/POSE_STEPS)
                tip=toy_tip(art)
                sprite=art.resize((size,size),Image.Resampling.LANCZOS)
                if os.name=='nt':
                    sprite.putalpha(sprite.getchannel('A').point(lambda value:255 if value>=128 else 0))
                self.tug_frames[name,step]=ImageTk.PhotoImage(sprite,master=self.root),tip
        sprite,tip=self.tug_frames[name,level]
        rest_tip=self.tug_frames[name,0][1]
        blocked=self.state.check('toy',time.time()) if not self.tug.started else ''
        draw_tug(self.desktop,sprite,size,tip,rest_tip,self.tug,self.paused,blocked)
        self.scene_controls={'leave_tug':TUG_EXIT}
        if self.tug.result=='idle':
            self.scene_controls['retry_tug']=TUG_RETRY

    def render_dance(self,elapsed):
        self.dance_photo=ImageTk.PhotoImage(self.dance.frame(elapsed),master=self.root)
        self.desktop.create_image(0,0,image=self.dance_photo,anchor='nw',tags='dance_stage')
        # The stop button only covers the clip while the cursor is over the stage.
        px,py=self.pointer()
        if 0<=px-self.root.winfo_rootx()<self.width and 0<=py-self.root.winfo_rooty()<self.height:
            draw_scene_button(self.desktop,STOP_BUTTON,'× 停止','dance_stop')
            self.scene_controls['stop_dance']=STOP_BUTTON
        self.hit=None

    def tick(self):
        if self.closing: return
        now=time.monotonic(); dt=now-self.last_tick; self.last_tick=now
        previous_unlocked=self.state.unlocked_stage
        if not self.paused and self.outdoor and (self.action=='walk' or self.fetch_mode and self.action is None and not self.state.low_needs()):
            self.walk_clock+=min(max(dt,0),.25)
        idle=user_idle_seconds()
        self.work_break.update(now,idle,self.state.break_reminders and not self.paused)
        busy=(self.tug is not None or self.game is not None or self.fetch_mode
              or self.action not in (None,'pet','sleep'))
        napping=(not busy and not self.outdoor and not self.paused
                 and idle is not None and idle>=NAP_AFTER_SECONDS)
        if napping!=self.napping:self.change_nap(napping)
        self.rest_state='nap' if napping else 'busy' if busy else 'rest'
        if not self.paused: self.state.tick(dt,idle is not None and idle<300,self.rest_state)
        if self.tug is not None:
            if not self.paused and self.tug.advance(now):
                self.stop_gesture()
                if self.tug.result!='idle':
                    self.state.finish('toy',time.time(),already_started=True)
                    self.save()
        elif self.game is not None:
            if not self.paused:
                px,py=self.pointer()
                self.game.advance(min(dt,.05),(px-self.root.winfo_rootx(),py-self.root.winfo_rooty()))
                if self.game.over and self.game_result is None:self.score_game()
        elif not self.paused and self.action and now-self.action_started>=ACTIONS[self.action]['duration']:
            key=self.action; self.action=None
            if key=='dance':self.stop_dance()
            self.state.finish(key,time.time(),already_started=True)
            self.say('她收起耳朵了，摸摸她吧' if key=='tap' else ACTIONS[key]['label']+'完成啦')
            if key=='ball':
                self.fetch_count+=1
                if self.state.urgent_needs():
                    self.say(f'第 {self.fetch_count} 球带回来了。'+self.state.check('ball',time.time()),5)
                else:self.say(f'第 {self.fetch_count} 球带回来了，再来一球吧！',5)
            self.resume_walk(now)
            self.save()
        if previous_unlocked!=self.state.unlocked_stage:
            self.say('解锁'+STAGES[self.state.unlocked_stage][2]+'啦！在“更多”里选择模样',10)
            self.save()
        if self.keyboard.error and not self.keyboard_error_shown: self.keyboard_error_shown=True; self.say(self.keyboard.error,15)
        self.poll_updates()
        if self.closing: return
        self.follow_pointer(now)
        self.take_keys(now)
        if not self.hidden:
            self.render(now)
        if (self.more or self.status_strip) and now-self.last_panel_refresh>.25:
            if self.more:self.more.refresh()
            if self.status_strip:self.status_strip.refresh(self.state)
            self.last_panel_refresh=now
        if now-self.last_save>30: self.save(); self.last_save=now
        animated=(self.tug is not None or self.game is not None or self.flame.level or self.keycaps or self.action in ('ball','snack','sleep','feed','water','dance','pet')
                  or self.charge.started is not None or self.facing.animating(now) or self.petting.active(now))
        interval = 180 if self.paused or self.hidden else 33 if animated else 90
        remaining = interval - round((time.monotonic()-now)*1000)
        self.root.after(max(1,remaining),self.tick)

    def change_nap(self,napping):
        """She naps while the computer sits untouched and says how much energy it brought back."""
        if napping:
            self.nap_energy=self.state.values['energy']
        else:
            gained=self.state.values['energy']-self.nap_energy
            if gained>=1:self.say(f'睡醒啦，体力恢复了 {gained:.0f}',5)
        self.napping=napping

    def begin_close(self):
        if self.closing:
            return False
        error=self.write_save()
        if error and not messagebox.askyesno('存档失败',error+'\n\n这次的进度没能保存，仍然退出小汉吗？',
                                             icon='warning',parent=self.root):
            return False
        self.closing=True
        self.end_dance()
        if self.game is not None:self.close_game()
        self.stop_gesture()
        self.close_more()
        self.hide_tools()
        return True

    def finish_close(self):
        self.keyboard.stop()
        self.root.destroy()

    def request_exit(self):
        if not self.begin_close():
            return
        self.desktop.pack_forget()
        self.recall_button.pack_forget()
        self.width,self.height=280,300
        self.resize_window()
        self.root.deiconify()
        canvas=tk.Canvas(self.root,width=self.width,height=self.height,bg=KEY,highlightthickness=0)
        canvas.pack()
        standing=self.images[f'{self.state.outfit}_{AGES[self.state.stage]}']
        self.farewell=FarewellAnimation(canvas,standing,self.finish_close)

    def close(self):
        if self.begin_close():
            self.finish_close()

def install_update(install_dir,pid):
    """Runs from the staged new build: replace the old program files, then start the pet again."""
    staged=Path(sys.executable).resolve().parent
    try:
        updater.wait_for_exit(pid)
        updater.apply_update(staged,install_dir)
    except updater.UpdateError as exc:
        root=tk.Tk();root.withdraw()
        messagebox.showerror('小汉更新失败',str(exc),parent=root);root.destroy()
    if (install_dir/updater.EXE_NAME).is_file():
        updater.launch(install_dir)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,default=default_data_path())
    parser.add_argument('--smoke',type=Path)
    parser.add_argument('--verify-package',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--verify-mac',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--apply-update',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--wait-pid',type=int,help=argparse.SUPPRESS)
    # Test hooks: a local manifest (file: URLs allowed) and a scripted update run.
    parser.add_argument('--update-manifest',help=argparse.SUPPRESS)
    parser.add_argument('--verify-update',type=Path,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.apply_update:
        if args.wait_pid is None: parser.error('--apply-update 需要 --wait-pid')
        install_update(args.apply_update,args.wait_pid)
        return
    # Smoke checks rewrite growth, outfit and settings, and skip the single-instance lock.
    if args.smoke and args.data.resolve()==default_data_path().resolve():
        parser.error('--smoke 会改写存档，请用 --data 指定一个隔离的测试存档路径')
    if os.name=='nt':
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except OSError:
            pass
    root=tk.Tk();root.withdraw()
    mutex=None;mac_lock=None
    if IS_MAC and not args.verify_mac:
        mac_lock=MacInstanceLock(Path(args.data).with_suffix('.lock'))
        try:acquired=mac_lock.acquire()
        except OSError as exc:
            messagebox.showerror('启动失败',f'无法打开存档目录：{exc}');root.destroy();return
        if not acquired:
            messagebox.showinfo('小汉已经在陪你啦','将鼠标移到小汉身上即可看到互动图标。');root.destroy();return
    if os.name=='nt' and not (args.smoke or args.verify_package or args.verify_update):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
        kernel.CreateMutexW.restype=ctypes.c_void_p
        mutex=kernel.CreateMutexW(None,False,'Local\\XiaohanDesktopCompanion')
        if not mutex:
            messagebox.showerror('启动失败','无法创建单实例锁');root.destroy();return
        if ctypes.get_last_error()==183:
            messagebox.showinfo('小汉已经在陪你啦','将鼠标移到小汉身上即可看到互动图标。');root.destroy();return
    try:
        app=DesktopPet(root,args.data,args.smoke,args.update_manifest)
    except (OSError,ValueError,KeyError,RuntimeError) as exc:
        if mac_lock:mac_lock.close()
        messagebox.showerror('小汉未能启动',f'{exc}\n\n已有存档不会被覆盖。');root.destroy();return
    root.deiconify()
    if args.verify_mac:
        from mac_check import schedule
        schedule(app,args.verify_mac)
    if args.verify_package:
        from package_check import schedule
        schedule(app,args.verify_package)
    if args.smoke:
        from smoke import schedule
        schedule(app,args.smoke)
    if args.verify_update:
        from update_check import schedule
        schedule(app,args.verify_update)
    root.mainloop()
    if mac_lock:mac_lock.close()
    if mutex:
        kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(mutex)

if __name__=='__main__':
    main()
