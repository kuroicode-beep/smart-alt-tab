# src/smart_alt_tab/controller.py
"""세션 상태머신: 훅 이벤트를 받아 전환기를 열고 선택을 이동하며 창을 전환한다.

중요 — 훅 콜백(on_key)은 시스템 전역이며 **Tcl/tkinter를 절대 건드리지 않는다**.
저수준 훅은 Tcl 메시지 펌프 도중 재진입 호출되므로, 콜백에서 tkinter(after/위젯)를
호출하면 Python 스레드 상태가 깨져 간헐적으로 프로세스가 죽는다(GIL 오류, 실측).
따라서 콜백은 순수 파이썬 상태만 갱신하고 세대 카운터를 올린다. 실제 UI 렌더와 창 전환은
mainloop 문맥에서 도는 폴러(_poll, after 재무장)가 그 상태를 읽어 처리한다.

콜백과 폴러는 같은 스레드에서 번갈아 실행되므로(콜백이 끝나야 mainloop가 재개) 별도 락 없이
안전하다. 콜백은 소비 여부만 즉시 반환한다.
"""

from __future__ import annotations

import tkinter as tk

from .switcher import Switcher
from .win import hook as hk
from .win.windows import WindowInfo, activate_window, is_alt_down, list_windows

_ALT_KEYS = frozenset({hk.VK_MENU, hk.VK_LMENU, hk.VK_RMENU})
_SHIFT_KEYS = frozenset({hk.VK_SHIFT, hk.VK_LSHIFT, hk.VK_RSHIFT})
_KEYDOWN = frozenset({hk.WM_KEYDOWN, hk.WM_SYSKEYDOWN})
_KEYUP = frozenset({hk.WM_KEYUP, hk.WM_SYSKEYUP})
_NEXT_KEYS = frozenset({hk.VK_RIGHT, hk.VK_DOWN})
_PREV_KEYS = frozenset({hk.VK_LEFT, hk.VK_UP})

POLL_MS = 15  # 폴러 주기(약 1프레임) — 반응성과 CPU의 균형


class Controller:
    def __init__(self, root: tk.Tk, switcher: Switcher) -> None:
        self._root = root
        self._switcher = switcher
        # --- 콜백에서만 변경, 폴러에서 읽음 (같은 스레드 → 락 불필요) ---
        self._active = False
        self._windows: list[WindowInfo] = []
        self._selected = 0
        self._alt_down = False
        self._shift_down = False
        self._gen = 0            # 상태 변경 세대(콜백에서 증가)
        self._pending_commit: int | None = None  # 전환할 hwnd
        # --- 폴러 전용 ---
        self._rendered_gen = -1

    def start(self) -> None:
        """폴러 시작. mainloop 시작 후(또는 직전) 호출."""
        self._poll()

    # -- 훅 이벤트 (시스템 전역 콜백 컨텍스트, Tcl 호출 금지) ----------------
    def on_key(self, msg: int, vk: int) -> bool:
        """True 반환 시 키 소비(기본 Alt+Tab 등 차단). 순수 상태만 갱신."""
        down = msg in _KEYDOWN
        up = msg in _KEYUP

        # 모디파이어 상태 추적 (소비하지 않음)
        if vk in _ALT_KEYS:
            self._alt_down = down
        elif vk in _SHIFT_KEYS:
            self._shift_down = down

        # Alt를 놓으면 → 선택 확정 후 전환(전환은 폴러가 수행)
        if up and vk in _ALT_KEYS and self._active:
            self._commit()
            return False  # Alt keyup은 통과시켜 OS의 Alt 상태를 정리(끼임 방지)

        if down:
            if vk == hk.VK_TAB and self._alt_down:
                if not self._active:
                    if not self._begin():
                        return False  # 열린 창 없음 → 소비 안 함(기본 Alt+Tab 폴백)
                else:
                    self._move(-1 if self._shift_down else +1)
                self._gen += 1
                return True
            if self._active:
                if vk in _NEXT_KEYS:
                    self._move(+1); self._gen += 1; return True
                if vk in _PREV_KEYS:
                    self._move(-1); self._gen += 1; return True
                if vk == hk.VK_ESCAPE:
                    self._cancel(); self._gen += 1; return True
                if vk == hk.VK_RETURN:
                    self._commit(); return True
        return False

    # -- 세션 로직 (콜백 컨텍스트, ctypes만 사용) --------------------------
    def _begin(self) -> bool:
        """세션 시작. 열린 창이 있으면 True, 없으면 False(호출부에서 미소비)."""
        self._windows = list_windows()  # ctypes(EnumWindows) — Tcl 아님, 안전
        if not self._windows:
            self._active = False
            return False
        self._active = True
        # 기본 선택: 첫 Tab은 "이전 창"(index 1), Shift면 마지막 창
        if len(self._windows) == 1:
            self._selected = 0
        elif self._shift_down:
            self._selected = len(self._windows) - 1
        else:
            self._selected = 1
        return True

    def _move(self, delta: int) -> None:
        if not self._windows:
            return
        self._selected = (self._selected + delta) % len(self._windows)

    def _cancel(self) -> None:
        self._active = False

    def _commit(self) -> None:
        target = None
        if self._active and self._windows:
            target = self._windows[self._selected]
        self._active = False
        self._gen += 1
        if target is not None:
            self._pending_commit = target.hwnd  # 실제 전환은 폴러가 수행

    # -- 폴러 (mainloop 스레드, Tcl 안전) ---------------------------------
    def _poll(self) -> None:
        try:
            # 0) 끼임 방지 워치독: 세션 중인데 Alt가 실제로는 놓였으면(=keyup 유실)
            #    선택을 확정해 오버레이가 남지 않게 한다.
            if self._active and not is_alt_down():
                self._commit()
            # 1) 대기 중인 창 전환 처리
            hwnd = self._pending_commit
            if hwnd is not None:
                self._pending_commit = None
                try:
                    activate_window(hwnd)
                except Exception:
                    pass
            # 2) 상태 변경 시에만 렌더
            if self._gen != self._rendered_gen:
                self._rendered_gen = self._gen
                if self._active:
                    self._switcher.show(self._windows, self._selected)
                else:
                    self._switcher.hide()
        finally:
            self._root.after(POLL_MS, self._poll)
