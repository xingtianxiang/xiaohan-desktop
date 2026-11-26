"""Slice approved fetch atlases and measure their embedded ball anchors."""
from collections import deque
from pathlib import Path
import json
import shutil
from statistics import median
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'outputs/XiaohanDesktop/assets'
SOURCES=ROOT/'work/fetch-action-sources'
GENERATED=Path('C:/Users/txing/.codex/generated_images/01a1c842-85b2-7933-8710-1e80f361c5f3')
FILES={'blue':'exec-774122e2-bdc6-4acd-80ab-4fb458001926.png',
       'red':'exec-72ecea36-aadd-46c8-ab35-5649348dad67.png',
       'yellow':'exec-7afb779e-6088-4669-9e40-b0affe6a8b48.png'}
POSES=('pickup','carry0','carry1','drop')
AGES=('puppy','teen','adult')


def visible_box(image):
    return image.getchannel('A').point(lambda a:255 if a>=128 else 0).getbbox()


def column_edges(row):
    alpha=row.getchannel('A');gaps=[]
    for x in range(row.width):
        empty=sum(a>=160 for a in alpha.crop((x,0,x+1,row.height)).getdata())<3
        if empty:
            if not gaps or x>gaps[-1][-1]+1:gaps.append([x])
            else:gaps[-1].append(x)
    internal=[gap for gap in gaps if gap[0]>row.width*.15 and gap[-1]<row.width*.85 and len(gap)>4]
    if len(internal)!=2:raise ValueError('Expected two clear sprite gutters')
    return [0,*[round((gap[0]+gap[-1])/2) for gap in internal],row.width]


def ball_box(image,pose):
    box=visible_box(image);w,h=box[2]-box[0],box[3]-box[1]
    pixels=image.load();candidates=set()
    for y in range(box[1],box[3]):
        for x in range(box[0],box[2]):
            if pose=='drop' and y<box[3]-h*.18:continue
            if pose!='drop' and x<box[0]+w*.65:continue
            r,g,b,a=pixels[x,y]
            if a>=128 and r>150 and 65<g<180 and b<115 and r-g>35 and g-b>20:
                candidates.add((x,y))
    groups=[]
    while candidates:
        start=candidates.pop();group=[start];queue=deque([start])
        while queue:
            x,y=queue.popleft()
            for point in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if point in candidates:candidates.remove(point);group.append(point);queue.append(point)
        if len(group)>8:groups.append(group)
    if not groups:raise ValueError('No orange ball found')
    group=max(groups,key=len)
    return min(p[0] for p in group),min(p[1] for p in group),max(p[0] for p in group)+1,max(p[1] for p in group)+1


SOURCES.mkdir(exist_ok=True)
metadata={}
for outfit,filename in FILES.items():
    local=SOURCES/(outfit+'.png')
    if not local.exists():shutil.copy2(GENERATED/filename,local)
    atlas=Image.open(local).convert('RGBA')
    rows=[atlas.crop((0,round(row*atlas.height/4),atlas.width,round((row+1)*atlas.height/4))) for row in range(4)]
    edges=[column_edges(row) for row in rows]
    for column,age in enumerate(AGES):
        cells=[]
        for row,pose in enumerate(POSES):
            cell=rows[row].crop((edges[row][column],0,edges[row][column+1],rows[row].height))
            cells.append((pose,cell,visible_box(cell),ball_box(cell,pose)))
        prefix=outfit if age=='adult' else outfit+'_'+age
        old=[visible_box(Image.open(ASSETS/(prefix+'_walk'+str(i)+'.png')).convert('RGBA')) for i in range(6 if age=='adult' else 4)]
        height=median(b[3]-b[1] for b in old)
        scale=min(height/max(b[3]-b[1] for _,_,b,_ in cells),232/max(b[2]-b[0] for _,_,b,_ in cells))
        for pose,cell,box,ball in cells:
            if pose not in ('pickup','drop'):continue
            crop=cell.crop(box)
            crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
            target=Image.new('RGBA',(256,256))
            left,top=(256-crop.width)//2,244-crop.height
            target.alpha_composite(crop,(left,top))
            name=prefix+'_fetch_'+pose
            target.save(ASSETS/(name+'.png'))
            bx=left+((ball[0]+ball[2])/2-box[0])*scale
            by=top+((ball[1]+ball[3])/2-box[1])*scale
            ground=target.getchannel('A').point(lambda a:255 if a>=95 else 0).getbbox()[3]
            metadata[name]={'ball':[(bx-128)/256,(ground-by)/256],
                            'radius':((ball[2]-ball[0])+(ball[3]-ball[1]))*scale/4/256,
                            'source':filename,'cell':[POSES.index(pose),column]}
(ASSETS/'fetch-anchors.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
print('Built',len(metadata),'fetch frames')
