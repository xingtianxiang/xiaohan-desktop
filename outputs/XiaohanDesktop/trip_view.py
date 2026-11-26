from desktop_platform import UI_FONT, screen_bounds
"""Small destination picker and companion-first outdoor controls."""
from functools import lru_cache
import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageDraw, ImageFilter, ImageTk
from animation import motion_frame

PAPER='#fffaf2'
INK='#30504c'
TEAL='#368b7d'
DESTINATIONS={'park':('阳光小公园','晒太阳，沿着草地走走'),'snow':('雪地小花园','和小汉一起看看雪景')}
CONTROLS={'home':(328,16,408,48),'walk':(10,284,86,319),'ball':(91,284,167,319),
          'care':(172,284,248,319),'scene':(253,284,329,319),'more':(334,284,410,319)}
CARE_LABELS = {'feed':'喂饭', 'water':'喝水', 'sleep':'休息', 'toilet':'上厕所'}


@lru_cache(maxsize=8)
def glass_pill(width,height,active=False):
    scale=3
    image=Image.new('RGBA',(width*scale,height*scale))
    draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((scale,2*scale,(width-1)*scale,(height-1)*scale),radius=height*scale/2,
                           fill=(40,75,60,30))
    image=image.filter(ImageFilter.GaussianBlur(scale))
    draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((scale,scale,(width-1)*scale,(height-3)*scale),radius=height*scale/2,
                           fill=(54,139,125,245) if active else (255,250,239,238),
                           outline=(255,255,249,230),width=scale)
    return image.resize((width,height),Image.Resampling.LANCZOS)


def pill(canvas,box,active=False,tag=''):
    left,top,right,bottom=box;key=(right-left,bottom-top,active)
    if not hasattr(canvas,'trip_photos'):canvas.trip_photos={}
    if key not in canvas.trip_photos:
        canvas.trip_photos[key]=ImageTk.PhotoImage(glass_pill(*key),master=canvas)
    canvas.create_image(left,top,anchor='nw',image=canvas.trip_photos[key],tags=tag)


def draw_scene_button(canvas,box,label,tag,active=False):
    pill(canvas,box,active,tag)
    left,top,right,bottom=box
    canvas.create_text((left+right)/2,(top+bottom)/2-1,text=label,fill='white' if active else INK,
                       font=(UI_FONT,9,'bold' if active else 'normal'),tags=tag)


def draw_scene_controls(canvas,scene,walking,paused=False):
    canvas.create_rectangle(0,290,420,330,fill=PAPER,outline='')
    pill(canvas,(12,12,188,66))
    title,subtitle=DESTINATIONS[scene]
    canvas.create_text(28,30,text=title,anchor='w',fill=INK,font=(UI_FONT,12,'bold'))
    canvas.create_text(28,50,text=subtitle,anchor='w',fill='#738279',font=(UI_FONT,8))
    controls = {key: CONTROLS[key] for key in ('home','more')} if paused else CONTROLS.copy()
    for key,box in controls.items():
        active=key=='walk' and walking
        label={'home':'‹  回桌面','walk':'停一停' if walking else '散步','ball':'扔球',
               'care':'照顾','scene':'换风景','more':'更多'}[key]
        draw_scene_button(canvas,box,label,'trip_'+key,active)
    return controls


def draw_scene_notice(canvas,text,action=None):
    if not hasattr(canvas,'trip_notice_font'):
        canvas.trip_notice_font=tkfont.Font(root=canvas,family=UI_FONT,size=9)
    width=min(288 if action else 348,max(100,canvas.trip_notice_font.measure(text)+32))
    button_width=80 if action else 0
    left=(420-width-button_width)//2
    pill(canvas,(left,250,left+width,278))
    canvas.create_text(left+width/2,263,text=text,width=width-20,fill=INK,font=canvas.trip_notice_font,tags='trip_notice')
    if action:
        box=(left+width+4,250,left+width+button_width,278)
        draw_scene_button(canvas,box,CARE_LABELS[action],'trip_'+action,active=True)
        return box


class TripPicker:
    def __init__(self,app):
        self.app=app;self.width=348;self.height=274
        self.win=tk.Toplevel(app.root);self.win.overrideredirect(True);self.win.attributes('-topmost',True)
        self.win.configure(bg=PAPER,highlightbackground='#d7ddd2',highlightthickness=1)
        self.win.geometry(f'{self.width}x{self.height}')
        self.win.bind('<Escape>',lambda e:app.close_trip_picker())
        header=tk.Frame(self.win,bg=PAPER);header.pack(fill='x',padx=14,pady=(12,0))
        tk.Label(header,text='今天去哪儿？',bg=PAPER,fg=INK,font=(UI_FONT,14,'bold')).pack(side='left')
        tk.Button(header,text='×',command=app.close_trip_picker,bg=PAPER,fg=INK,relief='flat',borderwidth=0,
                  font=('Segoe UI',14),cursor='hand2').pack(side='right')
        tk.Label(self.win,text='挑一处风景，和小汉一起放松一下',bg=PAPER,fg='#738279',font=(UI_FONT,9),anchor='w').pack(fill='x',padx=15,pady=(1,10))
        body=tk.Frame(self.win,bg=PAPER);body.pack(fill='x',padx=14)
        self.cards={};self.photos=[]
        for index,(scene,(title,subtitle)) in enumerate(DESTINATIONS.items()):
            card=tk.Canvas(body,width=151,height=166,bg=PAPER,highlightthickness=1,highlightbackground='#e1e6d9',
                           highlightcolor=TEAL,takefocus=True,cursor='hand2')
            card.grid(row=0,column=index,padx=(0,12) if index==0 else 0)
            name=motion_frame(app.state.outfit,app.state.stage,'walk',0)
            frame=app.outdoor_renderer.compose(scene,name,round(174*(.70,.88,1)[app.state.stage]),210,246)
            frame=frame.resize((151,104),Image.Resampling.LANCZOS).convert('RGBA')
            mask=Image.new('L',frame.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,150,103),radius=10,fill=255)
            frame.putalpha(mask);photo=ImageTk.PhotoImage(frame,master=self.win);self.photos.append(photo)
            card.create_image(0,0,image=photo,anchor='nw')
            card.create_text(10,122,text=title,anchor='w',fill=INK,font=(UI_FONT,10,'bold'))
            selected=app.outdoor and app.state.scene==scene
            card.create_text(10,148,text='正在这里  ✓' if selected else '去这里  →',anchor='w',fill=TEAL,font=(UI_FONT,9))
            card.bind('<Button-1>',lambda e,s=scene:app.set_scene(s))
            card.bind('<Return>',lambda e,s=scene:app.set_scene(s))
            card.bind('<space>',lambda e,s=scene:app.set_scene(s))
            card.bind('<Enter>',lambda e,c=card:c.configure(highlightbackground=TEAL))
            card.bind('<Leave>',lambda e,c=card:c.configure(highlightbackground='#e1e6d9'))
            self.cards[scene]=card
        self.place();self.win.lift();self.cards['park'].focus_set()

    def place(self):
        root=self.app.root
        rx,ry=root.winfo_x(),root.winfo_y()
        left,top,right,bottom=screen_bounds(root,rx+self.app.width/2,ry+self.app.height/2)
        x=rx-self.width-8 if rx-left>=self.width+8 else rx+self.app.width+8
        y=ry+self.app.height-self.height
        self.win.geometry(f'+{max(left,min(right-self.width,x))}+{max(top,min(bottom-self.height,y))}')
