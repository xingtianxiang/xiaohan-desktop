"""Build a clean Windows x64 folder bundle and shareable zip; never copy saves."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'outputs/XiaohanDesktop'
sys.path.insert(0,str(APP))
from version import VERSION  # noqa: E402
BUILD=ROOT/'work/portable-build'
NAME='小汉'
DIST=BUILD/'dist'/NAME
# ASCII asset name: GitHub release download URLs are built from it.
ARCHIVE=ROOT/'outputs/releases'/VERSION/f'xiaohan-windows64-{VERSION}.zip'


def main():
    if DIST.exists() or ARCHIVE.exists():
        raise SystemExit('Output already exists; retain/review the previous release before rebuilding.')
    BUILD.mkdir(parents=True,exist_ok=True)
    assets=[(str(p),'assets') for p in sorted((APP/'assets').glob('*.png'))]
    for name in ('fetch-anchors.json','dance_stage.webp','dance_stage.wav'):
        assets.append((str(APP/'assets'/name),'assets'))
    spec=BUILD/'xiaohan.spec'
    spec.write_text(
        f'a=Analysis([{str(APP/"app.py")!r}],pathex=[{str(APP)!r}],datas={assets!r},hiddenimports=[],excludes=[])\n'
        'pyz=PYZ(a.pure)\n'
        f'exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name={NAME!r},console=False,debug=False,strip=False,upx=False,icon={str(APP/"assets/blue_adult.png")!r})\n'
        f'coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name={NAME!r})\n',encoding='utf-8')
    subprocess.run([sys.executable,'-m','PyInstaller','--distpath',str(BUILD/'dist'),
                    '--workpath',str(BUILD/'build'),str(spec)],check=True)
    licenses=DIST/'开源许可';licenses.mkdir()
    shutil.copy2(Path(sys.base_prefix)/'LICENSE.txt',licenses/'Python.txt')
    pillow=importlib.metadata.distribution('Pillow')
    license_file=next(p for p in pillow.files if str(p).endswith('.dist-info/LICENSE'))
    shutil.copy2(pillow.locate_file(license_file),licenses/'Pillow.txt')
    shutil.copy2(ROOT/'work/packaging-licenses/tcl8.6.12.txt',licenses/'tcl8.6.txt')
    shutil.copy2(Path(sys.base_prefix)/'tcl/tk8.6/license.terms',licenses/'tk8.6.txt')
    installer=importlib.metadata.distribution('PyInstaller')
    license_file=next(p for p in installer.files if str(p).endswith('/COPYING.txt'))
    shutil.copy2(installer.locate_file(license_file),licenses/'PyInstaller.txt')
    (DIST/'使用说明.txt').write_text('''小汉 · 桌面宠物（Windows 64 位便携版）

1. 将压缩包完整解压到桌面或 D 盘等普通文件夹。
   不要放在微信、QQ 的接收文件夹或 Program Files 里，那里的文件可能是只读的，进度会存不下来。
2. 打开“小汉”文件夹，双击“小汉.exe”，就能开始陪伴。
   无需安装 Python，无需管理员权限；请勿直接在压缩包中运行。

鼠标移到小汉身上，会出现九宫格按钮：
喂食、喝水、上厕所、摸摸、玩玩具、出游、换装、睡觉、更多。
按住小汉可以拖动；右键也能打开更多。退出在“更多”最下方。
鼠标在小汉头上移动或在身上来回轻划就是摸摸，她会耳朵后贴、摇尾巴；
鼠标放在她头上时头会跟着动，靠近时她会看向鼠标，可在设置里关闭。
鼠标在她周围画一整圈，她就会上台跳那支即梦生成的舞，带原声，按 Esc 或点“× 停止”结束。
打字时她会一起敲键盘，火光随速度变大变小，鼠标不会点燃火光。
出游可选公园或雪地；扔球时按住鼠标蓄力、松手抛出。

成长：有效陪伴 20 / 40 小时且亲密度达到 20 / 55 后解锁少年 / 成年。
解锁后在“更多”自由选择大中小；进度条显示还差多久。
连续工作 60 分钟会提醒休息 10 分钟，可在更多中关闭。
肚子饿、口渴、疲劳会显示对应状态；上厕所约 2 小时提醒，3 小时很急。
关闭程序或暂停期间不会继续累积如厕需求。

首次启动是新的幼年小汉。进度保存在“小汉.exe”旁的 data 文件夹，自动保存。
换电脑时先退出小汉，再复制整个“小汉”文件夹，包含 data。
不要删掉或单独移动 _internal；它是运行必需文件。
有新版本时，“更多”里会出现“更新”按钮：点一下会自动下载、校验并替换程序，data 里的进度保留。
也可以手动更新：先退出并备份 data，再用新包中的程序和 _internal 替换旧版，保留 data。

系统：Windows 10 / 11，64 位 Intel/AMD；不适用于 macOS、手机或 32 位 Windows。
程序只会联网检查和下载小汉自己的更新（可在“更多 → 设置”关闭），不上传任何数据，
不保存键盘输入内容，鼠标位置只用于转身、不记录，不添加开机自启。
此分享版没有代码签名，Windows 可能显示未知发布者提示。
''',encoding='utf-8-sig')
    members=list(DIST.rglob('*'))
    if any(p.name=='pet.json' or p.name=='data' for p in members):
        raise RuntimeError('Release must not include a save directory.')
    ARCHIVE.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(ARCHIVE,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(members):
            if path.is_file():archive.write(path,Path(NAME)/path.relative_to(DIST))
    manifest={
        'version':VERSION,'archive':ARCHIVE.name,'bytes':ARCHIVE.stat().st_size,
        'sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        'python':sys.version,'PyInstaller':importlib.metadata.version('PyInstaller'),
        'Pillow':importlib.metadata.version('Pillow'),
        'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in APP.glob('*.py')},
        'files':len([p for p in members if p.is_file()]),'includes_user_save':False,
    }
    (ROOT/'outputs/XiaohanDesktop/portable-build.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='source_sha256'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
