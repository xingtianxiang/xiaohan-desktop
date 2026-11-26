"""Extract generated alpha atlases into the existing desktop sprite format."""
from pathlib import Path
import json
import shutil
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
GEN = Path('C:/Users/txing/.codex/generated_images/01a1c842-85b2-7933-8710-1e80f361c5f3')
SOURCES = {
    'blue_puppy': 'exec-c4be7281-11ff-41ec-ba0b-3d31b5c9d108.png',
    'blue_teen': 'exec-ab287b17-acf3-4f89-886e-c830931b2856.png',
    'red_puppy': 'exec-1f43de91-be27-4ad7-83fd-614870f4101e.png',
    'red_teen': 'exec-8b194afa-d452-4e3d-9584-99dea0ac5c2a.png',
    'yellow_puppy': 'exec-16c618a8-63ed-4240-a756-8cadfd8f1ebf.png',
    'yellow_teen': 'exec-96af9cbf-447d-4f4a-a979-f2859a67ae8e.png',
}
NAMES = ['eat0', 'eat1', 'drink0', 'drink1', 'sleep0', 'sleep1', 'play0', 'play1'] + [f'type{i}' for i in range(4)] + [f'walk{i}' for i in range(4)]
OUT = ROOT / 'outputs/XiaohanDesktop/assets'
SOURCE_OUT = ROOT / 'work/age-action-sources'


def extract():
    SOURCE_OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for prefix, filename in SOURCES.items():
        local = SOURCE_OUT / (prefix + '.png')
        if not local.exists():
            shutil.copy2(GEN / filename, local)
        atlas = Image.open(local).convert('RGBA')
        sprites = []
        boxes = []
        for index, name in enumerate(NAMES):
            row, col = divmod(index, 4)
            cell = atlas.crop((round(col*atlas.width/4), round(row*atlas.height/4), round((col+1)*atlas.width/4), round((row+1)*atlas.height/4)))
            # Match the renderer's color-key alpha threshold for visible bounds;
            # preserve generated alpha inside the crop, including soft fur edges.
            box = cell.getchannel('A').point(lambda a: 255 if a >= 128 else 0).getbbox()
            if not box:
                raise ValueError(f'Empty sprite: {prefix}_{name}')
            sprites.append(cell)
            boxes.append(box)
        # Shared scale within each sheet avoids breathing/step size jitter.
        scale = min(232/max(b[2]-b[0] for b in boxes), 232/max(b[3]-b[1] for b in boxes))
        for cell, box, name in zip(sprites, boxes, NAMES):
            crop = cell.crop(box)
            if name.startswith('walk'):
                crop = ImageOps.mirror(crop)  # Runtime expects outward travel to face right.
            crop = crop.resize((round(crop.width*scale), round(crop.height*scale)), Image.Resampling.LANCZOS)
            target = Image.new('RGBA', (256, 256))
            target.alpha_composite(crop, ((256-crop.width)//2, 244-crop.height))
            target.save(OUT / (prefix + '_' + name + '.png'))
            report.append(dict(name=prefix+'_'+name, source=filename, cell=NAMES.index(name), bbox=box))
    (SOURCE_OUT / 'manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Extracted {len(report)} age-specific frames')


if __name__ == '__main__':
    extract()
