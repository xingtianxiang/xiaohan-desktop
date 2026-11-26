"""Input activity: timestamp, count and decaying rate, never key contents."""
import ctypes as C
from ctypes import wintypes as W
import threading
import time
import os
import math
import sys

RATE_DECAY_SECONDS = .85

class KeyboardActivity:
    def __init__(self):
        self.last_activity = -1e10
        self.error = ''
        self.ready = threading.Event()
        self.thread = None
        self.hwnd = None
        self.count = 0
        self._speed_sample = (-1e10, 0.)
        self.stopped = threading.Event()

    def record_activity(self, now, count=1):
        rate = self.speed(now) + count/RATE_DECAY_SECONDS
        # Replace one immutable snapshot so the UI never reads a mixed sample.
        self._speed_sample = (now, rate)
        self.last_activity = now
        self.count += count

    def speed(self, now):
        sampled_at, rate = self._speed_sample
        return rate * math.exp(-max(0., now-sampled_at)/RATE_DECAY_SECONDS)

    def start(self):
        if sys.platform=='darwin':
            self.thread=threading.Thread(target=self._run_mac,name='XiaohanActivity',daemon=True)
            self.thread.start();return
        if os.name != 'nt':
            self.error = '键盘联动仅支持 Windows 和 macOS'
            self.ready.set()
            return
        self.thread = threading.Thread(target=self._run, name='XiaohanRawInput', daemon=True)
        self.thread.start()

    def _run_mac(self):
        try:
            from mac_activity import key_count,counter_delta
            previous=key_count();self.ready.set()
            while not self.stopped.wait(.025):
                current=key_count();count=counter_delta(previous,current);previous=current
                if count:self.record_activity(time.monotonic(),count)
        except (OSError,AttributeError) as exc:
            self.error=f'键盘联动未启动：{exc}';self.ready.set()

    def _run(self):
        try:
            self._message_loop()
        except Exception as exc:
            self.error = f'键盘联动未启动：{exc}'
            self.ready.set()

    def _message_loop(self):
        user = C.WinDLL('user32', use_last_error=True)
        kernel = C.WinDLL('kernel32', use_last_error=True)
        LRESULT = C.c_ssize_t
        WNDPROC = C.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
        class WNDCLASS(C.Structure):
            _fields_ = [('style', W.UINT), ('lpfnWndProc', WNDPROC), ('cbClsExtra', C.c_int), ('cbWndExtra', C.c_int), ('hInstance', W.HINSTANCE), ('hIcon', W.HICON), ('hCursor', W.HANDLE), ('hbrBackground', W.HBRUSH), ('lpszMenuName', W.LPCWSTR), ('lpszClassName', W.LPCWSTR)]
        class RAWINPUTDEVICE(C.Structure):
            _fields_ = [('usUsagePage', W.USHORT), ('usUsage', W.USHORT), ('dwFlags', W.DWORD), ('hwndTarget', W.HWND)]
        class HEADER(C.Structure):
            _fields_ = [('dwType', W.DWORD), ('dwSize', W.DWORD), ('hDevice', W.HANDLE), ('wParam', W.WPARAM)]
        class KEYBOARD(C.Structure):
            _fields_ = [('MakeCode', W.USHORT), ('Flags', W.USHORT), ('Reserved', W.USHORT), ('VKey', W.USHORT), ('Message', W.UINT), ('ExtraInformation', W.ULONG)]
        user.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
        user.DefWindowProcW.restype = LRESULT
        user.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, C.c_int, C.c_int, C.c_int, C.c_int, W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
        user.CreateWindowExW.restype = W.HWND
        user.RegisterClassW.argtypes = [C.POINTER(WNDCLASS)]
        user.UnregisterClassW.argtypes = [W.LPCWSTR, W.HINSTANCE]
        user.GetMessageW.argtypes = [C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT]
        user.GetMessageW.restype = W.BOOL
        user.TranslateMessage.argtypes = [C.POINTER(W.MSG)]
        user.DispatchMessageW.argtypes = [C.POINTER(W.MSG)]
        user.DispatchMessageW.restype = LRESULT
        user.RegisterRawInputDevices.argtypes = [C.POINTER(RAWINPUTDEVICE), W.UINT, W.UINT]
        user.GetRawInputData.argtypes = [W.HANDLE, W.UINT, W.LPVOID, C.POINTER(W.UINT), W.UINT]
        user.GetRawInputData.restype = W.UINT
        user.DestroyWindow.argtypes = [W.HWND]
        user.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
        kernel.GetModuleHandleW.argtypes = [W.LPCWSTR]
        kernel.GetModuleHandleW.restype = W.HMODULE
        @WNDPROC
        def callback(hwnd, msg, wp, lp):
            if msg == 0x00FF:
                size = W.UINT(0)
                if user.GetRawInputData(lp, 0x10000003, None, C.byref(size), C.sizeof(HEADER)) == 0:
                    buffer = C.create_string_buffer(size.value)
                    result = user.GetRawInputData(lp, 0x10000003, buffer, C.byref(size), C.sizeof(HEADER))
                    if result == size.value and size.value >= C.sizeof(HEADER) + C.sizeof(KEYBOARD):
                        header = HEADER.from_buffer(buffer)
                        if header.dwType == 1:
                            flags = KEYBOARD.from_buffer(buffer, C.sizeof(HEADER)).Flags
                            if not flags & 1:
                                self.record_activity(time.monotonic())
            elif msg == 0x0010:
                user.DestroyWindow(hwnd)
                return 0
            elif msg == 0x0002:
                user.PostQuitMessage(0)
                return 0
            return user.DefWindowProcW(hwnd, msg, wp, lp)
        instance = kernel.GetModuleHandleW(None)
        name = f'XiaohanKeyboard_{os.getpid()}'
        wc = WNDCLASS()
        wc.lpfnWndProc, wc.hInstance, wc.lpszClassName = callback, instance, name
        if not user.RegisterClassW(C.byref(wc)):
            raise C.WinError(C.get_last_error())
        self.hwnd = user.CreateWindowExW(0, name, name, 0, 0, 0, 0, 0, W.HWND(-3), None, instance, None)
        if not self.hwnd:
            raise C.WinError(C.get_last_error())
        device = RAWINPUTDEVICE(1, 6, 0x100, self.hwnd)
        try:
            if not user.RegisterRawInputDevices(C.byref(device), 1, C.sizeof(device)):
                raise C.WinError(C.get_last_error())
            self.ready.set()
            msg = W.MSG()
            while True:
                result = user.GetMessageW(C.byref(msg), None, 0, 0)
                if result == -1:
                    raise C.WinError(C.get_last_error())
                if result == 0:
                    break
                user.TranslateMessage(C.byref(msg))
                user.DispatchMessageW(C.byref(msg))
        finally:
            self.hwnd = None
            user.UnregisterClassW(name, instance)

    def stop(self):
        self.stopped.set()
        if self.hwnd:
            user = C.WinDLL('user32', use_last_error=True)
            user.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
            user.PostMessageW(self.hwnd, 0x0010, 0, 0)
        if self.thread:
            self.thread.join(timeout=2)

def user_idle_seconds():
    if sys.platform=='darwin':
        from mac_activity import idle_seconds
        return idle_seconds()
    if os.name != 'nt':
        return None
    class LASTINPUTINFO(C.Structure):
        _fields_ = [('cbSize', W.UINT), ('dwTime', W.DWORD)]
    info = LASTINPUTINFO(C.sizeof(LASTINPUTINFO), 0)
    if not C.windll.user32.GetLastInputInfo(C.byref(info)):
        return None
    elapsed = (C.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
    return elapsed / 1000

def user_is_active():
    idle = user_idle_seconds()
    return idle is not None and idle < 300
