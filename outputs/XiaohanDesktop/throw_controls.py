from desktop_platform import UI_FONT
"""Compact trajectory and power indicator for a hold-and-release throw."""
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter, ImageTk
from fetch_game import throw_point


@lru_cache(maxsize=101)
def power_badge(percent):
    scale=4
    size=(48*scale,112*scale)
    image=Image.new('RGBA',size)
    def rect(draw,box,radius,**kwargs):
        draw.rounded_rectangle(tuple(round(v*scale) for v in box),radius=round(radius*scale),**kwargs)
    shadow=Image.new('RGBA',size)
    draw=ImageDraw.Draw(shadow)
    rect(draw,(15,32,33,109),9,fill=(41,66,48,45))
    rect(draw,(5,6,43,26),10,fill=(41,66,48,30))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(2*scale)))
    draw=ImageDraw.Draw(image)
    rect(draw,(5,4,43,24),10,fill=(255,250,237,235),outline=(255,255,246,210),width=scale)
    rect(draw,(15,30,33,108),9,fill=(255,251,236,205),outline=(255,255,248,235),width=scale)
    rect(draw,(19,34,29,104),5,fill=(96,133,106,55))
    if percent>0:
        top=104-70*percent/100
        mask=Image.new('L',size)
        rect(ImageDraw.Draw(mask),(19,top,29,104),min(5,(104-top)/2),fill=255)
        gradient=Image.new('RGBA',size)
        gd=ImageDraw.Draw(gradient)
        for row in range(round(top*scale),104*scale+1):
            height=(104-row/scale)/70
            low,high=((69,146,125),(160,212,162)) if height<.75 else ((160,212,162),(244,208,128))
            blend=height/.75 if height<.75 else (height-.75)/.25
            color=tuple(round(a+(b-a)*blend) for a,b in zip(low,high))
            gd.line((0,row,size[0],row),fill=color+(255,))
        gradient.putalpha(mask);image.alpha_composite(gradient)
        if percent>=8:
            tip=top+min(4,(104-top)/2)
            glow=Image.new('RGBA',size);g=ImageDraw.Draw(glow)
            g.ellipse((19*scale,(tip-5)*scale,29*scale,(tip+5)*scale),fill=(255,242,177,135))
            image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(2*scale)))
            draw=ImageDraw.Draw(image)
            draw.ellipse((21.5*scale,(tip-2.5)*scale,26.5*scale,(tip+2.5)*scale),fill=(255,255,231,245))
    return image.resize((48,112),Image.Resampling.LANCZOS)


def draw_throw_controls(canvas, power, charging, busy, error='', count=0):
    ink='#30504c';paper='#fffaf2';teal='#368b7d'
    canvas.create_rectangle(0,0,420,37,fill=paper,outline='')
    canvas.create_text(16,18,text='小汉接球场',anchor='w',fill=ink,font=(UI_FONT,11,'bold'))
    canvas.create_text(251,18,text=f'已接回 {count} 球',anchor='e',fill=teal,font=(UI_FONT,9))
    if charging or (not busy and not error):
        for i in range(1,19):
            x,y,_,_=throw_point(i/18,power)
            canvas.create_oval(x-1.6,y-1.6,x+1.6,y+1.6,fill='#fff6ce',outline='#889268',tags='throw_trajectory')
        x,_,ground,radius=throw_point(1,power)
        canvas.create_oval(x-radius-4,ground-3,x+radius+4,ground+3,outline=teal,width=2,tags='throw_landing')
        center,bottom=x+24.5,ground-6
        percent=round(power*100)
        if not hasattr(canvas,'power_photos'): canvas.power_photos={}
        if percent not in canvas.power_photos:
            canvas.power_photos[percent]=ImageTk.PhotoImage(power_badge(percent),master=canvas)
        tags=('power_track','power_fill') if percent else ('power_track',)
        canvas.create_image(center,bottom,anchor='s',image=canvas.power_photos[percent],tags=tags)
        canvas.create_text(center,bottom-98,text=f'{percent}%',fill=ink,font=(UI_FONT,8,'bold'),tags='power_value')
    canvas.create_rectangle(0,290,420,330,fill=paper,outline='')
