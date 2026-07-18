# src/smart_alt_tab/controller.py
"""세션 상태머신: 훅 이벤트를 받아 전환기를 열고 선택을 이동하며 창을 전환한다.

훅 콜백(_on_key)은 시스템 전역이라 최소 작업만 한다:
상태만 갱신하고 소비 여부를 즉시 반환, 화면 갱신은 after_idle로 미룬다.
창 전환은 포그라운드 권한이 살아있는 콜백 시점에 동기로 수행한다.
"""

from __future__ import annotations

import tkinter as tk

from .switcher import Switcher
from .win import hook as hk
from .win.windows import WindowInfo, activate_window, list_windows

_ALT_KEYS = frozenset({hk.VK_MENU, hk.VK_LMENU, hk.VK_RMENU})
_SHIFT_KEYS = frozenset({hk.VK_SHIFT, hk.VK_LSHIFT, hk.VK_RSHIFT})
_KEYDOWN = frozenset({hk.WM_KEYDOWN, hk.WM_SYSKEYDOWN})
_KEYUP = frozenset({hk.WM_KEYUP, hk.WM_SYSKEYUP})
_NEXT_KEYS = frozenset({hk.VK_RIGHT, hk.VK_DOWN})
_PREV_KEYS = frozenset({hk.VK_LEFT, hk.VK_UP})


class Controller:
    def __init__(self, root: tk.Tk, switcher: Switcher) -> None:
        self._root = root
        self._switcher = switcher
        self._active = False
        self._windows: list[WindowInfo] = []
        self._selected = 0
        self._alt_down = False
        self._shift_down = False
        self._render_pending = False

    # -- 훅 이벤트 (시스템 전역 콜백 컨텍스트) ------------------------------
    def on_key(self, msg: int, vk: int) -> bool:
        """True 반환 시 키 소비(기본 Alt+Tab 등 차단)."""
        down = msg in _KEYDOWN
        up = msg in _KEYUP

        # 모디파이어 상태 추적 (소비하지 않음)
        if vk in _ALT_KEYS:
            self._alt_down = down
        elif vk in _SHIFT_KEYS:
            self._shift_down = down

        # Alt를 놓으면 → 선택 확정 후 전환
        if up and vk in _ALT_KEYS and self._active:
            self._commit()
            return False  # Alt keyup은 통과시켜 OS의 Alt 상태를 정리(끼임 방지)

        if down:
            if vk == hk.VK_TAB and self._alt_down:
                if not self._active:
                    self._begin()
                else:
                    self._move(-1 if self._shift_down else +1)
                self._request_render()
                return True
            if self._active:
                if vk in _NEXT_KEYS:
                    self._move(+1); self._request_render(); return True
                if vk in _PREV_KEYS:
                    self._move(-1); self._request_render(); return True
                if vk == hk.VK_ESCAPE:
                    self._cancel(); self._request_render(); return True
                if vk == hk.VK_RETURN:
                    self._commit(); return True
        return False

    # -- 세션 로직 -------------------------------------------------------
    def _begin(self) -> None:
        self._windows = list_windows()
        if not self._windows:
            self._active = False
            return
        self._active = True
        # 기본 선택: 첫 Tab은 "이전 창"(index 1), Shift면 마지막 창
        if len(self._windows) == 1:
            self._selected = 0
        elif self._shift_down:
            self._selected = len(self._windows) - 1
        else:
            self._selected = 1

    def _move(self, delta: int) -> None:
        if not self._windows:
            return
        n = len(self._windows)
        self._selected = (self._selected + delta) % n

    def _cancel(self) -> None:
        self._active = False

    def _commit(self) -> None:
        target = None
        if self._active and self._windows:
            target = self._windows[self._selected]
        self._active = False
        self._request_render()  # 오버레이 숨김 예약
        if target is not None:
            activate_window(target.hwnd)  # 콜백 시점에 동기 전환(권한 유지)

    # -- 화면 갱신 (mainloop 스레드로 위임) --------------------------------
    def _request_render(self) -> None:
        if not self._render_pending:
            self._render_pending = True
            self._root.after_idle(self._render)

    def _render(self) -> None:
        self._render_pending = False
        if self._active:
            self._switcher.show(self._windows, self._selected)
        else:
            self._switcher.hide()
