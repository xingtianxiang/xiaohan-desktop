from pathlib import Path
import sys
import json
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/XiaohanDesktop'))
from fetch_game import fetch_frame, walk_position
from outdoor import OutdoorRenderer
from animation import motion_frame, fetch_asset, FETCH_POSES
images={p.stem:Image.open(p).convert('RGBA') for p in (ROOT/'outputs/XiaohanDesktop/assets').glob('*.png')}
renderer=OutdoorRenderer(images)
metadata=json.loads((ROOT/'outputs/XiaohanDesktop/assets/fetch-anchors.json').read_text(encoding='utf-8'))
anchors={pose:metadata[fetch_asset('blue',2,pose)] for pose in FETCH_POSES}
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',15)
frames=[]
for index in range(301):
    progress=index/300
    sheet=Image.new('RGB',(840,332),'#fffaf2')
    draw=ImageDraw.Draw(sheet)
    for column,power in enumerate((.18,.88)):
        sample=fetch_frame(progress,power,174,anchors,walk_position(2))
        origin_name=motion_frame('blue',2,'walk',2)
        scene=renderer.compose_fetch('park','blue',2,174,sample,origin_name)
        sheet.paste(scene,(column*420,25))
        draw.text((column*420+14,3),f'力度 {power:.0%}',font=font,fill='#30504c')
        draw.text((column*420+14,311),sample.message,font=font,fill='#30504c')
    frames.append(sheet)
frames[160].save(ROOT/'outputs/xiaohan-fetch-depth.png')
for index in (67,80,87,93,100,108,115,139):frames[index*2].save(ROOT/f'work/desktop-qa/fetch-turn-{index}.png')
palette=frames[0].quantize(colors=128)
indexed=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
indexed[0].save(ROOT/'outputs/xiaohan-fetch.gif',save_all=True,append_images=indexed[1:],duration=33,loop=0,optimize=True)
indexed[132].save(ROOT/'outputs/xiaohan-return.gif',save_all=True,append_images=indexed[133:],duration=33,loop=0,optimize=True)
