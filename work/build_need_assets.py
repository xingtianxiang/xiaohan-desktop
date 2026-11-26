"""Cut the transparent needs atlases into aligned runtime sprites."""
from pathlib import Path
from statistics import median
import json
import shutil
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'outputs/XiaohanDesktop/assets'
SOURCES=ROOT/'work/need-state-sources'
POSES=('hungry0','hungry1','thirsty0','thirsty1','tired0','tired1')

def bounds(image):
    return image.getchannel('A').point(lambda a:255 if a>=160 else 0).getbbox()

def edges(image,count,vertical=False):
    alpha=image.getchannel('A')
    if vertical:alpha=alpha.transpose(Image.Transpose.TRANSPOSE)
    result=[0]
    for i in range(1,count):
        center=alpha.width*i/count;span=alpha.width/count*.45
        gaps=[];scores=[]
        for x in range(round(center-span),round(center+span)):
            score=sum(a>=160 for a in alpha.crop((x,0,x+1,alpha.height)).getdata())
            scores.append((score,x))
            if score<=1:
                if not gaps or x>gaps[-1][-1]+1:gaps.append([x])
                else:gaps[-1].append(x)
        if gaps:
            gap=max(gaps,key=len);result.append(round((gap[0]+gap[-1])/2))
        else:
            score,edge=min(scores)
            if score>alpha.height*.04:raise ValueError('Missing sprite gutter')
            result.append(edge)
    return result+[alpha.width]

def build():
    manifest=json.loads((ASSETS/'need-generation.json').read_text(encoding='utf-8'))
    SOURCES.mkdir(exist_ok=True)
    for outfit,source in manifest['files'].items():
        local=SOURCES/(outfit+'.png')
        if not local.exists():shutil.copy2(source,local)
        atlas=Image.open(local).convert('RGBA');columns=edges(atlas,3)
        for column,age in enumerate(('puppy','teen','adult')):
            strip=atlas.crop((columns[column],0,columns[column+1],atlas.height))
            rows=edges(strip,6,True);cells=[]
            for row in range(6):
                cell=strip.crop((0,rows[row],strip.width,rows[row+1]))
                box=bounds(cell)
                if box is None:raise ValueError((outfit,age,row,'empty'))
                cells.append(cell.crop(box))
            prefix=outfit if age=='adult' else outfit+'_'+age
            old=[bounds(Image.open(ASSETS/(prefix+'_walk'+str(i)+'.png')).convert('RGBA')) for i in range(6 if age=='adult' else 4)]
            target_height=median(b[3]-b[1] for b in old)
            scale=min(target_height/max(im.height for im in cells),232/max(im.width for im in cells),232/max(im.height for im in cells))
            for pose,cell in zip(POSES,cells):
                crop=cell.resize((round(cell.width*scale),round(cell.height*scale)),Image.Resampling.LANCZOS)
                target=Image.new('RGBA',(256,256));target.alpha_composite(crop,((256-crop.width)//2,244-crop.height))
                target.save(ASSETS/(prefix+'_'+pose+'.png'))
    print('Built 54 needs sprites')

if __name__=='__main__':build()
