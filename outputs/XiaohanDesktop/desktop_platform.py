"""Desktop paths and native window conventions."""
from pathlib import Path
import os
import sys

IS_MAC=sys.platform=='darwin'
UI_FONT='PingFang SC' if IS_MAC else 'Microsoft YaHei UI'
TRANSPARENT='systemTransparent' if IS_MAC else '#ff00ff'

if os.name=='nt':
    import ctypes
    from ctypes import wintypes

    class _MonitorInfo(ctypes.Structure):
        _fields_=[('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD)]

    _user32=ctypes.WinDLL('user32',use_last_error=True)
    _user32.MonitorFromPoint.argtypes=[wintypes.POINT,wintypes.DWORD]
    _user32.MonitorFromPoint.restype=wintypes.HMONITOR
    _user32.GetMonitorInfoW.argtypes=[wintypes.HMONITOR,ctypes.POINTER(_MonitorInfo)]
    _user32.GetMonitorInfoW.restype=wintypes.BOOL
    MONITOR_DEFAULTTONEAREST=2


def screen_bounds(widget,x,y):
    """Return (left, top, right, bottom) of the monitor nearest to screen point (x, y).

    Tk's winfo_screenwidth/height only describe the primary monitor on Windows, which kept the
    pet off secondary screens. MonitorFromPoint picks the monitor under the point, or the nearest
    one when monitors are rearranged:
    https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-monitorfrompoint
    """
    if os.name!='nt':
        return 0,0,widget.winfo_screenwidth(),widget.winfo_screenheight()
    monitor=_user32.MonitorFromPoint(wintypes.POINT(round(x),round(y)),MONITOR_DEFAULTTONEAREST)
    info=_MonitorInfo(cbSize=ctypes.sizeof(_MonitorInfo))
    if not _user32.GetMonitorInfoW(monitor,ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    rect=info.rcMonitor
    return rect.left,rect.top,rect.right,rect.bottom


def default_data_path():
    if sys.platform=='darwin':
        return Path.home()/'Library/Application Support/XiaohanDesktop/pet.json'
    base=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
    return base/'data/pet.json'


class MacInstanceLock:
    """Hold the flock descriptor until exit; deleting the lock file would race."""
    def __init__(self,path):
        self.path=Path(path);self.file=None

    def acquire(self):
        import fcntl
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('a')
        try:fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self.close();return False
        return True

    def close(self):
        if self.file:
            self.file.close();self.file=None
