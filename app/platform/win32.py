from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


def extend_frame(hwnd: int) -> None:
    if sys.platform != "win32":
        return

    class Margins(ctypes.Structure):
        _fields_ = [(name, ctypes.c_int) for name in ("left", "right", "top", "bottom")]

    try:
        dwm = ctypes.WinDLL("dwmapi")
        dwm.DwmExtendFrameIntoClientArea.argtypes = [wintypes.HWND, ctypes.POINTER(Margins)]
        dwm.DwmExtendFrameIntoClientArea.restype = ctypes.c_long
        margins = Margins(-1, -1, -1, -1)
        dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
    except OSError:
        pass


def set_click_through(hwnd: int, enabled: bool) -> None:
    if sys.platform != "win32" or not hwnd:
        return
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        user32.SetWindowLongW.restype = ctypes.c_long
        style = user32.GetWindowLongW(hwnd, -20)
        style = style | 0x00080000 | 0x00000020 if enabled else style & ~0x00000020
        user32.SetWindowLongW(hwnd, -20, style)
    except OSError:
        pass
