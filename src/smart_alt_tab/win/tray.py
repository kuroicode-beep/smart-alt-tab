# src/smart_alt_tab/win/tray.py
"""시스템 트레이 아이콘 (Shell_NotifyIconW, 순수 ctypes — 외부 의존성 없음).

트레이 메시지는 숨김 네이티브 윈도우의 WNDPROC로 들어오는데, 이는 Tk의 mainloop가 이미
돌리는 표준 Windows 메시지 루프(DispatchMessage)를 통해 호출된다 — WH_KEYBOARD_LL 저수준
훅과 달리 Tcl 이벤트 펌프 '바깥'에서 비동기 재진입하는 게 아니라 그 루프의 일부로 정상
디스패치되므로, 여기서 tkinter를 호출해도 안전하다(hook.py의 재진입 제약과는 다른 경로).
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable

from .windows import user32

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

# --- 상수 ---------------------------------------------------------------
WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_DESTROY = 0x0002
WM_NULL = 0x0000

NIM_ADD = 0x0
NIM_MODIFY = 0x1
NIM_DELETE = 0x2
NIF_MESSAGE = 0x1
NIF_ICON = 0x2
NIF_TIP = 0x4

TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
MF_STRING = 0x0000

IDI_APPLICATION = 32512
IDC_ARROW = 32512
GWL_WNDPROC = -4

ID_SETTINGS = 1001
ID_QUIT = 1002

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)


def _mkres(res_id: int):
    """MAKEINTRESOURCE — 정수 리소스 ID를 포인터 슬롯에 넣는 win32 관례."""
    return ctypes.c_wchar_p(res_id)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersionOrTimeout", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_ubyte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadIconW.restype = wintypes.HICON
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadCursorW.restype = wintypes.HANDLE
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_uint, wintypes.LPCWSTR]
user32.AppendMenuW.restype = wintypes.BOOL
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.TrackPopupMenu.argtypes = [
    wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, wintypes.HWND, ctypes.c_void_p,
]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.PostMessageW.restype = wintypes.BOOL

shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


class TrayIcon:
    """숨김 네이티브 윈도우 + Shell_NotifyIcon 트레이 아이콘. 우클릭: 설정/종료 메뉴."""

    _CLASS_NAME = "SmartAltTabTrayWnd"

    def __init__(self, tooltip: str, on_settings: Callable[[], None], on_quit: Callable[[], None]) -> None:
        self._on_settings = on_settings
        self._on_quit = on_quit
        self._hinst = kernel32.GetModuleHandleW(None)
        self._proc = WNDPROC(self._wndproc)  # GC 방지용 보관
        self._hwnd = None
        self._added = False

        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = self._proc
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = self._hinst
        wc.hIcon = user32.LoadIconW(None, _mkres(IDI_APPLICATION))
        wc.hCursor = user32.LoadCursorW(None, _mkres(IDC_ARROW))
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = self._CLASS_NAME
        if not user32.RegisterClassW(ctypes.byref(wc)):
            raise OSError(f"트레이 윈도우 클래스 등록 실패 (GetLastError={ctypes.get_last_error()})")

        self._hwnd = user32.CreateWindowExW(
            0, self._CLASS_NAME, "smart-alt-tab-tray", 0,
            0, 0, 0, 0, None, None, self._hinst, None,
        )
        if not self._hwnd:
            raise OSError(f"트레이 윈도우 생성 실패 (GetLastError={ctypes.get_last_error()})")

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = wc.hIcon
        nid.szTip = tooltip[:127]
        self._nid = nid
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            raise OSError("트레이 아이콘 추가 실패(Shell_NotifyIconW)")
        self._added = True

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAYICON:
                event = lparam & 0xFFFF if lparam < 0 else lparam
                if event in (WM_RBUTTONUP, WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    if event == WM_RBUTTONUP:
                        self._show_menu()
                    else:
                        self._on_settings()
                return 0
        except Exception:
            pass  # 콜백은 절대 예외로 죽지 않게
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_menu(self) -> None:
        # 메뉴 라벨은 set_labels()로 앱이 현재 언어에 맞게 주입해 둔 값을 그대로 쓴다.
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        hmenu = user32.CreatePopupMenu()
        try:
            user32.AppendMenuW(hmenu, MF_STRING, ID_SETTINGS, self._menu_label_settings())
            user32.AppendMenuW(hmenu, MF_STRING, ID_QUIT, self._menu_label_quit())
            user32.SetForegroundWindow(self._hwnd)
            cmd = user32.TrackPopupMenu(
                hmenu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, self._hwnd, None,
            )
            user32.PostMessageW(self._hwnd, WM_NULL, 0, 0)
            if cmd == ID_SETTINGS:
                self._on_settings()
            elif cmd == ID_QUIT:
                self._on_quit()
        finally:
            user32.DestroyMenu(hmenu)

    # 메뉴 라벨은 앱이 주입할 수 있도록 오버라이드 지점 제공
    def _menu_label_settings(self) -> str:
        return self.label_settings

    def _menu_label_quit(self) -> str:
        return self.label_quit

    label_settings = "설정"
    label_quit = "종료"

    def set_labels(self, settings: str, quit_: str) -> None:
        self.label_settings = settings
        self.label_quit = quit_

    def remove(self) -> None:
        if self._added:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            self._added = False
        if self._hwnd:
            user32.DestroyWindow(self._hwnd)
            self._hwnd = None
