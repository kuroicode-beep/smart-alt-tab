# src/smart_alt_tab/win/dpi.py
"""per-monitor v2 DPI 인식 선언 + 논리 px → 물리 px 환산.

첫 Tk 창 생성 전에 set_dpi_awareness()를 호출해야 한다. Tk 자체의 폰트 스케일링은
프로세스 전체 DPI만 따라가고 모니터 이동 시 실시간으로 갱신되지 않으므로, 화면에 그릴 때마다
대상 모니터 DPI를 직접 조회해 픽셀 단위(Tk 음수 폰트 크기)로 환산해 그린다.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
shcore = ctypes.WinDLL("shcore", use_last_error=True)

_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
MONITOR_DEFAULTTONEAREST = 2
MDT_EFFECTIVE_DPI = 0
BASE_DPI = 96

user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = wintypes.HMONITOR
shcore.GetDpiForMonitor.argtypes = [
    wintypes.HMONITOR, ctypes.c_int, ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.UINT),
]
shcore.GetDpiForMonitor.restype = ctypes.c_long  # HRESULT


def set_dpi_awareness() -> str:
    """DPI 인식을 최대 수준으로 설정하고 적용된 방식을 문자열로 반환한다.

    최신 API부터 단계적으로 시도 → 실패 시 하위 호환 폴백.
    """
    try:
        if user32.SetProcessDpiAwarenessContext(_PER_MONITOR_AWARE_V2):
            return "per-monitor-v2"
    except (AttributeError, OSError):
        pass
    try:
        if shcore.SetProcessDpiAwareness(2) == 0:
            return "per-monitor"
    except (AttributeError, OSError):
        pass
    try:
        if user32.SetProcessDPIAware():
            return "system"
    except (AttributeError, OSError):
        pass
    return "none"


def get_dpi_for_point(x: int, y: int) -> int:
    """지정 좌표가 속한 모니터의 DPI(가로)를 반환. 실패 시 96(=100%, 무배율)."""
    try:
        pt = wintypes.POINT(x, y)
        hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
        dpi_x = wintypes.UINT()
        dpi_y = wintypes.UINT()
        hr = shcore.GetDpiForMonitor(hmon, MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
        if hr == 0:
            return int(dpi_x.value)
    except (AttributeError, OSError):
        pass
    return BASE_DPI


def scale_for_point(x: int, y: int) -> float:
    """해당 좌표 모니터의 DPI 배율(96dpi=1.0 기준)."""
    return get_dpi_for_point(x, y) / BASE_DPI


def logical_to_physical_px(logical_px: int, scale: float) -> int:
    """논리 px(96dpi 기준)를 주어진 배율의 물리 px로 환산."""
    return max(1, round(logical_px * scale))
