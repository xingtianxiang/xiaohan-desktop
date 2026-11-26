"""Render comparisons using the production outdoor compositor."""
from pathlib import Path
import math
import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/XiaohanDesktop'))
from outdoor import OutdoorRenderer
from animation import motion_frame

images={p.stem:Image.open(p).convert('RGBA') for p in (ROOT/'outputs/XiaohanDesktop/assets').glob('*.png')}
renderer=OutdoorRenderer(images)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)


def old(scene):
    frame=ImageOps.fit(images['scene_'+scene],(420,290),Image.Resampling.LANCZOS).convert('RGBA')
    pet=images['blue_walk0'].resize((240,240),Image.Resampling.LANCZOS)
    pet.putalpha(pet.getchannel('A').point(lambda a:255 if a>=128 else 0))
    frame.alpha_composite(pet,(90,35))
    return frame.convert('RGB')


def main():
    comparison=Image.new('RGB',(872,670),'#eeeae1');draw=ImageDraw.Draw(comparison)
    draw.text((16,8),'原效果',font=font,fill='#30504c');draw.text((452,8),'小汉 · 调整后',font=font,fill='#30504c')
    for row,scene in enumerate(('park','snow')):
        comparison.paste(old(scene),(8,44+row*306))
        comparison.paste(renderer.compose(scene,'blue_walk0',174,210,246),(444,44+row*306))
    comparison.save(ROOT/'outputs/xiaohan-outdoor-comparison.png')
    frames=[]
    for scene in ('park','snow'):
        for stage,age in enumerate(('幼年','少年','成年')):
            for index in range(16):
                elapsed=index/8
                name=motion_frame('blue',stage,'walk',elapsed)
                x=118+184*math.sin(index/15*math.pi)
                frame=renderer.compose(scene,name,round(174*(.70,.88,1)[stage]),x,246,index>7)
                draw=ImageDraw.Draw(frame)
                draw.text((14,10),'小汉 · '+age,font=font,fill='#30504c')
                frames.append(frame.quantize(colors=128))
    frames[0].save(ROOT/'outputs/xiaohan-outdoor.gif',save_all=True,append_images=frames[1:],duration=125,loop=0,disposal=2)
    print('Rendered outdoor comparison and animated preview')


if __name__=='__main__':main()
