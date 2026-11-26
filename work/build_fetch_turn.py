"""Extract the six-row turnaround/trot sheets without changing their artwork."""
from pathlib import Path
from statistics import median
import json
import shutil
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'outputs/XiaohanDesktop/assets'
SOURCES=ROOT/'work/fetch-turn-sources'
POSES=('turnquarter','turnfront','run0','run1','run2','run3')
AGES=('puppy','teen','adult')

def bounds(image):
    return image.getchannel('A').point(lambda a:255 if a>=160 else 0).getbbox()

def ball_center(image):
    # The lit face of the yellow vest is close to the ball in hue. Match a
    # compact orange component with a dark muzzle directly above it.
    from collections import deque
    pixels=image.load()
    orange=set()
    for y in range(image.height//7,image.height*3//4):
        for x in range(image.width//3,image.width):
            r,g,b,a=pixels[x,y]
            if a>=150 and r>135 and 52<g<195 and r-g>38 and .18*(r-g)<g-b<1.05*(r-g):
                orange.add((x,y))
    candidates=[]
    while orange:
        seed=orange.pop()
        group=[seed]
        queue=deque([seed])
        while queue:
            x,y=queue.popleft()
            for pt in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if pt in orange:
                    orange.remove(pt);group.append(pt);queue.append(pt)
        if len(group)<6:continue
        xs,ys=zip(*group)
        l,t,r,b=min(xs),min(ys),max(xs),max(ys)
        w,h=r-l+1,b-t+1
        if not .55<w/h<2.3:continue
        center=median(xs)
        dark=sum(max(pixels[xx,yy][:3])<95 and pixels[xx,yy][3]>=150
                 for yy in range(max(0,t-h),t) for xx in range(max(0,int(center-w*.65)),min(image.width,int(center+w*.65)+1)))
        if dark:
            candidates.append((len(group)*min(1.,dark/(w*h*.20)),center,median(ys)))
    if not candidates:raise ValueError('Missing orange ball beneath muzzle')
    return max(candidates)[1:]

def edges(image,count,vertical=False):
    alpha=image.getchannel('A')
    if vertical:alpha=alpha.transpose(Image.Transpose.TRANSPOSE)
    result=[0]
    for i in range(1,count):
        center=alpha.width*i/count;span=alpha.width/count*.23
        gaps=[]
        for x in range(round(center-span),round(center+span)):
            if sum(a>=160 for a in alpha.crop((x,0,x+1,alpha.height)).getdata())<=2:
                if not gaps or x>gaps[-1][-1]+1:gaps.append([x])
                else:gaps[-1].append(x)
        if not gaps:raise ValueError('No clear atlas gutter')
        gap=max(gaps,key=len);result.append(round((gap[0]+gap[-1])/2))
    return result+[alpha.width]

def extract():
    manifest=json.loads((ASSETS/'fetch-turn-generation.json').read_text(encoding='utf-8'))
    SOURCES.mkdir(exist_ok=True)
    metadata=json.loads((ASSETS/'fetch-anchors.json').read_text(encoding='utf-8'))
    for outfit,source in manifest['files'].items():
        local=SOURCES/(outfit+'.png')
        if not local.exists():shutil.copy2(source,local)
        atlas=Image.open(local).convert('RGBA')
        row_edges=edges(atlas,6,True)
        rows=[atlas.crop((0,row_edges[i],atlas.width,row_edges[i+1])) for i in range(6)]
        cols=[edges(row,3) for row in rows]
        for column,age in enumerate(AGES):
            prefix=outfit if age=='adult' else outfit+'_'+age
            cells=[]
            for row,pose in enumerate(POSES):
                cell=rows[row].crop((cols[row][column],0,cols[row][column+1],rows[row].height))
                box=bounds(cell)
                if box is None:raise ValueError((outfit,age,pose))
                cells.append((pose,cell.crop(box)))
            reference=manifest['normalization'][prefix]
            scale=min(reference['height']/median(im.height for _,im in cells),232/max(im.width for _,im in cells),232/max(im.height for _,im in cells))
            for row,(pose,cell) in enumerate(cells):
                bx,by=ball_center(cell)
                crop=cell.resize((round(cell.width*scale),round(cell.height*scale)),Image.Resampling.LANCZOS)
                target=Image.new('RGBA',(256,256))
                left,top=(256-crop.width)//2,244-crop.height
                target.alpha_composite(crop,(left,top))
                name=prefix+'_fetch_'+pose;target.save(ASSETS/(name+'.png'))
                metadata[name]={'ball':[(left+bx*scale-128)/256,(244-top-by*scale)/256],
                    'radius':reference['radius'],
                    'source':local.name,'cell':[row,column]}
    (ASSETS/'fetch-anchors.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Extracted 54 turnaround/trot sprites')

if __name__=='__main__':extract()
