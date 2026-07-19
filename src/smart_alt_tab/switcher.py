# src/smart_alt_tab/switcher.py
"""고대비 다크 오버레이 전환기 UI (tkinter).

SVIL 디자인 토큰 적용: 큰 글씨, 색상만으로 상태 구분 금지(선택은 테두리+색+마커).
선택 이동만 반응하도록 화면 갱신은 controller가 호출한다.

DPI: Tk 자체의 폰트 스케일은 프로세스 시작 시 한 번(대개 주 모니터 기준) 고정되어 다중
모니터 간 이동에 실시간으로 따라오지 않는다. 그래서 매 표시(show)마다 대상 모니터의 실제
DPI를 조회해 논리 px(96dpi 기준)를 물리 px로 직접 환산하고, Tk 음수 폰트 크기(= 픽셀 단위)로
그린다(`win/dpi.py`).
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

from .config import Config, available_fonts
from .i18n import t
from .win.dpi import logical_to_physical_px, scale_for_point
from .win.windows import WindowInfo, cursor_workarea

# --- SVIL 색상 토큰 (하드코딩 금지 규칙 → 이 모듈에서 토큰으로 관리) ----------
BG = "#0d0d12"
SURFACE = "#16161d"
SURFACE_2 = "#1f1f2a"
BORDER_STRONG = "#6b6b82"
TEXT = "#f5f5f7"
TEXT_SUB = "#c9c9d4"
ACCENT = "#7ec8ff"
ACCENT_STRONG = "#b3ddff"
FOCUS = "#ffd479"

# 설정에서 고른 글꼴이 어떤 이유로든 못 잡히면 순서대로 폴백(모두 실제 패밀리, 합성 아님)
_BODY_FALLBACK = ["나눔고딕 ExtraBold", "Noto Sans KR Black", "Malgun Gothic"]
_MONO_FAMILIES = ["Consolas", "D2Coding", "monospace"]

MAX_VISIBLE = 9  # 한 화면에 보일 행 수 (초과분은 위/아래 인디케이터)
MIN_LOGICAL_PX = 12  # SVIL 최소 폰트 크기 (배율 적용 전 논리 px 기준)


def _pick_family(candidates: list[str], available: set[str], default: str) -> str:
    for fam in candidates:
        if fam in available:
            return fam
    return default


class Switcher:
    """숨김 상태로 대기하다 show()로 나타나는 오버레이."""

    def __init__(self, root: tk.Tk, config: Config | None = None) -> None:
        self._root = root
        self._config = config or Config.load()
        self._font_map = dict(available_fonts(root))  # {표시이름: 실제설치패밀리}
        available = set(tkfont.families(root))
        self._mono_family = _pick_family(_MONO_FAMILIES, available, "TkFixedFont")

        self._win = tk.Toplevel(root)
        self._win.withdraw()
        self._win.overrideredirect(True)  # 타이틀바 제거
        self._win.attributes("-topmost", True)
        self._win.configure(bg=BG)

        # 초기 폰트(1.0배율=96dpi 가정)로 생성 — show()에서 대상 모니터 배율로 재조정
        self._f_title = tkfont.Font(size=-20)
        self._f_row = tkfont.Font(size=-20)
        self._f_num = tkfont.Font(size=-16)
        self._f_hint = tkfont.Font(size=-14)
        self._built_scale: float | None = None
        self._built_font_label: str | None = None
        self._built_size: str | None = None
        self._apply_fonts(scale=1.0)

        # 바깥 테두리(강조 보더) → 안쪽 컨테이너
        self._frame = tk.Frame(
            self._win, bg=SURFACE, highlightthickness=2,
            highlightbackground=BORDER_STRONG, highlightcolor=BORDER_STRONG,
        )
        self._frame.pack(fill="both", expand=True)

        self._header = tk.Label(
            self._frame, font=self._f_title,
            bg=SURFACE, fg=ACCENT_STRONG, anchor="w", padx=24, pady=(0),
        )
        self._header.pack(fill="x", padx=0, pady=(18, 4))

        self._up_hint = tk.Label(
            self._frame, font=self._f_hint, bg=SURFACE, fg=TEXT_SUB, anchor="w", padx=28,
        )
        self._rows_holder = tk.Frame(self._frame, bg=SURFACE)
        self._rows_holder.pack(fill="both", expand=True, padx=16)
        self._down_hint = tk.Label(
            self._frame, font=self._f_hint, bg=SURFACE, fg=TEXT_SUB, anchor="w", padx=28,
        )

        self._footer = tk.Label(
            self._frame, font=self._f_num, bg=SURFACE, fg=TEXT_SUB,
            anchor="e", padx=24, pady=(4),
        )
        self._footer.pack(fill="x", pady=(4, 16))

        self._row_widgets: list[tuple[tk.Frame, tk.Label, tk.Label]] = []

    # -- 설정 반영 ----------------------------------------------------------
    def apply_config(self, config: Config) -> None:
        """설정 화면에서 저장한 값을 실행 중인 오버레이에 즉시 반영."""
        self._config = config
        self._built_font_label = None  # 다음 show()에서 강제로 폰트 재조정

    # -- 표시 -------------------------------------------------------------
    def show(self, windows: list[WindowInfo], selected: int) -> None:
        """목록·선택을 반영해 오버레이를 그리고 화면 안에 띄운다."""
        if not windows:
            self.hide()
            return
        # 커서가 있는 모니터의 작업영역 기준으로 폭·위치·DPI 계산(다중 모니터 대응)
        self._area = cursor_workarea()  # (left, top, width, height)
        ax, ay, aw, ah = self._area
        scale = scale_for_point(ax + aw // 2, ay + ah // 2)
        self._apply_fonts(scale)
        self._overlay_w = max(640, min(int(aw * 0.82), 1280))

        lang = self._config.lang
        self._header.config(text=t("switcher_header", lang))
        self._render_rows(windows, selected)
        hint = t("switcher_hint", lang)
        self._footer.config(text=f"{selected + 1} / {len(windows)}   ·   {hint}")
        self._win.update_idletasks()
        self._place()
        self._win.deiconify()
        self._win.lift()
        self._win.attributes("-topmost", True)

    def hide(self) -> None:
        self._win.withdraw()

    # -- 내부: 폰트/DPI ------------------------------------------------------
    def _apply_fonts(self, scale: float) -> None:
        """설정된 글꼴·크기를 대상 모니터 배율(scale)에 맞춰 물리 px로 재조정.

        Font 오브젝트를 새로 만들지 않고 configure()로 갱신 — 이미 그 Font를 쓰는
        모든 위젯에 자동 반영된다(같은 세션 중 재조정 시 위젯을 일일이 안 건드려도 됨).
        """
        label = self._config.font_label
        family = self._font_map.get(label)
        if not family:
            available = set(tkfont.families(self._root))
            family = _pick_family(_BODY_FALLBACK, available, "TkDefaultFont")
        size = self._config.size

        if (self._built_scale == scale and self._built_font_label == label
                and self._built_size == size):
            return
        self._built_scale, self._built_font_label, self._built_size = scale, label, size

        base = self._config.size_px()  # 논리 px (예: 18)

        def px(logical: int) -> int:
            return -logical_to_physical_px(max(MIN_LOGICAL_PX, logical), scale)

        self._f_title.configure(family=family, size=px(base + 8))
        self._f_row.configure(family=family, size=px(base + 4))
        self._f_num.configure(family=self._mono_family, size=px(base - 2))
        self._f_hint.configure(family=family, size=px(base - 4))

    # -- 내부 -------------------------------------------------------------
    def _render_rows(self, windows: list[WindowInfo], selected: int) -> None:
        lang = self._config.lang
        # 선택이 항상 보이도록 표시 구간 계산
        total = len(windows)
        if total <= MAX_VISIBLE:
            start = 0
        else:
            start = max(0, min(selected - MAX_VISIBLE // 2, total - MAX_VISIBLE))
        end = min(start + MAX_VISIBLE, total)

        # 위/아래 숨은 개수 인디케이터 (색만 아닌 텍스트로)
        above, below = start, total - end
        if above:
            self._up_hint.config(text=t("more_above", lang, n=above))
            self._up_hint.pack(fill="x", after=self._header)
        else:
            self._up_hint.pack_forget()

        self._sync_row_count(end - start)
        for i, (frame, num_lbl, title_lbl) in enumerate(self._row_widgets):
            idx = start + i
            w = windows[idx]
            is_sel = (idx == selected)
            marker = "▶ " if is_sel else "   "
            frame.config(
                highlightbackground=ACCENT if is_sel else SURFACE,
                highlightcolor=ACCENT if is_sel else SURFACE,
                bg=SURFACE_2 if is_sel else SURFACE,
            )
            num_lbl.config(
                text=f"{idx + 1:>2}",
                bg=SURFACE_2 if is_sel else SURFACE,
                fg=ACCENT if is_sel else TEXT_SUB,
            )
            title_lbl.config(
                text=marker + self._fit(w.title),
                bg=SURFACE_2 if is_sel else SURFACE,
                fg=TEXT if is_sel else TEXT_SUB,
            )

        if below:
            self._down_hint.config(text=t("more_below", lang, n=below))
            self._down_hint.pack(fill="x", before=self._footer)
        else:
            self._down_hint.pack_forget()

    def _sync_row_count(self, n: int) -> None:
        """행 위젯 풀을 n개로 맞춘다(재사용)."""
        while len(self._row_widgets) < n:
            frame = tk.Frame(
                self._rows_holder, bg=SURFACE, highlightthickness=3,
                highlightbackground=SURFACE, highlightcolor=SURFACE,
            )
            num_lbl = tk.Label(frame, font=self._f_num, bg=SURFACE, fg=TEXT_SUB, width=3, anchor="e")
            title_lbl = tk.Label(frame, font=self._f_row, bg=SURFACE, fg=TEXT_SUB, anchor="w")
            num_lbl.pack(side="left", padx=(12, 12), pady=8)
            title_lbl.pack(side="left", fill="x", expand=True, padx=(0, 16), pady=8)
            frame.pack(fill="x", pady=3)
            self._row_widgets.append((frame, num_lbl, title_lbl))
        while len(self._row_widgets) > n:
            frame, _, _ = self._row_widgets.pop()
            frame.destroy()

    def _fit(self, text: str, marker_px: int = 0) -> str:
        """제목을 오버레이 폭에 맞춰 픽셀 단위로 잘라낸다(넘치면 …)."""
        text = text.replace("\n", " ").strip()
        # 번호열·마커·좌우 여백을 제외한 제목 가용 폭
        avail = getattr(self, "_overlay_w", 1024) - 130
        if self._f_row.measure(text) <= avail:
            return text
        ell = "…"
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._f_row.measure(text[:mid] + ell) <= avail:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo] + ell

    def _place(self) -> None:
        """고정 너비로, 커서 모니터 작업영역 안에 완전히 들어오도록 배치(상단 1/3)."""
        self._win.update_idletasks()
        ax, ay, aw, ah = getattr(self, "_area", (0, 0,
                                                 self._win.winfo_screenwidth(),
                                                 self._win.winfo_screenheight()))
        w = getattr(self, "_overlay_w", self._win.winfo_width())
        h = min(self._win.winfo_reqheight(), int(ah * 0.9))
        x = ax + max(0, (aw - w) // 2)
        y = ay + max(0, (ah - h) // 3)
        self._win.geometry(f"{w}x{h}+{x}+{y}")
