# src/smart_alt_tab/app.py
"""앱 조립·실행. DPI 선언 → Tk → 훅 설치 → mainloop.

저수준 키보드 훅은 메시지 루프가 도는 스레드에 설치해야 콜백이 호출된다.
tkinter mainloop가 Windows 메시지를 펌프하므로 메인 스레드에 설치한다(실측 패턴).
"""

from __future__ import annotations

import os
import sys
import tkinter as tk

from .controller import Controller
from .switcher import Switcher
from .version import APP_VERSION
from .win.dpi import set_dpi_awareness
from .win.hook import KeyboardHook


def log_path() -> str:
    """무콘솔(pythonw)·자동실행 시 진단용 로그 파일 경로."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "smart-alt-tab")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "app.log")


def _ensure_output() -> None:
    """pythonw로 실행되면 sys.stdout/stderr가 None이라 print()가 죽는다.
    이 경우 로그 파일로 우회해 크래시를 막고 진단을 남긴다."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        f = open(log_path(), "a", encoding="utf-8", buffering=1)
    except OSError:
        f = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = f
    if sys.stderr is None:
        sys.stderr = f


def main() -> int:
    _ensure_output()  # 무콘솔 실행 대비(첫 print 전에)

    if not sys.platform.startswith("win"):
        print("smart-alt-tab은 Windows 전용입니다.", file=sys.stderr)
        return 2

    dpi_mode = set_dpi_awareness()  # 첫 Tk 창 전에 선언

    root = tk.Tk()
    root.withdraw()  # 메인 창은 숨김(트레이/오버레이만 사용)
    root.title(f"smart-alt-tab v{APP_VERSION}")

    switcher = Switcher(root)
    controller = Controller(root, switcher)
    hook = KeyboardHook(controller.on_key)

    try:
        hook.install()
    except OSError as exc:
        # 훅 실패 시 기본 Alt+Tab을 막지 않고 그대로 종료(안전 폴백)
        print(f"[오류] 키보드 훅 설치 실패: {exc}", file=sys.stderr)
        print("기본 Windows Alt+Tab이 그대로 동작합니다.", file=sys.stderr)
        root.destroy()
        return 1

    print(f"smart-alt-tab v{APP_VERSION} 실행 중 (DPI: {dpi_mode}).")
    print("Alt+Tab을 눌러 전환기를 여세요. 종료: 이 창에서 Ctrl+C.")

    # 폴러 시작: 훅 콜백이 올린 상태를 mainloop 문맥에서 안전하게 렌더·전환.
    # (Ctrl+C도 주기적으로 깨어나는 이 폴러 덕에 mainloop 중 처리된다.)
    controller.start()

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        hook.uninstall()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
