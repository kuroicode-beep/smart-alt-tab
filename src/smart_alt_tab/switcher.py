# src/smart_alt_tab/switcher.py
"""고대비 다크 오버레이 전환기 UI (tkinter).

SVIL 디자인 토큰 적용: 큰 글씨, 색상만으로 상태 구분 금지(선택은 테두리+색+마커).
선택 이동만 반응하도록 화면 갱신은 controller가 호출한다.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

from .win.windows import WindowInfo

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

# 본문 글꼴 우선순위(로컬 번들 우선, 없으면 시스템 폴백)
_BODY_FAMILIES = ["KyoboHandwriting2019", "Pretendard", "Malgun Gothic"]
_MONO_FAMILIES = ["Consolas", "D2Coding", "monospace"]

MAX_VISIBLE = 9  # 한 화면에 보일 행 수 (초과분은 위/아래 인디케이터)


def _pick_family(candidates: list[str], available: set[str], default: str) -> str:
    for fam in candidates:
        if fam in available:
            return fam
    return default


class Switcher:
    """숨김 상태로 대기하다 show()로 나타나는 오버레이."""

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._win = tk.Toplevel(root)
        self._win.withdraw()
        self._win.overrideredirect(True)  # 타이틀바 제거
        self._win.attributes("-topmost", True)
        self._win.configure(bg=BG)

        available = set(tkfont.families(root))
        body = _pick_family(_BODY_FAMILIES, available, "TkDefaultFont")
        mono = _pick_family(_MONO_FAMILIES, available, "TkFixedFont")
        self._f_title = tkfont.Font(family=body, size=26)
        self._f_row = tkfont.Font(family=body, size=22)
        self._f_num = tkfont.Font(family=mono, size=16)
        self._f_hint = tkfont.Font(family=body, size=14)

        # 바깥 테두리(강조 보더) → 안쪽 컨테이너
        self._frame = tk.Frame(
            self._win, bg=SURFACE, highlightthickness=2,
            highlightbackground=BORDER_STRONG, highlightcolor=BORDER_STRONG,
        )
        self._frame.pack(fill="both", expand=True)

        self._header = tk.Label(
            self._frame, text="창 전환", font=self._f_title,
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

    # -- 표시 -------------------------------------------------------------
    def show(self, windows: list[WindowInfo], selected: int) -> None:
        """목록·선택을 반영해 오버레이를 그리고 화면 중앙에 띄운다."""
        if not windows:
            self.hide()
            return
        self._render_rows(windows, selected)
        self._footer.config(text=f"{selected + 1} / {len(windows)}   ·   Alt 놓기=전환  Esc=취소")
        self._win.update_idletasks()
        self._center()
        self._win.deiconify()
        self._win.lift()
        self._win.attributes("-topmost", True)

    def hide(self) -> None:
        self._win.withdraw()

    # -- 내부 -------------------------------------------------------------
    def _render_rows(self, windows: list[WindowInfo], selected: int) -> None:
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
            self._up_hint.config(text=f"▲ 위로 {above}개 더")
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
                text=marker + _clip(w.title),
                bg=SURFACE_2 if is_sel else SURFACE,
                fg=TEXT if is_sel else TEXT_SUB,
            )

        if below:
            self._down_hint.config(text=f"▼ 아래로 {below}개 더")
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

    def _center(self) -> None:
        self._win.update_idletasks()
        w = self._win.winfo_width()
        h = self._win.winfo_height()
        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 3
        self._win.geometry(f"+{x}+{y}")


def _clip(text: str, limit: int = 64) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"
