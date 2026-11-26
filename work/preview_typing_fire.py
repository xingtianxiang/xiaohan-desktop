"""Export the production flame lifecycle with the desktop color-key alpha rule."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/XiaohanDesktop'))
from flame import TypingFlame
from animation import motion_frame
from keyboard_activity import KeyboardActivity

images={p.stem:Image.open(p).convert('RGBA') for p in (ROOT/'outputs/XiaohanDesktop/assets').glob('*.png')}
flame=TypingFlame(images)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
frames=[]
keyboard=KeyboardActivity()
pending=0.
for index in range(180):
    now=index/20
    rate=2 if now<2.5 else (10 if now<5 else (2 if now<7 else 0))
    pending+=rate/20
    while pending>=1:
        keyboard.record_activity(now);pending-=1
    typing=now-keyboard.last_activity<.8
    flame.update(now,typing,speed=keyboard.speed(now))
    frame=Image.new('RGB',(360,340),'#ece9e2')
    draw=ImageDraw.Draw(frame)
    label='慢速输入 · 小火' if now<2.5 else ('快速输入 · 火变旺' if now<5 else ('放慢速度 · 火收小' if now<7 else '停止输入 · 熄灭'))
    draw.text((180,22),label,font=font,fill='#30504c',anchor='mt')
    fire=flame.image(now,240,fade_alpha=False)
    if fire is not None:
        fire.putalpha(fire.getchannel('A').point(lambda a:255 if a>=128 else 0))
        frame.paste(fire,(180-fire.width//2,305-fire.height),fire)
    name=motion_frame('blue',2,'type',now) if typing else 'blue_adult'
    pet=images[name].resize((240,240),Image.Resampling.LANCZOS)
    pet.putalpha(pet.getchannel('A').point(lambda a:255 if a>=128 else 0))
    frame.paste(pet,(60,65),pet)
    frames.append(frame.quantize(colors=128))
frames[0].save(ROOT/'outputs/xiaohan-typing-fire.gif',save_all=True,append_images=frames[1:],duration=50,loop=0,disposal=2)
print('Saved slow / fast / slowing / stopped typing preview')

# Side-by-side comparison keeps the pet, pose and camera identical, making the
# speed-dependent height visible without waiting for one long sequence.
comparison=[]
effects=[TypingFlame(images) for _ in range(3)]
inputs=[KeyboardActivity() for _ in range(3)]
rates=(2,5,10)
titles=('B · 慢打：脚边小火','B · 正常：两侧火焰','B · 快打：肩部烈焰')
for index in range(100):
    now=index/20
    page=Image.new('RGB',(1080,340),'#ece9e2')
    for column,rate in enumerate(rates):
        if index%(20//rate)==0:inputs[column].record_activity(now)
        effects[column].update(now,True,speed=inputs[column].speed(now))
        tile=Image.new('RGB',(360,340),'#ece9e2')
        ImageDraw.Draw(tile).text((180,22),titles[column],font=font,fill='#30504c',anchor='mt')
        effect=effects[column].image(now,240,fade_alpha=False)
        if effect is not None:
            effect.putalpha(effect.getchannel('A').point(lambda a:255 if a>=128 else 0))
            tile.paste(effect,(180-effect.width//2,305-effect.height),effect)
        pet=images[motion_frame('blue',2,'type',now)].resize((240,240),Image.Resampling.LANCZOS)
        pet.putalpha(pet.getchannel('A').point(lambda a:255 if a>=128 else 0))
        tile.paste(pet,(60,65),pet);page.paste(tile,(column*360,0))
    if index>=40:comparison.append(page.quantize(colors=128))
    if index==80:page.save(ROOT/'outputs/xiaohan-B-speed.png')
comparison[0].save(ROOT/'outputs/xiaohan-B-speed.gif',save_all=True,append_images=comparison[1:],duration=50,loop=0,disposal=2)
print('Saved B slow / medium / fast comparison')
