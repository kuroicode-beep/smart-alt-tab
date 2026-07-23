# src/smart_alt_tab/app.py
"""앱 조립·실행. DPI 선언 → Tk → 훅 설치 → 트레이 → mainloop.

저수준 키보드 훅은 메시지 루프가 도는 스레드에 설치해야 콜백이 호출된다.
tkinter mainloop가 Windows 메시지를 펌프하므로 메인 스레드에 설치한다(실측 패턴).
"""

from __future__ import annotations

import datetime
import os
import sys
import tkinter as tk

from .config import Config
from .controller import Controller
from .i18n import t
from .settings_window import SettingsWindow
from .switcher import Switcher
from .version import APP_VERSION
from .win.dpi import set_dpi_awareness
from .win.hook import KeyboardHook
from .win.tray import TrayIcon


def log_path() -> str:
    """무콘솔(pythonw)·자동실행 시 진단용 로그 파일 경로."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "smart-alt-tab")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "app.log")


def _ensure_output() -> None:
    """pythonw로 실행되면 sys.stdout/stderr가 None이라 print()가 죽는다.
    이 경우 로그 파일로 우회해 크래시를 막는다."""
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


def log(msg: str, *, error: bool = False) -> None:
    """진단 메시지를 **항상 로그 파일에** 남기고, 쓸 수 있으면 콘솔에도 출력한다.

    `_ensure_output()`만으로는 부족하다 — 작업 스케줄러로 실행하면 sys.stdout이
    None이 아니라 NUL 핸들로 채워져서 `print()` 결과가 어디에도 남지 않는다(실측:
    관리자 자동 실행 전환 후 app.log가 갱신되지 않음). 그래서 파일 기록은 stdout
    상태와 무관하게 별도로 수행한다. 타임스탬프를 붙여 오래된 로그를 최신 실행으로
    착각하지 않게 한다.
    """
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    try:
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    stream = sys.stderr if error else sys.stdout
    if stream is not None:
        try:
            print(line, file=stream)
        except (OSError, ValueError):
            pass


def _is_elevated() -> bool:
    """관리자 권한으로 실행 중인지. 로그에 남겨 두면 '왜 특정 앱만 전환이 안 되는지'를
    바로 알 수 있다(일반 권한이면 관리자 앱 활성 시 훅이 키를 못 받는다)."""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def main() -> int:
    _ensure_output()  # 무콘솔 실행 대비(첫 print 전에)

    if not sys.platform.startswith("win"):
        log("smart-alt-tab은 Windows 전용입니다.", error=True)
        return 2

    dpi_mode = set_dpi_awareness()  # 첫 Tk 창 전에 선언
    config = Config.load()

    root = tk.Tk()
    root.withdraw()  # 메인 창은 숨김(트레이/오버레이만 사용)
    root.title(f"smart-alt-tab v{APP_VERSION}")

    switcher = Switcher(root, config)
    controller = Controller(root, switcher)
    hook = KeyboardHook(controller.on_key)

    try:
        hook.install()
    except OSError as exc:
        # 훅 실패 시 기본 Alt+Tab을 막지 않고 그대로 종료(안전 폴백)
        log(f"[오류] 키보드 훅 설치 실패: {exc}", error=True)
        log("기본 Windows Alt+Tab이 그대로 동작합니다.", error=True)
        root.destroy()
        return 1

    state = {"config": config}

    def on_config_change(new_config: Config) -> None:
        state["config"] = new_config
        switcher.apply_config(new_config)
        if tray is not None:
            tray.set_labels(t("tray_settings", new_config.lang), t("tray_quit", new_config.lang))

    settings = SettingsWindow(root, config, on_config_change)

    def open_settings() -> None:
        settings.show()

    def quit_app() -> None:
        try:
            hook.uninstall()
        except Exception:
            pass
        try:
            tray.remove()
        except Exception:
            pass
        root.after(0, root.quit)

    try:
        tray = TrayIcon(f"smart-alt-tab v{APP_VERSION}", open_settings, quit_app)
        tray.set_labels(t("tray_settings", config.lang), t("tray_quit", config.lang))
    except OSError as exc:
        log(f"[경고] 트레이 아이콘 생성 실패: {exc} — 전환기 자체는 계속 동작합니다.", error=True)
        tray = None

    elevated = "관리자" if _is_elevated() else "일반"
    log(f"smart-alt-tab v{APP_VERSION} 실행 중 (DPI: {dpi_mode}, 권한: {elevated}, PID: {os.getpid()}).")
    log("Alt+Tab을 눌러 전환기를 여세요. 트레이 아이콘 우클릭으로 설정·종료.")
    if not _is_elevated():
        log("[안내] 일반 권한입니다 — 관리자 권한으로 뜬 앱(예: 관리자 Cursor)이 활성일 때는 "
            "Windows UIPI 때문에 Alt+Tab을 가로채지 못합니다. "
            "scripts/install_admin_autostart.ps1 참고.")

    # 폴러 시작: 훅 콜백이 올린 상태를 mainloop 문맥에서 안전하게 렌더·전환.
    controller.start()

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        hook.uninstall()
        if tray is not None:
            try:
                tray.remove()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
