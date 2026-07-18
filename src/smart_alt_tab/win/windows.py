# src/smart_alt_tab/win/windows.py
"""창 열거(Alt+Tab 대상 필터)와 포그라운드 전환."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# --- 상수 ---------------------------------------------------------------
GW_OWNER = 4
GA_ROOTOWNER = 3
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
DWMWA_CLOAKED = 14
SW_RESTORE = 9
SW_SHOW = 5

# --- 프로토타입 ---------------------------------------------------------
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetLastActivePopup.argtypes = [wintypes.HWND]
user32.GetLastActivePopup.restype = wintypes.HWND
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

# 64bit 안전한 GetWindowLongPtrW (32bit 파이썬이면 GetWindowLongW 폴백)
_GetWindowLongPtr = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
_GetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int]
_GetWindowLongPtr.restype = ctypes.c_ssize_t

dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long  # HRESULT


@dataclass(frozen=True)
class WindowInfo:
    """전환 대상 창 한 건."""
    hwnd: int
    title: str


def _get_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _is_cloaked(hwnd: int) -> bool:
    """DWM cloaked(가상 데스크톱 등으로 숨은) 창인지."""
    val = wintypes.DWORD(0)
    hr = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(val), ctypes.sizeof(val)
    )
    if hr != 0:  # 속성 미지원 등 → cloaked 아님으로 간주
        return False
    return val.value != 0


def _is_alt_tab_window(hwnd: int) -> bool:
    """표준 Alt+Tab 목록 규칙으로 대상 여부 판정."""
    if not user32.IsWindowVisible(hwnd):
        return False

    ex_style = _GetWindowLongPtr(hwnd, GWL_EXSTYLE)
    # 강제 노출(APPWINDOW)이 아니면서 도구창이면 제외
    if (ex_style & WS_EX_TOOLWINDOW) and not (ex_style & WS_EX_APPWINDOW):
        return False

    # 소유 체인의 루트에서 마지막 활성 팝업이 자신이어야 대표 창
    root = user32.GetAncestor(hwnd, GA_ROOTOWNER)
    if user32.GetLastActivePopup(root) != hwnd:
        return False

    if not _get_title(hwnd):
        return False

    if _is_cloaked(hwnd):
        return False

    return True


def list_windows() -> list[WindowInfo]:
    """Alt+Tab 대상 창을 Z-순서(맨 앞이 현재 창)로 반환한다."""
    result: list[WindowInfo] = []

    @WNDENUMPROC
    def _cb(hwnd, _lparam):
        if _is_alt_tab_window(hwnd):
            result.append(WindowInfo(hwnd=int(hwnd), title=_get_title(hwnd)))
        return True  # 계속 열거

    user32.EnumWindows(_cb, 0)
    return result


def activate_window(hwnd: int) -> bool:
    """지정 창을 포그라운드로. 최소화면 복원. 실패 시 AttachThreadInput 우회."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    if user32.SetForegroundWindow(hwnd):
        return True

    # --- 폴백: 포그라운드 스레드에 입력을 붙여 권한 우회 ---
    fg = user32.GetForegroundWindow()
    cur_tid = kernel32.GetCurrentThreadId()
    fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    tgt_tid = user32.GetWindowThreadProcessId(hwnd, None)

    attached_fg = attached_tgt = False
    try:
        if fg_tid and fg_tid != cur_tid:
            attached_fg = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
        if tgt_tid and tgt_tid not in (cur_tid, fg_tid):
            attached_tgt = bool(user32.AttachThreadInput(cur_tid, tgt_tid, True))
        user32.BringWindowToTop(hwnd)
        user32.ShowWindow(hwnd, SW_SHOW)
        ok = bool(user32.SetForegroundWindow(hwnd))
    finally:
        if attached_tgt:
            user32.AttachThreadInput(cur_tid, tgt_tid, False)
        if attached_fg:
            user32.AttachThreadInput(cur_tid, fg_tid, False)
    return ok


if __name__ == "__main__":
    # 수동 검증: 현재 Alt+Tab 대상 창 목록 출력
    for i, w in enumerate(list_windows()):
        print(f"{i:2d}  {w.hwnd:>10}  {w.title}")
