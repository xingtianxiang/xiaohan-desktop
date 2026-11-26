"""Extract the shipped zip, run its executable twice, and verify portable saves."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/XiaohanDesktop'))
from version import VERSION  # noqa: E402
OUT=ROOT/'work/desktop-qa'/f'portable-{VERSION}'
ARCHIVE=ROOT/'outputs/releases'/VERSION/f'xiaohan-windows64-{VERSION}.zip'
EXTRACT=OUT/'朋友 解压测试'


def main():
    if EXTRACT.exists():raise RuntimeError('Use a fresh extraction directory for verification.')
    OUT.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(ARCHIVE) as archive:
        if archive.testzip() is not None:raise AssertionError('Zip CRC failed')
        names=archive.namelist()
        if any('/data/' in n or n.endswith(('.py','.vbs','.lnk','-generation.json')) for n in names):
            raise AssertionError('Unexpected development file or save in release')
        archive.extractall(EXTRACT)
    exe=EXTRACT/'小汉/小汉.exe'
    env=os.environ.copy()
    for key in ('PYTHONHOME','PYTHONPATH','TCL_LIBRARY','TK_LIBRARY'):env.pop(key,None)
    env['PATH']=str(Path(os.environ['SystemRoot'])/'System32')
    modules=[]
    for run in ('first','reopen'):
        evidence=OUT/run
        process=subprocess.Popen([str(exe),'--verify-package',str(evidence)],cwd=OUT,env=env)
        try:
            if run=='first':
                # Read only the child we launched, to verify where its runtime was loaded.
                import time
                psapi=ctypes.WinDLL('psapi',use_last_error=True)
                psapi.EnumProcessModules.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.HMODULE),wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
                psapi.GetModuleFileNameExW.argtypes=[wintypes.HANDLE,wintypes.HMODULE,wintypes.LPWSTR,wintypes.DWORD]
                # A freshly extracted exe starts slower while antivirus scans it; wait until Tk is loaded.
                deadline=time.monotonic()+20
                while True:
                    handles=(wintypes.HMODULE*1024)();needed=wintypes.DWORD()
                    if not psapi.EnumProcessModules(int(process._handle),handles,ctypes.sizeof(handles),ctypes.byref(needed)):
                        error=ctypes.get_last_error()
                        # ERROR_PARTIAL_COPY: the loader has not finished building the module list yet.
                        if error!=299 or time.monotonic()>deadline:raise ctypes.WinError(error)
                        time.sleep(.3);continue
                    modules=[]
                    for handle in handles[:needed.value//ctypes.sizeof(wintypes.HMODULE)]:
                        name=ctypes.create_unicode_buffer(32768)
                        if psapi.GetModuleFileNameExW(int(process._handle),handle,name,len(name)):modules.append(name.value)
                    if any(Path(m).name.lower()=='tk86t.dll' for m in modules) or time.monotonic()>deadline:break
                    time.sleep(.3)
            code=process.wait(timeout=45)
            if code:raise RuntimeError(f'{run} exited {code}')
        except BaseException:
            if process.poll() is None:process.kill();process.wait()
            raise
        result=json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        failed=[item for item in result['checks'] if not item['passed']]
        if failed:raise AssertionError(f'{run}: {failed}')
        initial=result['initial']
        if run=='first':
            assert initial['outfit']=='blue' and initial['stage']==0 and initial['completed']==0
        else:assert initial['outfit']=='red' and initial['scene']=='snow'
    runtime=[p for p in modules if Path(p).name.lower() in ('python311.dll','tcl86t.dll','tk86t.dll')]
    assert len(runtime)==3 and all(Path(p).is_relative_to(EXTRACT) for p in runtime),runtime
    assert not (OUT/'data').exists()
    checks=json.loads((OUT/'first/result.json').read_text(encoding='utf-8'))['checks']
    summary={'zip_crc':True,'no_personal_save':True,'fresh_start':True,'reopen_preserves_save':True,
             'unicode_space_extraction_path':True,'independent_of_working_directory':True,
             'system_only_path':True,'bundled_runtime_modules':runtime,'loaded_modules':modules,
             'checks_per_launch':len(checks),'launches':2,'other_computers_tested':False}
    (ROOT/'outputs/XiaohanDesktop/verification-portable.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('loaded_modules','bundled_runtime_modules')},ensure_ascii=False))


if __name__=='__main__':main()
