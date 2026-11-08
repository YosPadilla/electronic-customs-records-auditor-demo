from __future__ import annotations
import ctypes, time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
SW_MAXIMIZE = 3
SW_MINIMIZE = 6
WM_CLOSE = 0x0010
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

def _windows():
    items=[]
    @EnumWindowsProc
    def cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd): return True
        n=user32.GetWindowTextLengthW(hwnd)
        if n <= 0: return True
        buf=ctypes.create_unicode_buffer(n+1); user32.GetWindowTextW(hwnd,buf,n+1)
        cls=ctypes.create_unicode_buffer(256); user32.GetClassNameW(hwnd,cls,256)
        items.append((hwnd,buf.value,cls.value)); return True
    user32.EnumWindows(cb,0); return items

def find_window(title_contains: str, class_name: str|None=None, timeout: float=8):
    needle=title_contains.lower(); end=time.time()+timeout
    while time.time()<end:
        for hwnd,title,cls in _windows():
            if needle in title.lower() and (class_name is None or cls==class_name): return hwnd
        time.sleep(.15)
    return None

def maximize_foreground(hwnd):
    if not hwnd: return False
    user32.ShowWindow(hwnd,SW_MAXIMIZE); user32.SetForegroundWindow(hwnd); time.sleep(.4); return True

def close_window(hwnd):
    if hwnd: user32.PostMessageW(hwnd,WM_CLOSE,0,0)

def click(x:int,y:int):
    user32.SetCursorPos(int(x),int(y)); time.sleep(.35)
    user32.mouse_event(0x0002,0,0,0,0); user32.mouse_event(0x0004,0,0,0,0)

def minimize_console():
    hwnd=kernel32.GetConsoleWindow()
    if hwnd: user32.ShowWindow(hwnd,SW_MINIMIZE)
