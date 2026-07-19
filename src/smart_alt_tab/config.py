# src/smart_alt_tab/config.py
"""사용자 설정 저장소: 글꼴·글자 크기·언어. SVIL 화면 설정 표준(§2.1) 3항목.

%LOCALAPPDATA%\\smart-alt-tab\\config.json 에 저장. 실재하지 않는 글꼴은 노출하지 않는다
(SVIL 규칙: "글꼴 8종 중 로컬에 실재하는 것만 노출, 깨진 옵션 금지").
"""

from __future__ import annotations

import json
import os
import tkinter.font as tkfont
from dataclasses import asdict, dataclass

# SVIL 8종 표준 후보 — (표시 이름, 시도할 실제 설치 패밀리 순서)
# 나눔고딕은 저시력 가독성을 위해 실제 헤비 컷(ExtraBold)을 우선 시도한다(합성 아님, 실제 패밀리).
_FONT_CANDIDATES: list[tuple[str, list[str]]] = [
    ("나눔고딕", ["나눔고딕 ExtraBold", "NanumGothic ExtraBold", "나눔고딕", "NanumGothic"]),
    ("교보손글씨2019", ["KyoboHandwriting2019", "교보손글씨2019"]),
    ("고딕", ["맑은 고딕", "Malgun Gothic"]),
    ("나눔고딕(라이트)", ["나눔고딕 Light", "NanumGothic Light"]),
    ("라인시드", ["LINE Seed KR", "LINE Seed", "라인시드"]),
    ("고운돋움", ["고운돋움", "Goundodum"]),
    ("카페24동동", ["Cafe24Dongdong", "카페24동동체", "카페24동동"]),
    ("티머니둥근바람", ["TmoneyRoundWind", "티머니 둥근바람", "티머니둥근바람"]),
    ("레코", ["Recko", "레코"]),
]

# 글자 크기 3단계 (본문 기준 논리 px, 96dpi 기준)
SIZE_LEVELS = {"small": 16, "medium": 18, "large": 20}
SIZE_LABELS_KEY = {"small": "size_small", "medium": "size_medium", "large": "size_large"}

# 다국어 5종, 순서 고정
LANGUAGES = ["ko", "en", "ja", "zh", "vi"]
LANGUAGE_NAMES = {"ko": "한국어", "en": "English", "ja": "日本語", "zh": "中文", "vi": "Tiếng Việt"}

DEFAULT_FONT_LABEL = "나눔고딕"
DEFAULT_SIZE = "medium"
DEFAULT_LANG = "ko"


def available_fonts(root=None) -> list[tuple[str, str]]:
    """실제 설치된 SVIL 후보 폰트만 (표시이름, 실제패밀리) 순서대로 반환."""
    owns_root = root is None
    if owns_root:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
    try:
        installed = set(tkfont.families(root))
        result = []
        for label, candidates in _FONT_CANDIDATES:
            for fam in candidates:
                if fam in installed:
                    result.append((label, fam))
                    break
        return result
    finally:
        if owns_root:
            root.destroy()


def _config_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "smart-alt-tab")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "config.json")


@dataclass
class Config:
    font_label: str = DEFAULT_FONT_LABEL
    size: str = DEFAULT_SIZE
    lang: str = DEFAULT_LANG

    @classmethod
    def load(cls) -> "Config":
        try:
            with open(_config_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                font_label=data.get("font_label", DEFAULT_FONT_LABEL),
                size=data.get("size", DEFAULT_SIZE) if data.get("size") in SIZE_LEVELS else DEFAULT_SIZE,
                lang=data.get("lang", DEFAULT_LANG) if data.get("lang") in LANGUAGES else DEFAULT_LANG,
            )
        except (OSError, json.JSONDecodeError, ValueError):
            return cls()

    def save(self) -> None:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    def size_px(self) -> int:
        return SIZE_LEVELS.get(self.size, SIZE_LEVELS[DEFAULT_SIZE])
