"""Run on macOS from the reviewed build-source package."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tkinter
import urllib.request
from PIL import Image

ROOT=Path(__file__).resolve().parent
APP=ROOT/'app'
BUILD=ROOT/'build'
DIST=ROOT/'dist'
NAME='小汉'


def download(url,path):
    with urllib.request.urlopen(url,timeout=30) as response:path.write_bytes(response.read())


def main():
    if sys.platform!='darwin':raise SystemExit('Mac app must be built and checked on macOS.')
    arch=platform.machine()
    if arch not in ('arm64','x86_64'):raise SystemExit(f'Unsupported architecture: {arch}')
    if DIST.exists():raise SystemExit('Keep/review the existing release before rebuilding.')
    BUILD.mkdir(exist_ok=True);DIST.mkdir()
    license_dir=BUILD/'licenses';license_dir.mkdir()
    download(f'https://raw.githubusercontent.com/python/cpython/v{platform.python_version()}/LICENSE',license_dir/'Python.txt')
    for distribution,target in (('Pillow','LICENSE'),('PyInstaller','COPYING.txt')):
        info=importlib.metadata.distribution(distribution)
        source=next(p for p in info.files if p.name==target and '.dist-info' in str(p))
        shutil.copy2(info.locate_file(source),license_dir/(distribution+'.txt'))
    tk=tkinter.Tk();tk.withdraw()
    versions={'tcl':tk.tk.eval('info patchlevel'),'tk':tk.tk.eval('package require Tk')};tk.destroy()
    for component,version in versions.items():
        tag='core-'+version.replace('.','-')
        download(f'https://raw.githubusercontent.com/tcltk/{component}/{tag}/license.terms',license_dir/(component+'.txt'))
    Image.open(APP/'assets/blue_adult.png').save(BUILD/'xiaohan.icns')
    assets=[(str(p),'assets') for p in sorted((APP/'assets').glob('*.png'))]
    assets.append((str(APP/'assets/fetch-anchors.json'),'assets'))
    assets.append((str(license_dir),'licenses'))
    spec=BUILD/'mac.spec'
    plist={'CFBundleDisplayName':NAME,'CFBundleShortVersionString':'1.0.0','CFBundleVersion':'1',
           'LSMinimumSystemVersion':'15.0','NSHighResolutionCapable':True}
    spec.write_text(
        f'a=Analysis([{str(APP/"app.py")!r}],pathex=[{str(APP)!r}],datas={assets!r},hiddenimports=[],excludes=[])\n'
        'pyz=PYZ(a.pure)\n'
        f'exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name={NAME!r},console=False,debug=False,strip=False,upx=False,target_arch={arch!r})\n'
        f'coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name={NAME!r})\n'
        f'app=BUNDLE(coll,name={NAME+".app"!r},icon={str(BUILD/"xiaohan.icns")!r},bundle_identifier="com.xiaohan.desktop",info_plist={plist!r})\n',encoding='utf-8')
    subprocess.run([sys.executable,'-m','PyInstaller','--workpath',str(BUILD/'cache'),'--distpath',str(BUILD/'bundled'),str(spec)],check=True)
    bundle=BUILD/'bundled'/f'{NAME}.app'
    subprocess.run(['codesign','--verify','--deep','--strict',str(bundle)],check=True)
    release=BUILD/'小汉 Mac';release.mkdir()
    shutil.copytree(bundle,release/bundle.name,symlinks=True)
    shutil.copy2(ROOT/'使用说明.txt',release/'使用说明.txt')
    archive=DIST/f'小汉-macOS-{arch}.zip'
    subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(release),str(archive)],check=True)
    manifest={'archive':archive.name,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
              'bytes':archive.stat().st_size,'architecture':arch,'build_macos':platform.mac_ver()[0],
              'python':platform.python_version(),'PyInstaller':importlib.metadata.version('PyInstaller'),
              'Pillow':importlib.metadata.version('Pillow'),'tk':versions,'notarized':False,
              'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in APP.glob('*.py')}}
    (DIST/'build.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
