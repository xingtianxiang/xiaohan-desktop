"""Generate the keyboard typing frames with Jimeng Seedream 5.5 (green-screen bases, then four paw poses).

Usage: python generate_typing_frames.py <bases|poses> [set ...] [--poses 1,3]
Sets are <outfit>_<age>, e.g. red_teen; without names every set runs. Output and the prompt manifest go to
work/desktop-qa/keyboard-jimeng/set/. Earlier results are kept: a rerun writes a new file next to the old one.
"""
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'outputs/XiaohanDesktop/assets'
WORK = ROOT / 'work/desktop-qa/keyboard-jimeng'
SETS = WORK / 'set'
CLI = Path.home() / '.local/share/jimeng-novel/releases/jimeng-novel-1.0.3-windows-amd64-22ea0b0844ae/jimeng-novel.exe'
MODEL = 'seedream_5.5'
# The small blue set's green base fixes the composition every other set follows.
COMPOSITION = WORK / 'green/e5da3a92-8a76-4acd-bbb9-f71ec50fa9a0-15317165994508.png'
AGES = {'puppy': '幼年小汉，圆脸、短腿、身体圆滚滚',
        'teen': '少年小汉，比幼年更修长，腿和身体更长，脸稍微拉长',
        'adult': '成年小汉，体型最大，胸前和脖子的毛更厚更蓬，脸型成熟'}
OUTFITS = {'blue': ('戴蓝色胸背', '胸背上只挂一个徽章，和图2一样'),
           'red': ('脖子上系红色领巾', '不要胸背和徽章，只有红色领巾，结打在脖子一侧'),
           'yellow': ('穿暖黄色背心，领口和袖口是蓝色滚边', '不要胸背和徽章')}
BASE_PROMPT = (
    '图1是要沿用的画面：小汉侧身坐在一把斜放的小键盘后面，两只前爪搭在键盘上打字。请完全沿用图1的构图、角度、'
    '她在画面里的位置和大小、键盘的样式（米色键帽、深灰色底座）、键盘的位置和大小、纯绿色背景和柔和的绘本插画画风。\n'
    '图2、图3是这次要画的小汉：{age}，{outfit}。请按图2、图3画她的体型、脸型、毛发和衣服，{rule}。\n'
    '她看着画面前方，表情开心，两只前爪都搭在键盘上。背景是均匀的纯绿色（RGB 0,255,0），不要地面阴影，不要文字和水印。')
POSE_LEAD = ('保持图1完全不变：同一只小汉，身体的位置和大小、头的位置和朝向、脸和表情、衣服、键盘的位置角度和大小、'
             '纯绿色背景、画风全都不变。只改变两只前爪的姿势：')
POSES = {
    1: '画面左边那只前爪按在键盘上的一个键上，按得很用力，那个键陷下去；画面右边那只前爪高高抬起，明显离开键盘，爪子和键盘之间能看到一段空隙。',
    2: '两只前爪都平放在键盘上，肉垫贴着键帽。',
    3: '画面右边那只前爪按在键盘上的一个键上，按得很用力，那个键陷下去；画面左边那只前爪高高抬起，明显离开键盘，爪子和键盘之间能看到一段空隙。',
    4: '两只前爪都抬起来，明显离开键盘，悬在键盘上方，爪子和键盘之间能看到一段空隙。',
}
POSE_TAIL = '其他任何地方都不要改动，不要文字和水印。'
lock = threading.Lock()


def painting(outfit, age, pose=''):
    # Idle paintings always carry the age; adult motion frames drop it (blue_adult.png, blue_type0.png).
    if pose and age == 'adult':
        return ASSETS / f'{outfit}{pose}.png'
    return ASSETS / f'{outfit}_{age}{pose}.png'


def generate(name, kind, prompt, refs, out):
    out.mkdir(parents=True, exist_ok=True)
    before = set(out.glob('*.png'))
    args = [str(CLI), 'generate-image', '--model', MODEL, '--prompt', prompt, '--ratio', '1:1',
            '--generate-image-count', '1', '--team-id', '0', '--wait', '280', '--out', str(out) + '/']
    for ref in refs:
        args += ['--image', str(ref)]
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    made = sorted(set(out.glob('*.png')) - before)
    record = {'set': name, 'kind': kind, 'model': MODEL, 'prompt': prompt, 'refs': [str(r) for r in refs],
              'file': str(made[-1]) if made else None, 'ok': bool(made), 'log': result.stdout[-400:] + result.stderr[-400:]}
    with lock:
        manifest = SETS / 'manifest.json'
        entries = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else []
        entries.append(record)
        manifest.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding='utf-8')
        print(('OK  ' if made else 'FAIL') + f' {name} {kind}', flush=True)
    return record


def latest(folder):
    files = sorted(folder.glob('*.png'), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def jobs(mode, names, poses):
    for name in names:
        outfit, age = name.split('_')
        folder = SETS / name
        if mode == 'bases':
            prompt = BASE_PROMPT.format(age=AGES[age], outfit=OUTFITS[outfit][0], rule=OUTFITS[outfit][1])
            yield name, 'base', prompt, [COMPOSITION, painting(outfit, age), painting(outfit, age, '_type0')], folder / 'base'
        else:
            base = COMPOSITION if name == 'blue_puppy' else latest(folder / 'base')
            for pose in poses:
                yield name, f'pose{pose}', POSE_LEAD + POSES[pose] + POSE_TAIL, [base], folder / f'pose{pose}'


def main():
    args = sys.argv[1:]
    mode = args.pop(0)
    poses = [1, 2, 3, 4]
    if '--poses' in args:
        at = args.index('--poses')
        poses = [int(p) for p in args[at + 1].split(',')]
        del args[at:at + 2]
    names = args or [f'{o}_{a}' for o in OUTFITS for a in AGES if not (mode == 'bases' and o == 'blue' and a == 'puppy')]
    SETS.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda job: generate(*job), jobs(mode, names, poses)))
    print('done', sum(r['ok'] for r in results), 'of', len(results))


if __name__ == '__main__':
    main()
