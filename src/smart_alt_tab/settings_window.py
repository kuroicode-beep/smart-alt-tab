# src/smart_alt_tab/settings_window.py
"""설정 화면 — SVIL 화면 설정 표준(§2.1): 글꼴·글자 크기·다국어 3항목 + 업데이트 내역.

선택 즉시 저장·적용(별도 저장 버튼 없음 — 클릭 수를 줄여 접근성 향상).
버튼은 최소 50px 높이, 선택 상태는 색+테두리 병행(색만으로 구분 금지).
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Callable

from .config import LANGUAGE_NAMES, LANGUAGES, SIZE_LABELS_KEY, Config, available_fonts
from .i18n import t
from .version import APP_VERSION, VERSION_HISTORY
from .win.dpi import scale_for_point
from .win.windows import cursor_workarea

BG = "#0d0d12"
SURFACE = "#16161d"
SURFACE_2 = "#1f1f2a"
BORDER = "#3a3a48"
BORDER_STRONG = "#6b6b82"
TEXT = "#f5f5f7"
TEXT_SUB = "#c9c9d4"
ACCENT = "#7ec8ff"
ACCENT_STRONG = "#b3ddff"
FOCUS = "#ffd479"

_BODY_FALLBACK = ["나눔고딕 ExtraBold", "Noto Sans KR Black", "Malgun Gothic"]
_MONO_FAMILIES = ["Consolas", "D2Coding", "monospace"]


class SettingsWindow:
    """숨김 상태로 한 번 만들고 재사용. show()로 열고 닫기로 숨긴다."""

    def __init__(self, root: tk.Tk, config: Config, on_change: Callable[[Config], None]) -> None:
        self._root = root
        self._config = config
        self._on_change = on_change

        available = set(tkfont.families(root))

        def pick(cands, default):
            for c in cands:
                if c in available:
                    return c
            return default

        self._mono_family = pick(_MONO_FAMILIES, "TkFixedFont")
        self._fonts = available_fonts(root)  # [(표시이름, 실제패밀리), ...]

        self._win = tk.Toplevel(root)
        self._win.withdraw()
        self._win.title(f"smart-alt-tab v{APP_VERSION}")
        self._win.configure(bg=BG)
        self._win.protocol("WM_DELETE_WINDOW", self.hide)
        self._win.resizable(False, False)

        self._font_btns: dict[str, tk.Label] = {}
        self._size_btns: dict[str, tk.Label] = {}
        self._lang_btns: dict[str, tk.Label] = {}

        self._build()
        self._refresh_selection()

    # -- 공개 ---------------------------------------------------------------
    def show(self) -> None:
        self._apply_dpi()
        self._win.deiconify()
        self._win.lift()
        self._win.attributes("-topmost", True)
        self._win.after(150, lambda: self._win.attributes("-topmost", False))

    def hide(self) -> None:
        self._win.withdraw()

    # -- 레이아웃 -----------------------------------------------------------
    def _fonts_now(self) -> tuple[str, str]:
        """(본문 글꼴, 모노 글꼴) 현재 설정 기준."""
        fam = dict(self._fonts).get(self._config.font_label)
        if not fam:
            fam = _BODY_FALLBACK[0]
        return fam, self._mono_family

    def _build(self) -> None:
        body, mono = self._fonts_now()
        lang = self._config.lang

        self._f_h1 = tkfont.Font(family=body, size=-30)
        self._f_h2 = tkfont.Font(family=body, size=-24)
        self._f_body = tkfont.Font(family=body, size=-20)
        self._f_small = tkfont.Font(family=body, size=-16)
        self._f_mono = tkfont.Font(family=mono, size=-16)

        pad = 24
        outer = tk.Frame(self._win, bg=BG, padx=pad, pady=pad)
        outer.pack(fill="both", expand=True)

        self._title_lbl = tk.Label(outer, font=self._f_h1, bg=BG, fg=ACCENT_STRONG, anchor="w")
        self._title_lbl.pack(fill="x", pady=(0, 18))

        # --- 글꼴 ---
        self._sec_font = tk.Label(outer, font=self._f_h2, bg=BG, fg=TEXT, anchor="w")
        self._sec_font.pack(fill="x", pady=(4, 8))
        font_row = tk.Frame(outer, bg=BG)
        font_row.pack(fill="x", pady=(0, 6))
        for label, fam in self._fonts:
            btn = self._make_toggle(font_row, label, family=fam, size=-18)
            btn.pack(side="left", padx=(0, 10), pady=4)
            btn.bind("<Button-1>", lambda e, lb=label: self._set_font(lb))
            self._font_btns[label] = btn

        self._preview = tk.Label(
            outer, font=self._f_body, bg=SURFACE, fg=TEXT, anchor="w",
            padx=18, pady=14, highlightthickness=1, highlightbackground=BORDER,
        )
        self._preview.pack(fill="x", pady=(8, 20))

        # --- 글자 크기 ---
        self._sec_size = tk.Label(outer, font=self._f_h2, bg=BG, fg=TEXT, anchor="w")
        self._sec_size.pack(fill="x", pady=(4, 8))
        size_row = tk.Frame(outer, bg=BG)
        size_row.pack(fill="x", pady=(0, 20))
        for key in ("small", "medium", "large"):
            btn = self._make_toggle(size_row, t(SIZE_LABELS_KEY[key], lang), family=body, size=-18)
            btn.pack(side="left", padx=(0, 10), pady=4)
            btn.bind("<Button-1>", lambda e, k=key: self._set_size(k))
            self._size_btns[key] = btn

        # --- 언어 ---
        self._sec_lang = tk.Label(outer, font=self._f_h2, bg=BG, fg=TEXT, anchor="w")
        self._sec_lang.pack(fill="x", pady=(4, 8))
        lang_row = tk.Frame(outer, bg=BG)
        lang_row.pack(fill="x", pady=(0, 20))
        for code in LANGUAGES:
            btn = self._make_toggle(lang_row, LANGUAGE_NAMES[code], family=body, size=-18)
            btn.pack(side="left", padx=(0, 10), pady=4)
            btn.bind("<Button-1>", lambda e, c=code: self._set_lang(c))
            self._lang_btns[code] = btn

        self._status = tk.Label(outer, font=self._f_small, bg=BG, fg=TEXT_SUB, anchor="w")
        self._status.pack(fill="x", pady=(0, 20))

        # --- 업데이트 내역 ---
        sep = tk.Frame(outer, bg=BORDER, height=1)
        sep.pack(fill="x", pady=(0, 18))
        self._sec_history = tk.Label(outer, font=self._f_h2, bg=BG, fg=TEXT, anchor="w")
        self._sec_history.pack(fill="x", pady=(0, 10))

        hist_wrap = tk.Frame(outer, bg=BG)
        hist_wrap.pack(fill="both")
        canvas = tk.Canvas(hist_wrap, bg=BG, highlightthickness=0, width=640, height=220)
        vsb = tk.Scrollbar(hist_wrap, orient="vertical", command=canvas.yview)
        hist_inner = tk.Frame(canvas, bg=BG)
        hist_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=hist_inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def _wheel(e):
            canvas.yview_scroll(int(-e.delta / 120), "units")
        canvas.bind_all("<MouseWheel>", _wheel, add="+")

        for ver, date, summary in VERSION_HISTORY:
            row = tk.Frame(hist_inner, bg=BG)
            row.pack(fill="x", pady=6, padx=(0, 16))
            head = tk.Frame(row, bg=BG)
            head.pack(fill="x")
            tk.Label(head, text=f"v{ver}", font=self._f_mono, bg=BG, fg=ACCENT).pack(side="left")
            tk.Label(head, text=date, font=self._f_mono, bg=BG, fg=TEXT_SUB, padx=12).pack(side="left")
            tk.Label(row, text=summary, font=self._f_small, bg=BG, fg=TEXT_SUB,
                     anchor="w", justify="left", wraplength=600).pack(fill="x", pady=(2, 0))

        close_row = tk.Frame(outer, bg=BG)
        close_row.pack(fill="x", pady=(18, 0))
        self._close_btn = self._make_toggle(close_row, "", family=body, size=-18, is_primary=True)
        self._close_btn.pack(side="right")
        self._close_btn.bind("<Button-1>", lambda e: self.hide())

    def _make_toggle(self, parent, text, *, family, size, is_primary=False) -> tk.Label:
        f = tkfont.Font(family=family, size=size)
        lbl = tk.Label(
            parent, text=text, font=f, padx=20, pady=12,
            bg=(ACCENT_STRONG if is_primary else SURFACE_2),
            fg=("#000000" if is_primary else TEXT),
            highlightthickness=2,
            highlightbackground=(ACCENT_STRONG if is_primary else BORDER_STRONG),
            highlightcolor=(ACCENT_STRONG if is_primary else BORDER_STRONG),
            cursor="hand2",
        )
        lbl._toggle_font = f  # Font 객체를 위젯에 붙잡아 둬 GC로 사라지지 않게 함
        return lbl

    # -- 상태 반영 ------------------------------------------------------------
    def _set_font(self, label: str) -> None:
        self._config.font_label = label
        self._commit()

    def _set_size(self, key: str) -> None:
        self._config.size = key
        self._commit()

    def _set_lang(self, code: str) -> None:
        self._config.lang = code
        self._commit()

    def _commit(self) -> None:
        self._config.save()
        self._on_change(self._config)
        # 언어·글꼴이 바뀌면 화면 문구·미리보기 폰트도 다시 그린다
        for child in list(self._win.winfo_children()):
            child.destroy()
        self._build()
        self._refresh_selection()

    def _refresh_selection(self) -> None:
        lang = self._config.lang
        self._win.title(f"smart-alt-tab v{APP_VERSION} — {t('settings_title', lang)}")
        self._title_lbl.config(text=t("settings_title", lang))
        self._sec_font.config(text=t("settings_font", lang))
        self._sec_size.config(text=t("settings_size", lang))
        self._sec_lang.config(text=t("settings_lang", lang))
        self._sec_history.config(text=t("settings_history_title", lang))
        self._status.config(text=t("settings_saved", lang))
        self._preview.config(text=t("settings_preview", lang))
        self._close_btn.config(text=t("settings_close", lang))

        for label, btn in self._font_btns.items():
            sel = (label == self._config.font_label)
            btn.config(
                bg=SURFACE_2 if not sel else SURFACE,
                highlightbackground=ACCENT if sel else BORDER_STRONG,
                highlightcolor=ACCENT if sel else BORDER_STRONG,
                fg=ACCENT_STRONG if sel else TEXT,
                text=("✓ " if sel else "") + label,
            )
        for key, btn in self._size_btns.items():
            sel = (key == self._config.size)
            btn.config(
                bg=SURFACE_2 if not sel else SURFACE,
                highlightbackground=ACCENT if sel else BORDER_STRONG,
                highlightcolor=ACCENT if sel else BORDER_STRONG,
                fg=ACCENT_STRONG if sel else TEXT,
                text=("✓ " if sel else "") + t(SIZE_LABELS_KEY[key], lang),
            )
        for code, btn in self._lang_btns.items():
            sel = (code == self._config.lang)
            btn.config(
                bg=SURFACE_2 if not sel else SURFACE,
                highlightbackground=ACCENT if sel else BORDER_STRONG,
                highlightcolor=ACCENT if sel else BORDER_STRONG,
                fg=ACCENT_STRONG if sel else TEXT,
                text=("✓ " if sel else "") + LANGUAGE_NAMES[code],
            )

    def _apply_dpi(self) -> None:
        ax, ay, aw, ah = cursor_workarea()
        scale = scale_for_point(ax + aw // 2, ay + ah // 2)
        # 창 폭은 배율만큼 확대한 고정값, 높이는 실제 콘텐츠에 맞춰 자동(빈 공간 방지)
        w = min(int(720 * scale), aw - 40)
        self._win.geometry(f"{w}x100+0+0")  # reqheight 계산을 위한 임시 배치
        self._win.update_idletasks()
        h = min(self._win.winfo_reqheight(), ah - 40)
        x = ax + max(0, (aw - w) // 2)
        y = ay + max(0, (ah - h) // 2)
        self._win.geometry(f"{w}x{h}+{x}+{y}")
