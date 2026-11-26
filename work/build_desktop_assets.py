from pathlib import Path
import sys
from PIL import Image, ImageDraw
sys.path.insert(0,r'C:/Users/txing/.codex/plugins/cache/openai-curated-remote/work-pets/0.1.6/skills/create-pet/scripts')
from extract_strip_frames import remove_chroma_background
from despill_chroma_edges import atlas_edge_band, suppress_boundary_spill, srgb_to_linear

GEN=Path(r'C:/Users/txing/.codex/generated_images/01a1c842-85b2-7933-8710-1e80f361c5f3')
OUT=Path('outputs/XiaohanDesktop/assets')
CARE={'blue':'exec-4c4b732b-8149-4de1-b38a-f4a024051a51.png','red':'exec-fdebc87e-54dd-4a88-8b58-a74767e4510b.png','yellow':'exec-9c04fa0f-2359-4c6c-aede-f7876ca43af8.png'}
TYPE={'blue':'exec-06ccc804-b910-401b-86e6-da161bbc387e.png','red':'exec-ff494ad7-0c3c-4234-b37a-48d0f611f643.png','yellow':'exec-76e252ac-6e48-44c6-99ea-cf82cae62ce5.png'}
NAMES=['puppy','teen','adult','shy','eat0','eat1','drink0','drink1','play0','play1','sleep0','sleep1']

def clean(image):
    im=remove_chroma_background(image,(0,255,0),180)
    # Use the bundled edge-local spill cleanup; never repaint the character.
    pixels,_=suppress_boundary_spill(list(im.getdata()),size=im.size,boundary=atlas_edge_band(im.getchannel('A'),3),key_linear=(0.,1.,0.),strength=1.,edge_radius=3,spill_tolerance=.15,minimum_saturation=.1)
    im.putdata(pixels)
    return im

def cells(path,cols,rows):
    im=Image.open(path).convert('RGBA')
    return [clean(im.crop((round(c*im.width/cols),round(r*im.height/rows),round((c+1)*im.width/cols),round((r+1)*im.height/rows)))) for r in range(rows) for c in range(cols)]

def save_group(group,names,scale=None):
    boxes=[im.getbbox() for im in group]
    assert all(boxes),'Blank sprite'
    if scale is None:
        scale=min(232/max(b[2]-b[0] for b in boxes),232/max(b[3]-b[1] for b in boxes))
    for im,box,name in zip(group,boxes,names):
        crop=im.crop(box)
        crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
        target=Image.new('RGBA',(256,256))
        target.alpha_composite(crop,((256-crop.width)//2,244-crop.height))
        target.save(OUT/(name+'.png'))

OUT.mkdir(parents=True,exist_ok=True)
for outfit,path in CARE.items():
    save_group(cells(GEN/path,4,3),[outfit+'_'+n for n in NAMES])
for outfit,path in TYPE.items():
    save_group(cells(GEN/path,6,1),[outfit+'_type'+str(i) for i in range(6)])
from build_selected_fire import build as build_selected_fire
build_selected_fire()
walk=cells(GEN/'exec-0ec5279a-d206-40c7-8035-e4e79a7b768d.png',6,3)
for row,outfit in enumerate(CARE):
    save_group(walk[row*6:(row+1)*6],[outfit+'_walk'+str(i) for i in range(6)])
scenes=Image.open(GEN/'exec-723b850a-6c3e-40d9-9bd1-00221d0e2937.png')
for i,name in enumerate(('home','park','snow')):
    scenes.crop((round(i*scenes.width/3),0,round((i+1)*scenes.width/3),scenes.height)).save(OUT/('scene_'+name+'.png'))
Image.open(OUT/'blue_puppy.png').save(OUT/'xiaohan.ico',sizes=[(32,32),(64,64),(128,128),(256,256)])
sheet=Image.new('RGB',(1024,3*290),'#e7e4de')
d=ImageDraw.Draw(sheet)
for row,outfit in enumerate(CARE):
    for col,state in enumerate(('puppy','eat0','play0','type2')):
        im=Image.open(OUT/(outfit+'_'+state+'.png'))
        sheet.paste(im,(col*256,row*290),im)
        d.text((col*256+10,row*290+260),outfit+' / '+state,fill='black')
sheet.save('work/desktop-qa/asset-contact.jpg')
print('Built',len(list(OUT.glob('*.png'))),'PNG assets')
