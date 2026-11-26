"""Companion actions with separate views for growth, care and settings."""
import tkinter as tk

from desktop_platform import UI_FONT, screen_bounds
from model import ACTIONS, STAGES, NEED_LOW, NEED_CRITICAL
from trip_view import CARE_LABELS
from version import VERSION

PAPER = '#fffaf2'
INK = '#30504c'
MUTED = '#64766d'
TEAL = '#2e796c'
BUTTON = '#ecf1e8'
TRACK = '#e5e9df'
PAGE_TITLES = {'home': '小汉', 'growth': '成长', 'care': '照顾状态', 'settings': '设置'}


def care_meter_color(value):
    return TEAL if value>=NEED_LOW else '#b66c58' if value<NEED_CRITICAL else '#c99463'


class CareStatusStrip(tk.Canvas):
    def __init__(self, parent, open_details):
        super().__init__(parent,width=196,height=36,bg=BUTTON,highlightbackground=BUTTON,
                         highlightcolor=TEAL,highlightthickness=1,cursor='hand2',takefocus=True)
        self.gauges={}
        for index,(key,title) in enumerate((('food','饱腹'),('water','水分'),('energy','体力'))):
            left=7+62*index
            right=left+49
            self.create_text(left,12,text=title,anchor='w',fill=INK,font=(UI_FONT,8))
            number=self.create_text(right,12,anchor='e',fill=MUTED,font=(UI_FONT,8))
            self.create_rectangle(left,24,right,29,fill='#d4e1d6',outline='')
            bar=self.create_rectangle(left,24,left,29,outline='')
            self.gauges[key]=(left,right,number,bar)
        self.create_text(188,18,text='›',fill=TEAL,font=(UI_FONT,11,'bold'))
        self.bind('<ButtonRelease-1>',lambda event:open_details())
        self.bind('<Return>',lambda event:open_details())
        self.bind('<space>',lambda event:open_details())

    def refresh(self,state):
        for key,(left,right,number,bar) in self.gauges.items():
            value=state.need_level(key)
            color=care_meter_color(value)
            self.itemconfigure(number,text=f'{value:.0f}',fill=MUTED if value>=NEED_LOW else color)
            self.coords(bar,left,24,left+(right-left)*value/100,29)
            self.itemconfigure(bar,fill=color)


class MorePanel:
    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title('小汉 · 更多')
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        self.win.configure(bg=PAPER, highlightbackground='#d7ddd2', highlightthickness=1)
        self.win.bind('<Escape>', self.escape)
        self.win.protocol('WM_DELETE_WINDOW', app.close_more)

        body = tk.Frame(self.win, bg=PAPER, padx=14, pady=12)
        body.pack(fill='both', expand=True)
        header = tk.Frame(body, bg=PAPER)
        header.pack(fill='x', pady=(0,12))
        self.back = self.button(header, '‹ 返回', lambda: self.show('home'))
        self.title = tk.Label(header, bg=PAPER, fg=INK, font=(UI_FONT,14,'bold'))
        self.title.pack(side='left')
        self.close_button = self.button(header, '×  关闭', app.close_more)
        self.close_button.pack(side='right')

        self.pages = {page: tk.Frame(body, bg=PAPER) for page in PAGE_TITLES}
        self.build_home(self.pages['home'])
        self.build_growth(self.pages['growth'])
        self.build_care(self.pages['care'])
        self.build_settings(self.pages['settings'])
        self.page = None
        self.feedback = ''
        self.show('home')
        self.win.lift()
        self.close_button.focus_force()

    def escape(self, event=None):
        self.app.close_more()
        return 'break'

    @staticmethod
    def label(parent, text='', **kwargs):
        return tk.Label(parent, text=text, bg=PAPER, fg=INK, anchor='w', font=(UI_FONT,9), **kwargs)

    @staticmethod
    def button(parent, text, command, **kwargs):
        button = tk.Button(parent, text=text, command=command, bg=BUTTON, fg=INK,
                           activebackground='#dce9df', activeforeground=INK, disabledforeground='#829083',
                           relief='flat', borderwidth=0, highlightthickness=1, highlightbackground=BUTTON,
                           highlightcolor=TEAL, font=(UI_FONT,9), cursor='hand2',
                           takefocus=True, padx=8, pady=5, **kwargs)
        button.bind('<Return>', lambda event: button.invoke())
        return button

    def perform(self, key):
        self.feedback = '' if self.app.start_action(key) else self.app.notice
        if self.app.more is self:
            self.refresh()

    def build_home(self, body):
        actions = tk.Frame(body, bg=PAPER)
        actions.pack(fill='x')
        self.actions = {}
        for index,key in enumerate(('snack','ball','walk','tap')):
            column = index%2
            button = self.button(actions, ACTIONS[key]['label'], lambda k=key: self.perform(k))
            button.grid(row=index//2,column=column,sticky='ew',padx=(0,6) if column==0 else 0,pady=(0,6),ipady=2)
            actions.columnconfigure(column, weight=1, uniform='action')
            self.actions[key] = button
        dance=self.button(actions,ACTIONS['dance']['label'],lambda:self.perform('dance'))
        dance.grid(row=2,column=0,columnspan=2,sticky='ew',pady=(0,6),ipady=2)
        self.actions['dance']=dance

        self.status = tk.Frame(body, bg=PAPER)
        self.end = self.button(self.status, '结束互动', self.app.cancel_action)
        self.activity = self.label(self.status, justify='left', wraplength=250)
        self.activity.pack(side='left', fill='x', expand=True)

        self.snooze = self.button(body, '5 分钟后提醒', self.app.snooze_break)
        self.update_row = tk.Frame(body, bg=PAPER)
        self.update_label = self.label(self.update_row, justify='left', wraplength=180)
        self.update_label.configure(fg=TEAL)
        self.update_label.pack(side='left', fill='x', expand=True)
        self.update_button = self.button(self.update_row, '更新', self.start_update)
        self.update_button.pack(side='right')
        self.divider = tk.Frame(body, bg=TRACK, height=1)
        self.divider.pack(fill='x', pady=(6,10))
        nav = tk.Frame(body, bg=PAPER)
        nav.pack(fill='x')
        self.sections = {}
        for index,page in enumerate(('growth','care','settings')):
            button = self.button(nav, PAGE_TITLES[page]+' ›', lambda p=page: self.show(p))
            button.grid(row=0,column=index,sticky='ew',padx=(0,6) if index<2 else 0)
            nav.columnconfigure(index, weight=1, uniform='section')
            self.sections[page] = button

        footer = tk.Frame(body, bg=PAPER)
        footer.pack(fill='x', pady=(8,0))
        self.pause = self.button(footer, '暂停陪伴', self.app.toggle_pause)
        self.pause.pack(side='left', expand=True, fill='x')
        self.hide = self.button(footer, '暂时收起', self.app.hide_pet)
        self.hide.pack(side='left',expand=True,fill='x',padx=(6,0))
        self.home = self.button(footer, '回到桌面', lambda: self.app.set_scene(None))

    def build_growth(self, body):
        self.subtitle = self.label(body)
        self.subtitle.pack(fill='x', pady=(0,10))
        stages = tk.Frame(body, bg=PAPER)
        stages.pack(fill='x')
        self.stage_buttons = {}
        for stage in range(len(STAGES)):
            button = self.button(stages, '', lambda s=stage: self.app.select_stage(s), width=8)
            button.grid(row=0,column=stage,sticky='ew',padx=(0,6) if stage<len(STAGES)-1 else 0)
            stages.columnconfigure(stage, weight=1, uniform='stage')
            self.stage_buttons[stage] = button
        progress_header = tk.Frame(body, bg=PAPER)
        progress_header.pack(fill='x', pady=(12,3))
        self.growth_title = self.label(progress_header)
        self.growth_title.pack(side='left')
        self.growth_percent = self.label(progress_header)
        self.growth_percent.configure(fg=TEAL)
        self.growth_percent.pack(side='right')
        self.growth_bar = tk.Canvas(body, width=276, height=10, bg=PAPER, highlightthickness=0)
        self.growth_bar.pack(fill='x')
        self.growth_bar.bind('<Configure>', lambda event: self.refresh_growth())
        self.growth = self.label(body, justify='left', wraplength=276, height=2)
        self.growth.pack(fill='x', pady=(4,0))

    def build_care(self, body):
        self.bars = {}
        for index,(key,title) in enumerate((('food','饱腹'),('water','水分'),('energy','体力'),('mood','心情'),('toilet','如厕'))):
            column = index%2
            cell = tk.Frame(body, bg=PAPER)
            cell.grid(row=index//2,column=column,sticky='ew',padx=(0,10) if column==0 else 0,pady=(0,9))
            body.columnconfigure(column, weight=1, uniform='care')
            label = self.label(cell)
            label.pack(fill='x')
            bar = tk.Canvas(cell,width=128,height=6,bg=TRACK,highlightthickness=0)
            bar.pack(fill='x',pady=(4,0))
            bar.bind('<Configure>', lambda event: self.refresh_care())
            self.bars[key] = (label,bar,title)
        self.toilet_button = self.button(body, '上厕所', lambda: self.perform('toilet'))
        self.toilet_button.grid(row=2,column=1,sticky='ew',pady=(0,6))
        self.outdoor_care = tk.Frame(body, bg=PAPER)
        self.outdoor_care.grid(row=3,column=0,columnspan=2,sticky='ew',pady=(0,6))
        self.care_actions = {}
        for column,key in enumerate(('feed','water','sleep')):
            button = self.button(self.outdoor_care, CARE_LABELS[key], lambda k=key: self.perform(k))
            button.grid(row=0,column=column,sticky='ew',padx=(0,6) if column<2 else 0)
            self.outdoor_care.columnconfigure(column,weight=1,uniform='care_action')
            self.care_actions[key] = button
        self.care_feedback = self.label(body, justify='left', wraplength=270)
        self.care_feedback.grid(row=4,column=0,columnspan=2,sticky='ew')
        self.care_feedback.grid_remove()

    def start_update(self):
        self.app.start_update()
        self.refresh()

    def build_settings(self, body):
        self.switches = {}
        switches = [('keyboard_enabled','跟着打字'),('flames','打字火光'),('mouse_follow','看向鼠标'),
                    ('break_reminders','休息提醒 · 60 / 10 分钟')]
        if self.app.updates_supported:
            switches.append(('update_checks','自动检查更新'))
        for key,title in switches:
            row = tk.Frame(body, bg=PAPER)
            row.pack(fill='x', pady=(0,6))
            self.label(row, title).pack(side='left')
            button = self.button(row, '', lambda k=key: self.toggle_setting(k), width=7)
            button.pack(side='right')
            self.switches[key] = button
        self.rest_status = self.label(body)
        self.rest_status.pack(fill='x', pady=(2,4))
        self.version_status = self.label(body, justify='left', wraplength=276)
        self.version_status.configure(fg=MUTED)
        self.version_status.pack(fill='x', pady=(0,10))
        self.exit_button = self.button(body, '退出小汉', self.app.request_exit)
        self.exit_button.pack(anchor='e')

    def toggle_setting(self, key):
        self.app.set_option(key, not getattr(self.app.state,key))
        self.refresh()

    def show(self, page):
        if self.page is not None:
            self.pages[self.page].pack_forget()
        self.page = page
        self.feedback = ''
        self.title.configure(text=PAGE_TITLES[page])
        if page=='home':
            self.back.pack_forget()
        else:
            self.back.pack(side='left', before=self.title, padx=(0,8))
        self.pages[page].pack(fill='x')
        self.refresh()
        self.close_button.focus_set()

    def fit(self):
        self.win.update_idletasks()
        width = max(318, self.win.winfo_reqwidth())
        height = self.win.winfo_reqheight()
        if (width,height) != (getattr(self,'width',0),getattr(self,'height',0)):
            self.width,self.height = width,height
            self.win.geometry(f'{width}x{height}')
            self.place()

    def place(self):
        root = self.app.root
        rx,ry = root.winfo_x(),root.winfo_y()
        left,top,right,bottom = screen_bounds(root,rx+self.app.width/2,ry+self.app.height/2)
        x = rx-self.width-8 if rx-left>=self.width+8 else rx+self.app.width+8
        y = ry+self.app.height-self.height
        x = max(left,min(right-self.width,x))
        y = max(top,min(bottom-self.height,y))
        self.win.geometry(f'+{x}+{y}')

    def refresh(self):
        app,state = self.app,self.app.state
        busy = app.action is not None
        if self.page=='home':
            for key,button in self.actions.items():
                blocked = busy and not (key=='ball' and app.action=='walk')
                button.configure(state='disabled' if blocked or app.paused else 'normal')
            self.pause.configure(text='▶  继续陪伴' if app.paused else 'Ⅱ  暂停陪伴',
                                 bg='#dce9df' if app.paused else BUTTON)
            if app.outdoor and not self.home.winfo_manager():
                self.home.pack(side='left',expand=True,fill='x',padx=(6,0))
            elif not app.outdoor:
                self.home.pack_forget()
            status = ('已暂停陪伴' if app.paused else ACTIONS[app.action]['label']+'中' if busy
                      else self.feedback or state.need_text())
            self.activity.configure(text=status, wraplength=172 if busy and not app.paused else 270)
            self.end.configure(state='normal' if busy and not app.paused else 'disabled')
            if busy and not app.paused and not self.end.winfo_manager():
                self.end.pack(side='right')
            elif not busy or app.paused:
                self.end.pack_forget()
            if status and not self.status.winfo_manager():
                self.status.pack(fill='x',pady=(2,2),after=self.actions['snack'].master)
            elif not status:
                self.status.pack_forget()
            due = state.break_reminders and app.work_break.due and not app.paused
            self.snooze.configure(state='normal' if due else 'disabled')
            if due and not self.snooze.winfo_manager():
                self.snooze.pack(fill='x',pady=(2,4),after=self.status if status else self.actions['snack'].master)
            elif not due:
                self.snooze.pack_forget()
            update = app.update_text()
            if update:
                self.update_label.configure(text=update)
                self.update_button.configure(state='disabled' if app.update_install_job else 'normal')
                if not self.update_row.winfo_manager():
                    self.update_row.pack(fill='x', pady=(2,4), before=self.divider)
            else:
                self.update_row.pack_forget()
        elif self.page=='growth':
            self.subtitle.configure(text=f'亲密 {state.values["bond"]:.0f}  ·  陪伴 {state.companion_seconds/3600:.1f} 小时')
            for stage,button in self.stage_buttons.items():
                locked = stage>state.unlocked_stage
                selected = stage==state.stage
                label = ('小','中','大')[stage]+' · '+STAGES[stage][2]
                status = f'{STAGES[stage][0]//3600}小时解锁' if locked else '✓ 使用中' if selected else '选择'
                button.configure(text=label+'\n'+status,state='disabled' if locked or busy else 'normal',
                                 bg='#dce9df' if selected else BUTTON,fg=TEAL if selected else INK)
            self.refresh_growth()
        elif self.page=='care':
            self.refresh_care()
            if app.outdoor:
                self.outdoor_care.grid()
            else:
                self.outdoor_care.grid_remove()
            available = not app.paused and (not busy or app.outdoor and app.action=='walk')
            for button in (self.toilet_button,*self.care_actions.values()):
                button.configure(state='normal' if available else 'disabled')
            if self.feedback:
                self.care_feedback.configure(text=self.feedback)
                self.care_feedback.grid()
            else:
                self.care_feedback.grid_remove()
        elif self.page=='settings':
            for key,button in self.switches.items():
                enabled = getattr(state,key)
                button.configure(text='已开启' if enabled else '已关闭',fg=TEAL if enabled else MUTED)
            self.rest_status.configure(text=app.work_break.text() if state.break_reminders else '休息提醒已关闭')
            self.version_status.configure(text=f'版本 {VERSION}'+(' · '+app.update_status if app.updates_supported else ''))
        self.fit()

    def refresh_care(self):
        state = self.app.state
        low,urgent = state.low_needs(),state.urgent_needs()
        for key,(label,bar,title) in self.bars.items():
            value = state.need_level(key)
            if key=='toilet':
                label.configure(text='如厕 · '+('很急' if key in urgent else '想上厕所' if key in low else '舒适'))
            else:
                label.configure(text=f'{title}  {value:.0f}'+(' · 偏低' if key in low else ''))
            color = care_meter_color(value)
            bar.delete('all')
            bar.create_rectangle(0,0,bar.winfo_width()*value/100,6,fill=color,outline='')

    def refresh_growth(self):
        state = self.app.state
        fraction = state.growth_fraction()
        complete = state.unlocked_stage==len(STAGES)-1
        self.growth_title.configure(text='成长形态全部解锁' if complete else f'下一阶段 · {STAGES[state.unlocked_stage+1][2]}')
        percent = 100 if fraction==1 else int(fraction*100)
        self.growth_percent.configure(text='已完成' if complete else f'陪伴进度 {percent}%')
        bar = self.growth_bar
        width = max(12,bar.winfo_width())
        bar.delete('all')
        bar.create_line(5,5,width-5,5,width=8,fill=TRACK,capstyle='round',tags='track')
        if fraction>0:
            bar.create_line(5,5,5+(width-10)*fraction,5,width=8,fill=TEAL,capstyle='round',tags='progress')
        self.growth.configure(text=state.growth_progress()+ ('\n互动结束后可切换' if self.app.action else ''))
