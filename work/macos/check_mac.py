"""Check the actual macOS ZIP in an isolated home; fail rather than publish unchecked."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent


def main():
    if sys.platform!='darwin':raise SystemExit('Requires macOS.')
    manifest=json.loads((ROOT/'dist/build.json').read_text(encoding='utf-8'))
    output=ROOT/'verification';output.mkdir()
    extracted=output/'朋友 解压测试'
    subprocess.run(['ditto','-x','-k',str(ROOT/'dist'/manifest['archive']),str(extracted)],check=True)
    bundle=extracted/'小汉 Mac/小汉.app'
    exe=bundle/'Contents/MacOS/小汉'
    subprocess.run(['codesign','--verify','--deep','--strict',str(bundle)],check=True)
    arch=subprocess.check_output(['lipo','-archs',str(exe)],text=True).strip()
    if arch!=manifest['architecture']:raise AssertionError(f'Unexpected binary architecture: {arch}')
    home=output/'isolated-home';home.mkdir()
    env=os.environ.copy();env['HOME']=str(home);env['PATH']='/usr/bin:/bin:/usr/sbin:/sbin'
    for key in ('PYTHONHOME','PYTHONPATH','TCL_LIBRARY','TK_LIBRARY','DYLD_LIBRARY_PATH'):env.pop(key,None)
    for run in ('first','reopen'):
        evidence=output/run
        subprocess.run([str(exe),'--verify-mac',str(evidence)],cwd=output,env=env,check=True,timeout=60)
        result=json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        failures=[r for r in result['checks'] if not r['passed']]
        if failures:raise AssertionError(f'{run}: {failures}')
        if run=='first':
            if result['initial']['outfit']!='blue' or result['initial']['stage']!=0:raise AssertionError('Not a fresh pet')
        elif result['initial']['outfit']!='red':raise AssertionError('Reopen did not load saved outfit')
    manifest['verification']={'launches':2,'checks_per_launch':len(result['checks']),
                              'real_typing_verified':False,'visual_human_review':False,
                              'default_save_outside_bundle':True}
    (ROOT/'dist/verification.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(manifest['verification']))


if __name__=='__main__':main()
