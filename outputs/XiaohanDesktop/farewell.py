"""A short desktop farewell using the current age and clothes."""
import math
import os
import time

from PIL import Image, ImageTk

from desktop_platform import UI_FONT
from fetch_game import ramp
from trip_view import INK, pill

FAREWELL_SECONDS = 2.2


def farewell_pose(standing, bounds, elapsed):
    left,top,right,bottom=bounds
    width,height=right-left,bottom-top
    bow=ramp(elapsed,.12,.48)*(1-ramp(elapsed,.58,1.02))
    wag=ramp(elapsed,.18,.37)*(1-ramp(elapsed,1.47,1.65))
    tail=wag*math.sin(math.tau*2.3*(elapsed-.18))
    if not (bow or tail):
        return standing

    xs=(*range(0,standing.width,12),standing.width)
    ys=(*range(0,standing.height,12),standing.height)
    nodes={}
    for y in ys:
        v=(y-top)/height
        for x in xs:
            u=(x-left)/width
            head=(1-ramp(u,.37,.60))*(1-ramp(v,.46,.75))
            curl=ramp(u,.61,.84)*(1-ramp(v,.47,.73))
            nodes[x,y]=(x+width*(.033*head*bow-.082*curl*tail),
                        y-height*(.107*head*bow+.022*curl*abs(tail)))
    mesh=[]
    for y0,y1 in zip(ys,ys[1:]):
        for x0,x1 in zip(xs,xs[1:]):
            quad=(*nodes[x0,y0],*nodes[x0,y1],*nodes[x1,y1],*nodes[x1,y0])
            mesh.append(((x0,y0,x1,y1),quad))
    return standing.transform(standing.size,Image.Transform.MESH,mesh,Image.Resampling.BILINEAR)


class FarewellAnimation:
    def __init__(self, canvas, standing, finish):
        self.canvas=canvas
        self.standing=standing
        self.finish=finish
        self.bounds=standing.getchannel('A').point(lambda a:255 if a>=128 else 0).getbbox()
        self.started=time.monotonic()
        self.draw()

    def draw(self):
        now=time.monotonic()
        elapsed=now-self.started
        if elapsed>=FAREWELL_SECONDS:
            self.finish()
            return

        canvas=self.canvas
        canvas.delete('all')
        center=int(canvas['width'])/2
        ground=int(canvas['height'])-25
        scale=1-.87*ramp(elapsed,1.60,FAREWELL_SECONDS)
        side=round(240*scale)
        image=farewell_pose(self.standing,self.bounds,elapsed).resize((side,side),Image.Resampling.LANCZOS)
        if os.name=='nt':
            image.putalpha(image.getchannel('A').point(lambda a:255 if a>=128 else 0))
        self.picture=ImageTk.PhotoImage(image,master=canvas)
        canvas.create_image(center,ground,image=self.picture,anchor='s',tags='farewell_pet')

        if elapsed<1.93:
            pill(canvas,(round(center)-55,15,round(center)+55,47))
            canvas.create_text(center,30,text='回头见！',fill=INK,font=(UI_FONT,11,'bold'),tags='farewell_caption')
        if .51<elapsed<1.49:
            lift=ramp(elapsed,.51,1.49)
            size=round(9+11*math.sin(math.pi*lift))
            canvas.create_text(center+58+10*lift,106-44*lift,text='♥',fill='#cf7e80',font=(UI_FONT,size),
                               tags='farewell_heart')
        canvas.after(max(1,33-round((time.monotonic()-now)*1000)),self.draw)
