from pathlib import Path
import sys
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/XiaohanDesktop'))
from animation import motion_frame
from outdoor import OutdoorRenderer
assets=ROOT/'outputs/XiaohanDesktop/assets'
renderer=OutdoorRenderer({p.stem:Image.open(p).convert('RGBA') for p in assets.glob('*.png')})
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
frames=[]
for index in range(40):
    frame=Image.new('RGB',(660,242),'#fffaf2');draw=ImageDraw.Draw(frame)
    for col,(motion,title) in enumerate((('hungry','肚子饿了'),('thirsty','想喝水了'),('tired','累了，想休息'))):
        name=motion_frame('blue',2,motion,index/10)
        sprite=renderer.sprite('park',name,190,False)
        frame.paste(sprite,(col*220+15,24),sprite)
        draw.text((col*220+32,214),title,font=font,fill='#30504c')
    frames.append(frame)
frames[0].save(ROOT/'outputs/xiaohan-needs.png')
frames[0].save(ROOT/'outputs/xiaohan-needs.gif',save_all=True,append_images=frames[1:],duration=100,loop=0)
