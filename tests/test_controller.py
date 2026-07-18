# tests/test_controller.py
"""Controller 상태머신 단위 검증 (실제 훅 없이 이벤트 시퀀스 주입).

Alt+Tab의 감지→선택 이동→확정 전환 흐름을 결정적으로 확인한다.
list_windows / activate_window는 스텁으로 대체해 포커스를 실제로 바꾸지 않는다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import tkinter as tk

import smart_alt_tab.controller as ctrl
from smart_alt_tab.controller import Controller
from smart_alt_tab.win import hook as hk
from smart_alt_tab.win.windows import WindowInfo

# 결정적 창 목록 (index 0 = 현재 창)
FAKE = [WindowInfo(hwnd=100 + i, title=f"창{i}") for i in range(5)]


class FakeSwitcher:
    def show(self, windows, selected):
        pass

    def hide(self):
        pass


def make_controller(monkeypatch_calls):
    root = tk.Tk()
    root.withdraw()
    c = Controller(root, FakeSwitcher())
    return root, c


def run(events, *, windows=FAKE, alt_down=False, poll=True):
    """이벤트 시퀀스를 주입하고 (controller, consumed리스트, switched리스트) 반환.

    windows: list_windows 스텁 반환값. alt_down: 워치독용 is_alt_down 스텁 값.
    poll: 끝에 _poll을 1회 돌려 대기 전환/워치독을 mainloop처럼 처리할지.
    """
    switched = []
    orig_list = ctrl.list_windows
    orig_act = ctrl.activate_window
    orig_alt = ctrl.is_alt_down
    ctrl.list_windows = lambda: list(windows)
    ctrl.activate_window = lambda hwnd: switched.append(hwnd) or True
    ctrl.is_alt_down = lambda: alt_down
    try:
        root = tk.Tk()
        root.withdraw()
        c = Controller(root, FakeSwitcher())
        consumed = [c.on_key(msg, vk) for msg, vk in events]
        if poll:
            c._poll()  # 대기 전환/워치독을 mainloop 문맥처럼 1회 처리
        root.destroy()
    finally:
        ctrl.list_windows = orig_list
        ctrl.activate_window = orig_act
        ctrl.is_alt_down = orig_alt
    return c, consumed, switched


DN = hk.WM_SYSKEYDOWN
UP = hk.WM_KEYUP
KDN = hk.WM_KEYDOWN


def test_basic_alt_tab_switches_to_previous():
    # Alt down, Tab down, Alt up  → 이전 창(index 1)으로 전환
    c, consumed, switched = run([
        (DN, hk.VK_LMENU),
        (DN, hk.VK_TAB),
        (UP, hk.VK_LMENU),
    ])
    assert switched == [FAKE[1].hwnd], switched
    assert consumed[1] is True   # Tab 소비
    assert c._active is False


def test_tab_advances_selection():
    c, consumed, switched = run([
        (DN, hk.VK_LMENU),
        (DN, hk.VK_TAB),   # sel=1
        (DN, hk.VK_TAB),   # sel=2
        (DN, hk.VK_TAB),   # sel=3
        (UP, hk.VK_LMENU),
    ])
    assert switched == [FAKE[3].hwnd], switched


def test_arrows_move_selection():
    c, consumed, switched = run([
        (DN, hk.VK_LMENU),
        (DN, hk.VK_TAB),        # sel=1
        (KDN, hk.VK_RIGHT),     # sel=2
        (KDN, hk.VK_DOWN),      # sel=3
        (KDN, hk.VK_LEFT),      # sel=2
        (UP, hk.VK_LMENU),
    ])
    assert switched == [FAKE[2].hwnd], switched


def test_wraparound():
    # 5개 창, sel=1에서 back 2번 → 1→0→4 (wrap)
    c, consumed, switched = run([
        (DN, hk.VK_LMENU),
        (DN, hk.VK_TAB),        # sel=1
        (KDN, hk.VK_LEFT),      # sel=0
        (KDN, hk.VK_LEFT),      # sel=4 (wrap)
        (UP, hk.VK_LMENU),
    ])
    assert switched == [FAKE[4].hwnd], switched


def test_escape_cancels_no_switch():
    c, consumed, switched = run([
        (DN, hk.VK_LMENU),
        (DN, hk.VK_TAB),
        (KDN, hk.VK_ESCAPE),    # 취소
        (UP, hk.VK_LMENU),
    ])
    assert switched == [], switched
    assert c._active is False


def test_shift_tab_starts_at_last():
    c, consumed, switched = run([
        (DN, hk.VK_LSHIFT),     # shift 먼저
        (DN, hk.VK_LMENU),
        (DN, hk.VK_TAB),        # Shift+Alt+Tab → 마지막 창(index 4)
        (UP, hk.VK_LMENU),
    ])
    assert switched == [FAKE[4].hwnd], switched


def test_shift_tab_goes_backward_after_start():
    c, consumed, switched = run([
        (DN, hk.VK_LMENU),
        (DN, hk.VK_TAB),        # sel=1 (shift 없음)
        (DN, hk.VK_LSHIFT),     # shift down
        (DN, hk.VK_TAB),        # shift+tab → back → sel=0
        (UP, hk.VK_LSHIFT),
        (UP, hk.VK_LMENU),
    ])
    assert switched == [FAKE[0].hwnd], switched


def test_tab_without_alt_is_ignored():
    c, consumed, switched = run([
        (KDN, hk.VK_TAB),       # Alt 없이 Tab → 무시(비소비)
    ])
    assert consumed == [False]
    assert c._active is False
    assert switched == []


def test_no_windows_does_not_consume():
    # 열린 창이 없으면 Tab을 소비하지 않아 기본 Alt+Tab이 동작해야 함
    c, consumed, switched = run([
        (DN, hk.VK_LMENU),
        (DN, hk.VK_TAB),
    ], windows=[])
    assert consumed[-1] is False, consumed
    assert c._active is False
    assert switched == []


def test_watchdog_commits_when_alt_released_without_keyup():
    # Alt keyup 이벤트를 못 받은 상태(active 유지) → 폴러 워치독이 확정
    c, consumed, switched = run([
        (DN, hk.VK_LMENU),
        (DN, hk.VK_TAB),   # sel=1, active
        # Alt keyup 이벤트 없음
    ], alt_down=False)      # 실제 Alt는 놓임 → 워치독 발동
    assert switched == [FAKE[1].hwnd], switched
    assert c._active is False


def test_watchdog_does_not_fire_while_alt_held():
    # Alt를 아직 잡고 있으면 워치독은 확정하지 않는다
    c, consumed, switched = run([
        (DN, hk.VK_LMENU),
        (DN, hk.VK_TAB),
    ], alt_down=True)
    assert switched == []      # 아직 확정 안 됨
    assert c._active is True


def test_enter_commits_immediately():
    c, consumed, switched = run([
        (DN, hk.VK_LMENU),
        (DN, hk.VK_TAB),        # sel=1
        (KDN, hk.VK_RETURN),    # 즉시 확정
    ])
    assert switched == [FAKE[1].hwnd], switched
    assert c._active is False


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
    raise SystemExit(0 if passed == len(tests) else 1)
