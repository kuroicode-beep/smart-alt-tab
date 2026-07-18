# src/smart_alt_tab/win/dpi.py
"""per-monitor v2 DPI 인식 선언. 첫 Tk 창 생성 전에 호출해야 한다."""

import ctypes

# DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4 (핸들 값)
_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


def set_dpi_awareness() -> str:
    """DPI 인식을 최대 수준으로 설정하고 적용된 방식을 문자열로 반환한다.

    최신 API부터 단계적으로 시도 → 실패 시 하위 호환 폴백.
    """
    # 1) Windows 10 1703+ : per-monitor v2 (권장)
    try:
        user32 = ctypes.windll.user32
        if user32.SetProcessDpiAwarenessContext(_PER_MONITOR_AWARE_V2):
            return "per-monitor-v2"
    except (AttributeError, OSError):
        pass
    # 2) Windows 8.1+ : PROCESS_PER_MONITOR_DPI_AWARE = 2
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return "per-monitor"
    except (AttributeError, OSError):
        pass
    # 3) Vista+ : system DPI aware
    try:
        if ctypes.windll.user32.SetProcessDPIAware():
            return "system"
    except (AttributeError, OSError):
        pass
    return "none"


def get_dpi_for_point(x: int, y: int) -> int:
    """지정 좌표가 속한 모니터의 DPI(가로)를 반환. 실패 시 96(=100%)."""
    try:
        MONITOR_DEFAULTTONEAREST = 2
        MDT_EFFECTIVE_DPI = 0
        pt = ctypes.wintypes.POINT(x, y) if hasattr(ctypes, "wintypes") else None
        if pt is None:
            import ctypes.wintypes as wt  # noqa: F401
            pt = ctypes.wintypes.POINT(x, y)
        hmon = ctypes.windll.user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
        dpi_x = ctypes.c_uint()
        dpi_y = ctypes.c_uint()
        if ctypes.windll.shcore.GetDpiForMonitor(
            hmon, MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y)
        ) == 0:
            return int(dpi_x.value)
    except (AttributeError, OSError):
        pass
    return 96
