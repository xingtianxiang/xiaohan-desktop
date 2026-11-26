"""Extract the selected B animation with one shared crop and baseline."""
from pathlib import Path
import shutil
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/'work/flame-style-sources'
GEN=Path('C:/Users/txing/.codex/generated_images/01a1c842-85b2-7933-8710-1e80f361c5f3')
ATLAS_FILES={'B':'exec-44dcacb6-d01d-4172-92f8-a0eed9e1e5cc.png','F':'exec-9c367c25-697f-419c-ab9f-ee0ba9abd609.png'}


def build():
    SOURCES.mkdir(parents=True,exist_ok=True)
    for label,filename in ATLAS_FILES.items():
        local=SOURCES/f'{label}.png'
        if not local.exists():shutil.copy2(GEN/filename,local)
    atlas=Image.open(SOURCES/'B.png').convert('RGBA')
    cells=[];boxes=[]
    for row in range(2):
        for col in range(2):
            cell=atlas.crop((round(col*atlas.width/2),round(row*atlas.height/2),round((col+1)*atlas.width/2),round((row+1)*atlas.height/2)))
            box=cell.getchannel('A').point(lambda a:255 if a>=128 else 0).getbbox()
            if not box:raise ValueError('B flame atlas contains an empty frame')
            cells.append(cell);boxes.append(box)
    # One shared rectangle keeps roots and sparks from jumping between frames.
    union=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
    scale=min(232/(union[2]-union[0]),232/(union[3]-union[1]))
    for index,cell in enumerate(cells):
        crop=cell.crop(union)
        crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
        target=Image.new('RGBA',(256,256))
        target.alpha_composite(crop,((256-crop.width)//2,244-crop.height))
        target.save(ROOT/f'outputs/XiaohanDesktop/assets/fire{index}.png')
    print('Installed four B frames; F retained as an unselected source atlas')


if __name__=='__main__':build()
