"""Turn the generated green-screen typing poses into the pet's typing frames and keyboard geometry.

Usage: python build_typing_assets.py
Reads work/desktop-qa/keyboard-jimeng/set/<outfit>_<age>/pose1..4 (newest file in each, or the file named in
the set's choice.json), keys out the green, aligns the four poses of a set in one shared box, and writes
assets/<prefix>_type0..3.png, assets/typing-keyboards.json and assets/typing-generation.json.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'outputs/XiaohanDesktop/assets'
SETS = ROOT / 'work/desktop-qa/keyboard-jimeng/set'
ART = 256
SOLE = 246
# Frame order of the typing cycle: left paw presses, both lift, right paw presses, both rest.
ORDER = (1, 4, 3, 2)
KEY_DEPTH = .15


def key_out(image):
    rgb = np.asarray(image.convert('RGB')).astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    alpha = 1 - np.clip((g - np.maximum(r, b) - 22) / 88, 0, 1)
    h, w = alpha.shape
    alpha[: int(h * .11), : int(w * .22)] = 0  # Jimeng's corner watermark
    g = np.minimum(g, np.maximum(r, b) + 6)  # green spill on fur edges
    return Image.fromarray(np.dstack([r, g, b, alpha * 255]).clip(0, 255).astype(np.uint8), 'RGBA')


def keyboard(frame):
    """The key area: the keyboard's ends, its front edge (the dark base's top, as a line) and its depth.

    Paws cover the back rows and the generated keyboards show no back outline, so the depth is a share of the
    keyboard's length, matched by eye on the small blue set.
    """
    a = np.asarray(frame).astype(np.int32)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    base = (al > 200) & (np.maximum(np.maximum(r, g), b) < 95) & (np.abs(r - b) < 25)
    base[: int(ART * .7)] = False
    columns = [x for x in range(ART) if base[:, x].sum() >= 3]
    xs = np.array(columns, dtype=float)
    tops = np.array([np.nonzero(base[:, x])[0].min() for x in columns], dtype=float)
    left, right = float(np.percentile(xs, 2)), float(np.percentile(xs, 98))
    return {'left': round(left, 1), 'right': round(right, 1), 'front': [round(v, 5) for v in np.polyfit(xs, tops, 1)],
            'depth': round(KEY_DEPTH * (right - left), 1)}


def chosen(folder):
    choice = folder.parent / 'choice.json'
    picks = json.loads(choice.read_text(encoding='utf-8')) if choice.exists() else {}
    if folder.name in picks:
        return folder / picks[folder.name]
    return sorted(folder.glob('*.png'), key=lambda p: p.stat().st_mtime)[-1]


def build():
    geometry, sources = {}, {}
    manifest = json.loads((SETS / 'manifest.json').read_text(encoding='utf-8'))
    for folder in sorted(p for p in SETS.iterdir() if p.is_dir()):
        outfit, age = folder.name.split('_')
        files = [chosen(folder / f'pose{pose}') for pose in ORDER]
        keyed = [key_out(Image.open(path)) for path in files]
        boxes = [im.getchannel('A').point(lambda v: 255 if v > 128 else 0).getbbox() for im in keyed]
        box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
        scale = min(236 / (box[2] - box[0]), 232 / (box[3] - box[1]))
        size = (round((box[2] - box[0]) * scale), round((box[3] - box[1]) * scale))
        prefix = outfit if age == 'adult' else f'{outfit}_{age}'
        frames = []
        for index, image in enumerate(keyed):
            canvas = Image.new('RGBA', (ART, ART))
            canvas.alpha_composite(image.crop(box).resize(size, Image.Resampling.LANCZOS), ((ART - size[0]) // 2, SOLE - size[1]))
            canvas.save(ASSETS / f'{prefix}_type{index}.png')
            frames.append(canvas)
        geometry[folder.name] = keyboard(frames[ORDER.index(4)])
        prompts = {r['file']: r['prompt'] for r in manifest}
        sources[folder.name] = [{'frame': f'{prefix}_type{i}.png', 'pose': pose, 'source': path.name,
                                 'prompt': prompts.get(str(path))} for i, (pose, path) in enumerate(zip(ORDER, files))]
        print(folder.name, geometry[folder.name])
    (ASSETS / 'typing-keyboards.json').write_text(json.dumps(geometry, ensure_ascii=False, indent=1), encoding='utf-8')
    (ASSETS / 'typing-generation.json').write_text(json.dumps(
        {'tool': 'jimeng-novel generate-image', 'model': 'seedream_5.5',
         'note': 'Green-screen poses keyed out locally; the corner AI watermark is masked. Sources and logs: '
                 'work/desktop-qa/keyboard-jimeng/set (not tracked).',
         'sets': sources}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    build()
