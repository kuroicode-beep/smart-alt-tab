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
MONITOR_DEFAULTTONEAREST = 2
VK_MENU = 0x12  # Alt
VK_F15 = 0x7E  # 아무 앱도 기본 바인딩이 없는 여분 키 — 더미 입력용(부작용 없음)
KEYEVENTF_KEYUP = 0x0002


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

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
user32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, wintypes.DWORD, ctypes.c_void_p]
user32.keybd_event.restype = None

# 64bit 안전한 GetWindowLongPtrW (32bit 파이썬이면 GetWindowLongW 폴백)
_GetWindowLongPtr = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
_GetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int]
_GetWindowLongPtr.restype = ctypes.c_ssize_t

user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short

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


def _root_owner_representative(hwnd: int) -> int:
    """소유 체인을 올라가며 '보이는 마지막 활성 팝업'을 찾는다(Raymond Chen 규칙).

    Alt+Tab에는 각 소유 그룹의 대표 창 하나만 나와야 한다. 대화상자를 띄운 앱은
    대화상자가 대표가 되도록 GetLastActivePopup을 반복 추적한다.
    """
    walk = 0
    try_hwnd = user32.GetAncestor(hwnd, GA_ROOTOWNER)
    while try_hwnd != walk:
        walk = try_hwnd
        try_hwnd = user32.GetLastActivePopup(walk)
        if user32.IsWindowVisible(try_hwnd):
            break
    return walk


def _is_alt_tab_window(hwnd: int) -> bool:
    """표준 Alt+Tab 목록 규칙으로 대상 여부 판정(정교화)."""
    if not user32.IsWindowVisible(hwnd):
        return False

    # 소유 그룹의 대표 창이 자신이어야 함(중복/유령 제거)
    if _root_owner_representative(hwnd) != hwnd:
        return False

    ex_style = _GetWindowLongPtr(hwnd, GWL_EXSTYLE)
    # 강제 노출(APPWINDOW)이 아니면서 도구창이면 제외
    if (ex_style & WS_EX_TOOLWINDOW) and not (ex_style & WS_EX_APPWINDOW):
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


def _inject_dummy_key() -> None:
    """포그라운드 락 우회용 더미 키 입력.

    SetForegroundWindow는 기본적으로 "가장 최근에 입력을 받은 스레드"에서 호출해야
    통과된다. 우리 스레드는 LL 훅으로 키를 관찰만 할 뿐 그 입력을 실제로 받는 스레드가
    아니라서(포커스는 대상 앱에 있음) 이 조건을 만족하지 못한다. 아무 앱에도 기본
    바인딩이 없는 VK_F15로 press+release를 주입하면 시각적 부작용 없이 우리 스레드가
    "방금 입력을 받은" 자격을 얻어 SetForegroundWindow가 통과한다.
    """
    user32.keybd_event(VK_F15, 0, 0, None)
    user32.keybd_event(VK_F15, 0, KEYEVENTF_KEYUP, None)


def activate_window(hwnd: int) -> bool:
    """지정 창을 포그라운드로. 최소화면 복원. 실패 시 더미 입력→재시도, 그다음
    AttachThreadInput 우회.

    AttachThreadInput은 대상이 우리와 다른 무결성 수준(예: Electron 계열 앱의 저무결성
    렌더러 창)이면 ERROR_ACCESS_DENIED로 실패한다(실측 — Cursor 대상 재현). 더미 입력
    방식은 그 제약을 받지 않아 더 안정적이므로 AttachThreadInput보다 먼저 시도한다.
    """
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    if user32.SetForegroundWindow(hwnd):
        return True

    _inject_dummy_key()
    if user32.SetForegroundWindow(hwnd):
        return True

    # --- 최종 폴백: 포그라운드 스레드에 입력을 붙여 권한 우회(동일 무결성 수준일 때만) ---
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


def cursor_workarea() -> tuple[int, int, int, int]:
    """커서가 있는 모니터의 작업영역 (left, top, width, height). 실패 시 주 모니터."""
    pt = wintypes.POINT()
    try:
        if user32.GetCursorPos(ctypes.byref(pt)):
            hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcWork
                return (r.left, r.top, r.right - r.left, r.bottom - r.top)
    except OSError:
        pass
    # 폴백: 주 모니터 전체
    sw = user32.GetSystemMetrics(0) if hasattr(user32, "GetSystemMetrics") else 1920
    sh = user32.GetSystemMetrics(1) if hasattr(user32, "GetSystemMetrics") else 1080
    return (0, 0, sw, sh)


def is_alt_down() -> bool:
    """Alt 키가 실제로 눌려 있는지(실시간). 끼임 방지 워치독용."""
    return bool(user32.GetAsyncKeyState(VK_MENU) & 0x8000)


if __name__ == "__main__":
    # 수동 검증: 현재 Alt+Tab 대상 창 목록 출력
    for i, w in enumerate(list_windows()):
        print(f"{i:2d}  {w.hwnd:>10}  {w.title}")
