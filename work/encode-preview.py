from PIL import Image
from pathlib import Path
import sys
sys.path.insert(0,r'C:/Users/txing/.codex/plugins/cache/openai-curated-remote/work-pets/0.1.6/skills/create-pet/scripts')
from render_animation_previews import save_preview
im=Image.open('outputs/xiaohan-two-keys-frames.png').convert('RGBA')
frames=[]
for i in range(6):
    f=im.crop((i*192,0,(i+1)*192,208)).resize((384,416),Image.Resampling.LANCZOS)
    bg=Image.new('RGBA',f.size,'#f3f0e9'); bg.alpha_composite(f)
    frames.append(bg.convert('RGB'))
save_preview(frames,[120]*6,Path('outputs/xiaohan-two-keys.gif'))
with Image.open('outputs/xiaohan-two-keys.gif') as gif:
    print({'frames':gif.n_frames,'size':gif.size,'loop':gif.info.get('loop'),'duration':gif.info.get('duration')})
