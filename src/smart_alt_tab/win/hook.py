# src/smart_alt_tab/win/hook.py
"""WH_KEYBOARD_LL 저수준 키보드 훅.

콜백은 반드시 stdcall(WINFUNCTYPE)이어야 설치된다(cdecl이면 실패 — 실측).
훅은 시스템 전역이므로 콜백은 최소 작업만 하고, return 1 로 기본 처리를 소비한다.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# --- 상수 ---------------------------------------------------------------
WH_KEYBOARD_LL = 13
HC_ACTION = 0

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# 가상 키
VK_TAB = 0x09
VK_SHIFT = 0x10
VK_MENU = 0x12  # Alt
VK_ESCAPE = 0x1B
VK_RETURN = 0x0D
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LMENU = 0xA4
VK_RMENU = 0xA5

# ctypes 별칭
ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t
LPARAM = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HMODULE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, WPARAM, LPARAM]
user32.CallNextHookEx.restype = LRESULT
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


# on_key(msg, vk) -> bool : True면 키 소비(기본 처리 차단)
EventCallback = Callable[[int, int], bool]


class KeyboardHook:
    """저수준 키보드 훅 래퍼. install()은 메시지 루프가 도는 스레드에서 호출."""

    def __init__(self, on_key: EventCallback) -> None:
        self._on_key = on_key
        self._hook = None
        # 콜백 GC 방지용으로 인스턴스에 보관
        self._proc = HOOKPROC(self._raw_proc)

    def _raw_proc(self, n_code, w_param, l_param):
        if n_code == HC_ACTION:
            try:
                kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if self._on_key(int(w_param), int(kb.vkCode)):
                    return 1  # 소비: 기본 Alt+Tab 등 차단
            except Exception:
                # 훅에서 예외가 나도 절대 죽지 않게 — 키 흐름 유지(폴백)
                pass
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    def install(self) -> bool:
        if self._hook:
            return True
        hmod = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, hmod, 0)
        if not self._hook:
            err = ctypes.get_last_error()
            raise OSError(f"SetWindowsHookExW 실패 (GetLastError={err})")
        return True

    def uninstall(self) -> None:
        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
