"""Compose the shipped frames at their runtime sizes for visual comparison."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'outputs/XiaohanDesktop'
sys.path.insert(0,str(APP))
from animation import motion_frame
from flame import TypingFlame

FONT=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20)
SMALL=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
MOTIONS=[('eat','喂食'),('drink','喝水'),('sleep','睡觉'),('type','打字'),('walk','出去玩')]
IMAGES={p.stem:Image.open(p).convert('RGBA') for p in (APP/'assets').glob('*.png')}
FLAME=TypingFlame(IMAGES);FLAME.level=1.


def sprite(name,size):
    image=IMAGES[name].resize((size,size),Image.Resampling.LANCZOS)
    image.putalpha(image.getchannel('A').point(lambda a:255 if a>=128 else 0))
    return image


def page(t,outfit):
    FLAME.phase=t*31
    image=Image.new('RGB',(1200,800),'#ebe9e2');draw=ImageDraw.Draw(image)
    draw.text((26,15),'小汉 · 三阶段动作',font=FONT,fill='#30504c')
    draw.text((940,20),{'blue':'蓝色胸背','red':'红色领巾','yellow':'暖黄背心'}[outfit],font=SMALL,fill='#30504c')
    for col,(_,title) in enumerate(MOTIONS):
        draw.text((200+col*215,60),title,font=FONT,fill='#30504c',anchor='mt')
    for stage,label in enumerate(('幼年','少年','成年')):
        y=100+stage*230
        draw.text((24,y+100),label,font=FONT,fill='#30504c')
        size=round(220*(.70,.88,1)[stage])
        for col,(motion,_) in enumerate(MOTIONS):
            x=200+col*215
            if motion=='type':
                flame=FLAME.image(t,size,fade_alpha=False)
                flame.putalpha(flame.getchannel('A').point(lambda a:255 if a>=128 else 0))
                image.paste(flame,(x-flame.width//2,y+215-flame.height),flame)
            dog=sprite(motion_frame(outfit,stage,motion,t),size)
            image.paste(dog,(x-size//2,y+215-size),dog)
    return image


if __name__=='__main__':
    page(.2,'blue').save(ROOT/'outputs/xiaohan-age-actions.png')
    for outfit in ('red','yellow'):
        page(.2,outfit).save(ROOT/f'work/desktop-qa/age-{outfit}-comparison.png')
    frames=[page(i/8,outfit).resize((900,600),Image.Resampling.LANCZOS).quantize(colors=96) for outfit in ('blue','red','yellow') for i in range(16)]
    frames[0].save(ROOT/'outputs/xiaohan-age-actions.gif',save_all=True,append_images=frames[1:],duration=125,loop=0,disposal=2)
    print('Saved three-stage comparison PNG and GIF')
