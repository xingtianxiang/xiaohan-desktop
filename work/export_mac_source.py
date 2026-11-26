"""Create a reviewable, allow-listed cloud build tree without personal data."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'outputs/XiaohanDesktop'
DEST=ROOT/'outputs/XiaohanMacBuild'
ARCHIVE=ROOT/'outputs/小汉-Mac构建源码.zip'


def main():
    if DEST.exists() or ARCHIVE.exists():raise SystemExit('Review existing source export before replacing it.')
    (DEST/'app/assets').mkdir(parents=True)
    (DEST/'app/tests').mkdir()
    for source in APP.glob('*.py'):shutil.copy2(source,DEST/'app'/source.name)
    for source in (APP/'tests').glob('test_*.py'):shutil.copy2(source,DEST/'app/tests'/source.name)
    for source in (APP/'assets').glob('*.png'):shutil.copy2(source,DEST/'app/assets'/source.name)
    for name in ('fetch-anchors.json','dance_stage.webp','dance_stage.wav'):
        shutil.copy2(APP/'assets'/name,DEST/'app/assets'/name)
    for name in ('build_mac.py','check_mac.py','requirements.txt','README.md','使用说明.txt'):
        shutil.copy2(ROOT/'work/macos'/name,DEST/name)
    (DEST/'.github/workflows').mkdir(parents=True)
    shutil.copy2(ROOT/'work/macos/macos.yml',DEST/'.github/workflows/macos.yml')
    (DEST/'.gitignore').write_text('build/\ndist/\nverification/\n__pycache__/\n*.pyc\n.venv/\napp/data/\n',encoding='utf-8')
    files=sorted(p for p in DEST.rglob('*') if p.is_file())
    manifest={str(p.relative_to(DEST)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
    (DEST/'upload-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    with zipfile.ZipFile(ARCHIVE,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(DEST.rglob('*')):
            if path.is_file():archive.write(path,Path('XiaohanMacBuild')/path.relative_to(DEST))
    print(json.dumps({'source_only':True,'files':len(files)+1,'bytes':ARCHIVE.stat().st_size,'sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()},ensure_ascii=False))


if __name__=='__main__':main()
