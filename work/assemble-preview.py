from pathlib import Path
from PIL import Image
import sys
sys.path.insert(0, r'C:/Users/txing/.codex/plugins/cache/openai-curated-remote/work-pets/0.1.6/skills/create-pet/scripts')
from render_animation_previews import save_preview
root=Path('work/typing-two-keys/frames/running')
frames=[Image.open(p).convert('RGBA') for p in sorted(root.glob('*.png'))]
strip=Image.new('RGBA',(192*6,208))
for i,f in enumerate(frames): strip.paste(f,(192*i,0))
strip.save('work/typing-two-keys/strip.png')
