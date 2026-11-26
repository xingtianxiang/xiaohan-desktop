"""Export the restless potty idle pairs for each age and outfit."""
from pathlib import Path
from statistics import median
import json
import shutil
from PIL import Image
from build_need_assets import edges,bounds

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'outputs/XiaohanDesktop/assets'
manifest=json.loads((ASSETS/'toilet-generation.json').read_text(encoding='utf-8'))
local=ROOT/manifest['project_source'];local.parent.mkdir(exist_ok=True)
if not local.exists():shutil.copy2(manifest['source'],local)
atlas=Image.open(local).convert('RGBA');cols=edges(atlas,3)
for col,age in enumerate(('puppy','teen','adult')):
    strip=atlas.crop((cols[col],0,cols[col+1],atlas.height));rows=edges(strip,6,True)
    for group,outfit in enumerate(('blue','red','yellow')):
        cells=[]
        for row in (group*2,group*2+1):
            cell=strip.crop((0,rows[row],strip.width,rows[row+1]));cells.append(cell.crop(bounds(cell)))
        prefix=outfit if age=='adult' else outfit+'_'+age
        old=[bounds(Image.open(ASSETS/(prefix+'_walk'+str(i)+'.png')).convert('RGBA')) for i in range(6 if age=='adult' else 4)]
        scale=min(median(b[3]-b[1] for b in old)/max(im.height for im in cells),232/max(im.width for im in cells),232/max(im.height for im in cells))
        for index,cell in enumerate(cells):
            sprite=cell.resize((round(cell.width*scale),round(cell.height*scale)),Image.Resampling.LANCZOS)
            target=Image.new('RGBA',(256,256));target.alpha_composite(sprite,((256-sprite.width)//2,244-sprite.height))
            target.save(ASSETS/(prefix+'_potty'+str(index)+'.png'))
print('Built 18 potty idle sprites')
